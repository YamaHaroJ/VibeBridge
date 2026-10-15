#!/bin/bash
set -euo pipefail
ROOT="$HOME/VibeBridge"
SUPPORT="$HOME/Library/Application Support/VibeBridge"
PLIST="$HOME/Library/LaunchAgents/com.vibebridge.agent.plist"
mkdir -p "$SUPPORT" "$HOME/Library/LaunchAgents"
if ! command -v python3 >/dev/null 2>&1; then echo "ERROR: Python 3 is required."; exit 1; fi
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,9) else 1)' || { echo "ERROR: Python 3.9 or newer is required."; exit 1; }
if [ ! -f "$SUPPORT/token" ]; then
  python3 -c 'import secrets,pathlib; p=pathlib.Path.home()/"Library/Application Support/VibeBridge/token"; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(secrets.token_urlsafe(32)); p.chmod(0o600)'
fi
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.vibebridge.agent</string>
<key>ProgramArguments</key><array><string>/usr/bin/python3</string><string>$ROOT/agent/server.py</string></array>
<key>WorkingDirectory</key><string>$ROOT</string>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
<key>StandardOutPath</key><string>$SUPPORT/agent.log</string>
<key>StandardErrorPath</key><string>$SUPPORT/agent-error.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo
echo "VibeBridge agent installed and launched."
echo "Your local token (keep private):"
cat "$SUPPORT/token"
echo
echo "Health check:"
curl -sS -H "Authorization: Bearer $(cat "$SUPPORT/token")" http://127.0.0.1:43127/health
echo
echo "Next: open chrome://extensions, enable Developer mode, click Load unpacked, select $ROOT/extension"
