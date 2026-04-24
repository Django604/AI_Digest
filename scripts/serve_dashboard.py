from __future__ import annotations

import argparse
import functools
import json
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse

try:
    from .fetch_daily_data import format_business_date, parse_business_date, run_update
    from .scheduled_update_runner import ScheduledUpdateLock, build_lock_path, run_publish_step
except ImportError:  # pragma: no cover - script entrypoint fallback
    from fetch_daily_data import format_business_date, parse_business_date, run_update
    from scheduled_update_runner import ScheduledUpdateLock, build_lock_path, run_publish_step


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
DASHBOARD_JSON_PATH = DOCS_DIR / "data" / "dashboard.json"
DASHBOARD_SUMMARY_PATH = DOCS_DIR / "data" / "dashboard.summary.json"
MANUAL_UPDATE_MODE = "manual-web"


def build_idle_message(auto_publish: bool) -> str:
    if auto_publish:
        return "手动兜底更新服务已就绪，完成后会自动发布到 GitHub。"
    return "手动兜底更新服务已就绪。"


def build_running_message(auto_publish: bool) -> str:
    if auto_publish:
        return "手动兜底更新已启动，正在抓取数据并准备自动发布。"
    return "手动兜底更新已启动，正在抓取数据。"


def build_success_message(result: dict[str, object], auto_publish: bool) -> str:
    business_date = str(result.get("businessDate") or "")
    publish_status = str(result.get("publishStatus") or "disabled")
    if auto_publish and publish_status == "success":
        return f"手动兜底更新完成，业务日期：{business_date}，并已自动发布到 GitHub。"
    return f"手动兜底更新完成，业务日期：{business_date}。"


def summarize_external_lock(lock_details: str) -> str:
    if not lock_details.strip():
        return "检测到已有更新任务正在执行，请等当前任务结束后再手动补跑。"

    try:
        payload = json.loads(lock_details)
    except json.JSONDecodeError:
        return f"检测到已有更新任务正在执行，请稍后重试。锁信息：{lock_details}"

    mode = str(payload.get("mode") or "")
    started_at = str(payload.get("startedAt") or "")
    business_date = str(payload.get("businessDate") or "")

    mode_label = {
        "silent": "静默定时任务",
        "interactive": "交互定时任务",
        MANUAL_UPDATE_MODE: "网页手动补跑",
    }.get(mode, mode or "未知任务")

    details: list[str] = [f"来源：{mode_label}"]
    if business_date:
        details.append(f"业务日期：{business_date}")
    if started_at:
        details.append(f"开始时间：{started_at}")
    return "检测到已有更新任务正在执行，请等当前任务结束后再手动补跑。" + "（" + "；".join(details) + "）"


