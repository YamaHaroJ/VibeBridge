#!/usr/bin/env python3
"""Install the latest published VibeBridge release safely.

The hourly LaunchAgent and the popup's manual update action use this script.
Only versioned GitHub Releases are installed; master preview builds are ignored.
"""
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


def log(message):
    SUPPORT.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")


def run(args, timeout=90, check=True):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    output = (result.stdout + "\n" + result.stderr).strip()
    log("$ " + " ".join(args) + f" (exit {result.returncode})" +
        (": " + output[-2000:] if output else ""))
    if check and result.returncode:
        raise RuntimeError(output[-2000:] or f"Command failed: {args[0]}")
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
        log("Node is not installed locally; GitHub Actions covers JavaScript syntax.")


def main():
    time.sleep(1)
    log("Stable release update check started.")
    if not (ROOT / ".git").exists():
        raise RuntimeError("VibeBridge checkout is not a Git repository.")
    if run(["git", "status", "--porcelain"]):
        raise RuntimeError("Update stopped because local changes exist. Nothing was overwritten.")

    latest = run(["gh", "release", "view", "--repo", "YamaHaroJ/VibeBridge",
                  "--json", "tagName", "--jq", ".tagName"], timeout=45, check=False)
    if not latest or "not found" in latest.lower() or "HTTP 404" in latest:
        raise RuntimeError("No published VibeBridge release was found, or GitHub CLI could not reach GitHub.")
    current = run(["git", "rev-parse", "HEAD"])
    run(["git", "fetch", "origin", "tag", latest], timeout=120)
    target = run(["git", "rev-parse", latest + "^{commit}"])
    if target == current:
        log("Already running the latest published release " + latest + ".")
        return

    try:
        run(["git", "checkout", "--detach", latest], timeout=120)
        validate()
    except Exception as exc:
        log("Release validation failed; restoring " + current + ": " + str(exc))
        run(["git", "checkout", "--detach", current], timeout=120)
        raise

    log("Release " + latest + " validated. Restarting local agent.")
    uid = str(__import__("os").getuid())
    result = subprocess.run(["/bin/launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        log("Release installed, but agent restart failed: " + (result.stderr or result.stdout).strip())
        raise RuntimeError("Release installed and validated, but the agent restart failed.")
    log("Update complete: installed " + latest + ". Chrome may require extension reload unless installed from Chrome Web Store.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log("UPDATE FAILED: " + str(exc))
        sys.exit(1)
