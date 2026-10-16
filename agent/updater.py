#!/usr/bin/env python3
"""Safely sync VibeBridge from public master without blocking on unrelated local edits.

The updater preserves a user's local working tree. If the checkout is clean, it
fast-forwards normally. If unrelated files are modified, it updates only the
managed runtime paths (agent/ and extension/) provided those paths have no local
changes. Any conflict or validation failure leaves the local files untouched.
"""
import shutil
import subprocess
import sys
import time
import fcntl
from datetime import datetime
from pathlib import Path

ROOT = Path.home() / "VibeBridge"
SUPPORT = Path.home() / "Library/Application Support/VibeBridge"
LOG = SUPPORT / "update.log"
SYNC_MARKER = SUPPORT / "last-synced-revision"
LOCK_FILE = SUPPORT / "updater.lock"
LABEL = "com.vibebridge.agent"
REMOTE = "https://github.com/YamaHaroJ/VibeBridge.git"
MANAGED_PATHS = ("agent", "extension", "tests")


def log(message):
    SUPPORT.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")


def run(args, timeout=90, check=True):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    output = (result.stdout + "\n" + result.stderr).strip()
    log("$ " + " ".join(args) + f" (exit {result.returncode})" +
        (": " + output[-1800:] if output else ""))
    if check and result.returncode:
        raise RuntimeError(output[-1800:] or f"Command failed: {args[0]}")
    return result.stdout.strip()


