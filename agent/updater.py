#!/usr/bin/env python3
"""Check GitHub's public master branch for updates and safely restart VibeBridge."""
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path.home() / "VibeBridge"
SUPPORT = Path.home() / "Library/Application Support/VibeBridge"
LOG = SUPPORT / "update.log"
LABEL = "com.vibebridge.agent"
REMOTE = "https://github.com/YamaHaroJ/VibeBridge.git"


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
    run([sys.executable, "-m", "py_compile", "agent/server.py", "agent/updater.py"])
    run([sys.executable, "-m", "json.tool", "extension/manifest.json"])
    if shutil.which("node"):
        for script in ("extension/background.js", "extension/chatgpt.js", "extension/popup.js"):
            result = subprocess.run(["node", "--check", script], cwd=ROOT, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError("JavaScript syntax check failed for " + script + ": " +
                                   (result.stderr or result.stdout).strip())
    else:
        log("Node is not installed; JavaScript syntax validation is covered by GitHub Actions.")


def main():
    time.sleep(1)
    log("Automatic update check started.")
    if not (ROOT / ".git").exists():
        raise RuntimeError("VibeBridge checkout is not a Git repository.")
    if run(["git", "status", "--porcelain"]):
        raise RuntimeError("Update paused because local changes exist. Nothing was overwritten.")
    previous = run(["git", "rev-parse", "HEAD"])
    run(["git", "fetch", "--quiet", REMOTE, "master"], timeout=120)
    target = run(["git", "rev-parse", "FETCH_HEAD"])
    if previous == target:
        log("Already up to date.")
        return
    try:
        run(["git", "merge", "--ff-only", target], timeout=120)
        validate()
    except Exception as exc:
        log("Update validation failed; restoring " + previous + ": " + str(exc))
        run(["git", "reset", "--hard", previous], timeout=120)
        raise
    log("Update validated. Restarting local agent.")
    uid = str(__import__("os").getuid())
    result = subprocess.run(["/bin/launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        log("Files updated, but agent restart failed: " + (result.stderr or result.stdout).strip())
        raise RuntimeError("Update validated, but the agent restart failed.")
    log("Update complete. Chrome may need an extension reload until Chrome Web Store distribution is available.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log("UPDATE FAILED: " + str(exc))
        sys.exit(1)
