import base64
import hashlib
import json
import os
import platform
import re
import secrets
import signal
import shutil
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
BROWSER_STATUS_LOCK = threading.Lock()
BROWSER_STATUS = {"connected": False, "version": None, "host": None, "lastSeen": None, "tabs": {}}


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
    projects = discover_projects()
    if not projects:
        return {}

    def repo_remote(project):
        try:
            remote = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=project["path"], capture_output=True, text=True, timeout=5
            )
            if remote.returncode != 0:
                return None
            url = remote.stdout.strip().removesuffix(".git")
            if url.startswith("git@github.com:"):
                slug = url[len("git@github.com:"):]
            elif "github.com/" in url:
                slug = url.split("github.com/", 1)[1]
            else:
                return None
            return (slug.lower(), project["path"]) if slug else None
        except (OSError, subprocess.SubprocessError):
            return None

    # Repo probes are independent. Bound concurrency to keep repository discovery
    # responsive without launching one worker per checkout.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(8, len(projects)),
                            thread_name_prefix="vibebridge-repo-map") as pool:
        results = pool.map(repo_remote, projects)
        return {slug: path for item in results if item for slug, path in [item]}


_github_projects_cache = {"expires": 0.0, "value": None}
_github_projects_cache_lock = threading.Lock()


def github_projects():
    # Context resolution can run for every message. Avoid spawning gh and walking
    # every local repository on each request; refresh in the background window.
    now = time.monotonic()
    cached = _github_projects_cache["value"]
    if cached is not None and now < _github_projects_cache["expires"]:
        return [dict(repo) for repo in cached]

    with _github_projects_cache_lock:
        now = time.monotonic()
        cached = _github_projects_cache["value"]
        if cached is not None and now < _github_projects_cache["expires"]:
            return [dict(repo) for repo in cached]
        try:
            result = subprocess.run(
                ["gh", "repo", "list", "--limit", "1000", "--json",
                 "name,nameWithOwner,description,url,isPrivate,isArchived,updatedAt,defaultBranchRef"],
                capture_output=True, text=True, timeout=20
            )
        except FileNotFoundError:
            raise RuntimeError("GitHub CLI (gh) is not installed. Install GitHub CLI and sign in first.")
        except subprocess.TimeoutExpired:
            # If GitHub is momentarily slow, retain a previously successful cache.
            if cached is not None:
                return [dict(repo) for repo in cached]
            raise RuntimeError("GitHub repository listing timed out. Try again.")
        if result.returncode != 0:
            if cached is not None:
                return [dict(repo) for repo in cached]
            message = (result.stderr or result.stdout or "GitHub CLI could not list repositories").strip()
            raise RuntimeError(message[:1000])
        try:
            repositories = json.loads(result.stdout)
        except json.JSONDecodeError:
            if cached is not None:
                return [dict(repo) for repo in cached]
            raise RuntimeError("GitHub CLI returned an unreadable repository list.")
        local = local_repo_map()
        for repo in repositories:
            repo["localPath"] = local.get(str(repo.get("nameWithOwner", "")).lower())
        repositories.sort(key=lambda item: (item.get("nameWithOwner", "").lower()))
        _github_projects_cache["value"] = repositories
        _github_projects_cache["expires"] = time.monotonic() + 30
        return [dict(repo) for repo in repositories]


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

    def fetch_file(filename):
        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{slug}/contents/{filename}", "--jq", ".content"],
                capture_output=True, text=True, timeout=20
            )
            return filename, result, None
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return filename, None, exc

    # README naming is a convention, not a guarantee — plenty of real repos use
    # README.txt or no extension at all. A missing README.md specifically must
    # never be treated as fatal; try the common alternates before giving up.
    README_CANDIDATES = ("README.md", "README.txt", "README", "Readme.md")

    def fetch_readme():
        for filename in README_CANDIDATES:
            name, result, error = fetch_file(filename)
            if isinstance(error, FileNotFoundError):
                return name, result, error
            if isinstance(error, subprocess.TimeoutExpired):
                return name, result, error
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip()
                if "404" in detail or "Not Found" in detail:
                    continue  # try the next candidate name
                return name, result, error
            if result.stdout.strip():
                return name, result, error
        return None, None, None

    # README lookup (which may try several names sequentially) and the
    # VibeBridge memory lookup are independent; run them concurrently so total
    # wait is bounded by the slower of the two, not their sum.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="vibebridge-remote-context") as pool:
        readme_future = pool.submit(fetch_readme)
        memory_future = pool.submit(fetch_file, "VIBEBRIDGE_CONTEXT.md")
        results = [readme_future.result(), memory_future.result()]

    for filename, result, error in results:
        if filename is None:
            continue  # fetch_readme found no candidate at all; not an error
        if isinstance(error, FileNotFoundError):
            raise RuntimeError("GitHub CLI (gh) is not installed, so remote project context cannot be loaded.")
        if isinstance(error, subprocess.TimeoutExpired):
            errors.append(f"{filename}: GitHub request timed out")
            continue
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "GitHub API request failed").strip()
            if "404" in detail or "Not Found" in detail:
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
        if errors:
            # A real failure (auth, timeout, GitHub API error) is still fatal —
            # only a clean "no file by any common name" degrades gracefully.
            raise RuntimeError(f"Could not load useful context from GitHub repository {slug}. " + "; ".join(errors))
        # A repository with no README and no VibeBridge memory file is still a
        # real, nameable project — surface that plainly instead of failing the
        # whole context lookup and leaving ChatGPT with nothing at all.
        parts.append("No README or VibeBridge memory file was found in this repository. "
                      "Context is limited to the repository identity above.")
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


