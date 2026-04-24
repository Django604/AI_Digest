from __future__ import annotations

import json
import shutil
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest import mock

from scripts.scheduled_update_runner import (
    FINISH_AUTO_CLOSE_SECONDS,
    INTERACTIVE_MODE,
    ProgressUpdate,
    SILENT_MODE,
    ScheduledUpdateLock,
    build_run_dir,
    build_failure_message,
    build_lock_path,
    build_start_message,
    build_success_message,
    build_waiting_status,
    infer_progress_update,
    parse_args,
    resolve_message_visibility,
    run_scheduled_update,
)


class ScheduledUpdateRunnerTests(unittest.TestCase):
    def create_repo_temp_dir(self) -> Path:
        temp_dir = Path(__file__).resolve().parent / f".tmp-scheduled-update-runner-{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        return temp_dir

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

    def test_build_run_dir_includes_microseconds_to_avoid_same_second_collisions(self) -> None:
        earlier = build_run_dir(datetime(2026, 4, 23, 10, 13, 16, 123456))
        later = build_run_dir(datetime(2026, 4, 23, 10, 13, 16, 654321))

        self.assertNotEqual(earlier, later)
        self.assertTrue(str(earlier).endswith("20260423_101316_123456"))

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

    def test_parse_args_defaults_to_interactive_mode(self) -> None:
        actual = parse_args([])

        self.assertEqual(actual.mode, INTERACTIVE_MODE)
        self.assertFalse(actual.auto_publish)
        self.assertEqual(actual.publish_remote, "origin")
        self.assertEqual(actual.publish_branch, "main")

    def test_parse_args_accepts_auto_publish_options(self) -> None:
        actual = parse_args(
            [
                "--mode",
                SILENT_MODE,
                "--auto-publish",
                "--publish-remote",
                "upstream",
                "--publish-branch",
                "release",
                "--publish-commit-message",
                "nightly publish",
            ]
        )

        self.assertEqual(actual.mode, SILENT_MODE)
        self.assertTrue(actual.auto_publish)
        self.assertEqual(actual.publish_remote, "upstream")
        self.assertEqual(actual.publish_branch, "release")
        self.assertEqual(actual.publish_commit_message, "nightly publish")

    def test_resolve_message_visibility_disables_popups_in_silent_mode(self) -> None:
        actual = resolve_message_visibility(
            SILENT_MODE,
            suppress_start_message=False,
            suppress_finish_message=False,
        )

        self.assertEqual(actual, (False, False))

    def test_silent_mode_runs_without_popup_window(self) -> None:
        fake_result = {
            "businessDate": "2026-04-22",
            "runtimeDir": r"D:\WorkCode\AI_Digest\.runtime\daily_update\fake-run",
            "dashboardChanged": True,
            "summaryChanged": True,
        }

        runtime_root = self.create_repo_temp_dir()
        try:
            with mock.patch("scripts.scheduled_update_runner.SCHEDULED_RUNTIME_ROOT", runtime_root), mock.patch(
                "scripts.scheduled_update_runner.run_update",
                return_value=fake_result,
            ):
                exit_code = run_scheduled_update(
                    mode=SILENT_MODE,
                    business_date_text="2026-04-22",
                    show_start_message=False,
                    show_finish_message=False,
                )

            self.assertEqual(exit_code, 0)
            result_paths = list(runtime_root.glob("*/result.json"))
            self.assertEqual(len(result_paths), 1)
            payload = json.loads(result_paths[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["mode"], SILENT_MODE)
        finally:
            shutil.rmtree(runtime_root, ignore_errors=True)

    def test_auto_publish_runs_after_successful_update(self) -> None:
        fake_result = {
            "businessDate": "2026-04-22",
            "runtimeDir": r"D:\WorkCode\AI_Digest\.runtime\daily_update\fake-run",
            "dashboardChanged": True,
            "summaryChanged": True,
        }
        fake_publish = {
            "publishStatus": "success",
            "publishRemote": "origin",
            "publishBranch": "main",
            "publishCommitMessage": "Auto publish dashboard data 2026-04-22 (silent)",
        }

        runtime_root = self.create_repo_temp_dir()
        try:
            with mock.patch("scripts.scheduled_update_runner.SCHEDULED_RUNTIME_ROOT", runtime_root), mock.patch(
                "scripts.scheduled_update_runner.run_update",
                return_value=fake_result,
            ), mock.patch(
                "scripts.scheduled_update_runner.run_publish_step",
                return_value=fake_publish,
            ) as publish_mock:
                exit_code = run_scheduled_update(
                    mode=SILENT_MODE,
                    business_date_text="2026-04-22",
                    show_start_message=False,
                    show_finish_message=False,
                    auto_publish=True,
                )

            self.assertEqual(exit_code, 0)
            publish_mock.assert_called_once()
            result_paths = list(runtime_root.glob("*/result.json"))
            self.assertEqual(len(result_paths), 1)
            payload = json.loads(result_paths[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["publishStatus"], "success")
            self.assertEqual(payload["publishRemote"], "origin")
            self.assertEqual(payload["publishBranch"], "main")
        finally:
            shutil.rmtree(runtime_root, ignore_errors=True)

    def test_auto_publish_failure_marks_run_as_error(self) -> None:
        fake_result = {
            "businessDate": "2026-04-22",
            "runtimeDir": r"D:\WorkCode\AI_Digest\.runtime\daily_update\fake-run",
            "dashboardChanged": True,
            "summaryChanged": True,
        }

        runtime_root = self.create_repo_temp_dir()
        try:
            with mock.patch("scripts.scheduled_update_runner.SCHEDULED_RUNTIME_ROOT", runtime_root), mock.patch(
                "scripts.scheduled_update_runner.run_update",
                return_value=fake_result,
            ), mock.patch(
                "scripts.scheduled_update_runner.run_publish_step",
                side_effect=RuntimeError("push failed"),
            ):
                exit_code = run_scheduled_update(
                    mode=SILENT_MODE,
                    business_date_text="2026-04-22",
                    show_start_message=False,
                    show_finish_message=False,
                    auto_publish=True,
                )

            self.assertEqual(exit_code, 1)
            result_paths = list(runtime_root.glob("*/result.json"))
            self.assertEqual(len(result_paths), 1)
            payload = json.loads(result_paths[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["error"], "push failed")
            self.assertTrue(payload["autoPublish"])
        finally:
            shutil.rmtree(runtime_root, ignore_errors=True)

    def test_lock_prevents_duplicate_silent_run(self) -> None:
        runtime_root = self.create_repo_temp_dir()
        try:
            with mock.patch("scripts.scheduled_update_runner.SCHEDULED_RUNTIME_ROOT", runtime_root):
                lock = ScheduledUpdateLock(build_lock_path())
                acquired = lock.acquire(
                    {
                        "mode": INTERACTIVE_MODE,
                        "startedAt": "2026-04-23T09:00:00",
                        "businessDate": "2026-04-22",
                    }
                )
                self.assertTrue(acquired)
                try:
                    with mock.patch("scripts.scheduled_update_runner.run_update") as run_update_mock:
                        exit_code = run_scheduled_update(
                            mode=SILENT_MODE,
                            business_date_text="2026-04-22",
                            show_start_message=False,
                            show_finish_message=False,
                        )

                    self.assertEqual(exit_code, 0)
                    run_update_mock.assert_not_called()
                    result_paths = list(runtime_root.glob("*/result.json"))
                    self.assertEqual(len(result_paths), 1)
                    payload = json.loads(result_paths[0].read_text(encoding="utf-8"))
                    self.assertEqual(payload["status"], "skipped")
                    self.assertEqual(payload["reason"], "another-run-active")
                finally:
                    lock.release()
        finally:
            shutil.rmtree(runtime_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
