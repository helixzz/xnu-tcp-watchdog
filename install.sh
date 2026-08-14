#!/bin/sh
set -eu

SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SCRIPT_DEST=/usr/local/libexec/xnu-tcp-watchdog.py
CONFIG_DEST=/usr/local/etc/xnu-tcp-watchdog.json
PLIST_DEST=/Library/LaunchDaemons/io.github.xnu-tcp-watchdog.plist
LABEL=io.github.xnu-tcp-watchdog

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

if [ ! -x /usr/bin/python3 ]; then
  echo "/usr/bin/python3 is required. Install Apple's Command Line Tools first." >&2
  exit 1
fi

/usr/bin/install -d -o root -g wheel -m 0755 /usr/local/libexec
/usr/bin/install -d -o root -g wheel -m 0755 /usr/local/etc
/usr/bin/install -o root -g wheel -m 0755 "$SOURCE_DIR/xnu_tcp_watchdog.py" "$SCRIPT_DEST"
/usr/bin/install -o root -g wheel -m 0644 "$SOURCE_DIR/io.github.xnu-tcp-watchdog.plist" "$PLIST_DEST"
if [ ! -e "$CONFIG_DEST" ]; then
  /usr/bin/install -o root -g wheel -m 0600 "$SOURCE_DIR/config.example.json" "$CONFIG_DEST"
fi
/usr/bin/plutil -lint "$PLIST_DEST"
/usr/bin/python3 -m py_compile "$SCRIPT_DEST"

/bin/launchctl bootout system/$LABEL 2>/dev/null || true
/bin/launchctl bootstrap system "$PLIST_DEST"
/bin/launchctl enable system/$LABEL
/bin/launchctl kickstart -k system/$LABEL

echo "Installed and started $LABEL"
echo "Configuration: $CONFIG_DEST"
echo "Automatic reboot is disabled in the default configuration."
echo "Status: launchctl print system/$LABEL"
echo "Log:    tail -f /var/log/xnu-tcp-watchdog.log"
