import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import xnu_tcp_watchdog as watchdog


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tempdir.name)
        self.state_file = self.state_dir / "state.json"
        self.state_patches = (
            mock.patch.object(watchdog, "STATE_DIR", self.state_dir),
            mock.patch.object(watchdog, "STATE_FILE", self.state_file),
        )
        for patch in self.state_patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.state_patches):
            patch.stop()
        self.tempdir.cleanup()

    def test_default_configuration_is_safe(self):
        config = watchdog.load_config(self.state_dir / "missing.json")
        self.assertFalse(config["reboot_enabled"])
        self.assertEqual(config["telegram"]["chat_ids"], [])
        self.assertEqual(config["feishu"]["webhook_urls"], [])

    def test_configuration_merges_nested_notification_values(self):
        path = self.state_dir / "config.json"
        path.write_text(json.dumps({"telegram": {"chat_ids": ["42"]}}))
        config = watchdog.load_config(path)
        self.assertEqual(config["telegram"]["chat_ids"], ["42"])
        self.assertEqual(config["telegram"]["bot_token"], "")

    @mock.patch.object(watchdog, "schedule_reboot")
    @mock.patch.object(watchdog, "send_notifications", return_value=False)
    @mock.patch.object(watchdog, "tcp_counts", return_value=(10, 0))
    @mock.patch.object(watchdog, "boot_time", return_value=1000)
    def test_preemptive_reboot_is_deferred_without_notification(
        self, _boot, _counts, _notify, reboot
    ):
        uptime = watchdog.ROLLOVER_SECONDS - 1800
        config = watchdog.load_config(self.state_dir / "missing.json")
        config["reboot_enabled"] = True
        with mock.patch.object(watchdog.time, "time", return_value=1000 + uptime):
            watchdog.check_once(config)
        reboot.assert_not_called()

    @mock.patch.object(watchdog, "schedule_reboot")
    @mock.patch.object(watchdog, "send_notifications", return_value=False)
    @mock.patch.object(watchdog, "tcp_counts", return_value=(10, 0))
    @mock.patch.object(watchdog, "boot_time", return_value=1000)
    def test_rollover_schedules_emergency_reboot_even_if_notification_fails(
        self, _boot, _counts, _notify, reboot
    ):
        uptime = watchdog.ROLLOVER_SECONDS + 1
        config = watchdog.load_config(self.state_dir / "missing.json")
        config["reboot_enabled"] = True
        with mock.patch.object(watchdog.time, "time", return_value=1000 + uptime):
            watchdog.check_once(config)
        reboot.assert_called_once_with(config)


if __name__ == "__main__":
    unittest.main()
