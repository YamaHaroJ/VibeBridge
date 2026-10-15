#!/usr/bin/env python3
"""Chrome Native Messaging host for VibeBridge token bootstrap.

Chrome enforces the registered host's allowed_origins before launching this
program. Never print diagnostics to stdout: it is the framed protocol channel.
"""
import json
import os
import struct
import sys
from pathlib import Path

MAX_MESSAGE_BYTES = 1024 * 1024
TOKEN_FILE = Path.home() / "Library/Application Support/VibeBridge/token"


def decode_message(data):
    if len(data) < 4:
        raise ValueError("Native message header is truncated.")
    size = struct.unpack("<I", data[:4])[0]
    if size > MAX_MESSAGE_BYTES:
        raise ValueError("Native message is too large.")
    if len(data) != size + 4:
        raise ValueError("Native message body is truncated or has trailing bytes.")
    try:
        message = json.loads(data[4:].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Native message is not valid JSON.") from exc
    if not isinstance(message, dict):
        raise ValueError("Native message must be a JSON object.")
    return message


def handle_message(message, token):
    if message.get("type") != "getToken":
        return {"ok": False, "error": "Unsupported native message."}
    if not token:
        return {"ok": False, "error": "VibeBridge token is not configured."}
    return {"ok": True, "token": token}


def main():
    header = sys.stdin.buffer.read(4)
    if not header:
        return 0
    if len(header) != 4:
        return 1
    size = struct.unpack("<I", header)[0]
    if size > MAX_MESSAGE_BYTES:
        return 1
    body = sys.stdin.buffer.read(size)
    try:
        message = decode_message(header + body)
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        response = handle_message(message, token)
    except (OSError, ValueError) as exc:
        response = {"ok": False, "error": str(exc)}
    encoded = json.dumps(response, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(encoded)) + encoded)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
