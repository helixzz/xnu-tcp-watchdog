# XNU TCP Watchdog

[English](README.md) | **简体中文** | [日本語](README.ja.md) | [Français](README.fr.md) | [Español](README.es.md) | [한국어](README.ko.md)

这是一个小型 macOS LaunchDaemon，用来规避长期运行的 Mac 上已被报告的
XNU TCP 时钟回绕故障。它会在 `2^32` 毫秒边界之前发出警告，并可在 TCP
计时器停止推进前安排预防性重启。

> [!WARNING]
> 本项目是运维层面的临时规避方案，并非内核修复。它可以自动重启 Mac。
> 启用 `reboot_enabled` 前，请先审查代码并测试通知。

> [!IMPORTANT]
> 安装前请先阅读[是否需要本工具](#是否需要本工具)。Apple 发布的 macOS 26.4
> 和 26.5 源码已包含修复。守护程序**不会**自动识别已修复的系统，也不会在升级后自动停用。

## 为什么需要它

部分 XNU 版本使用 32 位毫秒计数器保存 TCP 时间戳时钟。系统连续运行约
49 天 17 小时 2 分 47 秒后，计数器会发生回绕。复现报告和公开 XNU 源码
分析表明，单调更新保护可能令 `tcp_now` 冻结，使 TIME_WAIT 无法清理，
最终耗尽临时 TCP 端口。

- [详细复现与源码分析](https://blog.forevers.love/blog/xnu-tcp-timestamp-overflow-49-day-bug/)
- [独立的 49.7 天实测报告](https://zenn.dev/inazumimakoto/articles/mac-tcp-report)
- [Apple 存在缺陷的实现：XNU 12377.81.4](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.81.4/bsd/netinet/tcp_subr.c)
- [Apple 已修复的实现：XNU 12377.101.15](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.101.15/bsd/netinet/tcp_subr.c#L3906)

问题在于回绕后仍使用普通的 `tmp < current_tcp_now` 比较，而非使用 32 位时钟本身。
修复后的代码使用 `TSTMP_LT(tmp, current_tcp_now)`，并明确说明要按模运算推进、
正确处理从 `0xFFFFFFFF` 到 `0` 的回绕。请查看对应发行标签：截至下述核查日期，
Apple 仓库的 `main` 仍指向较旧的 `xnu-12377.1.9`，不能代表最新发布源码。

## 是否需要本工具

最近源码核查日期：**2026-09-23**。以下仅针对这个 TCP 时钟更新缺陷，不代表系统
不存在其他网络问题。“已修复”指 Apple 为该版本公开的源码已确认包含修复；
本项目没有对每个出厂内核完成跨越 49.7 天的实机验证。

| macOS 版本 | 公开的 XNU 版本 | 证据与建议 |
| --- | --- | --- |
| 15.6 Sequoia（已核查的旧版本） | `11417.140.69` | 使用较早的增量更新实现，没有这个错误比较。无需为此缺陷使用本工具；其他旧构建未逐一核查。 |
| 26.0 Tahoe | `12377.1.9` | 源码存在错误比较。需要长期连续运行的 Mac 可考虑本工具，优先升级至已修复版本。 |
| 26.1 | `12377.41.6` | 源码存在错误比较，建议同上。 |
| 26.2 | `12377.61.12` | 源码存在错误比较，建议同上。 |
| 26.3 | `12377.81.4` | 源码存在错误比较，建议同上。 |
| 26.4 | `12377.101.15` | **公开源码已确认修复。** 正在运行的内核匹配时，无需为此缺陷安排预防性重启。 |
| 26.5 | `12377.121.6` | **公开源码已确认修复。** 建议同上。 |
| 27 | 尚未独立核实 | 预计继承修复，但这是推断，并非对出厂内核的验证。不能仅凭主版本号归类为“确认受影响”或“确认已修复”。 |
| 其他补丁版本、测试版或定制内核 | 需核对具体构建 | 未逐一验证。请将实际运行的 XNU 与下述证据匹配，不要仅凭版本号更大就断言已修复。 |

版本对应关系取自 Apple 自己的 macOS 发行清单中的 `xnu` 子模块：
[15.6](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-156)、
[26.0](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-260)、
[26.1](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-261)、
[26.2](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-262)、
[26.3](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-263)、
[26.4](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-264)、
[26.5](https://github.com/apple-oss-distributions/distribution-macOS/tree/macos-265)。
另见[旧版增量实现](https://github.com/apple-oss-distributions/xnu/blob/xnu-11417.140.69/bsd/netinet/tcp_subr.c)
与 [26.5 中保留的修复](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.121.6/bsd/netinet/tcp_subr.c)。

### 查看自己正在使用的版本

通过 **Apple 菜单 > 关于本机** 可以查看 macOS 版本。要同时查看系统版本、构建号
和实际运行的内核，请打开“终端”，运行以下只读命令，无需 `sudo`：

```sh
sw_vers
uname -v
```

`sw_vers` 中的 `ProductVersion` 是系统版本（例如 `26.4`），`BuildVersion` 是构建号。
在 `uname -v` 中找到类似 `root:xnu-12377.101.15~1/...` 的内容，其中的
`12377.101.15` 就对应上表中已修复的源码。Darwin 的版本编号与 macOS 不同：
例如 Darwin `25.4.0` 并不是 macOS `25.4`。完成系统更新并重启后再核对一次；
仅下载更新并不会替换正在运行的内核。

- **受影响的内核，需要长期连续运行：** 尽量升级至已修复版本。暂时无法升级时，
  可使用本工具告警，并按需启用预防性重启。回绕边界不意味着所有 Mac 都会在那一秒
  立即断网，实际表现还受负载和睡眠影响。
- **已知修复的内核，或已核查的旧版实现：** 无需为此缺陷使用本工具。
  已安装的用户可按下文卸载。
- **未知内核，包括未核实的 macOS 27 构建：** 核查对应源码或取得运行证据期间，
  保持 `"reboot_enabled": false`。关键无人值守设备是否临时安排重启，应根据运维需求
  明确决定；尚未确认不等于确认受影响。TIME_WAIT/SYN_SENT 数量升高也不能单独证明此缺陷。

### 升级到已修复版本后

目前守护程序依据 uptime 和连接数量工作，没有系统版本白名单，也不会直接检查
`tcp_now`。**原有的 `"reboot_enabled": true` 配置在升级后仍可能导致不必要的重启。**
重新运行安装程序也会保留已有配置。

在本仓库目录中运行以下命令即可卸载：

```sh
sudo ./uninstall.sh
```

它会卸载守护服务并移除程序和 plist，保留配置、状态与日志。如果希望保留监控，
请编辑 `/usr/local/etc/xnu-tcp-watchdog.json`，将 `"reboot_enabled"` 设为 `false`，然后执行：

```sh
sudo launchctl kickstart -k system/io.github.xnu-tcp-watchdog
```

这会关闭自动重启，但剩余的回绕告警仍不会识别内核是否已经修复。

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
