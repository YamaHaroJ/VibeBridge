#!/bin/bash
set -euo pipefail

TITLE="VibeBridge Setup"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PAYLOAD="$SCRIPT_DIR/VibeBridge"
DEST="$HOME/VibeBridge"
REPO="https://github.com/YamaHaroJ/VibeBridge.git"

dialog() {
  /usr/bin/osascript -e "display dialog \"$1\" with title \"$TITLE\" buttons {\"$2\"} default button \"$2\""
}
error_dialog() {
  /usr/bin/osascript -e "display alert \"$TITLE\" message \"$1\" as critical buttons {\"OK\"} default button \"OK\""
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer only supports macOS."
  exit 1
fi

PYTHON="$(command -v python3 || true)"
if [[ -z "$PYTHON" ]] || ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)'; then
  error_dialog "Python 3.9 or newer is required. Install Python 3, then run this installer again." || true
  open "https://www.python.org/downloads/macos/"
  exit 1
fi

GIT="$(command -v git || true)"
if [[ -z "$GIT" ]]; then
  error_dialog "Git is required. Install Apple's Command Line Tools, then run this installer again." || true
  /usr/bin/xcode-select --install || true
  exit 1
fi

if [[ -e "$DEST" ]]; then
  error_dialog "~/VibeBridge already exists. The installer will not overwrite it. Open the VibeBridge extension and choose Update VibeBridge safely instead." || true
  open "https://chatgpt.com/"
  open "chrome://extensions/"
  exit 2
fi

if [[ ! -d "$PAYLOAD/agent" || ! -d "$PAYLOAD/extension" ]]; then
  error_dialog "The package is missing its VibeBridge payload. Re-download the full installer package." || true
  exit 1
fi

/usr/bin/osascript -e 'display dialog "VibeBridge will install a local background agent in your home folder. The agent listens only on this Mac. GitHub CLI is optional for installation but required for repository-management features. The Chrome extension will only attach project context after you load it in Chrome. Continue?" with title "VibeBridge Setup" buttons {"Continue","Cancel"} default button "Continue"' || exit 1

mkdir -p "$HOME"
ditto "$PAYLOAD" "$DEST"
cd "$DEST"
git init -q -b master
git config user.name "VibeBridge Installer"
git config user.email "vibebridge-installer@users.noreply.github.com"
git add -A
git commit -q -m "Install VibeBridge package snapshot"
git remote add origin "$REPO"
git fetch --quiet origin master
git reset --hard origin/master >/dev/null

bash "$DEST/agent/install.sh"

open -a "Google Chrome" "chrome://extensions/"
/usr/bin/osascript -e 'display dialog "VibeBridge agent is installed. In Chrome, enable Developer mode and click Load unpacked, then select ~/VibeBridge/extension. Open the VibeBridge extension, paste the local token shown in Terminal, and click Save settings. GitHub repository-management features can be enabled later by installing GitHub CLI and signing in." with title "VibeBridge Setup" buttons {"OK"} default button "OK"'
echo
echo "Setup files installed at $DEST"
echo "Copy the local token above into the VibeBridge extension popup, then save settings."
read -r -p "Press Return after saving your token to close this window."
