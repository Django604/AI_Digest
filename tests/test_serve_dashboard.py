from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from unittest.mock import patch

from scripts import serve_dashboard


class ServeDashboardTests(unittest.TestCase):
    def wait_for(self, predicate, timeout: float = 3.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.05)
        return predicate()

    def test_update_task_manager_rejects_duplicate_start_without_deadlock(self) -> None:
        manager = serve_dashboard.UpdateTaskManager()
        started_event = threading.Event()
        release_event = threading.Event()

        def fake_run_update(*, log):
            log("fake running")
            started_event.set()
            self.assertTrue(release_event.wait(timeout=2))
            return {"businessDate": "2026-04-20"}

        with patch("scripts.serve_dashboard.run_update", side_effect=fake_run_update):
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

    def test_update_api_reports_status_and_can_trigger_update(self) -> None:
        started_event = threading.Event()
        release_event = threading.Event()

        def fake_run_update(*, log):
            log("fake api run")
            started_event.set()
            self.assertTrue(release_event.wait(timeout=2))
            return {"businessDate": "2026-04-20"}

        original_manager = serve_dashboard.DashboardHandler.update_manager
        serve_dashboard.DashboardHandler.update_manager = serve_dashboard.UpdateTaskManager()

        try:
            with patch("scripts.serve_dashboard.run_update", side_effect=fake_run_update):
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

                    httpd.shutdown()
                    server_thread.join(timeout=2)
        finally:
            serve_dashboard.DashboardHandler.update_manager = original_manager


if __name__ == "__main__":
    unittest.main()
