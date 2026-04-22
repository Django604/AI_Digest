from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path

from scripts.scheduled_update_runner import (
    build_failure_message,
    build_start_message,
    build_success_message,
)


class ScheduledUpdateRunnerTests(unittest.TestCase):
    def test_build_start_message_lists_update_flow(self) -> None:
        started_at = datetime(2026, 4, 22, 9, 0, 0)

        actual = build_start_message(started_at)

        self.assertIn("2026-04-22 09:00:00", actual)
        self.assertIn("抓取 7 张线索 / 来店日报表", actual)
        self.assertIn("回填 NEV+ICE_xsai.xlsm 与 NEV+ICE_ldai.xlsx", actual)

    def test_build_success_message_contains_result_summary(self) -> None:
        result = {
            "businessDate": "2026-04-21",
            "runtimeDir": r"D:\WorkCode\AI_Digest\.runtime\daily_update\20260421_20260422-090000",
            "dashboardChanged": True,
            "summaryChanged": False,
        }

        actual = build_success_message(
            result,
            datetime(2026, 4, 22, 9, 0, 0),
            datetime(2026, 4, 22, 9, 3, 5),
            Path(r"D:\WorkCode\AI_Digest\.runtime\scheduled_update\20260422_090000\scheduled_update.log"),
        )

        self.assertIn("业务日期：2026-04-21", actual)
        self.assertIn("dashboard.json 有变更：是", actual)
        self.assertIn("dashboard.summary.json 有变更：否", actual)
        self.assertIn("耗时：185 秒", actual)

    def test_build_failure_message_contains_error_and_log_path(self) -> None:
        actual = build_failure_message(
            datetime(2026, 4, 22, 9, 0, 0),
            datetime(2026, 4, 22, 9, 1, 30),
            Path(r"D:\WorkCode\AI_Digest\.runtime\scheduled_update\20260422_090000\scheduled_update.log"),
            "Chrome 启动失败",
        )

        self.assertIn("AI Digest 每日自动更新失败", actual)
        self.assertIn("错误信息：Chrome 启动失败", actual)
        self.assertIn("耗时：90 秒", actual)


if __name__ == "__main__":
    unittest.main()