def redact_checkpoint_text(value):
    """Remove common credentials before any checkpoint content is written to GitHub."""
    text = str(value or "")
    patterns = [
        (r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", "[REDACTED BEARER TOKEN]"),
        (r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b", "[REDACTED API KEY]"),
        (r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b", "[REDACTED GITHUB TOKEN]"),
        (r"(?i)\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|password|client[_ -]?secret)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]"),
        (r"(?i)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "[REDACTED PRIVATE KEY]"),
    ]
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.DOTALL if "PRIVATE KEY" in pattern else 0)
    return text


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
        summary_text = redact_checkpoint_text("\n\n".join(sections)).strip()[:9000]
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
            # Keep an evolving build timeline for this conversation. The new
            # summary/handoff is authoritative, while recent project-building
            # steps remain visible instead of being overwritten each turn.
            previous_body = next((body for key, body in sections if key == conv), "")
            history_match = re.search(r"(?ms)^### Recent project-building history\n(.*?)(?=^### |\Z)", previous_body)
            history = []
            if history_match:
                history = [line for line in history_match.group(1).splitlines() if line.strip().startswith("- ")]
            # Make retries idempotent: if the durable checkpoint content is
            # unchanged, do not create another GitHub commit just to refresh a
            # timestamp. Compare only the stable body, excluding generated history.
            existing_core = re.sub(
                r"(?ms)^### Recent project-building history\n.*$",
                "",
                re.sub(r"(?m)^_Last updated: .*_\n?", "", previous_body),
            ).strip()
            if existing_core == summary_text.strip():
                saved.append({"repository": slug, "path": path, "unchanged": True})
                wrote = True
                break
            if handoff:
                compact_handoff = redact_checkpoint_text(re.sub(r"\s+", " ", handoff).strip())[:1200]
                # Streaming retries or repeated assistant blocks must not append
                # the exact same handoff multiple times to the rolling timeline.
                if not any(line.split("] ", 1)[-1] == compact_handoff for line in history):
                    history.append("- [" + stamp + "] " + compact_handoff)
            history = history[-8:]
            summary_text += "\n\n### Recent project-building history\n" + "\n".join(history)
            summary_text = summary_text[:9000]
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


def _build_project_context(project):
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
    # These Git probes are independent. Run them concurrently so context
    # latency is closer to the slowest probe, not the sum of all four.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="vibebridge-git-probe") as pool:
        remote_future = pool.submit(safe_git_output, ["git", "remote", "get-url", "origin"], p)
        branch_future = pool.submit(safe_git_output, ["git", "branch", "--show-current"], p)
        status_future = pool.submit(safe_git_output, ["git", "status", "--short"], p)
        commit_future = pool.submit(safe_git_output, ["git", "log", "-1", "--oneline"], p)
        remote = remote_future.result()
        branch = branch_future.result()
        status = status_future.result()
        commit = commit_future.result()
    if remote:
        parts.append("GITHUB REMOTE: " + remote)
    if branch:
        parts.append("BRANCH: " + branch)
    parts.append("WORKING TREE: " + (status or "clean"))
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
        if remote:
            url = remote.strip().removesuffix(".git")
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


# Cache assembled context briefly: ChatGPT can trigger multiple overlapping
# context lookups for the same project while a message is being composed.
# A five-second TTL avoids repeated Git/gh subprocesses during one interaction
# while keeping local edits visible quickly. Cache is bounded and guarded for concurrent HTTP threads.
_CONTEXT_CACHE_TTL = 5.0
_CONTEXT_CACHE_MAX = 64
_context_cache = {}
_context_cache_lock = threading.Lock()
_context_build_locks = {}


def project_context(project):
    key = str(project)
    now = time.monotonic()
    with _context_cache_lock:
        cached = _context_cache.get(key)
        if cached and now - cached[0] < _CONTEXT_CACHE_TTL:
            return cached[1]
        if cached:
            _context_cache.pop(key, None)
        build_lock = _context_build_locks.setdefault(key, threading.Lock())

    # Coalesce simultaneous requests for the same project into one context build.
    # Waiting requests reuse the freshly built result instead of spawning duplicate
    # Git and GitHub CLI subprocesses.
    with build_lock:
        now = time.monotonic()
        with _context_cache_lock:
            cached = _context_cache.get(key)
            if cached and now - cached[0] < _CONTEXT_CACHE_TTL:
                return cached[1]

        context = _build_project_context(project)
        with _context_cache_lock:
            _context_cache[key] = (time.monotonic(), context)
            if len(_context_cache) > _CONTEXT_CACHE_MAX:
                oldest = min(_context_cache, key=lambda item: _context_cache[item][0])
                _context_cache.pop(oldest, None)
                _context_build_locks.pop(oldest, None)
            if len(_context_build_locks) > _CONTEXT_CACHE_MAX:
                for stale_key in list(_context_build_locks):
                    if stale_key not in _context_cache and stale_key != key:
                        _context_build_locks.pop(stale_key, None)
        return context


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
        if not path:
            return

        # A local checkout and its GitHub slug are the same project identity.
        # Normalize known remote aliases to the local checkout before de-duplication
        # so one message never injects the same README/memory twice (once locally
        # and again as a remote repository context).
        if path.startswith("github:"):
            slug = path[len("github:"):].strip()
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
                return
            repo = repos_by_slug.get(slug.lower())
            if repo and repo.get("localPath"):
                path = str(repo["localPath"]).strip()
                project = {**project, "name": repo.get("name") or slug.rsplit("/", 1)[-1], "path": path}

        if any(item["path"].lower() == path.lower() for item in resolved):
            return
        if path.startswith("github:"):
            slug = path[len("github:"):].strip()
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
    local_projects = discover_projects()
    for item in local_projects:
        name = str(item.get("name", "")).lower()
        if name and re.search(r"(?<![a-z0-9])" + re.escape(name).replace(r"\-", r"[-_ ]+") + r"(?![a-z0-9])", text):
            explicit_mentions.append(item)
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
                explicit_mentions.append({"name": repo["name"], "path": repo["localPath"]})
            else:
                explicit_mentions.append({"name": name, "path": "github:" + full, "repository": full, "remote": True})

    if switch_intent:
        # A switch starts a clean project scope and never carries stale context.
        for project in explicit_mentions:
            add(project)
        if not explicit_mentions:
            return []
    else:
        # Preserve conversation continuity while adding all projects named now.
        # When this message explicitly names a project, omit the global active
        # project unless it was already part of this conversation's known set.
        for value in known[:8]:
            add(value if isinstance(value, dict) else {"path": value})
        if not explicit_mentions and not resolved and active:
            add({"path": active})
        for project in explicit_mentions:
            add(project)

    local_projects = discover_projects()
    for item in local_projects:
        name = str(item.get("name", "")).lower()
        if name and re.search(r"(?<![a-z0-9])" + re.escape(name).replace(r"\-", r"[-_ ]+") + r"(?![a-z0-9])", text):
            add(item)

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

def browser_extension_snapshot():
    now = datetime.now(timezone.utc)
    with BROWSER_STATUS_LOCK:
        tabs = BROWSER_STATUS.get("tabs", {})
        recent = []
        for tab_id, item in list(tabs.items()):
            try:
                seen = datetime.fromisoformat(item["lastSeen"])
                if seen.tzinfo is None:
                    seen = seen.replace(tzinfo=timezone.utc)
                age = (now - seen).total_seconds()
            except (KeyError, TypeError, ValueError):
                age = float("inf")
            if age <= 120:
                recent.append({**item, "tabId": tab_id, "ageSeconds": max(0, int(age))})
        snapshot = {key: value for key, value in BROWSER_STATUS.items() if key != "tabs"}
        snapshot["tabs"] = recent
        snapshot["activeTabCount"] = len(recent)
        return snapshot


def local_diagnostics():
    """Return allowlisted VibeBridge service and deployment metadata, never logs or process arguments."""
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
    # A StartInterval LaunchAgent is normally idle between invocations. Report
    # its schedule and the last safe status line so "not running" is not mistaken
    # for a dead updater, without exposing arbitrary logs or environment values.
    updater_schedule = {"plistPresent": False, "runAtLoad": None, "startIntervalSeconds": None}
    updater_log_status = {"present": False, "lastLine": None}
    try:
        import plistlib
        updater_plist = Path.home() / "Library/LaunchAgents/com.vibebridge.updater.plist"
        if updater_plist.is_file():
            with updater_plist.open("rb") as handle:
                config = plistlib.load(handle)
            updater_schedule = {
                "plistPresent": True,
                "runAtLoad": config.get("RunAtLoad") is True,
                "startIntervalSeconds": config.get("StartInterval") if isinstance(config.get("StartInterval"), int) else None,
            }
        update_log = Path.home() / "Library/Application Support/VibeBridge/update.log"
        if update_log.is_file():
            lines = update_log.read_text(encoding="utf-8", errors="replace").splitlines()
            safe_lines = [line for line in lines[-200:] if any(term in line.lower() for term in (
                "automatic github update check started", "github revision already deployed",
                "checkout and deployed runtime already", "update complete", "could not adjust updater interval",
                "could not verify deployed extension manifest", "runtime files validated",
                "restart failed", "traceback", "error", "exception"
            ))]
            updater_log_status = {"present": True, "lastLine": safe_lines[-1][-240:] if safe_lines else None}
    except (OSError, ValueError, TypeError, ImportError):
        pass
    checkout = Path.home() / "VibeBridge"
    revision, dirty, extension_version = "unknown", None, "unknown"
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(checkout),
            capture_output=True, text=True, timeout=4
        )
        if head.returncode == 0:
            revision = head.stdout.strip()[:16] or "unknown"
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=str(checkout),
            capture_output=True, text=True, timeout=4
        )
        if status.returncode == 0:
            dirty = bool(status.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        manifest = json.loads((checkout / "extension" / "manifest.json").read_text(encoding="utf-8"))
        extension_version = str(manifest.get("version", "unknown"))[:40]
    except (OSError, ValueError, TypeError):
        pass
    return {
        "ok": True,
        "service": "VibeBridge",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platform": platform.system(),
        "osVersion": platform.mac_ver()[0] if platform.system() == "Darwin" else platform.release(),
        "agent": {**agent, "requestPid": os.getpid(), "port": PORT},
        "updater": {**updater, "schedule": updater_schedule, "logStatus": updater_log_status},
        "checkout": {"path": str(checkout), "revision": revision, "dirty": dirty,
                     "extensionVersion": extension_version},
        "browserExtension": browser_extension_snapshot(),
        "scope": "VibeBridge services and checkout metadata only; no file paths from status, unrelated processes, arguments, environment, secrets, or logs are returned.",
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
        if path == "/extension-status":
            version = str(body.get("version", "")).strip()[:40]
            host = str(body.get("host", "")).strip().lower()
            if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", version):
                return self.send_json(400, {"error": "Invalid extension version"})
            if host not in {"chatgpt.com", "chat.openai.com"}:
                return self.send_json(400, {"error": "Unrecognized ChatGPT host"})
            tab_id = body.get("tabId")
            if tab_id is not None and (not isinstance(tab_id, int) or isinstance(tab_id, bool) or tab_id < 0):
                return self.send_json(400, {"error": "Invalid browser tab ID"})
            seen = datetime.now(timezone.utc).isoformat(timespec="seconds")
            with BROWSER_STATUS_LOCK:
                BROWSER_STATUS.update({"connected": True, "version": version, "host": host, "lastSeen": seen})
                # Older already-loaded extension workers omit tabId. Preserve their
                # service heartbeat while only counting tabs reported by new code.
                if tab_id is not None:
                    tabs = BROWSER_STATUS.setdefault("tabs", {})
                    tabs[tab_id] = {"version": version, "host": host, "lastSeen": seen}
                    if len(tabs) > 200:
                        ordered = sorted(tabs.items(), key=lambda pair: pair[1].get("lastSeen", ""), reverse=True)
                        BROWSER_STATUS["tabs"] = dict(ordered[:200])
            return self.send_json(200, {"ok": True})
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
                # Always launch the stable bootstrap outside the checkout. If we
                # launch Path(__file__).with_name("updater.py"), an outdated
                # server can keep invoking the outdated updater and cannot repair
                # either itself or its LaunchAgent configuration.
                bootstrap = SUPPORT / "updater-bootstrap.py"
                legacy = Path(__file__).with_name("updater.py")
                if not bootstrap.is_file():
                    # Compatibility fallback: let the legacy updater attempt
                    # to bootstrap itself. Record this state instead of silently
                    # pretending the stable path is active.
                    script = legacy
                else:
                    script = bootstrap
                if not script.is_file():
                    return self.send_json(501, {"error": "No updater bootstrap or legacy updater is installed."})
                log_file = SUPPORT / "update.log"
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with log_file.open("a", encoding="utf-8") as handle:
                    handle.write("\n[" + __import__("datetime").datetime.now().isoformat(timespec="seconds") + "] Update requested from extension; launcher=" + str(script) + ".\n")
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
                return self.send_json(202, {"started": True, "launcher": str(script), "message": "Update started. Check Update status in a few seconds."})
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
                # Load independent project contexts concurrently instead of serially.
                # Preserve the original project order in the response.
                from concurrent.futures import ThreadPoolExecutor
                def load_one(project):
                    try:
                        return project, project_context(project["path"]), None
                    except Exception as exc:
                        return project, None, str(exc)[:250]
                with ThreadPoolExecutor(max_workers=min(8, max(1, len(projects))),
                                         thread_name_prefix="vibebridge-context") as pool:
                    results = list(pool.map(load_one, projects))
                sections = []
                loaded = []
                errors = []
                for project, context, error in results:
                    if error is not None:
                        errors.append(project["name"] + ": " + error)
                        continue
                    sections.append((project["name"], context))
                    loaded.append(project)
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
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
