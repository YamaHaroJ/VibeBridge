#!/bin/bash
set -euo pipefail
umask 077
ROOT="$HOME/VibeBridge"
PYTHON="$(command -v python3 || true)"
SUPPORT="$HOME/Library/Application Support/VibeBridge"
PLIST="$HOME/Library/LaunchAgents/com.vibebridge.agent.plist"
UPDATER_PLIST="$HOME/Library/LaunchAgents/com.vibebridge.updater.plist"
mkdir -p "$SUPPORT" "$HOME/Library/LaunchAgents"
if [ -z "$PYTHON" ]; then echo "ERROR: Python 3 is required."; exit 1; fi
"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,9) else 1)' || { echo "ERROR: Python 3.9 or newer is required."; exit 1; }
if [ ! -f "$SUPPORT/token" ]; then
  "$PYTHON" -c 'import secrets,pathlib; p=pathlib.Path.home()/"Library/Application Support/VibeBridge/token"; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(secrets.token_urlsafe(32))'
fi
chmod 600 "$SUPPORT/token"
chmod 700 "$SUPPORT"
cat > "$PLIST" <<EOF_PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.vibebridge.agent</string>
<key>ProgramArguments</key><array><string>$PYTHON</string><string>$ROOT/agent/server.py</string></array>
<key>WorkingDirectory</key><string>$ROOT</string>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
<key>StandardOutPath</key><string>$SUPPORT/agent.log</string>
<key>StandardErrorPath</key><string>$SUPPORT/agent-error.log</string>
</dict></plist>
EOF_PLIST
cat > "$UPDATER_PLIST" <<EOF_UPDATER
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.vibebridge.updater</string>
<key>ProgramArguments</key><array><string>$PYTHON</string><string>$ROOT/agent/updater.py</string></array>
<key>WorkingDirectory</key><string>$ROOT</string>
<key>StartInterval</key><integer>3600</integer>
<key>RunAtLoad</key><true/>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
<key>StandardOutPath</key><string>$SUPPORT/updater.log</string>
<key>StandardErrorPath</key><string>$SUPPORT/updater-error.log</string>
</dict></plist>
EOF_UPDATER
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/com.vibebridge.agent"
launchctl bootout "gui/$(id -u)" "$UPDATER_PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$UPDATER_PLIST"
echo
echo "VibeBridge agent installed and launched."
echo "Stable-release updater installed (checks hourly)."
echo "Private local token created with owner-only permissions; the extension pairs securely during first-run setup."
echo "Logs are stored under: $SUPPORT"
echo "Update logs: update.log; agent logs: agent.log and agent-error.log; updater launch logs: updater.log and updater-error.log"
echo
echo "Health check:"
curl -sS -H "Authorization: Bearer $(cat "$SUPPORT/token")" http://127.0.0.1:43127/health
echo
echo "Next: open chrome://extensions, enable Developer mode, click Load unpacked, select $ROOT/extension"
