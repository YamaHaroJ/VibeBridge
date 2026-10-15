import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import server


class AutomaticCheckpointTests(unittest.TestCase):
    def test_redacts_bearer_tokens(self):
        value = server.redact_checkpoint_text("Authorization: Bearer abcdef123456789")
        self.assertIn("[REDACTED]", value)
        self.assertNotIn("abcdef123456789", value)

    def test_redacts_api_keys(self):
        value = server.redact_checkpoint_text("api_key=supersecretvalue")
        self.assertNotIn("supersecretvalue", value)
        self.assertIn("[REDACTED]", value)

    def test_limits_checkpoint_excerpt(self):
        self.assertEqual(len(server.redact_checkpoint_text("x" * 2000)), 1200)

    def test_rejects_invalid_roles_before_github_access(self):
        with self.assertRaisesRegex(ValueError, "role must be user or assistant"):
            server.sync_message_checkpoint("system", "test", "chat")


if __name__ == "__main__":
    unittest.main()
