from __future__ import annotations

import argparse
import functools
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"


def _inside_docs(path: Path) -> bool:
    try:
        path.relative_to(DOCS_DIR)
        return True
    except ValueError:
        return False


class DashboardHandler(SimpleHTTPRequestHandler):
    """Serve docs/ with SPA-style fallback for clean URLs."""

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=str(DOCS_DIR if directory is None else directory), **kwargs)

    def end_headers(self):
        # Always disable browser caching so refreshed workbook data shows up immediately.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

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
