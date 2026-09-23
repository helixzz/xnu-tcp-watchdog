# XNU TCP Watchdog

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [Français](README.fr.md) | [Español](README.es.md) | **한국어**

장기간 실행되는 Mac에서 보고된 XNU TCP 시계 래핑 문제를 우회하기 위한 작은
macOS LaunchDaemon입니다. `2^32`밀리초 경계 전에 경고하고, TCP 타이머가 멈추기
전에 예방 재시작을 예약할 수 있습니다.

> [!WARNING]
> 이 프로젝트는 커널 수정이 아닌 운영상의 우회책입니다. Mac을 자동으로 재시작할
> 수 있으므로 `reboot_enabled`를 활성화하기 전에 코드를 검토하고 알림을 테스트하세요.

> [!IMPORTANT]
> 설치 전에 [버전별 상태와 확인 방법(영문)](README.md#do-i-need-this-tool)을 확인하세요.
> macOS 26.0–26.3의 공개 소스에는 이 결함이 있으며, 26.4와 26.5의 공개 소스에서는 수정되었습니다.
> macOS 27도 수정을 이어받을 것으로 예상되지만, 여기서는 독립적으로 검증하지 않았습니다.
> 이 도구는 수정된 OS를 자동으로 감지하지 않습니다. 수정된 커널로 업데이트한 뒤에는
> 도구를 제거하거나 `reboot_enabled`를 `false`로 설정하세요.

## 이 프로젝트가 필요한 이유

일부 XNU 버전은 TCP 타임스탬프 시계를 32비트 밀리초 카운터로 유지합니다. 연속
가동 시간이 약 49일 17시간 2분 47초에 이르면 카운터가 래핑됩니다. 재현 보고서와
공개 XNU 소스 분석에 따르면 단조 증가를 보장하는 업데이트 보호 로직이 `tcp_now`를
멈추게 하여 TIME_WAIT 정리를 막고, 결국 임시 TCP 포트를 고갈시킬 수 있습니다.

- [상세 재현 및 소스 분석](https://blog.forevers.love/blog/xnu-tcp-timestamp-overflow-49-day-bug/)
- [49.7일 시점의 독립 관측](https://zenn.dev/inazumimakoto/articles/mac-tcp-report)
- [Apple의 수정된 구현: XNU 12377.101.15](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.101.15/bsd/netinet/tcp_subr.c#L3906)

`sw_vers`와 `uname -v`로 OS와 실행 중인 커널을 확인한 뒤 위 링크의 표와 비교하세요.
소스 확인은 실제 기기의 장기 실행 검증과 다릅니다. 오래된 `main` 대신 해당 릴리스 태그를 확인하세요.

## 동작 방식

- 시스템 LaunchDaemon으로 5분마다 실행됩니다.
- uptime과 TIME_WAIT, SYN_SENT 개수를 기록합니다.
- 예정된 재시작 24시간 전과 1시간 전에 알립니다.
- 기본적으로 래핑 한 시간 전에 예방 재시작을 예약합니다.
- 높은 TIME_WAIT/SYN_SENT 값은 래핑에 가까운 구간에서만 긴급 신호로 사용합니다.
- 최종 알림이 어느 대상으로도 전달되지 않으면 예정된 재시작을 연기합니다.
- 래핑 경계에 도달한 뒤의 긴급 처리는 알림 성공 여부에 의존하지 않습니다.
- 자동 재시작은 **기본적으로 비활성화**되어 있으며 명시적으로 켜야 합니다.

## 요구 사항

- `/usr/bin/python3`가 있는 macOS(필요하면 Apple Command Line Tools 설치)
- 설치를 위한 관리자 계정
- 선택 사항: Telegram bot, Feishu 사용자 지정 bot Webhook 또는 사용자 지정 알림 명령

## 설치

```sh
git clone https://github.com/helixzz/xnu-tcp-watchdog.git
cd xnu-tcp-watchdog
sudo ./install.sh
```

설치 프로그램이 만드는 파일:

- `/usr/local/libexec/xnu-tcp-watchdog.py`
- `/usr/local/etc/xnu-tcp-watchdog.json` (`root:wheel`, 모드 `0600`)
- `/Library/LaunchDaemons/io.github.xnu-tcp-watchdog.plist`

기존 설정 파일은 덮어쓰지 않습니다.

## 알림 설정

root만 읽을 수 있는 설정 파일을 편집합니다:

```sh
sudo nano /usr/local/etc/xnu-tcp-watchdog.json
```

Telegram 예시:

```json
"telegram": {
  "bot_token": "123456:replace-with-your-token",
  "chat_ids": ["123456789"]
}
```

Feishu 사용자 지정 bot 예시:

```json
"feishu": {
  "webhook_urls": ["https://open.feishu.cn/open-apis/bot/v2/hook/replace-me"]
}
```

iMessage, OpenClaw, Hermes 또는 다른 알림 도구를 사용하려면 실행 파일과 인수를
`notification_command`에 지정하세요. 알림 본문은 셸을 거치지 않고 표준 입력으로
전달됩니다:

```json
"notification_command": ["/usr/local/bin/my-notify-wrapper"]
```

토큰과 Webhook URL은 설치된 설정에만 보관하고 Git에 커밋하지 마세요.

재시작을 활성화하기 전에 알림을 테스트합니다:

```sh
sudo /usr/bin/python3 /usr/local/libexec/xnu-tcp-watchdog.py --test-notification
```

성공하면 `"reboot_enabled": true`로 바꾸고 서비스를 다시 로드합니다:

```sh
sudo launchctl kickstart -k system/io.github.xnu-tcp-watchdog
```

## 확인 및 로그

```sh
sudo launchctl print system/io.github.xnu-tcp-watchdog
tail -20 /var/log/xnu-tcp-watchdog.log
```

5분 간격의 실행 사이에 `state = not running`으로 표시되는 것은 정상입니다. 최근
종료 코드와 실행 간격을 확인하세요.

## 제거

```sh
sudo ./uninstall.sh
```

복구를 위해 설정, 상태 및 로그는 남겨 둡니다. 더 이상 필요하지 않은지 확인한 뒤
수동으로 삭제하세요.

## 보안 참고 사항

- LaunchDaemon과 프로그램은 `root:wheel` 소유여야 합니다.
- API 자격 증명을 포함할 수 있으므로 설정 파일 모드는 `0600`입니다.
- 비밀 값은 설정에서 읽으며 명령줄 인수로 전달하거나 의도적으로 로그에 남기지 않습니다.
- 사용자 지정 알림 명령은 root로 실행됩니다. 일반 사용자가 수정할 수 없는 root 소유
  실행 파일만 사용하세요.

## 라이선스

[MIT](LICENSE)
