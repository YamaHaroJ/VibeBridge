import base64
import hashlib
import json
import os
import platform
import re
import secrets
import signal
import subprocess
import threading
import time
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
PAIRING_FILE = SUPPORT / "paired_extension_origin"


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
    try:
        checkpoint = subprocess.run(
            ["gh", "api", f"repos/{slug}/contents/memory/AUTO_CHECKPOINT.md", "--jq", ".content"],
            capture_output=True, text=True, timeout=4
        )
        if checkpoint.returncode == 0 and checkpoint.stdout.strip():
            checkpoint_text = base64.b64decode("".join(checkpoint.stdout.split()), validate=True).decode("utf-8", errors="replace").strip()
            if checkpoint_text:
                parts.append("ROLLING CONVERSATION CHECKPOINTS (GitHub):\n" + checkpoint_text[:5000])
    except (OSError, subprocess.TimeoutExpired, ValueError, base64.binascii.Error):
        pass
    if errors:
        parts.append("REMOTE CONTEXT WARNINGS: " + "; ".join(errors))
    return "\n\n".join(parts)[:18000]

def format_project_context_sections(sections):
    """Join named project contexts with real line breaks."""
    return "\n\n".join(
        "===== PROJECT CONTEXT: " + str(name) + " =====\n" + str(context)
        for name, context in sections
    )[:36000]


