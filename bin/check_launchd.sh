#!/bin/bash
# Verify both the installed plist contract and launchd registration.
set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "check_launchd.sh must run on macOS" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.hsin.skills-radar"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$UID"

plutil -lint "$TARGET"
python3 "$ROOT/bin/launchd_schedule.py" \
  --repo-root "$ROOT" --output "$TARGET" --runtime-path "$PATH" --verify
launchctl print "$DOMAIN/$LABEL"
echo "launchd registration PASS: $LABEL"
