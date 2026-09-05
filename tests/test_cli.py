import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from copyhomes.cli import main


class CliTests(unittest.TestCase):
    def test_plan_json_is_preview_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "notes.txt"
            home = root / "home"
            home.mkdir()
            source.write_text("hello\n", encoding="utf-8")

            stdout = StringIO()
            with patch("sys.stdout", stdout):
                exit_code = main(["plan", str(source), str(home), "--json"])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["homes"][0]["state"], "create")
            self.assertFalse((home / source.name).exists())

    def test_save_json_requires_explicit_receipt_path_for_undo(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "notes.txt"
            home = root / "home"
            home.mkdir()
            source.write_text("hello\n", encoding="utf-8")

            stdout = StringIO()
            with patch("sys.stdout", stdout):
                exit_code = main(["save", str(source), str(home), "--json"])

            self.assertEqual(exit_code, 2)
            self.assertIn("--receipt", stdout.getvalue())
            self.assertFalse((home / source.name).exists())

    def test_save_then_undo_cli_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "notes.txt"
            home = root / "home"
            receipt = root / "receipt.json"
            home.mkdir()
            source.write_text("hello\n", encoding="utf-8")

            save_stdout = StringIO()
            with patch("sys.stdout", save_stdout):
                save_exit = main(
                    [
                        "save",
                        str(source),
                        str(home),
                        "--receipt",
                        str(receipt),
                        "--json",
                    ]
                )
            self.assertEqual(save_exit, 0)
            self.assertTrue((home / source.name).exists())

            undo_stdout = StringIO()
            with patch("sys.stdout", undo_stdout):
                undo_exit = main(["undo", str(receipt), "--json"])

            self.assertEqual(undo_exit, 0)
            self.assertFalse((home / source.name).exists())
            self.assertEqual(json.loads(undo_stdout.getvalue())["removed"], 1)


if __name__ == "__main__":
    unittest.main()