def sync_message_checkpoint(summary, conversation):
    import base64
    from datetime import datetime

    raw = str(summary or "").strip()
    if not raw:
        raise ValueError("The assistant summary is empty.")
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        # A malformed JSON checkpoint must never be silently saved as raw text
        # into the VibeBridge repository; it could overwrite the wrong project's
        # rolling memory and conceal a broken assistant payload.
        if raw.startswith("{") or raw.startswith("["):
            raise ValueError("Assistant memory JSON is malformed; no checkpoint was saved.") from exc
        document = {"projects": [{"repository": "YamaHaroJ/VibeBridge", "summary": raw}]}
    projects = document.get("projects", [])
    if not isinstance(projects, list) or not projects:
        raise ValueError("No project summaries were provided.")

    conv = re.sub(r"[^A-Za-z0-9_.-]", "", str(conversation or "chat"))[:80] or "chat"
    saved, errors = [], []
    for entry in projects[:12]:
        if not isinstance(entry, dict):
            continue
        slug = str(entry.get("repository", "")).strip()
        if isinstance(entry.get("summary"), dict):
            summary_value = json.dumps(entry.get("summary"), ensure_ascii=False, indent=2)
        else:
            summary_value = str(entry.get("summary", "")).strip()
        handoff = str(entry.get("handoff", "")).strip()
        todos = entry.get("todos", [])
        decisions = entry.get("decisions", [])
        updated = str(entry.get("updated", "")).strip()
        sections = ["### Durable project summary\n" + summary_value] if summary_value else []
        if handoff:
            sections.append("### Latest conversation handoff\n" + handoff)
        if isinstance(todos, list) and todos:
            sections.append("### Living todo list\n" + json.dumps(todos[:40], ensure_ascii=False, indent=2))
        if isinstance(decisions, list) and decisions:
            sections.append("### Durable decisions\n" + json.dumps(decisions[:40], ensure_ascii=False, indent=2))
        if updated:
            sections.append("### Memory updated\n" + updated)
        summary_text = "\n\n".join(sections).strip()[:9000]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug) or not summary_text:
            errors.append("Skipped an invalid repository or empty summary.")
            continue
        check = subprocess.run(
            ["gh", "repo", "view", slug, "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
            capture_output=True, text=True, timeout=20
        )
        if check.returncode != 0 or check.stdout.strip().lower() != slug.lower():
            errors.append("Could not verify access to " + slug)
            continue
        path = "memory/AUTO_CHECKPOINT.md"
        wrote = False
        for attempt in range(3):
            get = subprocess.run(
                ["gh", "api", f"repos/{slug}/contents/{path}"],
                capture_output=True, text=True, timeout=20
            )
            sha, existing = None, ""
            if get.returncode == 0:
                item = json.loads(get.stdout)
                sha = item.get("sha")
                existing = base64.b64decode(item.get("content", "")).decode("utf-8", errors="replace")
            elif "404" not in (get.stderr + get.stdout):
                errors.append(slug + ": " + (get.stderr or get.stdout or "Could not read checkpoint").strip()[:250])
                break
            sections = re.findall(r"(?ms)^## Conversation: ([^\n]+)\n(.*?)(?=^## Conversation: |\Z)", existing)
            stamp = datetime.now().astimezone().isoformat(timespec="seconds")
            section = "## Conversation: " + conv + "\n_Last updated: " + stamp + "_\n\n" + summary_text
            others = ["## Conversation: " + key + "\n" + body.strip() for key, body in sections if key != conv]
            updated_text = "# Project Conversation Checkpoints\n\n" + section + "\n\n" + "\n\n".join(others[:40]) + "\n"
            payload = {
                "message": "Update ChatGPT checkpoint " + conv + " " + stamp,
                "content": base64.b64encode(updated_text.encode()).decode()
            }
            if sha:
                payload["sha"] = sha
            put = subprocess.run(
                ["gh", "api", "--method", "PUT", f"repos/{slug}/contents/{path}", "--input", "-"],
                input=json.dumps(payload), capture_output=True, text=True, timeout=30
            )
            if put.returncode == 0:
                saved.append({"repository": slug, "path": path})
                wrote = True
                break
            error = (put.stderr or put.stdout or "GitHub checkpoint update failed").strip()
            if "409" not in error and "sha" not in error.lower():
                errors.append(slug + ": " + error[:250])
                break
        if not wrote and not any(slug in item for item in errors):
            errors.append(slug + ": repeated concurrent updates prevented saving")
    if not saved:
        raise RuntimeError("; ".join(errors) or "No project checkpoints were saved.")
    return {"saved": True, "projects": saved, "errors": errors}



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
def expected_extension_origin():
    """Derive the only trusted Chrome extension origin from the pinned manifest key."""
    try:
        manifest_path = Path(__file__).resolve().parent.parent / "extension" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        key = manifest.get("key")
        digest = hashlib.sha256(base64.b64decode(key, validate=True)).digest()[:16]
        alphabet = "abcdefghijklmnop"
        extension_id = "".join(alphabet[b >> 4] + alphabet[b & 15] for b in digest)
        return "chrome-extension://" + extension_id
    except (OSError, ValueError, TypeError, KeyError):
        return ""


def trusted_extension_origin(origin):
    expected = expected_extension_origin()
    return bool(expected) and secrets.compare_digest(str(origin or ""), expected)


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


def run_bounded_command(command, cwd, timeout=120, stdout_limit=20000, stderr_limit=8000):
    """Run a command while retaining only bounded tails of stdout and stderr."""
    process = subprocess.Popen(
        command, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True
    )
    tails = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": max(0, int(stdout_limit)), "stderr": max(0, int(stderr_limit))}

    def drain(name, stream):
        tail = tails[name]
        limit = limits[name]
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            if limit == 0:
                continue
            tail.extend(chunk)
            if len(tail) > limit:
                del tail[:len(tail) - limit]

    readers = [
        threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    try:
        exit_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Kill descendants too; otherwise inherited pipes can keep readers blocked.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        for reader in readers:
            reader.join(timeout=2)
        raise
    for reader in readers:
        reader.join()
    return {
        "exitCode": exit_code,
        "stdout": bytes(tails["stdout"]).decode("utf-8", errors="replace"),
        "stderr": bytes(tails["stderr"]).decode("utf-8", errors="replace"),
    }


def validate_command_arguments(command):
    """Bound command payloads before spawning a local process."""
    if not isinstance(command, list) or not command:
        raise ValueError("command must be a non-empty argument array")
    if len(command) > 40:
        raise ValueError("command may contain at most 40 arguments")
    if not all(isinstance(arg, str) and len(arg) <= 4000 and "\\x00" not in arg for arg in command):
        raise ValueError("each command argument must be a string of at most 4000 characters without NUL bytes")
    return command


def project_path(raw):
    value = str(raw or "").strip()
    if value.startswith("github:"):
        slug = value[len("github:"):].strip().lower()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
            raise ValueError("Invalid GitHub repository path")
        local = local_repo_map().get(slug)
        if not local:
            raise ValueError("This GitHub repository is not cloned locally. Clone it into ~/Projects or ~/Developer before running Mac terminal commands.")
        value = local
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


def status_command(args, cwd=None, timeout=5):
    """Run a best-effort status probe without letting a missing tool or timeout break the API."""
    try:
        result = subprocess.run(args, cwd=str(cwd) if cwd else None,
                                capture_output=True, text=True, timeout=timeout)
        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": 1, "stdout": "", "stderr": str(exc)}


def safe_git_output(args, cwd, timeout=5):
    """Return optional Git metadata without letting a slow/broken Git block context."""
    try:
        result = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def project_context(project):
    if str(project).startswith("github:"):
        # A selected remote repository is already an explicit owner/repo slug.
        # Do not require `gh repo list` to succeed before fetching its context:
        # listing can fail transiently or omit repositories outside the default
        # account scope even while `gh api repos/{owner}/{repo}` still works.
        slug = str(project)[len("github:"):].strip()
        parts = slug.split("/")
        if (len(parts) != 2 or any(part in ("", ".", "..") for part in parts)
                or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts)):
            raise ValueError("Invalid GitHub repository path.")
        return remote_repo_context(slug)
    p = project_path(project)
    parts = [f"PROJECT: {p.name}", f"LOCAL PATH: {p}"]
    remote = safe_git_output(["git", "remote", "get-url", "origin"], p)
    if remote:
        parts.append("GITHUB REMOTE: " + remote)
    branch = safe_git_output(["git", "branch", "--show-current"], p)
    if branch:
        parts.append("BRANCH: " + branch)
    status = safe_git_output(["git", "status", "--short"], p)
    parts.append("WORKING TREE: " + (status or "clean"))
    commit = safe_git_output(["git", "log", "-1", "--oneline"], p)
    if commit:
        parts.append("LATEST COMMIT: " + commit)
    readme = read_text(p / "README.md", 6500)
    if readme:
        parts.append("README SUMMARY SOURCE (README text):\n" + readme)
    memory = read_text(p / "VIBEBRIDGE_CONTEXT.md", 6500)
    if memory:
        parts.append("PERSISTENT PROJECT MEMORY:\n" + memory)
    checkpoint = read_text(p / "memory" / "AUTO_CHECKPOINT.md", 9000)
    # Checkpoints are written to GitHub after each assistant response. For a local
    # checkout, fetch the shared checkpoint so a different ChatGPT conversation
    # receives the latest handoff even when the local file has not been pulled.
    try:
        remote_slug = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=str(p),
            capture_output=True, text=True, timeout=5
        )
        if remote_slug.returncode == 0:
            url = remote_slug.stdout.strip().removesuffix(".git")
            if url.startswith("git@github.com:"):
                slug = url[len("git@github.com:"):]
            elif "github.com/" in url:
                slug = url.split("github.com/", 1)[1]
            else:
                slug = ""
            if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
                # Bound remote checkpoint retrieval and treat it as optional. A slow
                # GitHub API must not delay otherwise usable local project context.
                try:
                    shared = subprocess.run(
                        ["gh", "api", f"repos/{slug}/contents/memory/AUTO_CHECKPOINT.md", "--jq", ".content"],
                        capture_output=True, text=True, timeout=4
                    )
                    if shared.returncode == 0 and shared.stdout.strip():
                        import base64
                        shared_text = base64.b64decode("".join(shared.stdout.split()), validate=True).decode("utf-8", errors="replace").strip()
                        if shared_text:
                            checkpoint = shared_text
                except (OSError, subprocess.TimeoutExpired, ValueError):
                    pass
    except Exception:
        pass
    if checkpoint:
        parts.append("LATEST CROSS-CONVERSATION HANDOFFS AND LIVING TODOS:\n" + checkpoint)
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




