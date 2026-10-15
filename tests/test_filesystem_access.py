import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import server


class FilesystemAccessTests(unittest.TestCase):
    def test_lists_files_inside_home(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as tmp:
            root = Path(tmp).resolve()
            (root / "example.txt").write_text("hello", encoding="utf-8")
            with patch.object(server, "HOME_ROOT", root):
                result = server.filesystem_listing(str(root))
            self.assertEqual(result["path"], str(root))
            self.assertTrue(any(item["name"] == "example.txt" for item in result["items"]))

    def test_reads_text_file(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as tmp:
            root = Path(tmp).resolve()
            file = root / "example.txt"
            file.write_text("hello", encoding="utf-8")
            with patch.object(server, "HOME_ROOT", root):
                resolved = server.filesystem_path(str(file))
                self.assertEqual(resolved.read_text(encoding="utf-8"), "hello")

    def test_rejects_paths_outside_home(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as tmp:
            root = Path(tmp) / "home"
            root.mkdir()
            outside = Path(tmp) / "outside.txt"
            outside.write_text("no", encoding="utf-8")
            with patch.object(server, "HOME_ROOT", root):
                with self.assertRaisesRegex(ValueError, "limited to your home folder"):
                    server.filesystem_path(str(outside))

    def test_rejects_empty_path(self):
        with self.assertRaisesRegex(ValueError, "path is required"):
            server.filesystem_path("")


if __name__ == "__main__":
    unittest.main()
