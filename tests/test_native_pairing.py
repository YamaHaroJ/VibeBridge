import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import server


class NativePairingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.pairing_file = Path(self.tempdir.name) / "paired_extension_origin"
        self.origin = "chrome-extension://" + ("a" * 32)
        self.approved = SimpleNamespace(returncode=0, stdout="button returned:Approve\n", stderr="")
        self.cancelled = SimpleNamespace(returncode=1, stdout="", stderr="User canceled.")

    def tearDown(self):
        self.tempdir.cleanup()

    @patch.object(server.subprocess, "run")
    def test_invalid_origin_is_rejected_without_showing_dialog(self, run):
        with patch.object(server, "PAIRING_FILE", self.pairing_file):
            status, payload = server.request_pairing("https://example.com")
        self.assertEqual(status, 403)
        self.assertNotIn("token", payload)
        run.assert_not_called()
        self.assertFalse(self.pairing_file.exists())

    @patch.object(server.subprocess, "run")
    def test_approval_shows_native_dialog_then_transfers_token(self, run):
        run.return_value = self.approved
        with patch.object(server, "PAIRING_FILE", self.pairing_file):
            status, payload = server.request_pairing(self.origin)
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True, "token": server.TOKEN})
        self.assertEqual(self.pairing_file.read_text(), self.origin)
        self.assertEqual(self.pairing_file.stat().st_mode & 0o777, 0o600)
        args = run.call_args.args[0]
        self.assertEqual(args[0], "/usr/bin/osascript")
        self.assertIn("display dialog (item 1 of argv)", args[2])
        self.assertIn("Approving shares the token", args[3])

    @patch.object(server.subprocess, "run")
    def test_cancel_never_transfers_token_or_remembers_origin(self, run):
        run.return_value = self.cancelled
        with patch.object(server, "PAIRING_FILE", self.pairing_file):
            status, payload = server.request_pairing(self.origin)
        self.assertEqual(status, 403)
        self.assertNotIn("token", payload)
        self.assertFalse(self.pairing_file.exists())

    @patch.object(server.subprocess, "run")
    def test_same_approved_extension_requires_fresh_native_approval(self, run):
        self.pairing_file.write_text(self.origin)
        run.return_value = self.approved
        with patch.object(server, "PAIRING_FILE", self.pairing_file):
            status, payload = server.request_pairing(self.origin)
        self.assertEqual(status, 200)
        self.assertEqual(payload["token"], server.TOKEN)
        run.assert_called_once()
        self.assertIn("A local program can imitate a browser origin", run.call_args.args[0][3])

    @patch.object(server.subprocess, "run")
    def test_different_extension_cannot_take_over_existing_pairing(self, run):
        self.pairing_file.write_text(self.origin)
        other_origin = "chrome-extension://" + ("b" * 32)
        with patch.object(server, "PAIRING_FILE", self.pairing_file):
            status, payload = server.request_pairing(other_origin)
        self.assertEqual(status, 403)
        self.assertNotIn("token", payload)
        run.assert_not_called()

    @patch.object(server.subprocess, "run", side_effect=FileNotFoundError("osascript missing"))
    def test_dialog_failure_does_not_transfer_token(self, run):
        with patch.object(server, "PAIRING_FILE", self.pairing_file):
            status, payload = server.request_pairing(self.origin)
        self.assertEqual(status, 503)
        self.assertNotIn("token", payload)
        self.assertFalse(self.pairing_file.exists())


if __name__ == "__main__":
    unittest.main()
