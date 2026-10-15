#!/bin/bash
set -euo pipefail
echo "VibeBridge GitHub authentication"
if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is not installed. Install it from https://cli.github.com/ and run this helper again."
  open "https://cli.github.com/"
  read -r -p "Press Return to close this window."
  exit 1
fi
gh auth login --web
if gh auth status; then
  echo
  echo "GitHub authentication succeeded. Run Install VibeBridge.command again."
else
  echo "GitHub authentication was not confirmed. Try again."
fi
read -r -p "Press Return to close this window."
