import json
import secrets
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 43127
ROOTS = [
    Path.home() / "Projects",
    Path.home() / "Developer",
    Path.home() / "VibeBridge",
    Path.home() / "MacOptimizer",
]
TOKEN_FILE = Path.home() / "Library/Application Support/VibeBridge/token"
TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
if not TOKEN_FILE.exists():
    TOKEN_FILE.write_text(secrets.token_urlsafe(32))
    TOKEN_FILE.chmod(0o600)
TOKEN = TOKEN_FILE.read_text().strip()


def discover_projects():
    found = {}
    for base in ROOTS:
        if not base.is_dir():
            continue
        candidates = [base]
        try:
            candidates.extend(p for p in base.iterdir() if p.is_dir() and not p.name.startswith("."))
        except OSError:
            continue
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
                if any(resolved == root.resolve() or root.resolve() in resolved.parents for root in ROOTS):
                    if (resolved / ".git").exists() or candidate == Path.home() / "VibeBridge" or candidate == Path.home() / "MacOptimizer":
                        found[str(resolved)] = {"name": resolved.name, "path": str(resolved)}
            except OSError:
                pass
    return sorted(found.values(), key=lambda item: item["name"].lower())


def project_path(raw):
    value = str(raw or "").strip()
    projects = discover_projects()
    # Resolve a remembered project name as well as an explicit filesystem path.
    matches = [item for item in projects if item["name"].lower() == value.lower() or item["path"].lower() == value.lower()]
    if len(matches) == 1:
        p = Path(matches[0]["path"])
    else:
        p = Path(value).expanduser().resolve()
    if not any(p == root.resolve() or root.resolve() in p.parents for root in ROOTS):
        raise ValueError("Project path is not allowed")
    if not p.is_dir():
        raise ValueError("Project path does not exist or is not allowed")
    return p


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        origin = self.headers.get("Origin", "")
        if origin.startswith("chrome-extension://"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        if not origin.startswith("chrome-extension://"):
            return self.send_json(403, {"error": "Extension origin required"})
        return self.send_json(200, {"ok": True})

    def authorized(self):
        return secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + TOKEN)

    def do_GET(self):
        if not self.authorized():
            return self.send_json(401, {"error": "Unauthorized"})
        if self.path == "/health":
            return self.send_json(200, {"ok": True, "service": "VibeBridge", "port": PORT})
        if self.path == "/projects":
            return self.send_json(200, {"projects": discover_projects()})
        return self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not self.authorized():
            return self.send_json(401, {"error": "Unauthorized"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1024 * 1024:
                return self.send_json(413, {"error": "Request too large"})
            body = json.loads(self.rfile.read(length))
        except Exception:
            return self.send_json(400, {"error": "Invalid JSON"})
        if self.path not in ("/diagnostics", "/run"):
            return self.send_json(404, {"error": "Not found"})
        try:
            root = project_path(body.get("project", ""))
        except (ValueError, OSError):
            return self.send_json(403, {"error": "Project not found or not allowed. Use the Projects list to select a discovered folder."})
        if self.path == "/diagnostics":
            commands = [["git", "status", "--short", "--branch"], ["git", "log", "-1", "--oneline"]]
            results = []
            for cmd in commands:
                try:
                    r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=15)
                    results.append({"command": cmd, "exitCode": r.returncode, "stdout": r.stdout[-12000:], "stderr": r.stderr[-4000:]})
                except Exception as e:
                    results.append({"command": cmd, "error": str(e)})
            return self.send_json(200, {"project": str(root), "results": results})
        cmd = body.get("command", [])
        if not isinstance(cmd, list) or not cmd or not all(isinstance(x, str) for x in cmd):
            return self.send_json(400, {"error": "command must be a non-empty argument array"})
        try:
            r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=120)
            return self.send_json(200, {"project": str(root), "exitCode": r.returncode, "stdout": r.stdout[-20000:], "stderr": r.stderr[-8000:]})
        except subprocess.TimeoutExpired:
            return self.send_json(408, {"error": "Command timed out"})
        except OSError as e:
            return self.send_json(400, {"error": str(e)})

    def log_message(self, fmt, *args):
        print("VibeBridge:", fmt % args)


print("VibeBridge listening on http://127.0.0.1:%d" % PORT)
HTTPServer((HOST, PORT), Handler).serve_forever()
