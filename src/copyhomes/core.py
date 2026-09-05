"""Core planning, copying, receipts, and undo logic for CopyHomes."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol, TypedDict, cast

HomeState = Literal[
    "create",
    "same",
    "replace",
    "conflict",
    "missing-directory",
    "invalid-home",
    "duplicate",
    "source-home",
]


class CopyHomesError(Exception):
    """Base error for expected CopyHomes failures."""


class PlanConflictError(CopyHomesError):
    """A plan contains a destination that is unsafe to apply."""


class UndoConflictError(CopyHomesError):
    """Undo was refused because a target changed after the receipt was made."""


class SourceChangedError(CopyHomesError):
    """The source changed between planning and applying."""


class ReceiptError(CopyHomesError):
    """A receipt is malformed, incomplete, or already undone."""


class _BinaryWriter(Protocol):
    def write(self, data: bytes, /) -> int: ...


class ReceiptHome(TypedDict, total=False):
    action: str
    directory: str
    target: str
    reason: str
    new_sha256: str
    previous_sha256: str | None
    backup: str | None


class Receipt(TypedDict, total=False):
    version: int
    created_at: str
    source: str
    source_sha256: str
    bytes: int
    recovery_dir: str | None
    undone: bool
    undone_at: str
    homes: list[ReceiptHome]


class SaveSummary(TypedDict):
    created: int
    replaced: int
    skipped: int
    receipt: str | None


class UndoSummary(TypedDict):
    removed: int
    restored: int
    receipt: str


@dataclass(frozen=True)
class HomePlan:
    """Decision for one destination directory."""

    directory: Path
    target: Path | None
    state: HomeState
    reason: str
    existing_sha256: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "directory": str(self.directory),
            "target": str(self.target) if self.target is not None else None,
            "state": self.state,
            "reason": self.reason,
            "existing_sha256": self.existing_sha256,
        }


@dataclass(frozen=True)
class Plan:
    """Immutable snapshot used for preview and apply."""

    source: Path
    source_sha256: str
    bytes: int
    homes: tuple[HomePlan, ...]
    replace: bool = False
    create_dirs: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "source": str(self.source),
            "source_sha256": self.source_sha256,
            "bytes": self.bytes,
            "replace": self.replace,
            "create_dirs": self.create_dirs,
            "homes": [home.to_dict() for home in self.homes],
        }


def _resolve_source(source: str | Path) -> Path:
    candidate = Path(source).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"source does not exist: {candidate}") from exc
    if not resolved.is_file():
        raise ValueError(f"source is not a file: {resolved}")
    return resolved


def _resolve_home(home: str | Path) -> Path:
    return Path(home).expanduser().resolve()


def sha256_path(path: Path) -> str:
    """Return SHA-256 for a file, streaming bytes instead of loading all data."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_plan(
    source: str | Path,
    homes: Iterable[str | Path],
    *,
    replace: bool = False,
    create_dirs: bool = False,
) -> Plan:
    """Build a read-only plan for saving ``source`` into explicit homes."""

    source_path = _resolve_source(source)
    home_values = list(homes)
    if not home_values:
        raise ValueError("at least one destination home is required")

    source_sha256 = sha256_path(source_path)
    seen: set[Path] = set()
    decisions: list[HomePlan] = []

    for raw_home in home_values:
        directory = _resolve_home(raw_home)
        if directory in seen:
            decisions.append(
                HomePlan(
                    directory=directory,
                    target=None,
                    state="duplicate",
                    reason="duplicate destination was supplied",
                )
            )
            continue
        seen.add(directory)

        if directory == source_path.parent:
            decisions.append(
                HomePlan(
                    directory=directory,
                    target=source_path,
                    state="source-home",
                    reason="source already lives in this home",
                    existing_sha256=source_sha256,
                )
            )
            continue

        target = directory / source_path.name
        if directory.exists() and not directory.is_dir():
            decisions.append(
                HomePlan(
                    directory=directory,
                    target=None,
                    state="invalid-home",
                    reason="destination is not a directory",
                )
            )
            continue

        if not directory.exists():
            state: HomeState = "create" if create_dirs else "missing-directory"
            reason = (
                "directory will be created by explicit --create-dirs"
                if create_dirs
                else "directory is missing; use --create-dirs to create it"
            )
            decisions.append(
                HomePlan(
                    directory=directory,
                    target=target,
                    state=state,
                    reason=reason,
                )
            )
            continue

        if target.is_symlink():
            decisions.append(
                HomePlan(
                    directory=directory,
                    target=target,
                    state="conflict",
                    reason="refusing to follow a symlink target",
                )
            )
            continue

        if not target.exists():
            decisions.append(
                HomePlan(
                    directory=directory,
                    target=target,
                    state="create",
                    reason="target does not exist",
                )
            )
            continue

        if not target.is_file():
            decisions.append(
                HomePlan(
                    directory=directory,
                    target=target,
                    state="conflict",
                    reason="target exists but is not a regular file",
                )
            )
            continue

        existing_sha256 = sha256_path(target)
        if existing_sha256 == source_sha256:
            state = "same"
            reason = "target already matches source"
        elif replace:
            state = "replace"
            reason = "target differs and explicit --replace allows replacement"
        else:
            state = "conflict"
            reason = "target differs; use --replace to replace it"
        decisions.append(
            HomePlan(
                directory=directory,
                target=target,
                state=state,
                reason=reason,
                existing_sha256=existing_sha256,
            )
        )

    return Plan(
        source=source_path,
        source_sha256=source_sha256,
        bytes=source_path.stat().st_size,
        homes=tuple(decisions),
        replace=replace,
        create_dirs=create_dirs,
    )


