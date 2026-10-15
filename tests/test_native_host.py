"""Protocol tests for the Chrome Native Messaging host."""
import json
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
import native_host


class NativeHostTests(unittest.TestCase):
    def test_reads_little_endian_framed_json(self):
        payload = json.dumps({"type": "getToken"}).encode()
        self.assertEqual(native_host.decode_message(struct.pack("<I", len(payload)) + payload),
                         {"type": "getToken"})

    def test_rejects_truncated_header_and_body(self):
        with self.assertRaisesRegex(ValueError, "header"):
            native_host.decode_message(b"\x01\x00")
        with self.assertRaisesRegex(ValueError, "truncated"):
            native_host.decode_message(struct.pack("<I", 12) + b"{}")

    def test_rejects_oversized_message(self):
        with self.assertRaisesRegex(ValueError, "too large"):
            native_host.decode_message(struct.pack("<I", native_host.MAX_MESSAGE_BYTES + 1))

    def test_only_token_request_is_supported(self):
        self.assertEqual(native_host.handle_message({"type": "ping"}, "secret"),
                         {"ok": False, "error": "Unsupported native message."})

    def test_token_request_returns_token(self):
        self.assertEqual(native_host.handle_message({"type": "getToken"}, "secret"),
                         {"ok": True, "token": "secret"})


if __name__ == "__main__":
    unittest.main()