def resolve_project_set(message, known_projects=None, active=""):
    """Resolve all explicitly discussed projects plus the projects already established in this conversation."""
    text = str(message or "").lower()
    known = known_projects if isinstance(known_projects, list) else []
    resolved = []
    try:
        repos = github_projects()
    except RuntimeError:
        repos = []
    repos_by_slug = {str(repo.get("nameWithOwner", "")).lower(): repo for repo in repos}

    def add(project):
        if not isinstance(project, dict):
            return
        path = str(project.get("path") or "").strip()
        if not path or any(item["path"].lower() == path.lower() for item in resolved):
            return
        if path.startswith("github:"):
            slug = path[len("github:"):].strip()
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
                return
            normalized_slug = slug.lower()
            repo = repos_by_slug.get(normalized_slug)
            # Preserve a previously selected remote project even if repository
            # discovery is temporarily unavailable. Loading its context still
            # performs authenticated GitHub API calls and reports real failures.
            canonical_slug = repo["nameWithOwner"] if repo else slug
            name = repo["name"] if repo else slug.rsplit("/", 1)[-1]
            item = {"name": name, "path": "github:" + canonical_slug,
                    "repository": canonical_slug, "remote": True}
        else:
            try:
                root = project_path(path)
            except (ValueError, OSError):
                return
            item = {"name": root.name, "path": str(root)}
        resolved.append(item)

    switch_intent = bool(re.search(
        r"\b(?:switch|change|move)\s+(?:the\s+)?(?:project|repo|repository)?\s*(?:to|over\s+to)\b|\bopen\s+(?:the\s+)?(?:repo|repository)\b",
        text
    ))

    # Resolve explicit project mentions first. A switch starts a new project
    # scope; otherwise keep the conversation's known projects for follow-ups.
    # Never inject a global active project alongside explicitly named projects.
    explicit_mentions = []
    # Resolve every connected repository explicitly mentioned, not just the first
    # match. This supports a single message discussing multiple related projects.
    aliases = {
        "autofill-insurance-extension": ("autofill", "insurance extension", "autofill extension"),
        "vibebridge": ("vibebridge", "vibe bridge"),
        "macoptimizer": ("macoptimizer", "mac optimizer"),
    }
    for repo in repos:
        full = str(repo.get("nameWithOwner", "")).lower()
        name = str(repo.get("name", "")).lower()
        normalized = name.replace("_", "-")
        name_pattern = re.escape(normalized).replace(r"\-", r"[-_ ]+")
        full_match = bool(full and re.search(r"(?<![a-z0-9])" + re.escape(full) + r"(?![a-z0-9_.-])", text))
        name_match = bool(name_pattern and re.search(r"(?<![a-z0-9])" + name_pattern + r"(?![a-z0-9])", text))
        alias_match = any(re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", text)
                          for alias in aliases.get(normalized, ()))
        if full_match or name_match or alias_match:
            if repo.get("localPath"):
                add({"name": repo["name"], "path": repo["localPath"]})
            else:
                add({"name": repo["name"], "path": "github:" + repo["nameWithOwner"],
                     "repository": repo["nameWithOwner"], "remote": True})

    if not resolved and active:
        try:
            project, _reason = match_project(message, active)
            if project:
                add(project)
        except (RuntimeError, ValueError):
            pass

    return resolved[:8]

