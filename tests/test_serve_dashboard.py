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
    def create_lock_path(self) -> Path:
        test_dir = serve_dashboard.PROJECT_ROOT / ".runtime" / "test_serve_dashboard" / str(uuid.uuid4())
        test_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(test_dir, ignore_errors=True))
        return test_dir / ".daily_update.lock"

    def wait_for(self, predicate, timeout: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.05)
        return predicate()

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

    def test_update_api_reports_status_and_can_trigger_update(self) -> None:
        started_event = threading.Event()
        release_event = threading.Event()

        def fake_run_update(*, log):
            log("fake api run")
            started_event.set()
            self.assertTrue(release_event.wait(timeout=2))
            return {
                "businessDate": "2026-04-20",
                "dashboardChanged": True,
                "summaryChanged": True,
            }

        original_manager = serve_dashboard.DashboardHandler.update_manager

        try:
            lock_path = self.create_lock_path()
            serve_dashboard.DashboardHandler.update_manager = serve_dashboard.UpdateTaskManager()
            with patch("scripts.serve_dashboard.build_lock_path", return_value=lock_path), patch(
                "scripts.serve_dashboard.run_update",
                side_effect=fake_run_update,
            ), patch(
                "scripts.serve_dashboard.run_publish_step",
                return_value={
                    "publishStatus": "success",
                    "publishRemote": "origin",
                    "publishBranch": "main",
                    "publishCommitMessage": "Manual publish test",
                },
            ) as publish_mock:
                with ThreadingHTTPServer(("127.0.0.1", 0), serve_dashboard.DashboardHandler) as httpd:
                    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                    server_thread.start()
                    base_url = f"http://127.0.0.1:{httpd.server_port}"

                    with urlopen(f"{base_url}/api/update-status", timeout=2) as response:
                        self.assertEqual(response.status, 200)
                        payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(payload["status"], "idle")
                    self.assertFalse(payload["running"])

                    request = Request(f"{base_url}/api/update-data", method="POST", data=b"")
                    with urlopen(request, timeout=2) as response:
                        self.assertEqual(response.status, 202)
                        payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(payload["status"], "running")
                    self.assertTrue(started_event.wait(timeout=1))

                    with urlopen(f"{base_url}/api/update-status", timeout=2) as response:
                        running_payload = json.loads(response.read().decode("utf-8"))
                    self.assertTrue(running_payload["running"])

                    release_event.set()
                    self.assertTrue(
                        self.wait_for(
                            lambda: json.loads(urlopen(f"{base_url}/api/update-status", timeout=2).read().decode("utf-8"))[
                                "status"
                            ]
                            == "success"
                        )
                    )

                    with urlopen(f"{base_url}/api/update-status", timeout=2) as response:
                        completed_payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(completed_payload["status"], "success")
                    self.assertEqual(completed_payload["result"]["businessDate"], "2026-04-20")
                    self.assertEqual(completed_payload["result"]["publishStatus"], "success")
                    self.assertEqual(completed_payload["result"]["publishRemote"], "origin")
                    self.assertTrue(publish_mock.called)

                    httpd.shutdown()
                    server_thread.join(timeout=2)
        finally:
            serve_dashboard.DashboardHandler.update_manager = original_manager

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


if __name__ == "__main__":
    unittest.main()