class UpdateTaskManager:
    def __init__(
        self,
        *,
        auto_publish: bool = True,
        publish_remote: str = "origin",
        publish_branch: str = "main",
        publish_commit_message: str = "",
    ) -> None:
        self._lock = threading.Lock()
        self._shared_lock: ScheduledUpdateLock | None = None
        self._auto_publish = auto_publish
        self._publish_remote = publish_remote
        self._publish_branch = publish_branch
        self._publish_commit_message = publish_commit_message
        self._state = {
            "available": True,
            "running": False,
            "status": "idle",
            "message": build_idle_message(auto_publish),
            "result": None,
            "error": "",
            "updatedAt": None,
        }

    def snapshot(self) -> dict:
        with self._lock:
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> dict:
        return json.loads(json.dumps(self._state, ensure_ascii=False))

    def start(self) -> tuple[bool, dict]:
        with self._lock:
            if self._state["running"]:
                snapshot = self._snapshot_unlocked()
                return False, snapshot

        started_at = datetime.now()
        business_date = parse_business_date()
        shared_lock = ScheduledUpdateLock(build_lock_path())
        lock_metadata = {
            "mode": MANUAL_UPDATE_MODE,
            "startedAt": started_at.isoformat(timespec="seconds"),
            "businessDate": format_business_date(business_date),
            "source": "serve_dashboard",
        }
        if not shared_lock.acquire(lock_metadata):
            lock_details = shared_lock.read_metadata()
            with self._lock:
                self._state.update(
                    {
                        "running": False,
                        "status": "busy",
                        "message": summarize_external_lock(lock_details),
                        "result": None,
                        "error": "",
                        "updatedAt": started_at.isoformat(timespec="seconds"),
                    }
                )
                snapshot = self._snapshot_unlocked()
            return False, snapshot

        with self._lock:
            self._shared_lock = shared_lock
            self._state.update(
                {
                    "running": True,
                    "status": "running",
                    "message": build_running_message(self._auto_publish),
                    "result": None,
                    "error": "",
                    "updatedAt": started_at.isoformat(timespec="seconds"),
                }
            )
            snapshot = self._snapshot_unlocked()

        worker = threading.Thread(target=self._run, daemon=True, name="ai-digest-update")
        worker.start()
        return True, snapshot

    def log(self, message: str) -> None:
        with self._lock:
            self._state["message"] = message
            self._state["updatedAt"] = datetime.now().isoformat(timespec="seconds")

    def _run(self) -> None:
        partial_result: dict[str, object] | None = None
        try:
            result = run_update(log=self.log)
            partial_result = result
            if self._auto_publish:
                publish_result = run_publish_step(
                    business_date=str(result.get("businessDate") or ""),
                    mode=MANUAL_UPDATE_MODE,
                    remote=self._publish_remote,
                    branch=self._publish_branch,
                    commit_message=self._publish_commit_message,
                    log=self.log,
                )
                result = {**result, **publish_result}
            else:
                result = {**result, "publishStatus": "disabled"}
        except Exception as exc:
            with self._lock:
                error_message = f"手动兜底更新失败：{exc}"
                result_payload = None
                if partial_result is not None and self._auto_publish:
                    error_message = f"数据已更新，但自动发布失败：{exc}"
                    result_payload = {
                        **partial_result,
                        "publishStatus": "error",
                        "publishRemote": self._publish_remote,
                        "publishBranch": self._publish_branch,
                    }
                self._state.update(
                    {
                        "running": False,
                        "status": "error",
                        "message": error_message,
                        "result": result_payload,
                        "error": str(exc),
                        "updatedAt": datetime.now().isoformat(timespec="seconds"),
                    }
                )
            return
        finally:
            with self._lock:
                shared_lock = self._shared_lock
                self._shared_lock = None
            if shared_lock is not None:
                shared_lock.release()

        with self._lock:
            self._state.update(
                {
                    "running": False,
                    "status": "success",
                    "message": build_success_message(result, self._auto_publish),
                    "result": result,
                    "error": "",
                    "updatedAt": datetime.now().isoformat(timespec="seconds"),
                }
            )


def load_json_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _inside_docs(path: Path) -> bool:
    try:
        path.relative_to(DOCS_DIR)
        return True
    except ValueError:
        return False


