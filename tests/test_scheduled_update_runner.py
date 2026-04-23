from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path

from scripts.scheduled_update_runner import (
    FINISH_AUTO_CLOSE_SECONDS,
    ProgressUpdate,
    build_failure_message,
    build_start_message,
    build_success_message,
    build_waiting_status,
    infer_progress_update,
)


class ScheduledUpdateRunnerTests(unittest.TestCase):
    def test_build_start_message_lists_update_flow_and_auto_start_rule(self) -> None:
        started_at = datetime(2026, 4, 22, 9, 0, 0)

        actual = build_start_message(started_at)

        self.assertIn("2026-04-22 09:00:00", actual)
        self.assertIn("抓取 7 张线索 / 来店日报表", actual)
        self.assertIn("回填 NEV+ICE_xsai.xlsm 与 NEV+ICE_ldai.xlsx", actual)
        self.assertIn("2 分钟内未点击", actual)

    def test_build_waiting_status_mentions_remaining_seconds(self) -> None:
        self.assertEqual(
            build_waiting_status(37),
            "将在 37 秒后自动开始，你也可以立即点击“开始更新”。",
        )

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
        self.assertIn(f"窗口会在 {FINISH_AUTO_CLOSE_SECONDS} 秒后自动关闭", actual)

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
        self.assertIn(f"窗口会在 {FINISH_AUTO_CLOSE_SECONDS} 秒后自动关闭", actual)

    def test_infer_progress_update_advances_by_known_log_rule(self) -> None:
        actual = infer_progress_update("开始抓取：NEV 来店本期 + 同期", 20)

        self.assertEqual(
            actual,
            ProgressUpdate(progress=50, message="正在抓取 NEV 来店本期与同期。"),
        )

    def test_infer_progress_update_keeps_progress_monotonic_for_unknown_log(self) -> None:
        actual = infer_progress_update("这是一条未命中的调试日志", 64)

        self.assertEqual(
            actual,
            ProgressUpdate(progress=64, message="这是一条未命中的调试日志"),
        )


if __name__ == "__main__":
    unittest.main()
