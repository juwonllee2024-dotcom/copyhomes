"""Command-line interface for CopyHomes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence

from .core import (
    CopyHomesError,
    Plan,
    build_plan,
    save_plan,
    undo_receipt,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="copyhomes",
        description="Save one file to multiple explicit local homes with a receipt.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan", help="preview destinations without writing")
    plan.add_argument("source")
    plan.add_argument("homes", nargs="+")
    plan.add_argument("--replace", action="store_true")
    plan.add_argument("--create-dirs", action="store_true")
    plan.add_argument("--json", action="store_true")

    save = commands.add_parser("save", help="apply a preview and write a receipt")
    save.add_argument("source")
    save.add_argument("homes", nargs="+")
    save.add_argument("--replace", action="store_true")
    save.add_argument("--create-dirs", action="store_true")
    save.add_argument("--receipt", required=False)
    save.add_argument("--json", action="store_true")

    undo = commands.add_parser("undo", help="revert files from a receipt")
    undo.add_argument("receipt")
    undo.add_argument("--json", action="store_true")
    return parser


def _safe_text(value: object) -> str:
    text = str(value)
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x80-\x9f]", "?", text)


def _print_plan(plan: Plan) -> None:
    print(f"source: {_safe_text(plan.source)}")
    print(f"sha256: {plan.source_sha256}")
    print(f"bytes: {plan.bytes}")
    for home in plan.homes:
        target = _safe_text(home.target) if home.target else "-"
        print(f"{home.state.upper():18} {target} — {home.reason}")


def _error(message: str, as_json: bool, error_type: str) -> None:
    payload = {"error": _safe_text(message), "type": error_type}
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"copyhomes: {_safe_text(message)}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    as_json = bool(getattr(args, "json", False))
    try:
        if args.command == "plan":
            plan = build_plan(
                args.source,
                args.homes,
                replace=args.replace,
                create_dirs=args.create_dirs,
            )
            if as_json:
                print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
            else:
                _print_plan(plan)
            return 0

        if args.command == "save":
            if not args.receipt:
                raise ValueError("--receipt is required so save can be undone")
            plan = build_plan(
                args.source,
                args.homes,
                replace=args.replace,
                create_dirs=args.create_dirs,
            )
            save_result = save_plan(plan, args.receipt)
            if as_json:
                print(json.dumps(save_result, indent=2, sort_keys=True))
            else:
                print(
                    f"saved: {save_result['created']} created, "
                    f"{save_result['replaced']} replaced, "
                    f"{save_result['skipped']} skipped"
                )
                print(f"receipt: {_safe_text(save_result['receipt'])}")
            return 0

        if args.command == "undo":
            undo_result = undo_receipt(args.receipt)
            if as_json:
                print(json.dumps(undo_result, indent=2, sort_keys=True))
            else:
                print(
                    f"undone: {undo_result['removed']} created files removed, "
                    f"{undo_result['restored']} replaced files restored"
                )
            return 0

        raise ValueError(f"unknown command: {args.command}")
    except CopyHomesError as exc:
        _error(str(exc), as_json, type(exc).__name__)
        return 1
    except (OSError, ValueError, TypeError) as exc:
        _error(str(exc), as_json, type(exc).__name__)
        return 2
