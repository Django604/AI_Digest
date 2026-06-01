from __future__ import annotations

import json
import shutil
import threading
import time
import unittest
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from unittest.mock import patch

from scripts import serve_dashboard


class ServeDashboardTests(unittest.TestCase):
    def create_access_log_root(self) -> Path:
        test_dir = serve_dashboard.PROJECT_ROOT / "tests" / ".tmp" / f"serve-dashboard-access-log-{uuid.uuid4()}"
        test_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(test_dir, ignore_errors=True))
        return test_dir

    def create_lock_path(self) -> Path:
        test_dir = serve_dashboard.PROJECT_ROOT / ".runtime" / "test_serve_dashboard" / str(uuid.uuid4())
        test_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(test_dir, ignore_errors=True))
        return test_dir / ".daily_update.lock"

    def create_source_file(self, directory: Path, name: str, content: str) -> Path:
        path = directory / name
        path.write_text(content, encoding="utf-8")
        return path

    def wait_for(self, predicate, timeout: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.05)
        return predicate()

    def read_access_log_entries(self, root: Path) -> list[dict]:
        log_files = sorted(root.glob("visits-*.jsonl"))
        payloads: list[dict] = []
        for log_file in log_files:
            for line in log_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    payloads.append(json.loads(line))
        return payloads

    def test_resolve_client_ip_prefers_forwarded_headers(self) -> None:
        class DummyHeaders(dict):
            def get(self, key, default=None):
                return super().get(key, default)

        headers = DummyHeaders(
            {
                "CF-Connecting-IP": "203.0.113.8",
                "X-Forwarded-For": "198.51.100.10, 10.0.0.1",
                "X-Real-IP": "192.0.2.5",
            }
        )

        client_ip, remote_addr, forwarded_for = serve_dashboard.resolve_client_ip(headers, ("127.0.0.1", 4173))

        self.assertEqual(client_ip, "203.0.113.8")
        self.assertEqual(remote_addr, "127.0.0.1")
        self.assertEqual(forwarded_for, "198.51.100.10, 10.0.0.1")

    def test_update_task_manager_rejects_duplicate_start_without_deadlock(self) -> None:
        started_event = threading.Event()
        release_event = threading.Event()

        def fake_run_update(*, log):
            log("fake running")
            started_event.set()
            self.assertTrue(release_event.wait(timeout=2))
            return {"businessDate": "2026-04-20"}

        lock_path = self.create_lock_path()
        manager = serve_dashboard.UpdateTaskManager(auto_publish=False)
        with patch("scripts.serve_dashboard.build_lock_path", return_value=lock_path), patch(
            "scripts.serve_dashboard.build_current_dashboard_result",
            return_value=None,
        ), patch(
            "scripts.serve_dashboard.run_update",
            side_effect=fake_run_update,
        ):
            started, first_snapshot = manager.start()
            self.assertTrue(started)
            self.assertTrue(first_snapshot["running"])
            self.assertEqual(first_snapshot["status"], "running")
            self.assertTrue(started_event.wait(timeout=1))

            started_again, second_snapshot = manager.start()
            self.assertFalse(started_again)
            self.assertTrue(second_snapshot["running"])
            self.assertEqual(second_snapshot["status"], "running")

            release_event.set()
            self.assertTrue(self.wait_for(lambda: manager.snapshot()["status"] == "success"))
            self.assertFalse(manager.snapshot()["running"])

    def test_update_task_manager_reports_external_lock_conflict(self) -> None:
        lock_path = self.create_lock_path()
        blocker = serve_dashboard.ScheduledUpdateLock(lock_path)
        self.assertTrue(
            blocker.acquire(
                {
                    "mode": "silent",
                    "startedAt": "2026-04-24T09:00:00",
                    "businessDate": "2026-04-23",
                }
            )
        )
        self.addCleanup(blocker.release)

        manager = serve_dashboard.UpdateTaskManager(auto_publish=False)
        with patch("scripts.serve_dashboard.build_lock_path", return_value=lock_path):
            started, snapshot = manager.start()

        self.assertFalse(started)
        self.assertEqual(snapshot["status"], "busy")
        self.assertIn("检测到已有更新任务正在执行", snapshot["message"])

    def test_update_task_manager_skips_fetch_when_dashboard_is_current(self) -> None:
        lock_path = self.create_lock_path()
        leads_path = self.create_source_file(lock_path.parent, "NEV+ICE_xsai.xlsm", "leads")
        arrival_path = self.create_source_file(lock_path.parent, "NEV+ICE_ldai.xlsx", "arrival")
        summary_path = lock_path.parent / "dashboard.summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "reportDate": "2026-04-29",
                    "inputs": {
                        "workbookModifiedAt": serve_dashboard.datetime.fromtimestamp(leads_path.stat().st_mtime).isoformat(timespec="seconds"),
                        "arrivalWorkbookModifiedAt": serve_dashboard.datetime.fromtimestamp(arrival_path.stat().st_mtime).isoformat(timespec="seconds"),
                    },
                }
            ),
            encoding="utf-8",
        )

        manager = serve_dashboard.UpdateTaskManager()
        with patch("scripts.serve_dashboard.build_lock_path", return_value=lock_path), patch(
            "scripts.serve_dashboard.DASHBOARD_SUMMARY_PATH",
            summary_path,
        ), patch(
            "scripts.serve_dashboard.LEADS_WORKBOOK_PATH",
            leads_path,
        ), patch(
            "scripts.serve_dashboard.ARRIVAL_WORKBOOK_PATH",
            arrival_path,
        ), patch(
            "scripts.serve_dashboard.parse_business_date",
            return_value=serve_dashboard.date(2026, 4, 29),
        ), patch(
            "scripts.serve_dashboard.run_update",
        ) as run_update_mock, patch(
            "scripts.serve_dashboard.run_publish_step",
            return_value={
                "publishStatus": "success",
                "publishRemote": "origin",
                "publishBranch": "main",
                "publishCommitMessage": "Manual publish test",
            },
        ) as publish_mock:
            started, snapshot = manager.start()
            self.assertTrue(started)
            self.assertEqual(snapshot["status"], "running")
            self.assertTrue(self.wait_for(lambda: manager.snapshot()["status"] == "success"))

        run_update_mock.assert_not_called()
        publish_mock.assert_called_once()
        completed = manager.snapshot()
        self.assertTrue(completed["result"]["skippedRefresh"])
        self.assertEqual(completed["result"]["businessDate"], "2026-04-29")

    def test_update_task_manager_does_not_skip_when_current_workbook_changed(self) -> None:
        lock_path = self.create_lock_path()
        leads_path = self.create_source_file(lock_path.parent, "NEV+ICE_xsai.xlsm", "leads-newer")
        arrival_path = self.create_source_file(lock_path.parent, "NEV+ICE_ldai.xlsx", "arrival")
        summary_path = lock_path.parent / "dashboard.summary.json"
        stale_leads_mtime = "2026-05-02T00:30:33"
        summary_path.write_text(
            json.dumps(
                {
                    "reportDate": "2026-05-01",
                    "inputs": {
                        "workbookModifiedAt": stale_leads_mtime,
                        "arrivalWorkbookModifiedAt": serve_dashboard.datetime.fromtimestamp(arrival_path.stat().st_mtime).isoformat(timespec="seconds"),
                    },
                }
            ),
            encoding="utf-8",
        )

        manager = serve_dashboard.UpdateTaskManager(auto_publish=False)
        with patch("scripts.serve_dashboard.build_lock_path", return_value=lock_path), patch(
            "scripts.serve_dashboard.DASHBOARD_SUMMARY_PATH",
            summary_path,
        ), patch(
            "scripts.serve_dashboard.LEADS_WORKBOOK_PATH",
            leads_path,
        ), patch(
            "scripts.serve_dashboard.ARRIVAL_WORKBOOK_PATH",
            arrival_path,
        ), patch(
            "scripts.serve_dashboard.parse_business_date",
            return_value=serve_dashboard.date(2026, 5, 1),
        ), patch(
            "scripts.serve_dashboard.run_update",
            return_value={"businessDate": "2026-05-01", "dashboardChanged": True, "summaryChanged": True},
        ) as run_update_mock:
            started, snapshot = manager.start()
            self.assertTrue(started)
            self.assertEqual(snapshot["status"], "running")
            self.assertTrue(self.wait_for(lambda: manager.snapshot()["status"] == "success"))

        run_update_mock.assert_called_once()
        completed = manager.snapshot()
        self.assertFalse(completed["result"].get("skippedRefresh", False))
        self.assertEqual(completed["result"]["businessDate"], "2026-05-01")

    def test_update_api_reports_manual_fallback_moved(self) -> None:
        with ThreadingHTTPServer(("127.0.0.1", 0), serve_dashboard.DashboardHandler) as httpd:
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()
            base_url = f"http://127.0.0.1:{httpd.server_port}"

            try:
                with urlopen(f"{base_url}/api/update-status", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertFalse(payload["available"])
                self.assertIn("附魔工作台", payload["message"])

                request = Request(f"{base_url}/api/update-data", method="POST", data=b"")
                with self.assertRaises(Exception) as context:
                    urlopen(request, timeout=2)
                self.assertIn("HTTP Error 409", str(context.exception))
            finally:
                httpd.shutdown()
                server_thread.join(timeout=2)

    def test_dashboard_data_endpoint_returns_payload(self) -> None:
        with ThreadingHTTPServer(("127.0.0.1", 0), serve_dashboard.DashboardHandler) as httpd:
            httpd.cors_allow_origins = ("*",)
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()
            base_url = f"http://127.0.0.1:{httpd.server_port}"

            try:
                with urlopen(f"{base_url}/api/dashboard-data", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertIn("meta", payload)
                self.assertIn("dashboards", payload)
            finally:
                httpd.shutdown()
                server_thread.join(timeout=2)

    def test_dashboard_data_endpoint_supports_archived_month(self) -> None:
        temp_dir = serve_dashboard.PROJECT_ROOT / "tests" / ".tmp" / f"serve-dashboard-archive-{uuid.uuid4()}"
        archive_dir = temp_dir / "monthly" / "2026-04"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_payload = {"meta": {"reportDate": "2026-04-30"}, "dashboards": {"brief": {"id": "brief"}}}
        (archive_dir / "dashboard.json").write_text(json.dumps(archive_payload), encoding="utf-8")
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

        with patch("scripts.serve_dashboard.MONTHLY_ARCHIVE_DIR", temp_dir / "monthly"):
            with ThreadingHTTPServer(("127.0.0.1", 0), serve_dashboard.DashboardHandler) as httpd:
                httpd.cors_allow_origins = ("*",)
                server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                server_thread.start()
                base_url = f"http://127.0.0.1:{httpd.server_port}"

                try:
                    with urlopen(f"{base_url}/api/dashboard-data?month=2026-04", timeout=2) as response:
                        self.assertEqual(response.status, 200)
                        payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(payload["meta"]["reportDate"], "2026-04-30")
                finally:
                    httpd.shutdown()
                    server_thread.join(timeout=2)

    def test_dashboard_archive_endpoint_returns_index_payload(self) -> None:
        temp_dir = serve_dashboard.PROJECT_ROOT / "tests" / ".tmp" / f"serve-dashboard-index-{uuid.uuid4()}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        archive_index_path = temp_dir / "index.json"
        archive_index_path.write_text(
            json.dumps(
                {
                    "latestMonth": "2026-04",
                    "months": [{"key": "2026-04", "label": "2026 年 4 月"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

        with patch("scripts.serve_dashboard.MONTHLY_ARCHIVE_INDEX_PATH", archive_index_path):
            with ThreadingHTTPServer(("127.0.0.1", 0), serve_dashboard.DashboardHandler) as httpd:
                httpd.cors_allow_origins = ("*",)
                server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                server_thread.start()
                base_url = f"http://127.0.0.1:{httpd.server_port}"

                try:
                    with urlopen(f"{base_url}/api/dashboard-archive", timeout=2) as response:
                        self.assertEqual(response.status, 200)
                        payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(payload["latestMonth"], "2026-04")
                    self.assertEqual(payload["months"][0]["key"], "2026-04")
                finally:
                    httpd.shutdown()
                    server_thread.join(timeout=2)

    def test_archive_current_month_opens_source_month_on_first_day(self) -> None:
        temp_dir = serve_dashboard.PROJECT_ROOT / "tests" / ".tmp" / f"serve-dashboard-save-archive-{uuid.uuid4()}"
        docs_dir = temp_dir / "docs"
        data_dir = docs_dir / "data"
        monthly_dir = data_dir / "monthly"
        data_dir.mkdir(parents=True, exist_ok=True)
        dashboard_path = data_dir / "dashboard.json"
        summary_path = data_dir / "dashboard.summary.json"
        index_path = monthly_dir / "index.json"
        dashboard_path.write_text(
            json.dumps(
                {
                    "meta": {
                        "reportDate": "2026-05-31",
                        "reportDateLabel": "2026-05-31",
                        "workbookModifiedAt": "2026-06-01T09:07:16",
                    },
                    "dashboards": {"brief": {"id": "brief"}},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        summary_path.write_text(
            json.dumps(
                {
                    "generatedAt": "2026-06-01T09:08:00",
                    "reportDate": "2026-05-31",
                    "reportDateLabel": "2026-05-31",
                    "inputs": {"workbookModifiedAt": "2026-06-01T09:07:16"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))

        with patch("scripts.serve_dashboard.DOCS_DIR", docs_dir), patch(
            "scripts.serve_dashboard.DASHBOARD_JSON_PATH", dashboard_path
        ), patch("scripts.serve_dashboard.DASHBOARD_SUMMARY_PATH", summary_path), patch(
            "scripts.serve_dashboard.MONTHLY_ARCHIVE_DIR", monthly_dir
        ), patch("scripts.serve_dashboard.MONTHLY_ARCHIVE_INDEX_PATH", index_path):
            result = serve_dashboard.archive_current_dashboard_month()

        self.assertEqual(result["archivedMonthKey"], "2026-05")
        self.assertEqual(result["openMonthKey"], "2026-06")
        self.assertTrue(result["newMonthOpened"])
        self.assertTrue((monthly_dir / "2026-05" / "dashboard.json").exists())
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(index_payload["latestMonth"], "2026-06")
        self.assertEqual(index_payload["months"][0]["key"], "2026-06")
        self.assertEqual(index_payload["months"][0]["dashboardPath"], "./data/dashboard.json")

    def test_options_request_includes_cors_headers(self) -> None:
        with ThreadingHTTPServer(("127.0.0.1", 0), serve_dashboard.DashboardHandler) as httpd:
            httpd.cors_allow_origins = ("https://django604.github.io",)
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()
            base_url = f"http://127.0.0.1:{httpd.server_port}"

            try:
                request = Request(f"{base_url}/api/update-data", method="OPTIONS")
                request.add_header("Origin", "https://django604.github.io")
                with urlopen(request, timeout=2) as response:
                    self.assertEqual(response.status, 204)
                    self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://django604.github.io")
                    self.assertIn("POST", response.headers.get("Access-Control-Allow-Methods", ""))
            finally:
                httpd.shutdown()
                server_thread.join(timeout=2)

    def test_page_visit_is_logged_without_frontend_output(self) -> None:
        access_log_root = self.create_access_log_root()
        with ThreadingHTTPServer(("127.0.0.1", 0), serve_dashboard.DashboardHandler) as httpd:
            httpd.cors_allow_origins = ("*",)
            httpd.access_log_enabled = True
            httpd.access_log_root = access_log_root
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()
            base_url = f"http://127.0.0.1:{httpd.server_port}"

            try:
                request = Request(f"{base_url}/AI_Digest", headers={"User-Agent": "serve-dashboard-test"})
                with urlopen(request, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                self.assertTrue(self.wait_for(lambda: len(self.read_access_log_entries(access_log_root)) == 1))
                entries = self.read_access_log_entries(access_log_root)
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["path"], "/AI_Digest")
                self.assertEqual(entries[0]["clientIp"], "127.0.0.1")
                self.assertEqual(entries[0]["userAgent"], "serve-dashboard-test")
                self.assertEqual(entries[0]["statusCode"], 200)
            finally:
                httpd.shutdown()
                server_thread.join(timeout=2)

    def test_static_asset_and_update_status_do_not_pollute_access_log(self) -> None:
        access_log_root = self.create_access_log_root()
        with ThreadingHTTPServer(("127.0.0.1", 0), serve_dashboard.DashboardHandler) as httpd:
            httpd.cors_allow_origins = ("*",)
            httpd.access_log_enabled = True
            httpd.access_log_root = access_log_root
            server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            server_thread.start()
            base_url = f"http://127.0.0.1:{httpd.server_port}"

            try:
                with urlopen(f"{base_url}/assets/app.js", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                with urlopen(f"{base_url}/api/update-status", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                entries = self.read_access_log_entries(access_log_root)
                self.assertEqual(entries, [])
            finally:
                httpd.shutdown()
                server_thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
