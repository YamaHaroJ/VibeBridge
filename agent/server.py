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


def local_repo_map():
    found = {}
    for project in discover_projects():
        try:
            remote = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=project["path"], capture_output=True, text=True, timeout=5
            )
            if remote.returncode == 0:
                url = remote.stdout.strip().removesuffix(".git")
                if url.startswith("git@github.com:"):
                    slug = url[len("git@github.com:"):]
                elif "github.com/" in url:
                    slug = url.split("github.com/", 1)[1]
                else:
                    slug = ""
                if slug:
                    found[slug.lower()] = project["path"]
        except Exception:
            pass
    return found


def github_projects():
    try:
        result = subprocess.run(
            ["gh", "repo", "list", "--limit", "1000", "--json",
             "name,nameWithOwner,description,url,isPrivate,isArchived,updatedAt,defaultBranchRef"],
            capture_output=True, text=True, timeout=45
        )
    except FileNotFoundError:
        raise RuntimeError("GitHub CLI (gh) is not installed. Install GitHub CLI and sign in first.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("GitHub repository listing timed out. Try again.")
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "GitHub CLI could not list repositories").strip()
        raise RuntimeError(message[:1000])
    try:
        repositories = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("GitHub CLI returned an unreadable repository list.")
    local = local_repo_map()
    for repo in repositories:
        repo["localPath"] = local.get(str(repo.get("nameWithOwner", "")).lower())
    repositories.sort(key=lambda item: (item.get("nameWithOwner", "").lower()))
    return repositories


def github_repo_for_name(value):
    value = str(value or "").strip().lower()
    if value.startswith("github:"):
        value = value[len("github:"):]
    if not value:
        return None
    try:
        repos = github_projects()
    except RuntimeError:
        return None
    exact = [r for r in repos if str(r.get("nameWithOwner", "")).lower() == value]
    if len(exact) == 1:
        return exact[0]
    short = value.rsplit("/", 1)[-1]
    matches = [r for r in repos if str(r.get("name", "")).lower() == short]
    return matches[0] if len(matches) == 1 else None