def local_diagnostics():
    """Return a small allowlisted snapshot of VibeBridge services, never raw process arguments or logs."""
    def service_snapshot(label):
        if platform.system() != "Darwin":
            return {"label": label, "loaded": False, "state": "unavailable-on-this-platform", "pid": None}
        try:
            result = subprocess.run(
                ["/bin/launchctl", "print", f"gui/{os.getuid()}/{label}"],
                capture_output=True, text=True, timeout=3
            )
        except (OSError, subprocess.TimeoutExpired):
            return {"label": label, "loaded": False, "state": "query-failed", "pid": None}
        if result.returncode != 0:
            return {"label": label, "loaded": False, "state": "not-loaded", "pid": None}
        state_match = re.search(r"(?m)^\s*state = ([^\r\n]+)", result.stdout)
        pid_match = re.search(r"(?m)^\s*pid = (\d+)", result.stdout)
        return {
            "label": label,
            "loaded": True,
            "state": state_match.group(1).strip() if state_match else "loaded",
            "pid": int(pid_match.group(1)) if pid_match else None,
        }

    agent = service_snapshot("com.vibebridge.agent")
    updater = service_snapshot("com.vibebridge.updater")
    return {
        "ok": True,
        "service": "VibeBridge",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platform": platform.system(),
        "osVersion": platform.mac_ver()[0] if platform.system() == "Darwin" else platform.release(),
        "agent": {**agent, "requestPid": os.getpid(), "port": PORT},
        "updater": updater,
        "scope": "VibeBridge launch services only; no unrelated process names, arguments, environment, or logs are returned.",
    }


