import hashlib
import json
import secrets
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HOST = "127.0.0.1"
PORT = 43127
ROOTS = [
    Path.home() / "Projects",
    Path.home() / "Developer",
    Path.home() / "VibeBridge",
    Path.home() / "MacOptimizer",
]
SUPPORT = Path.home() / "Library/Application Support/VibeBridge"
TOKEN_FILE = SUPPORT / "token"
MEMORY_DIR = SUPPORT / "projects"
SUPPORT.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
if not TOKEN_FILE.exists():
    TOKEN_FILE.write_text(secrets.token_urlsafe(32))
    TOKEN_FILE.chmod(0o600)
TOKEN = TOKEN_FILE.read_text().strip()


def discover_projects():
    found = {}
    for base in ROOTS:
        if not base.is_dir():
            continue
        try:
            candidates = [base] + [p for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")]
        except OSError:
            continue
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
                if any(resolved == root.resolve() or root.resolve() in resolved.parents for root in ROOTS):
                    if (resolved / ".git").exists() or candidate in (Path.home() / "VibeBridge", Path.home() / "MacOptimizer"):
                        found[str(resolved)] = {"name": resolved.name, "path": str(resolved)}
            except OSError:
                pass
    return sorted(found.values(), key=lambda item: item["name"].lower())


def project_path(raw):
    value = str(raw or "").strip()
    projects = discover_projects()
    matches = [item for item in projects if item["name"].lower() == value.lower() or item["path"].lower() == value.lower()]
    p = Path(matches[0]["path"]) if len(matches) == 1 else Path(value).expanduser().resolve()
    if not any(p == root.resolve() or root.resolve() in p.parents for root in ROOTS):
        raise ValueError("Project path is not allowed")
    if not p.is_dir():
        raise ValueError("Project path does not exist or is not allowed")
    return p


def read_text(path, limit=9000):
    try:
        return path.read_text(errors="replace")[:limit].strip()
    except (OSError, UnicodeError):
        return ""


def project_context(project):
    p = project_path(project)
    parts = [f"PROJECT: {p.name}", f"LOCAL PATH: {p}"]
    remote = subprocess.run(["git", "remote", "get-url", "origin"], cwd=str(p), capture_output=True, text=True, timeout=5)
    if remote.returncode == 0 and remote.stdout.strip():
        parts.append("GITHUB REMOTE: " + remote.stdout.strip())
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=str(p), capture_output=True, text=True, timeout=5)
    if branch.returncode == 0:
        parts.append("BRANCH: " + branch.stdout.strip())
    status = subprocess.run(["git", "status", "--short"], cwd=str(p), capture_output=True, text=True, timeout=5)
    if status.returncode == 0:
        parts.append("WORKING TREE: " + (status.stdout.strip() or "clean"))
    commit = subprocess.run(["git", "log", "-1", "--oneline"], cwd=str(p), capture_output=True, text=True, timeout=5)
    if commit.returncode == 0 and commit.stdout.strip():
        parts.append("LATEST COMMIT: " + commit.stdout.strip())
    readme = read_text(p / "README.md", 6500)
    if readme:
        parts.append("README SUMMARY SOURCE (README text):\n" + readme)
    memory = read_text(p / "VIBEBRIDGE_CONTEXT.md", 6500)
    if memory:
        parts.append("PERSISTENT PROJECT MEMORY:\n" + memory)
    memory_file = MEMORY_DIR / (hashlib.sha256(str(p).encode()).hexdigest() + ".md")
    local_memory = read_text(memory_file, 6500)
    if local_memory:
        parts.append("VIBEBRIDGE SAVED NOTES:\n" + local_memory)
    return "\n\n".join(parts)[:18000]


def match_project(message, active=""):
    projects = discover_projects()
    text = str(message or "").lower()
    explicit = [item for item in projects if item["name"].lower() in text]
    if len(explicit) == 1:
        return explicit[0], "message"
    if len(explicit) > 1:
        return None, "ambiguous"
    if active:
        try:
            return {"name": project_path(active).name, "path": str(project_path(active))}, "active"
        except (ValueError, OSError):
            pass
    return None, "none"


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
        self.send_header("Content-Length", str(len(data)))
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
        path = urlparse(self.path).path
        if path == "/health":
            return self.send_json(200, {"ok": True, "service": "VibeBridge", "port": PORT})
        if path == "/projects":
            return self.send_json(200, {"projects": discover_projects()})
        if path == "/context":
            query = parse_qs(urlparse(self.path).query)
            message = query.get("message", [""])[0]
            active = query.get("active", [""])[0]
            project, reason = match_project(message, active)
            if reason == "ambiguous":
                return self.send_json(200, {"matched": False, "ambiguous": True, "candidates": [p["name"] for p in discover_projects() if p["name"].lower() in message.lower()]})
            if not project:
                return self.send_json(200, {"matched": False, "reason": "no-project-match"})
            try:
                return self.send_json(200, {"matched": True, "matchReason": reason, "project": project, "context": project_context(project["path"])})
            except Exception as e:
                return self.send_json(400, {"error": str(e)})
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
        path = urlparse(self.path).path
        if path == "/context":
            project, reason = match_project(body.get("message", ""), body.get("active", ""))
            if reason == "ambiguous":
                return self.send_json(200, {"matched": False, "ambiguous": True})
            if not project:
                return self.send_json(200, {"matched": False})
            try:
                return self.send_json(200, {"matched": True, "matchReason": reason, "project": project, "context": project_context(project["path"])})
            except Exception as e:
                return self.send_json(400, {"error": str(e)})
        if path == "/remember":
            try:
                root = project_path(body.get("project", ""))
            except (ValueError, OSError):
                return self.send_json(403, {"error": "Project not found or not allowed"})
            note = str(body.get("note", "")).strip()
            if not note:
                return self.send_json(400, {"error": "note is required"})
            if len(note) > 3000:
                return self.send_json(413, {"error": "Note is too long (max 3000 characters)"})
            memory_file = MEMORY_DIR / (hashlib.sha256(str(root).encode()).hexdigest() + ".md")
            with memory_file.open("a", encoding="utf-8") as handle:
                handle.write("\\n- " + note.replace("\\n", " ") + "\\n")
            return self.send_json(200, {"saved": True, "project": root.name})
        if path not in ("/diagnostics", "/run"):
            return self.send_json(404, {"error": "Not found"})
        try:
            root = project_path(body.get("project", ""))
        except (ValueError, OSError):
            return self.send_json(403, {"error": "Project not found or not allowed. Use the Projects list to select a discovered folder."})
        if path == "/diagnostics":
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