def remote_repo_context(slug):
    parts = [f"PROJECT: {slug.rsplit('/', 1)[-1]}", f"GITHUB REPOSITORY: {slug}",
             "SOURCE: GitHub repository (not cloned locally). Local file edits and terminal commands require cloning."]
    for filename in ("README.md", "VIBEBRIDGE_CONTEXT.md"):
        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{slug}/contents/{filename}", "--jq", ".content"],
                capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0 and result.stdout.strip():
                import base64
                content = base64.b64decode("".join(result.stdout.split())).decode("utf-8", errors="replace").strip()
                if content:
                    label = "PERSISTENT PROJECT MEMORY" if filename == "VIBEBRIDGE_CONTEXT.md" else "README"
                    parts.append(label + " (" + filename + "):\n" + content[:6500])
        except Exception:
            pass
    return "\\n\\n".join(parts)[:18000]


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
    if str(project).startswith("github:"):
        repo = github_repo_for_name(str(project))
        if not repo:
            raise ValueError("GitHub repository could not be resolved.")
        return remote_repo_context(repo["nameWithOwner"])
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
    # Resolve GitHub repositories by full owner/name or unique repository name.
    try:
        repos = github_projects()
    except RuntimeError:
        repos = []
    remote_explicit = []
    for repo in repos:
        full = str(repo.get("nameWithOwner", "")).lower()
        name = str(repo.get("name", "")).lower()
        # Match the exact repository slug/name, plus distinctive words from its
        # name so natural requests like "switch to Autofill" work.
        full_match = bool(full and full in text)
        name_match = bool(name and __import__("re").search(
            r"(?<![a-z0-9])" + __import__("re").escape(name).replace(r"\\-", r"[-_ ]+") + r"(?![a-z0-9])",
            text
        ))
        aliases = {
            "autofill-insurance-extension": ("autofill", "insurance extension", "autofill extension"),
            "vibebridge": ("vibebridge", "vibe bridge"),
            "macoptimizer": ("macoptimizer", "mac optimizer"),
        }.get(name.replace("_", "-"), ())
        alias_match = any(__import__("re").search(
            r"(?<![a-z0-9])" + __import__("re").escape(alias) + r"(?![a-z0-9])", text
        ) for alias in aliases)
        if full_match or name_match or alias_match:
            remote_explicit.append(repo)
    # Prefer exact full slug mentions, otherwise only accept a unique short name.
    exact_slug = [repo for repo in remote_explicit if str(repo.get("nameWithOwner", "")).lower() in text]
    chosen = exact_slug if exact_slug else remote_explicit
    unique = {str(repo.get("nameWithOwner", "")).lower(): repo for repo in chosen}
    if len(unique) == 1:
        repo = next(iter(unique.values()))
        if repo.get("localPath"):
            return {"name": repo["name"], "path": repo["localPath"]}, "message"
        return {"name": repo["name"], "path": "github:" + repo["nameWithOwner"], "repository": repo["nameWithOwner"], "remote": True}, "message"
    if len(unique) > 1:
        return None, "ambiguous"
    if active:
        if str(active).startswith("github:"):
            repo = github_repo_for_name(active)
            if repo:
                if repo.get("localPath"):
                    return {"name": repo["name"], "path": repo["localPath"]}, "active"
                return {"name": repo["name"], "path": "github:" + repo["nameWithOwner"], "repository": repo["nameWithOwner"], "remote": True}, "active"
        try:
            p = project_path(active)
            return {"name": p.name, "path": str(p)}, "active"
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
        if path == "/github-projects":
            try:
                return self.send_json(200, {"repositories": github_projects()})
            except RuntimeError as e:
                return self.send_json(400, {"error": str(e)})
        if path == "/update-status":
            log_file = SUPPORT / "update.log"
            try:
                lines = log_file.read_text(errors="replace").splitlines()[-30:]
            except OSError:
                lines = []
            return self.send_json(200, {"log": lines})
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
        if path == "/update":
            try:
                script = Path(__file__).with_name("updater.py")
                if not script.is_file():
                    return self.send_json(501, {"error": "Updater helper is not installed in this checkout yet."})
                log_file = SUPPORT / "update.log"
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with log_file.open("a", encoding="utf-8") as handle:
                    handle.write("\n[" + __import__("datetime").datetime.now().isoformat(timespec="seconds") + "] Update requested from extension.\n")
                subprocess.Popen(
                    [__import__("sys").executable, str(script)],
                    cwd=str(ROOTS[2]),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    close_fds=True,
                )
                return self.send_json(202, {"started": True, "message": "Update started. Check Update status in a few seconds."})
            except Exception as e:
                return self.send_json(500, {"error": "Could not start updater: " + str(e)})
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
        if path == "/clone":
            slug = str(body.get("repository", "")).strip()
            if not __import__("re").fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
                return self.send_json(400, {"error": "Choose a valid owner/repository from GitHub."})
            owner, repo_name = slug.split("/", 1)
            target_root = Path.home() / "Projects"
            target = (target_root / repo_name).resolve()
            if target_root.resolve() not in target.parents:
                return self.send_json(400, {"error": "Invalid clone destination."})
            if target.exists():
                return self.send_json(409, {"error": f"{target} already exists. Choose the existing local project instead."})
            try:
                target_root.mkdir(parents=True, exist_ok=True)
                result = subprocess.run(
                    ["gh", "repo", "clone", slug, str(target)],
                    capture_output=True, text=True, timeout=180
                )
            except FileNotFoundError:
                return self.send_json(400, {"error": "GitHub CLI (gh) is not installed."})
            except subprocess.TimeoutExpired:
                return self.send_json(408, {"error": "Clone timed out. Check whether the repository finished cloning before retrying."})
            if result.returncode != 0:
                message = (result.stderr or result.stdout or "Clone failed").strip()
                return self.send_json(400, {"error": message[-1500:]})
            return self.send_json(200, {"cloned": True, "repository": slug, "project": {"name": repo_name, "path": str(target)}})
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
                handle.write("\n- " + note.replace("\n", " ") + "\n")
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
