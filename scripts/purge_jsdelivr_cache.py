#!/usr/bin/env python3
"""Purge jsDelivr cache entries for the public files under ``docs/``."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCS_DIR = PROJECT_ROOT / "docs"
DEFAULT_REPOSITORY = "Django604/AI_Digest"
DEFAULT_REF = "main"
PURGE_API_ROOT = "https://purge.jsdelivr.net/gh"
DEFAULT_ATTEMPTS = 3
DEFAULT_TIMEOUT_SECONDS = 20.0

CRITICAL_FILES = frozenset(
    {
        "docs/index.svg",
        "docs/assets/app.js",
        "docs/assets/styles.css",
        "docs/data/dashboard.json",
        "docs/data/dashboard.summary.json",
        "docs/data/monthly/index.json",
    }
)
MONTHLY_CRITICAL_NAMES = frozenset({"dashboard.json", "dashboard.summary.json"})
TRANSIENT_HTTP_CODES = frozenset({408, 409, 425, 429})
DASHBOARD_PURGE_PATHS = (
    "docs/index.svg",
    "docs/assets/app.js",
    "docs/assets/styles.css",
    "docs/data/dashboard.json",
    "docs/data/dashboard.summary.json",
    "docs/data/monthly/index.json",
)


@dataclass(frozen=True)
class PurgeResult:
    repo_path: str
    url: str
    success: bool
    attempts: int
    error: str = ""
    throttled: bool = False


def enumerate_docs_files(docs_dir: Path) -> list[str]:
    """Return sorted repository paths for every public file in ``docs_dir``."""
    docs_dir = docs_dir.resolve()
    if not docs_dir.is_dir():
        raise FileNotFoundError(f"docs directory does not exist: {docs_dir}")

    return sorted(
        f"docs/{path.relative_to(docs_dir).as_posix()}"
        for path in docs_dir.rglob("*")
        if path.is_file()
    )


def build_dashboard_purge_paths(docs_dir: Path = DEFAULT_DOCS_DIR) -> list[str]:
    """Return the focused cache paths needed after a dashboard publish."""
    repo_paths = list(DASHBOARD_PURGE_PATHS)
    index_path = docs_dir / "data" / "monthly" / "index.json"
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}

    latest_month = str(payload.get("latestMonth") or "").strip()
    if (
        len(latest_month) == 7
        and latest_month[:4].isdigit()
        and latest_month[4] == "-"
        and latest_month[5:].isdigit()
    ):
        month_number = int(latest_month[5:])
        if 1 <= month_number <= 12:
            repo_paths.extend(
                [
                    f"docs/data/monthly/{latest_month}/dashboard.json",
                    f"docs/data/monthly/{latest_month}/dashboard.summary.json",
                ]
            )

    return sorted(set(repo_paths))


def build_purge_url(
    repo_path: str,
    *,
    repository: str = DEFAULT_REPOSITORY,
    ref: str = DEFAULT_REF,
) -> str:
    """Build a jsDelivr purge URL with safely encoded repository components."""
    repository_parts = [part for part in repository.strip("/").split("/") if part]
    if len(repository_parts) != 2:
        raise ValueError("repository must use the owner/name format")
    if not ref.strip():
        raise ValueError("ref must not be empty")

    encoded_repository = "/".join(quote(part, safe="") for part in repository_parts)
    encoded_ref = quote(ref.strip(), safe="")
    encoded_path = quote(repo_path.lstrip("/"), safe="/")
    return f"{PURGE_API_ROOT}/{encoded_repository}@{encoded_ref}/{encoded_path}"


def is_critical_file(repo_path: str) -> bool:
    if repo_path in CRITICAL_FILES:
        return True
    path = Path(repo_path)
    return (
        repo_path.startswith("docs/data/monthly/")
        and path.name in MONTHLY_CRITICAL_NAMES
    )


def _request_purge(url: str, timeout: float) -> str:
    request = Request(
        url,
        headers={"User-Agent": "AI-Digest-jsDelivr-purge/1.0"},
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        status = response.getcode()
        body = response.read().decode("utf-8", errors="replace")
    if not 200 <= status < 300:
        raise RuntimeError(f"unexpected HTTP status {status}: {body[:300]}")
    return body


def _validate_purge_payload(body: str) -> tuple[bool, str, bool]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        return False, f"invalid JSON response: {exc}", False

    if payload.get("status") != "finished":
        return False, f"unexpected purge status: {payload.get('status')!r}", False

    paths = payload.get("paths")
    if not isinstance(paths, dict) or not paths:
        return False, "purge response does not contain path results", False

    path_result = next(iter(paths.values()))
    if not isinstance(path_result, dict):
        return False, "purge path result has an invalid format", False
    if path_result.get("throttled"):
        return True, "", True

    providers = path_result.get("providers")
    if not isinstance(providers, dict) or not providers:
        return False, "purge response does not contain provider results", False
    failed_providers = sorted(name for name, succeeded in providers.items() if succeeded is not True)
    if failed_providers:
        return False, f"providers failed: {', '.join(failed_providers)}", False

    return True, "", False


def _http_error_is_transient(exc: HTTPError) -> bool:
    return exc.code in TRANSIENT_HTTP_CODES or 500 <= exc.code < 600


def purge_file(
    repo_path: str,
    *,
    repository: str = DEFAULT_REPOSITORY,
    ref: str = DEFAULT_REF,
    attempts: int = DEFAULT_ATTEMPTS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retry_delay: float = 1.0,
    request_func: Callable[[str, float], str] = _request_purge,
    sleep_func: Callable[[float], None] = time.sleep,
) -> PurgeResult:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if timeout <= 0:
        raise ValueError("timeout must be greater than 0")

    url = build_purge_url(repo_path, repository=repository, ref=ref)
    last_error = "unknown purge failure"

    for attempt in range(1, attempts + 1):
        retryable = True
        try:
            body = request_func(url, timeout)
            success, error, throttled = _validate_purge_payload(body)
            if success:
                return PurgeResult(repo_path, url, True, attempt, throttled=throttled)
            last_error = error
        except HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            last_error = f"HTTP {exc.code}: {response_body[:300] or exc.reason}"
            retryable = _http_error_is_transient(exc)
        except (URLError, TimeoutError, OSError) as exc:
            last_error = f"network error: {exc}"
        except RuntimeError as exc:
            last_error = str(exc)

        if not retryable or attempt == attempts:
            return PurgeResult(repo_path, url, False, attempt, last_error)
        sleep_func(retry_delay * attempt)

    return PurgeResult(repo_path, url, False, attempts, last_error)


def run_purge(
    *,
    docs_dir: Path = DEFAULT_DOCS_DIR,
    repo_paths: Sequence[str] | None = None,
    repository: str = DEFAULT_REPOSITORY,
    ref: str = DEFAULT_REF,
    attempts: int = DEFAULT_ATTEMPTS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    log: Callable[[str], None] = print,
    request_func: Callable[[str, float], str] = _request_purge,
    sleep_func: Callable[[float], None] = time.sleep,
) -> int:
    if repo_paths is None:
        try:
            resolved_repo_paths = enumerate_docs_files(docs_dir)
        except FileNotFoundError as exc:
            log(f"[FAIL] {exc}")
            return 1
    else:
        resolved_repo_paths = sorted(
            {
                str(path).replace("\\", "/").lstrip("/")
                for path in repo_paths
                if str(path).strip()
            }
        )

    if not resolved_repo_paths:
        log(f"[FAIL] no public files found under {docs_dir}")
        return 1

    results: list[PurgeResult] = []
    for repo_path in resolved_repo_paths:
        result = purge_file(
            repo_path,
            repository=repository,
            ref=ref,
            attempts=attempts,
            timeout=timeout,
            request_func=request_func,
            sleep_func=sleep_func,
        )
        results.append(result)
        if result.throttled:
            log(f"[THROTTLED] {repo_path} (cache was purged recently)")
        elif result.success:
            log(f"[OK] {repo_path} (attempts={result.attempts})")
        else:
            log(f"[FAIL] {repo_path} (attempts={result.attempts}) {result.error}")
            log(f"       {result.url}")

    failures = [result for result in results if not result.success]
    throttled_results = [result for result in results if result.throttled]
    critical_failures = [result for result in failures if is_critical_file(result.repo_path)]
    log(
        "Summary: "
        f"total={len(results)} "
        f"succeeded={len(results) - len(failures)} "
        f"failed={len(failures)} "
        f"critical_failed={len(critical_failures)} "
        f"throttled={len(throttled_results)}"
    )

    if critical_failures:
        log("Critical jsDelivr entries failed to purge; stopping the release workflow.")
        return 1
    if failures:
        log("Non-critical jsDelivr entries failed to purge; review the URLs above.")
    return 0


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS_DIR)
    parser.add_argument("--repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--ref", default=DEFAULT_REF)
    parser.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    if args.attempts < 1:
        parser.error("--attempts must be at least 1")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    return run_purge(
        docs_dir=args.docs_dir,
        repository=args.repository,
        ref=args.ref,
        attempts=args.attempts,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
