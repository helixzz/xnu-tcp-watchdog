#!/usr/bin/env python3
"""Preempt the XNU 2^32-millisecond TCP clock rollover on long-lived Macs."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROLLOVER_SECONDS = 2**32 / 1000
CONFIG_FILE = Path("/usr/local/etc/xnu-tcp-watchdog.json")
STATE_DIR = Path("/var/db/xnu-tcp-watchdog")
STATE_FILE = STATE_DIR / "state.json"
LOCK_FILE = Path("/var/run/xnu-tcp-watchdog.lock")

DEFAULTS: dict[str, Any] = {
    "preempt_margin_seconds": 3600,
    "time_wait_emergency": 8000,
    "syn_sent_emergency": 1000,
    "resource_check_window_seconds": 90000,
    "reboot_delay_minutes": 1,
    "reboot_enabled": False,
    "telegram": {"bot_token": "", "chat_ids": []},
    "feishu": {"webhook_urls": []},
    "notification_command": [],
}


def log(message: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}", flush=True)


def run(args: list[str]) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def load_config(path: Path = CONFIG_FILE) -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULTS))
    try:
        supplied = json.loads(path.read_text())
    except FileNotFoundError:
        return config
    for key, value in supplied.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    return config


def boot_time() -> float:
    raw = run(["/usr/sbin/sysctl", "-n", "kern.boottime"])
    return float(raw.split("sec = ", 1)[1].split(",", 1)[0])


def tcp_counts() -> tuple[int, int]:
    output = run(["/usr/sbin/netstat", "-an", "-p", "tcp"])
    states = [line.split()[-1] for line in output.splitlines() if line.split()]
    return states.count("TIME_WAIT"), states.count("SYN_SENT")


def read_state(current_boot: int) -> dict[str, Any]:
    try:
        state = json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        state = {}
    if state.get("boot") != current_boot:
        state = {"boot": current_boot, "sent": []}
    return state


def write_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, sort_keys=True) + "\n")
    os.chmod(temp, 0o600)
    temp.replace(STATE_FILE)


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def send_notifications(config: dict[str, Any], message: str) -> bool:
    configured = 0
    delivered = 0

    telegram = config.get("telegram", {})
    token = telegram.get("bot_token", "")
    for chat_id in telegram.get("chat_ids", []):
        if not token:
            break
        configured += 1
        try:
            payload = urllib.parse.urlencode({"chat_id": str(chat_id), "text": message}).encode()
            request = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage", data=payload, method="POST"
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.load(response)
            if result.get("ok") is True:
                delivered += 1
            else:
                log("Telegram rejected a notification")
        except Exception as exc:
            log(f"Telegram notification failed: {type(exc).__name__}: {exc}")

    for webhook_url in config.get("feishu", {}).get("webhook_urls", []):
        configured += 1
        try:
            result = post_json(
                str(webhook_url), {"msg_type": "text", "content": {"text": message}}
            )
            if result.get("code", result.get("StatusCode", 0)) == 0:
                delivered += 1
            else:
                log("Feishu rejected a notification")
        except Exception as exc:
            log(f"Feishu notification failed: {type(exc).__name__}: {exc}")

    command = config.get("notification_command", [])
    if command:
        configured += 1
        try:
            subprocess.run(command, input=message, text=True, check=True, timeout=30)
            delivered += 1
        except Exception as exc:
            log(f"custom notification command failed: {type(exc).__name__}: {exc}")

    if configured == 0:
        log("no notification channel is configured")
    else:
        log(f"notification delivered through {delivered}/{configured} target(s)")
    return delivered > 0


def human_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"


def notify_once(config: dict[str, Any], state: dict[str, Any], key: str, message: str) -> bool:
    if key in state["sent"]:
        return True
    if not send_notifications(config, message):
        return False
    state["sent"].append(key)
    write_state(state)
    return True


def schedule_reboot(config: dict[str, Any]) -> None:
    if not config.get("reboot_enabled", False):
        log("reboot disabled by configuration")
        return
    delay = max(1, int(config.get("reboot_delay_minutes", 1)))
    result = subprocess.run(["/sbin/shutdown", "-r", f"+{delay}"], check=False)
    if result.returncode != 0:
        log(f"shutdown command failed with exit code {result.returncode}")


def check_once(config: dict[str, Any]) -> int:
    boot = int(boot_time())
    uptime = max(0.0, time.time() - boot)
    time_wait, syn_sent = tcp_counts()
    state = read_state(boot)
    write_state(state)
    hostname = socket.gethostname()
    log(
        f"host={hostname} uptime={human_duration(uptime)} "
        f"TIME_WAIT={time_wait} SYN_SENT={syn_sent}"
    )

    margin = max(300, int(config["preempt_margin_seconds"]))
    reboot_at = ROLLOVER_SECONDS - margin
    warn_24h_at = reboot_at - 86400
    warn_1h_at = reboot_at - 3600
    resource_window_at = ROLLOVER_SECONDS - int(config["resource_check_window_seconds"])

    rollover_reached = uptime >= ROLLOVER_SECONDS
    resource_emergency = uptime >= resource_window_at and (
        time_wait >= int(config["time_wait_emergency"])
        or syn_sent >= int(config["syn_sent_emergency"])
    )
    if rollover_reached or resource_emergency:
        reason = (
            "XNU TCP 2^32-ms rollover threshold reached"
            if rollover_reached
            else f"TCP socket emergency: TIME_WAIT={time_wait}, SYN_SENT={syn_sent}"
        )
        delay = max(1, int(config["reboot_delay_minutes"]))
        notify_once(
            config,
            state,
            "emergency",
            f"[CRITICAL] {hostname}: {reason}. Uptime {human_duration(uptime)}. "
            f"This Mac will reboot in about {delay} minute(s).",
        )
        log(reason + "; scheduling reboot")
        schedule_reboot(config)
        return 0


    if uptime >= reboot_at:
        remaining = ROLLOVER_SECONDS - uptime
        delay = max(1, int(config["reboot_delay_minutes"]))
        message = (
            f"[CRITICAL] {hostname}: preventive reboot in about {delay} minute(s). "
            f"Uptime {human_duration(uptime)}; estimated XNU TCP rollover in "
            f"{human_duration(remaining)}. TIME_WAIT={time_wait}, SYN_SENT={syn_sent}."
        )
        if notify_once(config, state, "preempt_reboot", message):
            log("preventive threshold reached and notification delivered; scheduling reboot")
            schedule_reboot(config)
        else:
            log("preventive reboot deferred because no notification was delivered")
        return 0


    remaining = reboot_at - uptime
    if uptime >= warn_1h_at:
        notify_once(
            config,
            state,
            "warn_1h",
            f"[WARNING] {hostname}: preventive reboot is due in about "
            f"{human_duration(remaining)}. TIME_WAIT={time_wait}, SYN_SENT={syn_sent}.",
        )
    elif uptime >= warn_24h_at:
        notify_once(
            config,
            state,
            "warn_24h",
            f"[NOTICE] {hostname}: preventive reboot is due in about "
            f"{human_duration(remaining)} to avoid the XNU TCP clock rollover.",
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG_FILE)
    parser.add_argument("--test-notification", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.test_notification:
        message = f"[TEST] {socket.gethostname()}: XNU TCP watchdog notification works."
        return 0 if send_notifications(config, message) else 1

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("another watchdog instance is active; exiting")
            return 0
        return check_once(config)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"fatal error: {type(exc).__name__}: {exc}")
        raise
