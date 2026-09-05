import json
import tempfile
import unittest
from pathlib import Path

from copyhomes.core import (
    PlanConflictError,
    UndoConflictError,
    build_plan,
    save_plan,
    undo_receipt,
)


class CoreTests(unittest.TestCase):
    def test_plan_explains_missing_same_and_conflict_homes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "notes.txt"
            source.write_text("today\n", encoding="utf-8")
            missing = root / "missing-home"
            same_home = root / "same-home"
            conflict_home = root / "conflict-home"
            same_home.mkdir()
            conflict_home.mkdir()
            (same_home / source.name).write_text("today\n", encoding="utf-8")
            (conflict_home / source.name).write_text("older\n", encoding="utf-8")

            plan = build_plan(source, [missing, same_home, conflict_home])

            self.assertEqual(
                [home.state for home in plan.homes],
                ["missing-directory", "same", "conflict"],
            )
            self.assertIn("--create-dirs", plan.homes[0].reason)
            self.assertIn("--replace", plan.homes[2].reason)

    def test_save_creates_verified_copies_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "draft.md"
            home_a = root / "a"
            home_b = root / "b"
            receipt = root / "receipts" / "save.json"
            home_a.mkdir()
            home_b.mkdir()
            source.write_bytes(b"one source, two homes\n")

            plan = build_plan(source, [home_a, home_b])
            result = save_plan(plan, receipt)

            self.assertEqual(result["created"], 2)
            self.assertEqual((home_a / source.name).read_bytes(), source.read_bytes())
            self.assertEqual((home_b / source.name).read_bytes(), source.read_bytes())
            saved_receipt = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(saved_receipt["source_sha256"], plan.source_sha256)
            self.assertEqual(len(saved_receipt["homes"]), 2)

    def test_conflict_never_overwrites_without_replace(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "draft.md"
            home = root / "home"
            home.mkdir()
            target = home / source.name
            source.write_text("new\n", encoding="utf-8")
            target.write_text("keep me\n", encoding="utf-8")

            plan = build_plan(source, [home])
            with self.assertRaises(PlanConflictError):
                save_plan(plan, None)

            self.assertEqual(target.read_text(encoding="utf-8"), "keep me\n")

    def test_replace_then_undo_restores_previous_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "draft.md"
            home = root / "home"
            receipt = root / "save.json"
            home.mkdir()
            source.write_text("new\n", encoding="utf-8")
            target = home / source.name
            target.write_text("old\n", encoding="utf-8")

            plan = build_plan(source, [home], replace=True)
            save_plan(plan, receipt)
            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")

            result = undo_receipt(receipt)

            self.assertEqual(result["restored"], 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "old\n")

    def test_undo_refuses_target_changed_after_save(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "draft.md"
            home = root / "home"
            receipt = root / "save.json"
            home.mkdir()
            source.write_text("new\n", encoding="utf-8")

            plan = build_plan(source, [home])
            save_plan(plan, receipt)
            target = home / source.name
            target.write_text("someone edited it\n", encoding="utf-8")

            with self.assertRaises(UndoConflictError):
                undo_receipt(receipt)

            self.assertEqual(target.read_text(encoding="utf-8"), "someone edited it\n")


if __name__ == "__main__":
    unittest.main()
