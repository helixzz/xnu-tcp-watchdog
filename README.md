# XNU TCP Watchdog

**English** | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [Français](README.fr.md) | [Español](README.es.md) | [한국어](README.ko.md)

A small macOS LaunchDaemon that works around a reported XNU TCP clock rollover
failure on long-lived Macs. It warns before the `2^32`-millisecond boundary and
can schedule a preventive reboot before TCP timers stop advancing.

> [!WARNING]
> This project is an operational workaround, not a kernel fix. It can reboot a
> Mac automatically. Review the code and test notifications before enabling
> `reboot_enabled`.

> [!IMPORTANT]
> Check [whether you need this tool](#do-i-need-this-tool) before installing.
> Apple's macOS 26.4 and 26.5 source releases contain a fix. The watchdog does
> **not** detect fixed OS versions or disable itself after an upgrade.

## Why this exists

Some XNU versions keep the TCP timestamp clock in a 32-bit millisecond counter.
At roughly 49 days, 17 hours, 2 minutes, and 47 seconds of uptime, the counter
wraps. Reports and public XNU source analysis indicate that the monotonic update
guard can then leave `tcp_now` frozen, preventing TIME_WAIT cleanup and
eventually exhausting ephemeral TCP ports.

- [Detailed reproduction and source analysis](https://blog.forevers.love/blog/xnu-tcp-timestamp-overflow-49-day-bug/)
- [Independent 49.7-day observation](https://zenn.dev/inazumimakoto/articles/mac-tcp-report)
- [Apple's affected implementation, XNU 12377.81.4](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.81.4/bsd/netinet/tcp_subr.c)
- [Apple's fixed implementation, XNU 12377.101.15](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.101.15/bsd/netinet/tcp_subr.c#L3906)

The defect is the ordinary `tmp < current_tcp_now` comparison after a 32-bit
wrap, not the use of a 32-bit clock by itself. The fixed code uses
`TSTMP_LT(tmp, current_tcp_now)` and explicitly documents modular advancement
from `0xFFFFFFFF` to `0`. Inspect a release tag: as of the review below, Apple's
`main` still points to the older `xnu-12377.1.9` import.

## Do I need this tool?

Last source review: **2026-09-23**. This table concerns only this particular TCP
clock update defect, not every possible cause of network failure. "Fixed" means
confirmed in Apple's published source for that release; this project has not
performed a 49.7-day runtime test on each shipping kernel.

| macOS release | Published XNU | Evidence and recommendation |
| --- | --- | --- |
| 15.6 Sequoia (checked older release) | `11417.140.69` | Uses the older incremental clock update, without this defective comparison. No need for this workaround for this defect. Other older builds were not individually checked. |
| 26.0 Tahoe | `12377.1.9` | Defective comparison present. Consider the workaround for a Mac that must run continuously; updating to a fixed release is preferable. |
| 26.1 | `12377.41.6` | Defective comparison present; same recommendation. |
| 26.2 | `12377.61.12` | Defective comparison present; same recommendation. |
| 26.3 | `12377.81.4` | Defective comparison present; same recommendation. |
| 26.4 | `12377.101.15` | **Fix confirmed in published source.** No preventive reboot needed for this defect when your running kernel matches. |
| 26.5 | `12377.121.6` | **Fix confirmed in published source.** Same recommendation. |
| 27 | Not independently verified here | Expected to inherit the fix, but this is an inference, not verification of the shipping kernel. Do not classify it as confirmed affected or confirmed fixed based only on its major version. |
| Other point releases, betas, or custom kernels | Check the exact build | Not individually verified. Match the running XNU to the evidence below; do not assume a newer version number alone proves the fix. |

Version mappings come from the `xnu` submodule in Apple's own macOS release
manifests: [15.6](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-156),
[26.0](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-260),
[26.1](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-261),
[26.2](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-262),
[26.3](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-263),
[26.4](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-264),
and [26.5](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-265).
See also the [older incremental implementation](https://github.com/apple-oss-distributions/xnu/blob/xnu-11417.140.69/bsd/netinet/tcp_subr.c)
and the [26.5 fix](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/bsd/netinet/tcp_subr.c).

### Check your Mac

Choose **Apple menu > About This Mac** for the macOS version. For the product
version, build number, and kernel actually running, open Terminal and run these
read-only commands (no `sudo` required):

```sh
sw_vers
uname -v
```

`sw_vers` reports `ProductVersion` (for example, `26.4`) and `BuildVersion`.
In `uname -v`, find `root:xnu-12377.101.15~1/...`: the `12377.101.15` portion
matches the fixed source above. Darwin's version is a different numbering
scheme: Darwin `25.4.0` is not macOS `25.4`. Check again after completing an OS
update and rebooting. A downloaded update alone does not change the running kernel.

- **Affected kernel, long continuous operation:** update to a fixed release if
  possible. If you cannot, the watchdog can provide alerts and optional
  preventive reboots. The rollover boundary is not a guarantee that every Mac
  loses networking at that exact instant; workload and sleep affect observations.
- **Known fixed kernel, or the checked older implementation:** this tool is not
  needed for this defect. Remove an existing installation as described below.
- **Unknown kernel, including unverified macOS 27 builds:** keep
  `"reboot_enabled": false` while checking the exact release source or obtaining
  runtime evidence. For a critical unattended Mac, choose a temporary reboot
  policy explicitly based on your operational needs; uncertainty is not evidence
  that the machine is affected. High TIME_WAIT/SYN_SENT counts alone do not
  identify this defect.

### After upgrading to a fixed release

The watchdog currently uses uptime and socket counts; it has no OS-version
allowlist and does not inspect `tcp_now` directly. **An existing
`"reboot_enabled": true` setting can still cause unnecessary reboots after an
OS upgrade.** The installer also preserves an existing configuration.

From this repository's directory, uninstall it with:

```sh
sudo ./uninstall.sh
```

This unloads the daemon and removes its program and plist; configuration,
state, and logs are retained. If you prefer to keep monitoring, edit
`/usr/local/etc/xnu-tcp-watchdog.json`, set `"reboot_enabled": false`, then run:

```sh
sudo launchctl kickstart -k system/io.github.xnu-tcp-watchdog
```

This disables reboots but does not make the remaining rollover alerts aware
of the kernel fix.

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
