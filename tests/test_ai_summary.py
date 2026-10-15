import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import server


class NoPaidApiCheckpointTests(unittest.TestCase):
    def test_empty_summary_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "assistant summary is empty"):
            server.sync_message_checkpoint("", "chat")


if __name__ == "__main__":
    unittest.main()
