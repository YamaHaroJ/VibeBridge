import json
import os
import secrets
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 43127
ROOTS = [Path.home() / "Projects", Path.home() / "Developer", Path.home() / "VibeBridge", Path.home() / "MacOptimizer"]
TOKEN_FILE = Path.home() / "Library/Application Support/VibeBridge/token"

TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
if not TOKEN_FILE.exists():
    TOKEN_FILE.write_text(secrets.token_urlsafe(32))
    TOKEN_FILE.chmod(0o600)
TOKEN = TOKEN_FILE.read_text().strip()

def allowed(path):
    p = Path(path).expanduser().resolve()
    return any(p == root.resolve() or root.resolve() in p.parents for root in ROOTS)

class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "chrome-extension://*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_json(200, {"ok": True})

    def authorized(self):
        return secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + TOKEN)

    def do_GET(self):
        if not self.authorized():
            return self.send_json(401, {"error": "Unauthorized"})
        if self.path == "/health":
            return self.send_json(200, {"ok": True, "service": "VibeBridge", "port": PORT})
        if self.path == "/projects":
            roots = [str(p) for p in ROOTS if p.exists()]
            return self.send_json(200, {"projects": roots})
        return self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self.authorized():
            return self.send_json(401, {"error": "Unauthorized"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        except Exception:
            return self.send_json(400, {"error": "Invalid JSON"})
        if self.path == "/diagnostics":
            root = body.get("project", "")
            if not allowed(root) or not Path(root).is_dir():
                return self.send_json(403, {"error": "Project path is not allowed"})
            commands = [
                ["git", "status", "--short", "--branch"],
                ["git", "log", "-1", "--oneline"],
            ]
            results = []
            for cmd in commands:
                try:
                    r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=15)
                    results.append({"command": cmd, "exitCode": r.returncode, "stdout": r.stdout[-12000:], "stderr": r.stderr[-4000:]})
                except Exception as e:
                    results.append({"command": cmd, "error": str(e)})
            return self.send_json(200, {"project": str(Path(root).resolve()), "results": results})
        if self.path == "/run":
            root = body.get("project", "")
            cmd = body.get("command", [])
            if not allowed(root) or not Path(root).is_dir():
                return self.send_json(403, {"error": "Project path is not allowed"})
            if not isinstance(cmd, list) or not cmd or not all(isinstance(x, str) for x in cmd):
                return self.send_json(400, {"error": "command must be an argument array"})
            try:
                r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=120)
                return self.send_json(200, {"exitCode": r.returncode, "stdout": r.stdout[-20000:], "stderr": r.stderr[-8000:]})
            except subprocess.TimeoutExpired:
                return self.send_json(408, {"error": "Command timed out"})
        return self.send_json(404, {"error": "Not found"})

    def log_message(self, fmt, *args):
        print("VibeBridge:", fmt % args)

print("VibeBridge listening on http://127.0.0.1:%d" % PORT)
HTTPServer((HOST, PORT), Handler).serve_forever()
