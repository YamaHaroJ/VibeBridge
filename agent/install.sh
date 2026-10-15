#!/bin/bash
set -euo pipefail
umask 077
ROOT="$HOME/VibeBridge"
PYTHON="$(command -v python3 || true)"
SUPPORT="$HOME/Library/Application Support/VibeBridge"
PLIST="$HOME/Library/LaunchAgents/com.vibebridge.agent.plist"
UPDATER_PLIST="$HOME/Library/LaunchAgents/com.vibebridge.updater.plist"
NATIVE_HOST_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
NATIVE_HOST_MANIFEST="$NATIVE_HOST_DIR/com.vibebridge.agent.json"
# Chrome extension ID (derived from the pinned public key in extension/manifest.json).
EXTENSION_ID="meedpihcbldnlcahpeijakginpjdkghp"
mkdir -p "$SUPPORT" "$HOME/Library/LaunchAgents"
if [ -z "$PYTHON" ]; then echo "ERROR: Python 3 is required."; exit 1; fi
if [ ! -f "$ROOT/agent/native_host.py" ]; then
  echo "ERROR: Native Messaging host script is missing: $ROOT/agent/native_host.py"
  echo "Update the VibeBridge checkout, then rerun this installer."
  exit 1
fi
if [ ! -f "$ROOT/extension/manifest.json" ] || [ ! -f "$ROOT/extension/popup.html" ]; then
  echo "ERROR: Chrome extension files are missing from $ROOT/extension."
  echo "The extension must be loaded from this stable folder, not from agent/ or a temporary download."
  exit 1
fi
EXTENSION_ID_FROM_MANIFEST="$("$PYTHON" -c 'import json,pathlib; m=json.loads(pathlib.Path("'"$ROOT"'/extension/manifest.json").read_text()); print(m.get("key",""))' 2>/dev/null || true)"
if [ -z "$EXTENSION_ID_FROM_MANIFEST" ]; then
  echo "ERROR: extension/manifest.json has no stable extension key."
  exit 1
fi
"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,9) else 1)' || { echo "ERROR: Python 3.9 or newer is required."; exit 1; }
if [ ! -f "$SUPPORT/token" ]; then
  "$PYTHON" -c 'import secrets,pathlib; p=pathlib.Path.home()/"Library/Application Support/VibeBridge/token"; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(secrets.token_urlsafe(32))'
fi
chmod 600 "$SUPPORT/token"
chmod 700 "$SUPPORT"

# Register the Native Messaging host for the pinned VibeBridge extension ID.
mkdir -p "$NATIVE_HOST_DIR"
"$PYTHON" - "$NATIVE_HOST_MANIFEST" "$PYTHON" "$ROOT/agent/native_host.py" "$EXTENSION_ID" <<'PY_HOST'
import json, pathlib, sys
manifest_path, python, host_script, extension_id = sys.argv[1:]
manifest = {
    "name": "com.vibebridge.agent",
    "description": "VibeBridge secure token bootstrap",
    "path": str(pathlib.Path(python).resolve()),
    "args": [str(pathlib.Path(host_script).resolve())],
    "type": "stdio",
    "allowed_origins": ["chrome-extension://" + extension_id + "/"],
}
path = pathlib.Path(manifest_path)
path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
path.chmod(0o600)
# Validate the exact manifest Chrome will read before restarting services.
loaded = json.loads(path.read_text(encoding="utf-8"))
assert loaded["name"] == "com.vibebridge.agent"
assert loaded["type"] == "stdio"
assert pathlib.Path(loaded["path"]).is_file(), "Native host interpreter does not exist"
assert pathlib.Path(loaded["args"][0]).is_file(), "Native host script does not exist"
assert loaded["allowed_origins"] == ["chrome-extension://" + extension_id + "/"]
print("Native Messaging manifest verified:", path)
PY_HOST
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
<key>StartInterval</key><integer>5</integer><key>RunAtLoad</key><true/>
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
echo "Chrome Native Messaging host: $NATIVE_HOST_MANIFEST"
echo "GitHub updater installed (checks every 5 seconds)."
echo "Private local token created with owner-only permissions; the extension pairs securely during first-run setup."
echo "Logs are stored under: $SUPPORT"
echo "Update logs: update.log; agent logs: agent.log and agent-error.log; updater launch logs: updater.log and updater-error.log"
echo
echo "Health check (waiting up to 15 seconds for the agent)..."
HEALTH_OK=0
for attempt in $(seq 1 15); do
  if curl --silent --show-error --max-time 1 \
    -H "Authorization: Bearer $(cat "$SUPPORT/token")" \
    http://127.0.0.1:43127/health; then
    HEALTH_OK=1
    break
  fi
  sleep 1
done
echo
if [ "$HEALTH_OK" -ne 1 ]; then
  echo "ERROR: VibeBridge agent did not become healthy."
  echo
  echo "== launchctl service state =="
  launchctl print "gui/$(id -u)/com.vibebridge.agent" 2>&1 || true
  echo
  echo "== Recent agent errors =="
  tail -n 80 "$SUPPORT/agent-error.log" 2>/dev/null || true
  echo
  echo "== Recent updater errors =="
  tail -n 80 "$SUPPORT/updater-error.log" 2>/dev/null || true
  echo
  echo "== Recent update log =="
  tail -n 80 "$SUPPORT/update.log" 2>/dev/null || true
  exit 1
fi
echo
echo "VibeBridge agent health check passed."
echo
echo "Chrome extension install location: $ROOT/extension"
echo "Persistence: Chrome remembers this unpacked extension across restarts while this folder remains in place."
echo "The updater replaces files inside this folder; it does not move or delete the extension folder."
echo "Do not load $ROOT/agent. In Chrome, use Load unpacked and select exactly $ROOT/extension."
open -a "Google Chrome" "chrome://extensions/" >/dev/null 2>&1 || true
