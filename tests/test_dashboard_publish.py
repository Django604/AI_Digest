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
            "scripts.dashboard_publish._run_command_with_timeout",
            side_effect=[
                dashboard_publish.CommandResult(3221225786, ""),
                dashboard_publish.CommandResult(0, "To github.com:Django604/AI_Digest.git\n   old..new  HEAD -> main\n"),
            ],
        ) as run_command_mock, mock.patch("scripts.dashboard_publish.time.sleep"):
            with mock.patch(
                "scripts.dashboard_publish._purge_published_cache",
                return_value=8,
            ) as purge_mock:
                actual = dashboard_publish.publish_dashboard(
                    business_date="2026-05-11",
                    mode="interactive",
                    skip_rebuild=True,
                    log=logs.append,
                )

        self.assertEqual(actual["publishStatus"], "success")
        self.assertEqual(actual["publishCachePurgeStatus"], "success")
        self.assertEqual(run_command_mock.call_count, 2)
        purge_mock.assert_called_once()
        self.assertTrue(any("Push was interrupted once; retrying after a short pause..." in line for line in logs))

    def test_publish_dashboard_pushes_existing_commits_when_publish_scope_is_clean(self) -> None:
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
                dashboard_publish.CommandResult(0, ""),
            ],
        ), mock.patch(
            "scripts.dashboard_publish._run_command_with_timeout",
            return_value=dashboard_publish.CommandResult(0, "Everything up-to-date\n"),
        ) as push_mock, mock.patch(
            "scripts.dashboard_publish._purge_published_cache",
            return_value=8,
        ) as purge_mock:
            actual = dashboard_publish.publish_dashboard(
                skip_rebuild=True,
                push_if_no_changes=True,
                log=logs.append,
            )

        self.assertEqual(actual["publishStatus"], "no_changes")
        self.assertEqual(actual["publishPushAttempted"], "true")
        self.assertEqual(actual["publishCachePurgeStatus"], "success")
        self.assertEqual(actual["publishCachePurgedFiles"], "8")
        push_mock.assert_called_once()
        purge_mock.assert_called_once()
        self.assertEqual(push_mock.call_args.args[0], ["git", "push", "origin", "HEAD:main"])
        self.assertTrue(any("checking pending commits" in line for line in logs))

    def test_purge_published_cache_targets_remote_repository_and_branch(self) -> None:
        logs: list[str] = []
        with mock.patch(
            "scripts.dashboard_publish.build_dashboard_purge_paths",
            return_value=["docs/data/dashboard.json", "docs/data/monthly/2026-07/dashboard.json"],
        ), mock.patch(
            "scripts.dashboard_publish.run_purge",
            return_value=0,
        ) as purge_mock:
            actual = dashboard_publish._purge_published_cache(
                repo_root=dashboard_publish.PROJECT_ROOT,
                remote_url="git@github.com:Django604/AI_Digest.git",
                branch="main",
                log=logs.append,
            )

        self.assertEqual(actual, 2)
        kwargs = purge_mock.call_args.kwargs
        self.assertEqual(kwargs["repository"], "Django604/AI_Digest")
        self.assertEqual(kwargs["ref"], "main")
        self.assertEqual(len(kwargs["repo_paths"]), 2)

    def test_purge_published_cache_reports_post_push_failure(self) -> None:
        with mock.patch(
            "scripts.dashboard_publish.build_dashboard_purge_paths",
            return_value=["docs/data/dashboard.json"],
        ), mock.patch("scripts.dashboard_publish.run_purge", return_value=1):
            with self.assertRaises(dashboard_publish.PublishError) as context:
                dashboard_publish._purge_published_cache(
                    repo_root=dashboard_publish.PROJECT_ROOT,
                    remote_url="https://github.com/Django604/AI_Digest.git",
                    branch="main",
                    log=lambda _message: None,
                )

        self.assertEqual(context.exception.phase, "cache_purge")
        self.assertIn("GitHub push succeeded", str(context.exception))

    def test_check_staged_files_allows_monthly_archive_files(self) -> None:
        staged_output = "docs/data/monthly/index.json\ndocs/data/monthly/2026-05/dashboard.json\n"
        with mock.patch(
            "scripts.dashboard_publish._run_git",
            return_value=dashboard_publish.CommandResult(0, staged_output),
        ):
            dashboard_publish._check_staged_files(dashboard_publish.PROJECT_ROOT)


if __name__ == "__main__":
    unittest.main()
