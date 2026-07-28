#!/bin/bash
# Install/reload the versioned daily dispatcher contract on the canonical Mac.
set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "install_launchd.sh must run on macOS" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.hsin.skills-radar"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$UID"

python3 "$ROOT/bin/launchd_schedule.py" \
  --repo-root "$ROOT" --output "$TARGET" --runtime-path "$PATH"
plutil -lint "$TARGET"
launchctl bootout "$DOMAIN" "$TARGET" >/dev/null 2>&1 || true
launchctl bootstrap "$DOMAIN" "$TARGET"
launchctl enable "$DOMAIN/$LABEL"
python3 "$ROOT/bin/launchd_schedule.py" \
  --repo-root "$ROOT" --output "$TARGET" --runtime-path "$PATH" --verify
launchctl print "$DOMAIN/$LABEL"

echo "installed $LABEL: daily 08:30 Asia/Taipei"
echo "run now if desired: launchctl kickstart -k $DOMAIN/$LABEL"