def _unsafe_homes(plan: Plan) -> list[str]:
    return [
        f"{home.directory}: {home.reason}"
        for home in plan.homes
        if home.state in {"conflict", "missing-directory", "invalid-home"}
    ]


def _copy_stream(source: Path, destination: _BinaryWriter) -> None:
    with source.open("rb") as source_stream:
        shutil.copyfileobj(source_stream, destination, length=1024 * 1024)


def _write_new(source: Path, target: Path) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    binary_flag = getattr(os, "O_BINARY", 0)
    fd = os.open(target, flags | binary_flag, 0o666)
    try:
        with os.fdopen(fd, "wb") as destination:
            _copy_stream(source, destination)
            destination.flush()
            os.fsync(destination.fileno())
    except BaseException:
        if target.exists():
            target.unlink()
        raise


def _replace_file(source: Path, target: Path) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{target.name}.copyhomes-",
            dir=target.parent,
            delete=False,
        ) as destination:
            temporary_path = Path(destination.name)
            _copy_stream(source, destination)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _write_json_atomic(path: Path, payload: Receipt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.name}.copyhomes-",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _rollback(entries: list[ReceiptHome], source_sha256: str) -> None:
    for entry in reversed(entries):
        target = Path(entry["target"])
        action = entry["action"]
        try:
            if action == "created":
                if target.exists() and target.is_file():
                    if sha256_path(target) == source_sha256:
                        target.unlink()
            elif action == "replaced":
                backup_name = entry.get("backup")
                if backup_name and target.exists() and target.is_file():
                    if sha256_path(target) == source_sha256:
                        _replace_file(Path(backup_name), target)
        except OSError:
            continue


def save_plan(plan: Plan, receipt_path: str | Path | None) -> SaveSummary:
    """Apply a plan, preserving conflicts and writing an optional undo receipt."""

    unsafe = _unsafe_homes(plan)
    if unsafe:
        raise PlanConflictError("unsafe plan: " + "; ".join(unsafe))
    if plan.source.exists() and sha256_path(plan.source) != plan.source_sha256:
        raise SourceChangedError("source changed after preview; build a new plan")

    receipt: Path | None = None
    if receipt_path is not None:
        receipt = Path(receipt_path).expanduser().resolve()
        if receipt == plan.source or any(home.target == receipt for home in plan.homes):
            raise ValueError("receipt must not overwrite the source or a destination")
    if any(home.state == "replace" for home in plan.homes) and receipt is None:
        raise ValueError("--replace requires --receipt so the change can be undone")

    recovery_dir: Path | None = None
    if receipt is not None:
        receipt.parent.mkdir(parents=True, exist_ok=True)
    if any(home.state == "replace" for home in plan.homes):
        assert receipt is not None
        recovery_dir = receipt.parent / f".copyhomes-recovery-{uuid.uuid4().hex[:12]}"
        recovery_dir.mkdir(parents=True, exist_ok=False)

    entries: list[ReceiptHome] = []
    created = 0
    replaced = 0
    skipped = 0
    try:
        for index, home in enumerate(plan.homes):
            if home.state in {"duplicate", "source-home", "same"}:
                skipped += 1
                entries.append(
                    {
                        "action": "skipped",
                        "directory": str(home.directory),
                        "target": str(home.target) if home.target else "",
                        "reason": home.reason,
                        "new_sha256": plan.source_sha256,
                        "previous_sha256": home.existing_sha256,
                        "backup": None,
                    }
                )
                continue

            if home.state == "create" and not home.directory.exists():
                home.directory.mkdir(parents=True, exist_ok=True)
            if not home.directory.is_dir() or home.target is None:
                raise PlanConflictError(f"cannot use destination: {home.directory}")

            if home.state == "create":
                _write_new(plan.source, home.target)
                entries.append(
                    {
                        "action": "created",
                        "directory": str(home.directory),
                        "target": str(home.target),
                        "reason": home.reason,
                        "new_sha256": plan.source_sha256,
                        "previous_sha256": None,
                        "backup": None,
                    }
                )
                if sha256_path(home.target) != plan.source_sha256:
                    raise CopyHomesError(f"verification failed: {home.target}")
                created += 1
                continue

            if home.state == "replace":
                if recovery_dir is None:
                    raise CopyHomesError(
                        "replacement recovery directory was not prepared"
                    )
                backup = recovery_dir / f"{index}-{home.target.name}.bak"
                _write_new(home.target, backup)
                _replace_file(plan.source, home.target)
                entries.append(
                    {
                        "action": "replaced",
                        "directory": str(home.directory),
                        "target": str(home.target),
                        "reason": home.reason,
                        "new_sha256": plan.source_sha256,
                        "previous_sha256": home.existing_sha256,
                        "backup": str(backup),
                    }
                )
                if sha256_path(home.target) != plan.source_sha256:
                    raise CopyHomesError(f"verification failed: {home.target}")
                replaced += 1
                continue

            raise PlanConflictError(f"unknown plan state: {home.state}")
        if receipt is not None:
            receipt_payload: Receipt = {
                "version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source": str(plan.source),
                "source_sha256": plan.source_sha256,
                "bytes": plan.bytes,
                "recovery_dir": str(recovery_dir) if recovery_dir else None,
                "undone": False,
                "homes": entries,
            }
            _write_json_atomic(receipt, receipt_payload)
    except BaseException:
        _rollback(entries, plan.source_sha256)
        if recovery_dir is not None and recovery_dir.exists():
            shutil.rmtree(recovery_dir)
        raise

    return {
        "created": created,
        "replaced": replaced,
        "skipped": skipped,
        "receipt": str(receipt) if receipt else None,
    }


