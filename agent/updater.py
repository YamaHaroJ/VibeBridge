#!/usr/bin/env python3
"""Safely update the local VibeBridge checkout and restart its LaunchAgent.

Only updates a clean checkout. Logs progress to Application Support so the
extension can show status even if the agent restarts during the update.
"""
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path.home() / "VibeBridge"
SUPPORT = Path.home() / "Library/Application Support/VibeBridge"
LOG = SUPPORT / "update.log"
PLIST = Path.home() / "Library/LaunchAgents/com.vibebridge.agent.plist"
LABEL = "com.vibebridge.agent"


def log(message):
    SUPPORT.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")


def run(args, timeout=90):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    output = (result.stdout + "\n" + result.stderr).strip()
    log("$ " + " ".join(args) + f" (exit {result.returncode})" + (": " + output[-2500:] if output else ""))
    if result.returncode:
        raise RuntimeError(output[-2500:] or f"Command failed: {args[0]}")
    return result.stdout.strip()


def main():
    time.sleep(1)
    log("Update started.")
    if not (ROOT / ".git").exists():
        raise RuntimeError("VibeBridge checkout is not a Git repository.")
    dirty = run(["git", "status", "--porcelain"])
    if dirty:
        raise RuntimeError("Update stopped: local changes exist. Nothing was overwritten. Resolve or commit local changes before updating.")
    previous = run(["git", "rev-parse", "HEAD"])
    run(["git", "fetch", "origin", "master"], timeout=120)
    run(["git", "merge", "--ff-only", "origin/master"], timeout=120)
    try:
        run([sys.executable, "-m", "py_compile", "agent/server.py"])
        run([sys.executable, "-m", "json.tool", "extension/manifest.json"])
        if shutil.which("node"):
            for script in ("extension/background.js", "extension/chatgpt.js", "extension/popup.js"):
                check = subprocess.run(["node", "--check", script], cwd=ROOT, capture_output=True, text=True)
                if check.returncode:
                    raise RuntimeError("JavaScript syntax check failed for " + script + ": " + (check.stderr or check.stdout).strip())
        else:
            log("Node is not installed locally; JavaScript syntax is covered by GitHub Actions.")
    except Exception as exc:
        log("Validation failed; rolling back to " + previous + ": " + str(exc))
        run(["git", "reset", "--hard", previous])
        raise
    log("Validation passed. Restarting local agent.")
    uid = str(__import__("os").getuid())
    # The LaunchAgent remains responsible for starting the service after kickstart.
    result = subprocess.run(["/bin/launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"], capture_output=True, text=True, timeout=30)
    if result.returncode:
        log("Update files validated, but agent restart failed: " + (result.stderr or result.stdout).strip())
        raise RuntimeError("Update files installed and validated, but the agent restart failed. " + (result.stderr or result.stdout).strip())
    log("Update complete. Agent restart requested.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log("UPDATE FAILED: " + str(exc))
