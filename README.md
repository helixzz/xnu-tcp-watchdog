# XNU TCP Watchdog

A small macOS LaunchDaemon that works around a reported XNU TCP clock rollover
failure on long-lived Macs. It warns before the `2^32`-millisecond boundary and
can schedule a preventive reboot before TCP timers stop advancing.

> [!WARNING]
> This project is an operational workaround, not a kernel fix. It can reboot a
> Mac automatically. Review the code and test notifications before enabling
> `reboot_enabled`.

## Why this exists

Some XNU versions keep the TCP timestamp clock in a 32-bit millisecond counter.
At roughly 49 days, 17 hours, 2 minutes, and 47 seconds of uptime, the counter
wraps. Reports and public XNU source analysis indicate that the monotonic update
guard can then leave `tcp_now` frozen, preventing TIME_WAIT cleanup and
eventually exhausting ephemeral TCP ports.

- [Detailed reproduction and source analysis](https://blog.forevers.love/blog/xnu-tcp-timestamp-overflow-49-day-bug/)
- [Independent 49.7-day observation](https://zenn.dev/inazumimakoto/articles/mac-tcp-report)
- [Apple's public `calculate_tcp_clock()` implementation](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/netinet/tcp_subr.c#L3510-L3544)

Apple may change the implementation in future macOS releases. Check your
installed OS and current XNU source before assuming the workaround is still
needed.

## Behavior

- Runs every five minutes as a system LaunchDaemon.
- Logs uptime plus TIME_WAIT and SYN_SENT counts.
- Warns 24 hours and one hour before the planned preventive reboot.
- Defaults to a preventive reboot one hour before the rollover boundary.
- Uses elevated TIME_WAIT/SYN_SENT counts as an emergency signal only near the
  rollover window.
- Defers the planned reboot if no notification target accepted the final alert.
- At or after rollover, emergency handling does not depend on notification
  success.
- Automatic reboot is **disabled by default** and must be explicitly enabled.

## Requirements

- macOS with `/usr/bin/python3` (install Apple's Command Line Tools if needed)
- An administrator account for installation
- Optional: Telegram bot, Feishu custom bot webhook, or a custom notification
  command

## Install

```sh
git clone https://github.com/helixzz/xnu-tcp-watchdog.git
cd xnu-tcp-watchdog
sudo ./install.sh
```

The installer creates:

- `/usr/local/libexec/xnu-tcp-watchdog.py`
- `/usr/local/etc/xnu-tcp-watchdog.json` (`root:wheel`, mode `0600`)
- `/Library/LaunchDaemons/io.github.xnu-tcp-watchdog.plist`

It never overwrites an existing configuration file.

## Configure notifications

Edit the root-only configuration:

```sh
sudo nano /usr/local/etc/xnu-tcp-watchdog.json
```

Telegram example:

```json
"telegram": {
  "bot_token": "123456:replace-with-your-token",
  "chat_ids": ["123456789"]
}
```

Feishu custom bot example:

```json
"feishu": {
  "webhook_urls": ["https://open.feishu.cn/open-apis/bot/v2/hook/replace-me"]
}
```

For iMessage, OpenClaw, Hermes, or another notifier, provide an executable and
arguments in `notification_command`. The alert text is passed on standard
input; no shell is involved:

```json
"notification_command": ["/usr/local/bin/my-notify-wrapper"]
```

Keep tokens and webhook URLs only in the installed configuration. Never commit
them to Git.

Test delivery before enabling reboots:

```sh
sudo /usr/bin/python3 /usr/local/libexec/xnu-tcp-watchdog.py --test-notification
```

Then set `"reboot_enabled": true` and reload the service:

```sh
sudo launchctl kickstart -k system/io.github.xnu-tcp-watchdog
```

## Verify and inspect logs

```sh
sudo launchctl print system/io.github.xnu-tcp-watchdog
tail -20 /var/log/xnu-tcp-watchdog.log
```

`state = not running` is normal between five-minute checks; inspect the last
exit code and run interval.

## Uninstall

```sh
sudo ./uninstall.sh
```

Configuration, state, and logs are retained intentionally so removal is
recoverable. Delete them manually only after confirming they are no longer
needed.

## Security notes

- The LaunchDaemon and program must be owned by `root:wheel`.
- Configuration is mode `0600` because it may contain API credentials.
- Secrets are read from the configuration and are never passed as command-line
  arguments or intentionally logged.
- Custom notification commands run as root. Use only a root-owned executable
  that cannot be modified by unprivileged users.

## License

[MIT](LICENSE)