def _load_receipt(path: Path) -> Receipt:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"could not read receipt: {path}") from exc
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ReceiptError("unsupported or malformed receipt version")
    homes = raw.get("homes")
    if not isinstance(homes, list):
        raise ReceiptError("receipt has no homes list")
    if raw.get("undone") is True:
        raise ReceiptError("receipt was already undone")
    return cast(Receipt, raw)


def _receipt_path(value: object, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ReceiptError(f"receipt field missing: {field}")
    return Path(value).expanduser().resolve()


def _inside(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def undo_receipt(receipt_path: str | Path) -> UndoSummary:
    """Undo only files whose bytes still match this receipt."""

    receipt = Path(receipt_path).expanduser().resolve()
    payload = _load_receipt(receipt)
    homes = payload["homes"]
    new_sha256 = payload.get("source_sha256")
    if not isinstance(new_sha256, str):
        raise ReceiptError("receipt source hash missing")

    recovery_dir_value = payload.get("recovery_dir")
    recovery_dir = (
        Path(recovery_dir_value).expanduser().resolve()
        if isinstance(recovery_dir_value, str) and recovery_dir_value
        else None
    )
    if recovery_dir is not None and not _inside(receipt.parent, recovery_dir):
        raise ReceiptError("receipt recovery directory escapes receipt folder")

    operations: list[tuple[str, Path, Path | None]] = []
    for entry in homes:
        action = entry.get("action")
        if action == "skipped":
            continue
        if action not in {"created", "replaced"}:
            raise ReceiptError(f"unsupported receipt action: {action}")
        target = _receipt_path(entry.get("target"), "target")
        if target.is_symlink() or not target.exists() or not target.is_file():
            raise UndoConflictError(f"target is no longer the recorded file: {target}")
        if entry.get("new_sha256") != new_sha256 or sha256_path(target) != new_sha256:
            raise UndoConflictError(f"target changed after save: {target}")
        if action == "created":
            operations.append((action, target, None))
            continue

        backup_path = _receipt_path(entry.get("backup"), "backup")
        if recovery_dir is None or not _inside(recovery_dir, backup_path):
            raise ReceiptError("receipt backup escapes recovery directory")
        previous_sha256 = entry.get("previous_sha256")
        if not isinstance(previous_sha256, str):
            raise ReceiptError("replacement backup hash missing")
        if not backup_path.is_file() or sha256_path(backup_path) != previous_sha256:
            raise UndoConflictError(
                f"replacement backup is missing or changed: {backup_path}"
            )
        operations.append((action, target, backup_path))

    removed = 0
    restored = 0
    for action, target, undo_backup in operations:
        if action == "created":
            target.unlink()
            removed += 1
        else:
            assert undo_backup is not None
            _replace_file(undo_backup, target)
            restored += 1

    if recovery_dir is not None and recovery_dir.exists():
        shutil.rmtree(recovery_dir)
    payload["undone"] = True
    payload["undone_at"] = datetime.now(timezone.utc).isoformat()
    _write_json_atomic(receipt, payload)
    return {"removed": removed, "restored": restored, "receipt": str(receipt)}
