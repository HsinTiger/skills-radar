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

if ! command -v gh >/dev/null 2>&1; then
  echo "install_launchd.sh: gh is not available in the PATH that would be captured" >&2
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "install_launchd.sh: gh auth status failed" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "install_launchd.sh: python3 is not available in the PATH that would be captured" >&2
  exit 1
fi
if ! python3 -c 'import numpy, sklearn; from zoneinfo import ZoneInfo; ZoneInfo("Asia/Taipei")' >/dev/null 2>&1; then
  echo "install_launchd.sh: Python dependencies missing; run python3 -m pip install -r requirements-ml.txt" >&2
  exit 1
fi
if ! command -v agy >/dev/null 2>&1 && ! command -v claude >/dev/null 2>&1; then
  echo "install_launchd.sh: neither agy nor claude is available in the PATH that would be captured" >&2
  exit 1
fi

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
