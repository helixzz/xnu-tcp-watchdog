# XNU TCP Watchdog

[English](README.md) | [简体中文](README.zh-CN.md) | **日本語** | [Français](README.fr.md) | [Español](README.es.md) | [한국어](README.ko.md)

長期間稼働する Mac で報告されている XNU TCP クロックのラップアラウンド障害を
回避するための、小さな macOS LaunchDaemon です。`2^32` ミリ秒の境界より前に
警告し、TCP タイマーが停止する前に予防的な再起動を予約できます。

> [!WARNING]
> このプロジェクトは運用上の回避策であり、カーネルの修正ではありません。
> Mac を自動的に再起動できます。`reboot_enabled` を有効にする前に、コードを
> 確認し、通知をテストしてください。

## 背景

一部の XNU バージョンでは、TCP タイムスタンプクロックが 32 ビットのミリ秒
カウンターで保持されています。連続稼働時間が約 49 日 17 時間 2 分 47 秒に
達するとカウンターがラップします。再現報告と公開 XNU ソースの分析によると、
単調増加を保証する更新処理によって `tcp_now` が停止し、TIME_WAIT が回収されず、
最終的に一時 TCP ポートが枯渇する可能性があります。

- [詳細な再現とソース解析](https://blog.forevers.love/blog/xnu-tcp-timestamp-overflow-49-day-bug/)
- [49.7 日目の独立検証](https://zenn.dev/inazumimakoto/articles/mac-tcp-report)
- [Apple が公開している `calculate_tcp_clock()` の実装](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/netinet/tcp_subr.c#L3510-L3544)

Apple は将来の macOS で実装を変更する可能性があります。この回避策が現在も必要か、
インストール済み OS と最新の XNU ソースを確認してください。

## 動作

- システム LaunchDaemon として 5 分ごとに実行します。
- uptime、TIME_WAIT、SYN_SENT の数を記録します。
- 予定された再起動の 24 時間前と 1 時間前に通知します。
- デフォルトではラップアラウンドの 1 時間前に予防的再起動を予定します。
- TIME_WAIT/SYN_SENT の異常増加は、境界付近でのみ緊急シグナルとして扱います。
- 最終通知がどの通知先にも届かなければ、予定再起動を延期します。
- 境界到達後の緊急処理は、通知の成功に依存しません。
- 自動再起動は**デフォルトで無効**です。明示的に有効化してください。

## 必要条件

- `/usr/bin/python3` が利用できる macOS（必要なら Apple Command Line Tools を導入）
- インストールに使用する管理者アカウント
- 任意：Telegram bot、Feishu カスタム bot Webhook、または独自通知コマンド

## インストール

```sh
git clone https://github.com/helixzz/xnu-tcp-watchdog.git
cd xnu-tcp-watchdog
sudo ./install.sh
```

作成されるファイル：

- `/usr/local/libexec/xnu-tcp-watchdog.py`
- `/usr/local/etc/xnu-tcp-watchdog.json`（`root:wheel`、モード `0600`）
- `/Library/LaunchDaemons/io.github.xnu-tcp-watchdog.plist`

既存の設定ファイルは上書きされません。

## 通知の設定

root のみが読める設定ファイルを編集します：

```sh
sudo nano /usr/local/etc/xnu-tcp-watchdog.json
```

Telegram の例：

```json
"telegram": {
  "bot_token": "123456:replace-with-your-token",
  "chat_ids": ["123456789"]
}
```

Feishu カスタム bot の例：

```json
"feishu": {
  "webhook_urls": ["https://open.feishu.cn/open-apis/bot/v2/hook/replace-me"]
}
```

iMessage、OpenClaw、Hermes などを使う場合は、`notification_command` に実行
ファイルと引数を指定します。アラート本文は shell を経由せず標準入力に渡されます：

```json
"notification_command": ["/usr/local/bin/my-notify-wrapper"]
```

トークンや Webhook URL はインストール済み設定にだけ保存し、Git にコミットしないで
ください。

再起動を有効にする前に通知をテストします：

```sh
sudo /usr/bin/python3 /usr/local/libexec/xnu-tcp-watchdog.py --test-notification
```

成功したら `"reboot_enabled": true` に変更し、サービスを再読み込みします：

```sh
sudo launchctl kickstart -k system/io.github.xnu-tcp-watchdog
```

## 確認とログ

```sh
sudo launchctl print system/io.github.xnu-tcp-watchdog
tail -20 /var/log/xnu-tcp-watchdog.log
```

5 分ごとの実行の合間に `state = not running` と表示されるのは正常です。直近の終了
コードと実行間隔を確認してください。

## アンインストール

```sh
sudo ./uninstall.sh
```

復旧できるよう、設定、状態、ログは意図的に残します。不要であることを確認した後に
手動で削除してください。

## セキュリティ

- LaunchDaemon とプログラムは `root:wheel` の所有にしてください。
- API 資格情報を含む可能性があるため、設定ファイルはモード `0600` です。
- シークレットは設定から読み取り、コマンドライン引数やログには意図的に出力しません。
- 独自通知コマンドは root で実行されます。一般ユーザーが変更できない root 所有の
  実行ファイルだけを使用してください。

## ライセンス

[MIT](LICENSE)