def validate():
    # Do not deploy a runtime update unless its regression suite passes first.
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], timeout=120)
    run([sys.executable, "-m", "py_compile", "agent/server.py", "agent/updater.py"])
    run([sys.executable, "-m", "json.tool", "extension/manifest.json"])
    if shutil.which("node"):
        for script in ("extension/background.js", "extension/chatgpt.js", "extension/popup.js"):
            result = subprocess.run([ "node", "--check", script], cwd=ROOT, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError("JavaScript syntax check failed for " + script + ": " +
                                   (result.stderr or result.stdout).strip())
    else:
        log("Node is not installed; JavaScript syntax validation is covered by GitHub Actions.")


def atomic_copy(source, destination):
    """Publish one file atomically so Chrome cannot read a partially copied file."""
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".vibebridge-tmp")
    try:
        shutil.copy2(source, temporary)
        # Same-directory replace is atomic on the same filesystem.
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def sync_extension_tree(source, destination):
    """Update the unpacked extension without ever removing its registered root.

    Chrome stores an unpacked extension's absolute path in its profile. A
    delete-and-recreate update can make Chrome discard that registration if it
    starts during the gap. Each file is now atomically published, with the
    manifest published last, and the root directory is never removed.
    """
    source = Path(source)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)

    source_files = {p.relative_to(source) for p in source.rglob("*") if p.is_file()}
    manifest_rel = Path("manifest.json")
    if manifest_rel not in source_files:
        raise RuntimeError("Staged extension is missing manifest.json.")

    # Publish payload files atomically; retain the old valid manifest meanwhile.
    for rel in sorted(source_files, key=lambda p: str(p)):
        if rel == manifest_rel:
            continue
        atomic_copy(source / rel, destination / rel)

    # The manifest is the commit marker: publish only after every payload file.
    atomic_copy(source / manifest_rel, destination / manifest_rel)

    # Remove obsolete files only after the new manifest is valid and present.
    for path in sorted(destination.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_file() and path.relative_to(destination) not in source_files:
            path.unlink()
        elif path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass


def launch_agent():
    log("Runtime files validated. Restarting local agent.")
    uid = str(__import__("os").getuid())
    result = subprocess.run(["/bin/launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        log("Files updated, but agent restart failed: " + (result.stderr or result.stdout).strip())
        raise RuntimeError("Update validated, but the agent restart failed.")
    log("Update complete. Chrome Reload will load the extension files now on disk.")


def main():
    time.sleep(1)
    log("Automatic GitHub update check started.")
    if not (ROOT / ".git").exists():
        raise RuntimeError("VibeBridge checkout is not a Git repository.")

    # Keep the installed LaunchAgent polling frequently so Chrome's Reload action
    # picks up recently pushed GitHub files without a separate update button.
    plist = Path.home() / "Library/LaunchAgents/com.vibebridge.updater.plist"
    try:
        import plistlib
        if plist.exists():
            with plist.open("rb") as handle:
                config = plistlib.load(handle)
            changed = False
            if config.get("StartInterval") != 5:
                config["StartInterval"] = 5
                changed = True
            if config.get("RunAtLoad") is not True:
                config["RunAtLoad"] = True
                changed = True
            if changed:
                with plist.open("wb") as handle:
                    plistlib.dump(config, handle)
                log("Enabled immediate updater launch and 5-second polling; reloading its LaunchAgent.")
                uid = str(__import__("os").getuid())
                subprocess.run(["/bin/launchctl", "bootout", f"gui/{uid}", str(plist)],
                               capture_output=True, text=True, timeout=10)
                subprocess.run(["/bin/launchctl", "bootstrap", f"gui/{uid}", str(plist)],
                               capture_output=True, text=True, timeout=10)
    except Exception as exc:
        log("Could not adjust updater interval: " + str(exc))

    status = run(["git", "status", "--porcelain"])
    previous = run(["git", "rev-parse", "HEAD"])
    run(["git", "fetch", "--quiet", REMOTE, "master"], timeout=120)
    target = run(["git", "rev-parse", "FETCH_HEAD"])
    synced = SYNC_MARKER.read_text(encoding="utf-8").strip() if SYNC_MARKER.is_file() else ""
    # Archive-syncing a dirty checkout intentionally leaves HEAD behind. Remember
    # the deployed revision to prevent a five-second timer from rewriting files
    # and restarting the agent on every poll.
    if synced == target:
        log("GitHub revision already deployed: " + target[:12] + ". No files changed.")
        return
    if previous == target and not status:
        log("Checkout already at GitHub revision: " + target[:12] + ".")
        SYNC_MARKER.parent.mkdir(parents=True, exist_ok=True)
        SYNC_MARKER.write_text(target + "\n", encoding="utf-8")
        return

    if not status:
        try:
            run(["git", "merge", "--ff-only", target], timeout=120)
            validate()
        except Exception as exc:
            log("Update validation failed; restoring " + previous + ": " + str(exc))
            run(["git", "reset", "--hard", previous], timeout=120)
            raise
        launch_agent()
        SYNC_MARKER.parent.mkdir(parents=True, exist_ok=True)
        SYNC_MARKER.write_text(target + "\n", encoding="utf-8")
        return

    # A dirty checkout should not block delivery of runtime updates if the
    # user's edits are elsewhere. Never overwrite edits within managed paths.
    managed_status = run(["git", "status", "--porcelain", "--", *MANAGED_PATHS])
    if managed_status:
        log("Local runtime files differ from GitHub. The explicit update request will replace agent/ and extension/ with the validated latest release.")
    else:
        log("Unrelated local changes detected; syncing managed runtime paths.")
    stage = ROOT / ".vibebridge-update-stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    try:
        for path in MANAGED_PATHS:
            archive = subprocess.run(["git", "archive", target, path], cwd=ROOT,
                                     capture_output=True, check=True, timeout=90)
            import tarfile
            import io
            with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as tar:
                # Git-created archives contain only repository-relative paths.
                tar.extractall(stage)
        # Validate the staged payload before touching the working files.
        staged_manifest = stage / "extension" / "manifest.json"
        import json
        manifest = json.loads(staged_manifest.read_text(encoding="utf-8"))
        if manifest.get("manifest_version") != 3:
            raise RuntimeError("Staged extension manifest is invalid.")
        if shutil.which("node"):
            for script in ("background.js", "chatgpt.js", "popup.js"):
                check = subprocess.run(["node", "--check", str(stage / "extension" / script)],
                                       capture_output=True, text=True, timeout=30)
                if check.returncode:
                    raise RuntimeError("Staged JavaScript validation failed: " + script + ": " + check.stderr)
        import py_compile
        for script in ("server.py", "updater.py"):
            py_compile.compile(str(stage / "agent" / script), doraise=True)

        # Backup runtime paths, replace from staged archive, and roll back on failure.
        backup = ROOT / ".vibebridge-update-backup"
        if backup.exists():
            shutil.rmtree(backup)
        backup.mkdir()
        for path in MANAGED_PATHS:
            source = ROOT / path
            if source.exists():
                shutil.copytree(source, backup / path)
        try:
            for path in MANAGED_PATHS:
                destination = ROOT / path
                if path == "extension":
                    sync_extension_tree(stage / path, destination)
                else:
                    if destination.exists():
                        shutil.rmtree(destination)
                    shutil.copytree(stage / path, destination)
            validate()
        except Exception:
            for path in MANAGED_PATHS:
                destination = ROOT / path
                saved = backup / path
                if path == "extension" and saved.exists():
                    sync_extension_tree(saved, destination)
                else:
                    if destination.exists():
                        shutil.rmtree(destination)
                    if saved.exists():
                        shutil.copytree(saved, destination)
            raise
        log("Managed runtime files updated from GitHub; unrelated local edits were preserved.")
        launch_agent()
        SYNC_MARKER.parent.mkdir(parents=True, exist_ok=True)
        SYNC_MARKER.write_text(target + "\n", encoding="utf-8")
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        shutil.rmtree(ROOT / ".vibebridge-update-backup", ignore_errors=True)


if __name__ == "__main__":
    try:
        SUPPORT.mkdir(parents=True, exist_ok=True)
        with LOCK_FILE.open("w", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                sys.exit(0)
            main()
    except Exception as exc:
        log("UPDATE FAILED: " + str(exc))
        sys.exit(1)