class DashboardHandler(SimpleHTTPRequestHandler):
    """Serve docs/ with SPA-style fallback for clean URLs."""

    update_manager = UpdateTaskManager()

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=str(DOCS_DIR if directory is None else directory), **kwargs)

    def _resolve_cors_origin(self) -> str | None:
        allowed = getattr(self.server, "cors_allow_origins", ("*",))
        origin = self.headers.get("Origin")
        if "*" in allowed:
            return "*"
        if origin and origin in allowed:
            return origin
        return None

    def _send_json(self, payload: dict, status_code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        cors_origin = self._resolve_cors_origin()
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            if cors_origin != "*":
                self.send_header("Vary", "Origin")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/update-status":
            self._send_json(self.update_manager.snapshot())
            return
        if parsed.path == "/api/dashboard-data":
            try:
                self._send_json(load_json_payload(DASHBOARD_JSON_PATH))
            except FileNotFoundError:
                self._send_json({"error": f"dashboard data not found: {DASHBOARD_JSON_PATH.name}"}, status_code=404)
            return
        if parsed.path == "/api/dashboard-summary":
            try:
                self._send_json(load_json_payload(DASHBOARD_SUMMARY_PATH))
            except FileNotFoundError:
                self._send_json({"error": f"dashboard summary not found: {DASHBOARD_SUMMARY_PATH.name}"}, status_code=404)
            return
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/update-data":
            started, snapshot = self.update_manager.start()
            self._send_json(snapshot, status_code=202 if started else 409)
            return
        self.send_error(404, "Not Found")

    def send_head(self):
        parsed = urlparse(self.path)
        requested = unquote(parsed.path)
        candidate = (Path(self.directory) / requested.lstrip("/")).resolve()

        if (not _inside_docs(candidate) or not candidate.exists()) and Path(requested).suffix == "":
            self.path = "/index.html"

        return super().send_head()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the AI Digest dashboard with sane defaults.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=4173, help="Port to listen on (default: 4173)")
    publish_group = parser.add_mutually_exclusive_group()
    publish_group.add_argument(
        "--auto-publish",
        dest="auto_publish",
        action="store_true",
        default=True,
        help="Automatically publish workbook/dashboard changes to GitHub after a successful manual update (default: on).",
    )
    publish_group.add_argument(
        "--no-auto-publish",
        dest="auto_publish",
        action="store_false",
        help="Disable automatic GitHub publish after a successful manual update.",
    )
    parser.add_argument("--publish-remote", default="origin", help="Git remote name used by manual auto publish.")
    parser.add_argument("--publish-branch", default="main", help="Git branch name used by manual auto publish.")
    parser.add_argument(
        "--publish-commit-message",
        default="",
        help="Optional git commit message used by manual auto publish.",
    )
    parser.add_argument(
        "--cors-allow-origin",
        action="append",
        default=[],
        help="Allowed CORS origin. Repeat this option to allow multiple origins. Default: *",
    )
    browser_group = parser.add_mutually_exclusive_group()
    browser_group.add_argument(
        "--open-browser",
        dest="open_browser",
        action="store_true",
        default=True,
        help="Automatically open the dashboard in your browser (default: on).",
    )
    browser_group.add_argument(
        "--no-open-browser",
        dest="open_browser",
        action="store_false",
        help="Do not open a browser window after the server starts.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not DOCS_DIR.exists():
        print(f"[serve_dashboard] docs directory not found: {DOCS_DIR}", file=sys.stderr)
        return 1

    DashboardHandler.update_manager = UpdateTaskManager(
        auto_publish=args.auto_publish,
        publish_remote=args.publish_remote,
        publish_branch=args.publish_branch,
        publish_commit_message=args.publish_commit_message,
    )

    handler: Callable[..., DashboardHandler] = functools.partial(DashboardHandler, directory=str(DOCS_DIR))
    try:
        with ThreadingHTTPServer((args.host, args.port), handler) as httpd:
            httpd.cors_allow_origins = tuple(args.cors_allow_origin or ["*"])
            url = f"http://{args.host}:{args.port}"
            print(f"Serving {DOCS_DIR} at {url}")
            print("Clean URLs such as /docs or /AI_Digest fall back to index.html. Press Ctrl+C to exit.")
            print("Update API is available at /api/update-status, /api/update-data, /api/dashboard-data and /api/dashboard-summary.")
            if args.auto_publish:
                print(
                    "Manual update button will auto publish to "
                    f"{args.publish_remote}/{args.publish_branch} after a successful refresh."
                )
            else:
                print("Manual update button will refresh local data only; auto publish is disabled.")
            if args.open_browser:
                webbrowser.open(url)
            httpd.serve_forever()
    except OSError as exc:
        print(f"[serve_dashboard] 无法绑定 {args.host}:{args.port} -> {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
