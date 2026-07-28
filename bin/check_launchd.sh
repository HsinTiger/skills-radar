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
RUNTIME_PATH=$(python3 - "$TARGET" <<'PY'
import plistlib
import sys
with open(sys.argv[1], "rb") as handle:
    print(plistlib.load(handle)["EnvironmentVariables"]["PATH"])
PY
)
if ! env PATH="$RUNTIME_PATH" /bin/sh -c 'command -v gh' >/dev/null 2>&1; then
  echo "launchd contract FAIL: installed PATH cannot resolve gh" >&2
  exit 1
fi
if ! env PATH="$RUNTIME_PATH" gh auth status >/dev/null 2>&1; then
  echo "launchd contract FAIL: gh auth is unavailable under installed PATH" >&2
  exit 1
fi
if ! env PATH="$RUNTIME_PATH" /bin/sh -c 'command -v python3' >/dev/null 2>&1; then
  echo "launchd contract FAIL: installed PATH cannot resolve python3" >&2
  exit 1
fi
if ! env PATH="$RUNTIME_PATH" python3 -c 'import numpy, sklearn; from zoneinfo import ZoneInfo; ZoneInfo("Asia/Taipei")' >/dev/null 2>&1; then
  echo "launchd contract FAIL: required Python packages or timezone data are unavailable" >&2
  exit 1
fi
if ! env PATH="$RUNTIME_PATH" /bin/sh -c 'command -v agy || command -v claude' >/dev/null 2>&1; then
  echo "launchd contract FAIL: installed PATH cannot resolve agy or claude" >&2
  exit 1
fi
launchctl print "$DOMAIN/$LABEL"
echo "launchd registration PASS: $LABEL"
