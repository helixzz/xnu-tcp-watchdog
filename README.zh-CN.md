# XNU TCP Watchdog

[English](README.md) | **简体中文** | [日本語](README.ja.md) | [Français](README.fr.md) | [Español](README.es.md) | [한국어](README.ko.md)

这是一个小型 macOS LaunchDaemon，用来规避长期运行的 Mac 上已被报告的
XNU TCP 时钟回绕故障。它会在 `2^32` 毫秒边界之前发出警告，并可在 TCP
计时器停止推进前安排预防性重启。

> [!WARNING]
> 本项目是运维层面的临时规避方案，并非内核修复。它可以自动重启 Mac。
> 启用 `reboot_enabled` 前，请先审查代码并测试通知。

## 为什么需要它

部分 XNU 版本使用 32 位毫秒计数器保存 TCP 时间戳时钟。系统连续运行约
49 天 17 小时 2 分 47 秒后，计数器会发生回绕。复现报告和公开 XNU 源码
分析表明，单调更新保护可能令 `tcp_now` 冻结，使 TIME_WAIT 无法清理，
最终耗尽临时 TCP 端口。

- [详细复现与源码分析](https://blog.forevers.love/blog/xnu-tcp-timestamp-overflow-49-day-bug/)
- [独立的 49.7 天实测报告](https://zenn.dev/inazumimakoto/articles/mac-tcp-report)
- [Apple 公开的 `calculate_tcp_clock()` 实现](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/netinet/tcp_subr.c#L3510-L3544)

Apple 可能会在未来的 macOS 版本中修改相关实现。不要默认认为本工具永远
有必要；请先检查已安装的系统版本和最新 XNU 源码。

## 工作方式

- 作为系统 LaunchDaemon，每五分钟运行一次。
- 记录 uptime、TIME_WAIT 和 SYN_SENT 数量。
- 在计划重启前 24 小时和 1 小时发出通知。
- 默认在回绕边界前一小时安排预防性重启。
- 仅在临近回绕的时间窗口内，将异常升高的 TIME_WAIT/SYN_SENT 作为紧急信号。
- 如果最终告警未被任何通知目标接受，则延后计划性重启。
- 到达或超过回绕边界后，紧急处理不依赖通知是否发送成功。
- 自动重启**默认关闭**，必须显式启用。

## 环境要求

- 带有 `/usr/bin/python3` 的 macOS（必要时安装 Apple Command Line Tools）
- 用于安装的管理员账户
- 可选：Telegram bot、飞书自定义机器人 Webhook 或自定义通知命令

## 安装

```sh
git clone https://github.com/helixzz/xnu-tcp-watchdog.git
cd xnu-tcp-watchdog
sudo ./install.sh
```

安装程序会创建：

- `/usr/local/libexec/xnu-tcp-watchdog.py`
- `/usr/local/etc/xnu-tcp-watchdog.json`（`root:wheel`，权限 `0600`）
- `/Library/LaunchDaemons/io.github.xnu-tcp-watchdog.plist`

已有的配置文件不会被覆盖。

## 配置通知

编辑仅 root 可读的配置文件：

```sh
sudo nano /usr/local/etc/xnu-tcp-watchdog.json
```

Telegram 示例：

```json
"telegram": {
  "bot_token": "123456:replace-with-your-token",
  "chat_ids": ["123456789"]
}
```

飞书自定义机器人示例：

```json
"feishu": {
  "webhook_urls": ["https://open.feishu.cn/open-apis/bot/v2/hook/replace-me"]
}
```

如需使用 iMessage、OpenClaw、Hermes 或其他通知器，请在
`notification_command` 中设置可执行文件及其参数。告警文本会通过标准输入
传入，不经过 shell：

```json
"notification_command": ["/usr/local/bin/my-notify-wrapper"]
```

令牌和 Webhook URL 只能保存在安装后的配置文件中，切勿提交到 Git。

启用重启前先测试通知：

```sh
sudo /usr/bin/python3 /usr/local/libexec/xnu-tcp-watchdog.py --test-notification
```

确认成功后，将 `"reboot_enabled"` 设为 `true` 并重新加载服务：

```sh
sudo launchctl kickstart -k system/io.github.xnu-tcp-watchdog
```

## 验证与查看日志

```sh
sudo launchctl print system/io.github.xnu-tcp-watchdog
tail -20 /var/log/xnu-tcp-watchdog.log
```

在两次五分钟检查之间看到 `state = not running` 属正常现象；请检查最近退出码
和运行间隔。

## 卸载

```sh
sudo ./uninstall.sh
```

为了便于恢复，配置、状态和日志会被保留。确认不再需要后再手动删除。

## 安全说明

- LaunchDaemon 和程序必须由 `root:wheel` 所有。
- 配置文件权限为 `0600`，因为其中可能含有 API 凭据。
- 密钥只从配置文件读取，不会作为命令行参数传递，也不会被有意写入日志。
- 自定义通知命令以 root 身份运行。只能使用由 root 所有且普通用户无法修改的程序。

## 许可证

[MIT](LICENSE)