def request_pairing(origin):
    """Legacy HTTP token bootstrap is disabled; use Chrome Native Messaging."""
    return 410, {
        "error": "HTTP pairing is disabled. Use the registered VibeBridge Chrome Native Messaging host."
    }


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        origin = self.headers.get("Origin", "")
        if trusted_extension_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        if not trusted_extension_origin(origin):
            return self.send_json(403, {"error": "Registered VibeBridge extension origin required"})
        return self.send_json(200, {"ok": True})

    def authorized(self):
        return secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + TOKEN)

    def require_extension_origin(self):
        """Reject browser-origin requests unless they come from the installed extension."""
        origin = self.headers.get("Origin", "")
        if origin:
            if not trusted_extension_origin(origin):
                self.send_json(403, {"error": "Untrusted browser origin"})
                return False
        return True

    def do_GET(self):
        if not self.require_extension_origin():
            return
        if not self.authorized():
            return self.send_json(401, {"error": "Unauthorized"})
        path = urlparse(self.path).path
        if path == "/health":
            return self.send_json(200, {"ok": True, "service": "VibeBridge", "port": PORT})
        if path == "/diagnostics/local":
            return self.send_json(200, local_diagnostics())
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
            log_names = ("update.log", "updater.log", "updater-error.log", "agent.log", "agent-error.log")
            logs = {}
            for name in log_names:
                try:
                    logs[name] = (SUPPORT / name).read_text(errors="replace").splitlines()[-35:]
                except OSError:
                    logs[name] = []
            deployed_revision = ""
            try:
                deployed_revision = (SUPPORT / "last-synced-revision").read_text(encoding="utf-8").strip()
            except OSError:
                pass
            current = status_command(["git", "rev-parse", "--short", "HEAD"], cwd=ROOTS[2], timeout=5)
            remote = status_command(["git", "ls-remote", "https://github.com/YamaHaroJ/VibeBridge.git", "refs/heads/master"], timeout=12)
            loaded = status_command(["/bin/launchctl", "list", "com.vibebridge.updater"], timeout=5)
            return self.send_json(200, {
                "logs": logs,
                # Archive deployment deliberately leaves Git HEAD unchanged when the
                # checkout has local edits. Report the deployed marker first so the
                # extension can verify the files actually installed, not stale HEAD.
                "currentRevision": (deployed_revision[:12] if deployed_revision else
                                    current.stdout.strip()[:12] if current.returncode == 0 else "unknown"),
                "remoteRevision": remote.stdout.split()[0][:12] if remote.returncode == 0 and remote.stdout.split() else "unavailable",
                "updaterLoaded": loaded.returncode == 0 and "Could not find service" not in loaded.stderr,
            })
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
        path = urlparse(self.path).path
        if path != "/pair" and not self.require_extension_origin():
            return
        if path == "/pair":
            status, payload = request_pairing(self.headers.get("Origin", ""))
            return self.send_json(status, payload)
        if not self.authorized():
            return self.send_json(401, {"error": "Unauthorized"})
        try:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None or not re.fullmatch(r"[0-9]+", raw_length.strip()):
                return self.send_json(400, {"error": "Invalid Content-Length"})
            length = int(raw_length)
            if length > 1024 * 1024:
                return self.send_json(413, {"error": "Request too large"})
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                return self.send_json(400, {"error": "JSON body must be an object"})
        except (ValueError, TypeError, json.JSONDecodeError):
            return self.send_json(400, {"error": "Invalid JSON"})
        except OSError:
            return self.send_json(400, {"error": "Could not read request body"})
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
                force_managed = body.get("forceManaged") is True
                command = [__import__("sys").executable, str(script)]
                if force_managed:
                    command.append("--force-managed")
                subprocess.Popen(
                    command,
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
        if path == "/contexts":
            try:
                projects = resolve_project_set(
                    body.get("message", ""),
                    body.get("projects", []),
                    body.get("active", "")
                )
                if not projects:
                    return self.send_json(200, {"matched": False, "projects": [], "reason": "no-project-match"})
                sections = []
                loaded = []
                errors = []
                for project in projects:
                    try:
                        context = project_context(project["path"])
                        sections.append((project["name"], context))
                        loaded.append(project)
                    except Exception as exc:
                        errors.append(project["name"] + ": " + str(exc)[:250])
                if not loaded:
                    return self.send_json(400, {"error": "; ".join(errors) or "Could not load project context."})
                return self.send_json(200, {
                    "matched": True,
                    "projects": loaded,
                    "context": format_project_context_sections(sections),
                    "errors": errors
                })
            except Exception as e:
                return self.send_json(400, {"error": str(e)})
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
        try:
            cmd = validate_command_arguments(body.get("command", []))
        except ValueError as exc:
            return self.send_json(400, {"error": str(exc)})
        try:
            result = run_bounded_command(cmd, root, timeout=120)
            return self.send_json(200, {"project": str(root), **result})
        except subprocess.TimeoutExpired:
            return self.send_json(408, {"error": "Command timed out"})
        except OSError as e:
            return self.send_json(400, {"error": str(e)})

    def log_message(self, fmt, *args):
        print("VibeBridge:", fmt % args)



# Remote task queue: GitHub Issues are treated as a strict task enum, never as shell input.
# Only issues opened by the repository owner and titled exactly "VibeBridge task: <task>"
# are eligible. Results are posted to the issue and the issue is closed after processing.
REMOTE_TASK_REPO = "YamaHaroJ/VibeBridge"
REMOTE_TASK_OWNER = "YamaHaroJ"
REMOTE_TASKS = {"validate", "test", "diagnostics", "terminal-smoke"}
REMOTE_TASK_POLL_SECONDS = 2
REMOTE_TASK_LIST_ARGS = ["gh", "issue", "list", "--repo", REMOTE_TASK_REPO, "--state", "open", "--json", "number,title,body,author", "--limit", "100"]
_remote_task_seen = set()


def run_remote_task(task):
    """Run one predefined, bounded task; never execute issue text as a command."""
    root = Path.home() / "VibeBridge"
    if task not in REMOTE_TASKS:
        raise ValueError("Unsupported remote task.")
    if task == "validate":
        commands = [
            ["python3", "-m", "py_compile", "agent/server.py", "agent/updater.py"],
            ["python3", "-m", "json.tool", "extension/manifest.json"],
            ["bash", "-n", "agent/install.sh"],
            ["node", "--check", "extension/background.js"],
            ["node", "--check", "extension/chatgpt.js"],
            ["node", "--check", "extension/popup.js"],
        ]
    elif task == "test":
        commands = [["python3", "-m", "unittest", "discover", "-s", "tests", "-v"]]
    elif task == "diagnostics":
        # Diagnostics is a fixed, allowlisted snapshot. Never dump general process
        # arguments or local logs into a GitHub issue.
        return True, "Local VibeBridge service snapshot:\n" + json.dumps(local_diagnostics(), indent=2)
    elif task == "terminal-smoke":
        # Exercise the actual authenticated HTTP /run route with a harmless fixed
        # command. Never return or log the local bearer token.
        import urllib.error
        import urllib.request
        if not root.is_dir():
            raise RuntimeError("Expected checkout is missing: " + str(root))
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        request_body = json.dumps({
            "project": str(root),
            "command": ["python3", "-c", "print('VibeBridge terminal relay OK')"]
        }).encode("utf-8")
        request = urllib.request.Request(
            f"http://{HOST}:{PORT}/run",
            data=request_body,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            return False, "Authenticated local /run smoke test failed: " + str(exc)
        if result.get("exitCode") != 0 or "VibeBridge terminal relay OK" not in result.get("stdout", ""):
            return False, "Local /run route responded, but the harmless command did not pass: " + json.dumps(result)[:2000]
        return True, "Authenticated local /run route PASS\nProject: " + str(result.get("project")) + "\nOutput: " + result["stdout"].strip()
    if not root.is_dir():
        raise RuntimeError("Expected checkout is missing: " + str(root))
    output = []
    success = True
    for command in commands:
        try:
            result = subprocess.run(command, cwd=str(root), capture_output=True, text=True, timeout=45)
            output.append("$ " + " ".join(command) + "\n" +
                          (result.stdout or "")[-7000:] +
                          (("\nSTDERR:\n" + result.stderr[-3000:]) if result.stderr else "") +
                          "\nexit=" + str(result.returncode))
            if result.returncode != 0:
                success = False
                break
        except (OSError, subprocess.TimeoutExpired) as exc:
            output.append("$ " + " ".join(command) + "\nERROR: " + str(exc))
            success = False
            break
    return success, "\n\n".join(output)[-12000:]


def remote_task_worker():
    """Poll authenticated GitHub issue metadata and run only owner-authored enum tasks."""
    while True:
        try:
            listed = subprocess.run(
                REMOTE_TASK_LIST_ARGS,
                capture_output=True, text=True, timeout=8
            )
            if listed.returncode != 0:
                detail = (listed.stderr or listed.stdout or "").strip()
                print("VibeBridge task queue poll failed (exit " + str(listed.returncode) + "): " + detail[:1000], flush=True)
            else:
                issues = json.loads(listed.stdout or "[]")
                for issue in issues:
                    number = issue.get("number")
                    title = str(issue.get("title", ""))
                    author = issue.get("author") or {}
                    login = str(author.get("login", ""))
                    task = title.removeprefix("VibeBridge task: ").strip()
                    if (not isinstance(number, int) or login.lower() != REMOTE_TASK_OWNER.lower()
                            or title != "VibeBridge task: " + task or task not in REMOTE_TASKS
                            or number in _remote_task_seen):
                        continue
                    _remote_task_seen.add(number)
                    ok, detail = run_remote_task(task)
                    state = "PASS" if ok else "FAIL"
                    body = "Mac runner task **" + task + "**: **" + state + "**\n\n" + detail
                    # GitHub CLI uses the authenticated local account; issue content is never evaluated.
                    subprocess.run(
                        ["gh", "issue", "comment", str(number), "--repo", REMOTE_TASK_REPO, "--body", body],
                        capture_output=True, text=True, timeout=10
                    )
                    subprocess.run(
                        ["gh", "issue", "close", str(number), "--repo", REMOTE_TASK_REPO],
                        capture_output=True, text=True, timeout=10
                    )
        except Exception as exc:
            print("VibeBridge remote-task worker:", str(exc)[:500])
        time.sleep(REMOTE_TASK_POLL_SECONDS)


def configure_fast_updates():
    """Configure GitHub polling so Chrome's normal Reload sees recent source updates."""
    plist = Path.home() / "Library/LaunchAgents/com.vibebridge.updater.plist"
    try:
        import plistlib
        if not plist.is_file():
            return
        with plist.open("rb") as handle:
            config = plistlib.load(handle)
        if config.get("StartInterval") == 5:
            return
        config["StartInterval"] = 5
        with plist.open("wb") as handle:
            plistlib.dump(config, handle)
        uid = str(__import__("os").getuid())
        subprocess.run(["/bin/launchctl", "bootout", f"gui/{uid}", str(plist)],
                       capture_output=True, text=True, timeout=10)
        subprocess.run(["/bin/launchctl", "bootstrap", f"gui/{uid}", str(plist)],
                       capture_output=True, text=True, timeout=10)
        print("VibeBridge GitHub updater configured for 5-second polling.")
    except Exception as exc:
        print("Could not configure 5-second GitHub polling:", str(exc)[:300])


def main():
    configure_fast_updates()
    print("VibeBridge listening on http://127.0.0.1:%d" % PORT)
    threading.Thread(target=remote_task_worker, name="vibebridge-remote-tasks", daemon=True).start()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
