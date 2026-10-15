import hashlib
import json
import re
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
    import base64
    loaded = []
    errors = []
    for filename in ("README.md", "VIBEBRIDGE_CONTEXT.md"):
        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{slug}/contents/{filename}", "--jq", ".content"],
                capture_output=True, text=True, timeout=20
            )
        except FileNotFoundError:
            raise RuntimeError("GitHub CLI (gh) is not installed, so remote project context cannot be loaded.")
        except subprocess.TimeoutExpired:
            errors.append(f"{filename}: GitHub request timed out")
            continue
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "GitHub API request failed").strip()
            if filename == "VIBEBRIDGE_CONTEXT.md" and ("404" in detail or "Not Found" in detail):
                continue
            errors.append(f"{filename}: {detail[:300]}")
            continue
        if not result.stdout.strip():
            continue
        try:
            encoded = "".join(result.stdout.split())
            content = base64.b64decode(encoded, validate=True).decode("utf-8", errors="replace").strip()
        except (ValueError, base64.binascii.Error) as exc:
            errors.append(f"{filename}: GitHub returned invalid base64 content ({exc})")
            continue
        if content:
            label = "PERSISTENT PROJECT MEMORY" if filename == "VIBEBRIDGE_CONTEXT.md" else "README"
            parts.append(label + " (" + filename + "):\n" + content[:6500])
            loaded.append(filename)
    if not loaded:
        detail = "; ".join(errors) if errors else "The repository has no readable README.md or VIBEBRIDGE_CONTEXT.md."
        raise RuntimeError(f"Could not load useful context from GitHub repository {slug}. {detail}")
    if slug.lower() == "yamaharoJ/vibebridge".lower():
        try:
            checkpoint = subprocess.run(
                ["gh", "api", "repos/YamaHaroJ/VibeBridge/contents/memory/AUTO_CHECKPOINT.md", "--jq", ".content"],
                capture_output=True, text=True, timeout=15
            )
            if checkpoint.returncode == 0 and checkpoint.stdout.strip():
                checkpoint_text = base64.b64decode("".join(checkpoint.stdout.split()), validate=True).decode("utf-8", errors="replace").strip()
                if checkpoint_text:
                    parts.append("ROLLING CONVERSATION CHECKPOINTS (GitHub):\n" + checkpoint_text[:5000])
        except (subprocess.TimeoutExpired, ValueError, base64.binascii.Error):
            pass
    if errors:
        parts.append("REMOTE CONTEXT WARNINGS: " + "; ".join(errors))
    return "\n\n".join(parts)[:18000]

