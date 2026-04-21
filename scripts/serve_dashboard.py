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
    from .fetch_daily_data import run_update
except ImportError:  # pragma: no cover - script entrypoint fallback
    from fetch_daily_data import run_update


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"


class UpdateTaskManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = {
            "available": True,
            "running": False,
            "status": "idle",
            "message": "本地更新服务已就绪。",
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
            self._state.update(
                {
                    "running": True,
                    "status": "running",
                    "message": "更新任务已启动，正在准备浏览器取数。",
                    "result": None,
                    "error": "",
                    "updatedAt": datetime.now().isoformat(timespec="seconds"),
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
        try:
            result = run_update(log=self.log)
        except Exception as exc:
            with self._lock:
                self._state.update(
                    {
                        "running": False,
                        "status": "error",
                        "message": f"更新失败：{exc}",
                        "result": None,
                        "error": str(exc),
                        "updatedAt": datetime.now().isoformat(timespec="seconds"),
                    }
                )
            return

        with self._lock:
            self._state.update(
                {
                    "running": False,
                    "status": "success",
                    "message": f"更新完成，业务日期：{result['businessDate']}",
                    "result": result,
                    "error": "",
                    "updatedAt": datetime.now().isoformat(timespec="seconds"),
                }
            )


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
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/update-status":
            self._send_json(self.update_manager.snapshot())
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

    handler: Callable[..., DashboardHandler] = functools.partial(DashboardHandler, directory=str(DOCS_DIR))
    try:
        with ThreadingHTTPServer((args.host, args.port), handler) as httpd:
            url = f"http://{args.host}:{args.port}"
            print(f"Serving {DOCS_DIR} at {url}")
            print("Clean URLs such as /docs or /AI_Digest fall back to index.html. Press Ctrl+C to exit.")
            print("Local update API is available at /api/update-data and /api/update-status.")
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
