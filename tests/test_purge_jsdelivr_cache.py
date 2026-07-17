import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from scripts import purge_jsdelivr_cache


def successful_payload() -> str:
    return json.dumps(
        {
            "status": "finished",
            "paths": {
                "/gh/Django604/AI_Digest@main/docs/index.html": {
                    "throttled": False,
                    "providers": {"CF": True, "FY": True},
                }
            },
        }
    )


class PurgeJsDelivrCacheTests(unittest.TestCase):
    def test_enumerate_docs_files_returns_sorted_repository_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "public"
            (docs_dir / "assets").mkdir(parents=True)
            (docs_dir / "data").mkdir()
            (docs_dir / "data" / "dashboard.json").write_text("{}", encoding="utf-8")
            (docs_dir / "index.svg").write_text("<svg/>", encoding="utf-8")
            (docs_dir / "assets" / "app.js").write_text("", encoding="utf-8")

            actual = purge_jsdelivr_cache.enumerate_docs_files(docs_dir)

        self.assertEqual(
            actual,
            [
                "docs/assets/app.js",
                "docs/data/dashboard.json",
                "docs/index.svg",
            ],
        )

    def test_build_purge_url_encodes_ref_and_unicode_path(self) -> None:
        actual = purge_jsdelivr_cache.build_purge_url(
            "docs/assets/中文 file.js",
            repository="Django604/AI Digest",
            ref="release/test",
        )

        self.assertEqual(
            actual,
            "https://purge.jsdelivr.net/gh/Django604/AI%20Digest@release%2Ftest/"
            "docs/assets/%E4%B8%AD%E6%96%87%20file.js",
        )

    def test_build_dashboard_purge_paths_includes_latest_month(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            index_path = docs_dir / "data" / "monthly" / "index.json"
            index_path.parent.mkdir(parents=True)
            index_path.write_text(json.dumps({"latestMonth": "2026-07"}), encoding="utf-8")

            actual = purge_jsdelivr_cache.build_dashboard_purge_paths(docs_dir)

        self.assertIn("docs/data/dashboard.json", actual)
        self.assertIn("docs/data/monthly/index.json", actual)
        self.assertIn("docs/data/monthly/2026-07/dashboard.json", actual)
        self.assertIn("docs/data/monthly/2026-07/dashboard.summary.json", actual)
        self.assertNotIn("docs/assets/app.js", actual)
        self.assertNotIn("docs/index.svg", actual)

    def test_run_purge_can_target_only_selected_paths(self) -> None:
        logs: list[str] = []
        requests: list[str] = []

        def request(url: str, _timeout: float) -> str:
            requests.append(url)
            return successful_payload()

        exit_code = purge_jsdelivr_cache.run_purge(
            repo_paths=["docs/data/monthly/index.json", "docs/data/dashboard.json"],
            attempts=1,
            log=logs.append,
            request_func=request,
            sleep_func=lambda _seconds: None,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(requests), 2)
        self.assertIn("total=2", logs[-1])

    def test_purge_file_retries_a_transient_network_error(self) -> None:
        request = mock.Mock(side_effect=[URLError("connection reset"), successful_payload()])
        sleep = mock.Mock()

        actual = purge_jsdelivr_cache.purge_file(
            "docs/index.html",
            attempts=3,
            request_func=request,
            sleep_func=sleep,
        )

        self.assertTrue(actual.success)
        self.assertEqual(actual.attempts, 2)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(1.0)

    def test_monthly_dashboard_files_are_critical(self) -> None:
        self.assertFalse(purge_jsdelivr_cache.is_critical_file("docs/index.html"))
        self.assertTrue(purge_jsdelivr_cache.is_critical_file("docs/index.svg"))
        self.assertTrue(
            purge_jsdelivr_cache.is_critical_file(
                "docs/data/monthly/2026-07/dashboard.summary.json"
            )
        )
        self.assertFalse(
            purge_jsdelivr_cache.is_critical_file("docs/data/monthly/2026-07/preview.png")
        )

    def test_run_purge_fails_when_a_critical_entry_fails(self) -> None:
        failed_payload = json.dumps(
            {
                "status": "finished",
                "paths": {
                    "/gh/example": {
                        "throttled": False,
                        "providers": {"CF": False, "FY": True},
                    }
                },
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()
            (docs_dir / "index.svg").write_text("<svg/>", encoding="utf-8")
            logs: list[str] = []

            exit_code = purge_jsdelivr_cache.run_purge(
                docs_dir=docs_dir,
                attempts=1,
                log=logs.append,
                request_func=lambda _url, _timeout: failed_payload,
                sleep_func=lambda _seconds: None,
            )

        self.assertEqual(exit_code, 1)
        self.assertTrue(any("providers failed: CF" in line for line in logs))
        self.assertIn("critical_failed=1", logs[-2])

    def test_run_purge_accepts_a_recently_purged_throttled_entry(self) -> None:
        throttled_payload = json.dumps(
            {
                "status": "finished",
                "paths": {
                    "/gh/example": {
                        "throttled": True,
                        "throttlingReset": 120,
                    }
                },
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()
            (docs_dir / "index.svg").write_text("<svg/>", encoding="utf-8")
            logs: list[str] = []

            exit_code = purge_jsdelivr_cache.run_purge(
                docs_dir=docs_dir,
                attempts=1,
                log=logs.append,
                request_func=lambda _url, _timeout: throttled_payload,
                sleep_func=lambda _seconds: None,
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(any(line.startswith("[THROTTLED]") for line in logs))
        self.assertIn("throttled=1", logs[-1])

    def test_run_purge_reports_a_success_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            (docs_dir / "assets").mkdir(parents=True)
            (docs_dir / "index.html").write_text("ok", encoding="utf-8")
            (docs_dir / "assets" / "app.js").write_text("", encoding="utf-8")
            logs: list[str] = []

            exit_code = purge_jsdelivr_cache.run_purge(
                docs_dir=docs_dir,
                attempts=1,
                log=logs.append,
                request_func=lambda _url, _timeout: successful_payload(),
                sleep_func=lambda _seconds: None,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            logs[-1],
            "Summary: total=2 succeeded=2 failed=0 critical_failed=0 throttled=0",
        )


if __name__ == "__main__":
    unittest.main()
