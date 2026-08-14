#!/bin/sh
set -eu

LABEL=io.github.xnu-tcp-watchdog
PLIST_DEST=/Library/LaunchDaemons/io.github.xnu-tcp-watchdog.plist
SCRIPT_DEST=/usr/local/libexec/xnu-tcp-watchdog.py

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

/bin/launchctl bootout system/$LABEL 2>/dev/null || true
/bin/rm -f "$PLIST_DEST" "$SCRIPT_DEST"
echo "Removed $LABEL (configuration, state, and logs were retained)."
