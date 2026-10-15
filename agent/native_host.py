#!/usr/bin/env python3
"""Chrome Native Messaging host for VibeBridge token bootstrap.

Chrome enforces the registered host's allowed_origins before launching this
program. Never print diagnostics to stdout: it is the framed protocol channel.
"""
import json
import os
import traceback
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


def log_error(message):
    """Write diagnostics to a private file, never to the stdout protocol stream."""
    try:
        log_path = TOKEN_FILE.parent / "native-host-error.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(message.rstrip() + "\n")
        log_path.chmod(0o600)
    except Exception:
        pass


def read_exact(stream, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError(f"Native Messaging stream ended with {remaining} bytes still expected.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def write_response(response):
    encoded = json.dumps(response, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(encoded)) + encoded)
    sys.stdout.buffer.flush()


def main():
    try:
        header = read_exact(sys.stdin.buffer, 4)
        if not header:
            return 0
        if len(header) != 4:
            log_error("Native message header was truncated.")
            write_response({"ok": False, "error": "Native message header was truncated."})
            return 0
        size = struct.unpack("<I", header)[0]
        if size > MAX_MESSAGE_BYTES:
            log_error("Native message exceeded the size limit.")
            write_response({"ok": False, "error": "Native message is too large."})
            return 0
        body = read_exact(sys.stdin.buffer, size)
        message = decode_message(header + body)
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        write_response(handle_message(message, token))
        return 0
    except Exception as exc:
        detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        log_error(detail)
        try:
            write_response({"ok": False, "error": str(exc) or type(exc).__name__})
            return 0
        except Exception:
            return 1

if __name__ == "__main__":
    raise SystemExit(main())
