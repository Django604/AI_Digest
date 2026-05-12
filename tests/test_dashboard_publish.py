import unittest
from unittest import mock

from scripts import dashboard_publish


class DashboardPublishTests(unittest.TestCase):
    def test_resolve_publish_commit_message_prefers_explicit_message(self) -> None:
        actual = dashboard_publish.resolve_publish_commit_message(
            business_date="2026-05-11",
            mode="interactive",
            explicit_message="Manual override",
        )

        self.assertEqual(actual, "Manual override")

    def test_publish_dashboard_returns_no_changes_when_publish_scope_is_clean(self) -> None:
        with mock.patch("scripts.dashboard_publish._ensure_git_available"), mock.patch(
            "scripts.dashboard_publish._check_staged_files"
        ), mock.patch(
            "scripts.dashboard_publish._run_git",
            side_effect=[
                dashboard_publish.CommandResult(0, "D:/WorkCode/AI_Digest\n"),
                dashboard_publish.CommandResult(0, "main\n"),
                dashboard_publish.CommandResult(0, "git@github.com:Django604/AI_Digest.git\n"),
                dashboard_publish.CommandResult(0, ""),
                dashboard_publish.CommandResult(0, ""),
            ],
        ):
            actual = dashboard_publish.publish_dashboard(
                skip_rebuild=True,
                log=lambda _message: None,
            )

        self.assertEqual(actual["publishStatus"], "no_changes")
        self.assertEqual(actual["publishRemote"], "origin")
        self.assertEqual(actual["publishBranch"], "main")

    def test_publish_dashboard_retries_interrupted_push_once(self) -> None:
        logs: list[str] = []
        with mock.patch("scripts.dashboard_publish._ensure_git_available"), mock.patch(
            "scripts.dashboard_publish._check_staged_files"
        ), mock.patch(
            "scripts.dashboard_publish._run_git",
            side_effect=[
                dashboard_publish.CommandResult(0, "D:/WorkCode/AI_Digest\n"),
                dashboard_publish.CommandResult(0, "main\n"),
                dashboard_publish.CommandResult(0, "git@github.com:Django604/AI_Digest.git\n"),
                dashboard_publish.CommandResult(0, ""),
                dashboard_publish.CommandResult(0, "docs/data/dashboard.json\n"),
                dashboard_publish.CommandResult(0, "[main abc1234] Auto publish dashboard data 2026-05-11 (interactive)\n"),
            ],
        ), mock.patch(
            "scripts.dashboard_publish._run_command",
            side_effect=[
                dashboard_publish.CommandResult(3221225786, ""),
                dashboard_publish.CommandResult(0, "To github.com:Django604/AI_Digest.git\n   old..new  HEAD -> main\n"),
            ],
        ) as run_command_mock, mock.patch("scripts.dashboard_publish.time.sleep"):
            actual = dashboard_publish.publish_dashboard(
                business_date="2026-05-11",
                mode="interactive",
                skip_rebuild=True,
                log=logs.append,
            )

        self.assertEqual(actual["publishStatus"], "success")
        self.assertEqual(run_command_mock.call_count, 2)
        self.assertTrue(any("Push was interrupted once; retrying after a short pause..." in line for line in logs))


if __name__ == "__main__":
    unittest.main()
