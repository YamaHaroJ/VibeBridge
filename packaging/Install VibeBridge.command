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
  error_dialog "Python 3.9 or newer is required. Setup cannot continue until Python is installed." || true
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

/usr/bin/osascript -e 'display dialog "VibeBridge setup\n\nThis approval installs the local agent and enables hourly updates from the public VibeBridge GitHub repository. The agent listens only on this Mac. It does not upload your project files automatically.\n\nAfter this step, Chrome still requires you to approve the extension installation. Until the Chrome Web Store version is published, Chrome requires Developer mode + Load unpacked. GitHub sign-in is only needed for GitHub repository tools.\n\nContinue with setup?" with title "VibeBridge Setup" buttons {"Continue","Cancel"} default button "Continue"' || exit 1

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
/usr/bin/osascript -e 'display dialog "VibeBridge agent and hourly updater are installed.\\n\\nIn Chrome, enable Developer mode, click Load unpacked, and select ~/VibeBridge/extension. Then open the VibeBridge popup and click Connect this Mac. Approve the native macOS connection prompt when it appears; the token transfers securely without copying it from Terminal.\\n\\nThe extension includes Maintenance & diagnostics to request updates and inspect local logs. Chrome must still be reloaded after extension files change.\\n\\nRequired approvals: this installer, the Chrome extension, and the one-time native connection prompt. No broad Full Disk Access permission is requested." with title "VibeBridge Setup" buttons {"OK"} default button "OK"'
echo
echo "Setup files installed at $DEST"
echo "Next: connect the extension in Chrome; no token copying or Terminal commands are needed."
