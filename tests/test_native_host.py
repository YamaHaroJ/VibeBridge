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


    def test_manifest_key_matches_installer_extension_id(self):
        import base64
        import hashlib

        manifest_path = Path(__file__).resolve().parents[1] / "extension" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(base64.b64decode(manifest["key"])).digest()[:16]
        extension_id = "".join(
            chr(ord("a") + nibble)
            for byte in digest
            for nibble in (byte >> 4, byte & 0x0F)
        )
        installer = (Path(__file__).resolve().parents[1] / "agent" / "install.sh").read_text(encoding="utf-8")
        self.assertIn('EXTENSION_ID="' + extension_id + '"', installer)


    def test_main_emits_framed_token_response(self):
        import io
        from unittest.mock import patch

        payload = json.dumps({"type": "getToken"}).encode("utf-8")
        framed = struct.pack("<I", len(payload)) + payload
        output = io.BytesIO()
        with patch.object(native_host, "TOKEN_FILE") as token_file, \
             patch.object(native_host.sys, "stdin", io.TextIOWrapper(io.BytesIO(framed), encoding="utf-8")):
            # Native host reads binary stdin; provide a binary-compatible stdin object.
            native_host.sys.stdin = type("Input", (), {"buffer": io.BytesIO(framed)})()
            native_host.sys.stdout = type("Output", (), {"buffer": output})()
            token_file.read_text.return_value = "test-token"
            self.assertEqual(native_host.main(), 0)
        output.seek(0)
        response_size = struct.unpack("<I", output.read(4))[0]
        response = json.loads(output.read(response_size).decode("utf-8"))
        self.assertEqual(response, {"ok": True, "token": "test-token"})

    def test_main_returns_error_when_token_file_missing(self):
        import io
        from unittest.mock import patch

        payload = json.dumps({"type": "getToken"}).encode("utf-8")
        framed = struct.pack("<I", len(payload)) + payload
        output = io.BytesIO()
        with patch.object(native_host, "TOKEN_FILE") as token_file, \
             patch.object(native_host.sys, "stdin", type("Input", (), {"buffer": io.BytesIO(framed)})()), \
             patch.object(native_host.sys, "stdout", type("Output", (), {"buffer": output})()):
            token_file.read_text.side_effect = FileNotFoundError("missing")
            self.assertEqual(native_host.main(), 0)
        output.seek(0)
        response_size = struct.unpack("<I", output.read(4))[0]
        response = json.loads(output.read(response_size).decode("utf-8"))
        self.assertFalse(response["ok"])
        self.assertIn("missing", response["error"])


if __name__ == "__main__":
    unittest.main()