def sync_message_checkpoint(summary, conversation):
    import base64
    from datetime import datetime
    repo = "YamaHaroJ/VibeBridge"
    summary = str(summary or "").strip()
    if not summary:
        raise ValueError("The assistant summary is empty.")
    summary = summary[:12000]
    conv = re.sub(r"[^A-Za-z0-9_.-]", "", str(conversation or "chat"))[:80] or "chat"
    path = "memory/AUTO_CHECKPOINT.md"
    for attempt in range(3):
        get = subprocess.run(["gh", "api", f"repos/{repo}/contents/{path}"], capture_output=True, text=True, timeout=20)
        sha, existing = None, ""
        if get.returncode == 0:
            item = json.loads(get.stdout)
            sha = item.get("sha")
            existing = base64.b64decode(item.get("content", "")).decode("utf-8", errors="replace")
        elif "404" not in (get.stderr + get.stdout):
            raise RuntimeError((get.stderr or get.stdout or "Could not read checkpoint file").strip()[:700])
        sections = re.findall(r"(?ms)^## Conversation: ([^\n]+)\n(.*?)(?=^## Conversation: |\Z)", existing)
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        section = "## Conversation: " + conv + "\n_Last updated: " + stamp + "_\n\n" + summary
        others = ["## Conversation: " + key + "\n" + body.strip() for key, body in sections if key != conv]
        updated = "# VibeBridge Conversation Checkpoints\n\n" + section + "\n\n" + "\n\n".join(others[:40]) + "\n"
        payload = {"message": "Save ChatGPT project checkpoint " + conv + " " + stamp, "content": base64.b64encode(updated.encode()).decode()}
        if sha:
            payload["sha"] = sha
        result = subprocess.run(["gh", "api", "--method", "PUT", f"repos/{repo}/contents/{path}", "--input", "-"], input=json.dumps(payload), capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return {"saved": True, "path": path, "conversation": conv, "timestamp": stamp}
        error = (result.stderr or result.stdout or "GitHub checkpoint update failed").strip()
        if "409" not in error and "sha" not in error.lower():
            raise RuntimeError(error[:1000])
    raise RuntimeError("GitHub checkpoint changed repeatedly; retry the save.")



def create_github_repo(name, description="", private=True):
    name = str(name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name):
        raise ValueError("Repository name must use only letters, numbers, periods, hyphens, or underscores.")
    args = ["gh", "repo", "create", name] + (["--private"] if private else ["--public"])
    if description:
        args += ["--description", str(description)[:300]]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=45)
    except FileNotFoundError:
        raise RuntimeError("GitHub CLI (gh) is not installed.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Creating the GitHub repository timed out.")
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "GitHub repository creation failed").strip()[-1000:])
    output = (result.stdout or "").strip().splitlines()
    url = next((line.strip() for line in reversed(output) if "github.com/" in line), "")
    slug = url.rstrip("/").split("github.com/", 1)[-1] if url else ""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
        raise RuntimeError("GitHub created a repository, but its owner/name could not be read from the command output. Output: " + (result.stdout or "").strip()[-500:])

    import base64
    starter_files = {
        "README.md": (
            "# " + slug.rsplit("/", 1)[-1] + "\n\n"
            "Project repository created by VibeBridge. Replace this README with the project's purpose, setup, architecture, and usage.\n"
        ),
        "VIBEBRIDGE_CONTEXT.md": (
            "# Project Memory\n\n"
            "## Goal\nDescribe what this project should do.\n\n"
            "## Architecture\nRecord the important components and how they fit together.\n\n"
            "## Decisions\nRecord durable decisions here.\n\n"
            "## Current state\nRepository created by VibeBridge; implementation has not started. Verify code before assuming features exist.\n\n"
            "## Next task\nAsk ChatGPT to define the minimum viable implementation and begin with tests.\n"
        ),
    }
    for path, text in starter_files.items():
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        try:
            seeded = subprocess.run(
                ["gh", "api", f"repos/{slug}/contents/{path}", "-X", "PUT",
                 "-f", "message=Initialize VibeBridge project memory", "-f", f"content={encoded}"],
                capture_output=True, text=True, timeout=45
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Repository {slug} was created, but initializing {path} timed out. The repository exists; retry initialization after checking GitHub.")
        if seeded.returncode != 0:
            detail = (seeded.stderr or seeded.stdout or "GitHub API rejected the file creation").strip()[-700:]
            raise RuntimeError(f"Repository {slug} was created, but initializing {path} failed: {detail}")
    return {"nameWithOwner": slug, "url": "https://github.com/" + slug, "private": bool(private), "initialized": True}


# Filesystem access is intentionally scoped to the authenticated user's home
# directory. macOS privacy controls still apply to protected folders.
HOME_ROOT = Path.home().resolve()
MAX_FILE_BYTES = 2 * 1024 * 1024


def filesystem_path(raw):
    value = str(raw or "").strip()
    if not value:
        raise ValueError("A filesystem path is required.")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = HOME_ROOT / candidate
    resolved = candidate.resolve()
    if resolved != HOME_ROOT and HOME_ROOT not in resolved.parents:
        raise ValueError("Filesystem access is limited to your home folder.")
    # Block sensitive system-managed directories even if path handling changes.
    blocked = (Path("/System"), Path("/Library"), Path("/private"), Path("/usr"), Path("/bin"), Path("/sbin"), Path("/Applications"))
    if any(resolved == item or item in resolved.parents for item in blocked):
        raise ValueError("This system-managed location is not accessible through VibeBridge.")
    return resolved


def filesystem_listing(raw):
    path = filesystem_path(raw or str(HOME_ROOT))
    if not path.exists() or not path.is_dir():
        raise ValueError("Folder does not exist.")
    items = []
    for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))[:500]:
        try:
            items.append({
                "name": child.name,
                "path": str(child),
                "type": "folder" if child.is_dir() else "file",
                "hidden": child.name.startswith("."),
                "size": child.stat().st_size if child.is_file() else None,
            })
        except OSError:
            continue
    return {"path": str(path), "parent": str(path.parent) if path != HOME_ROOT else None, "items": items}


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
    text = str(message or "").lower()
    projects = discover_projects()
    switch_intent = bool(re.search(r"\b(?:switch|change|move)\s+(?:the\s+)?(?:project|repo|repository)?\s*(?:to|over\s+to)\b|\bopen\s+(?:the\s+)?(?:repo|repository)\b", text))

    def as_project(repo):
        if repo.get("localPath"):
            return {"name": repo["name"], "path": repo["localPath"]}
        return {"name": repo["name"], "path": "github:" + repo["nameWithOwner"],
                "repository": repo["nameWithOwner"], "remote": True}

    repos = None
    slug_match = re.search(r"(?<![a-z0-9])([a-z0-9_.-]+/[a-z0-9_.-]+)(?![a-z0-9_.-])", text)
    if slug_match:
        try:
            repos = github_projects()
        except RuntimeError as exc:
            raise RuntimeError("Could not search GitHub for the explicitly named repository. " + str(exc))
        slug = slug_match.group(1).lower()
        exact = [repo for repo in repos if str(repo.get("nameWithOwner", "")).lower() == slug]
        if len(exact) == 1:
            return as_project(exact[0]), "message"
        if switch_intent:
            raise RuntimeError("The explicitly named GitHub repository was not found in the authenticated GitHub CLI account: " + slug_match.group(1))

    # Exact owner/repository slugs take priority over a same-named local folder.
    local_explicit = [
        item for item in projects
        if re.search(
            r"(?<![a-z0-9])" + re.escape(item["name"].lower()).replace(r"\-", r"[-_ ]+") + r"(?![a-z0-9])",
            text
        )
    ]
    if len(local_explicit) == 1:
        return local_explicit[0], "message"
    if len(local_explicit) > 1:
        return None, "ambiguous"

    if repos is None:
        try:
            repos = github_projects()
        except RuntimeError as exc:
            # Never silently attach the previous project's context to an explicit switch request.
            target_alias = bool(re.search(r"\bautofill\b|\bmac\s*optimizer\b|\bvibe\s*bridge\b", text))
            if switch_intent and target_alias:
                raise RuntimeError("Could not search GitHub to resolve the requested project. " + str(exc))
            repos = []

    aliases = {
        "autofill-insurance-extension": ("autofill", "insurance extension", "autofill extension"),
        "vibebridge": ("vibebridge", "vibe bridge"),
        "macoptimizer": ("macoptimizer", "mac optimizer"),
    }
    remote_explicit = []
    for repo in repos:
        full = str(repo.get("nameWithOwner", "")).lower()
        name = str(repo.get("name", "")).lower()
        normalized_name = name.replace("_", "-")
        pattern = re.escape(normalized_name).replace(r"\-", r"[-_ ]+")
        full_match = bool(full and full in text)
        name_match = bool(pattern and re.search(r"(?<![a-z0-9])" + pattern + r"(?![a-z0-9])", text))
        alias_match = any(
            re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", text)
            for alias in aliases.get(normalized_name, ())
        )
        if full_match or name_match or alias_match:
            remote_explicit.append(repo)

    exact_slug = [repo for repo in remote_explicit if str(repo.get("nameWithOwner", "")).lower() in text]
    chosen = exact_slug if exact_slug else remote_explicit
    unique = {str(repo.get("nameWithOwner", "")).lower(): repo for repo in chosen}
    if len(unique) == 1:
        return as_project(next(iter(unique.values()))), "message"
    if len(unique) > 1:
        return None, "ambiguous"
    if switch_intent:
        # An explicit target that cannot be resolved must never fall back to old context.
        raise RuntimeError("The requested project could not be resolved. Use the repository name or owner/repository, then check GitHub CLI connection in VibeBridge settings.")

    # No explicit target: keep the current project where possible.
    if active:
        if str(active).startswith("github:"):
            repo = github_repo_for_name(active)
            if repo:
                return as_project(repo), "active"
            return {"name": str(active).split("/")[-1], "path": str(active), "remote": True}, "active"
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
        if path == "/filesystem/list":
            query = parse_qs(urlparse(self.path).query)
            try:
                return self.send_json(200, filesystem_listing(query.get("path", [str(HOME_ROOT)])[0]))
            except (ValueError, OSError) as e:
                return self.send_json(400, {"error": str(e)})
        if path == "/filesystem/read":
            query = parse_qs(urlparse(self.path).query)
            try:
                target = filesystem_path(query.get("path", [""])[0])
                if not target.is_file():
                    raise ValueError("Path is not a file.")
                if target.stat().st_size > MAX_FILE_BYTES:
                    raise ValueError("File exceeds the 2 MB read limit.")
                return self.send_json(200, {"path": str(target), "content": target.read_text(encoding="utf-8", errors="replace")})
            except (ValueError, OSError) as e:
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
            try:
                project, reason = match_project(message, active)
                if reason == "ambiguous":
                    return self.send_json(200, {"matched": False, "ambiguous": True, "candidates": [p["name"] for p in discover_projects() if p["name"].lower() in message.lower()]})
                if not project:
                    return self.send_json(200, {"matched": False, "reason": "no-project-match"})
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
        if path == "/checkpoint":
            try:
                result = sync_message_checkpoint(body.get("summary", ""), body.get("conversation", "chat"))
                return self.send_json(200, result)
            except (ValueError, RuntimeError) as e:
                return self.send_json(400, {"error": str(e)})
        if path == "/filesystem/write":
            try:
                target = filesystem_path(body.get("path", ""))
                content = body.get("content")
                if not isinstance(content, str):
                    raise ValueError("content must be a string.")
                if len(content.encode("utf-8")) > MAX_FILE_BYTES:
                    return self.send_json(413, {"error": "File exceeds the 2 MB write limit."})
                if not target.parent.is_dir():
                    raise ValueError("Parent folder does not exist.")
                if target.exists() and not target.is_file():
                    raise ValueError("Target path is not a file.")
                target.write_text(content, encoding="utf-8")
                return self.send_json(200, {"written": True, "path": str(target), "bytes": len(content.encode("utf-8"))})
            except (ValueError, OSError) as e:
                return self.send_json(400, {"error": str(e)})
        if path == "/filesystem/mkdir":
            try:
                target = filesystem_path(body.get("path", ""))
                target.mkdir(parents=False, exist_ok=False)
                return self.send_json(201, {"created": True, "path": str(target)})
            except (ValueError, OSError) as e:
                return self.send_json(400, {"error": str(e)})
        if path == "/create-repository":
            try:
                repo = create_github_repo(body.get("name", ""), body.get("description", ""), body.get("private", True))
                project = {"name": repo["nameWithOwner"].split("/", 1)[1], "path": "github:" + repo["nameWithOwner"], "repository": repo["nameWithOwner"], "remote": True}
                context = remote_repo_context(repo["nameWithOwner"])
                return self.send_json(201, {"created": True, "repository": repo, "project": project, "context": context,
                                            "message": "Repository created and initialized with README.md and VIBEBRIDGE_CONTEXT.md. Context is ready for this message."})
            except ValueError as e:
                return self.send_json(400, {"error": str(e)})
            except RuntimeError as e:
                return self.send_json(400, {"error": str(e)})
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
            try:
                project, reason = match_project(body.get("message", ""), body.get("active", ""))
                if reason == "ambiguous":
                    return self.send_json(200, {"matched": False, "ambiguous": True})
                if not project:
                    return self.send_json(200, {"matched": False})
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


def main():
    print("VibeBridge listening on http://127.0.0.1:%d" % PORT)
    HTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
