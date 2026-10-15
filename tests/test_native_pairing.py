import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import server


class NativePairingTests(unittest.TestCase):
    def test_legacy_http_pairing_never_transfers_token(self):
        with patch.object(server.subprocess, "run") as run:
            status, payload = server.request_pairing("chrome-extension://" + "a" * 32)
        self.assertEqual(status, 410)
        self.assertNotIn("token", payload)
        self.assertIn("Native Messaging", payload["error"])
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
