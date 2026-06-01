from __future__ import annotations

import argparse
import calendar
import copy
import functools
import json
import sys
import threading
import webbrowser
from datetime import date, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

try:
    from .build_dashboard import build_column_calendar_meta, month_key, write_monthly_archive
    from .dashboard_publish import PublishError, resolve_publish_commit_message
    from .fetch_daily_data import format_business_date, parse_business_date, run_update
    from .scheduled_update_runner import ScheduledUpdateLock, build_lock_path, run_publish_step
except ImportError:  # pragma: no cover - script entrypoint fallback
    from build_dashboard import build_column_calendar_meta, month_key, write_monthly_archive
    from dashboard_publish import PublishError, resolve_publish_commit_message
    from fetch_daily_data import format_business_date, parse_business_date, run_update
    from scheduled_update_runner import ScheduledUpdateLock, build_lock_path, run_publish_step


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
DATA_SOURCE_DIR = PROJECT_ROOT / "data" / "source"
DASHBOARD_JSON_PATH = DOCS_DIR / "data" / "dashboard.json"
DASHBOARD_SUMMARY_PATH = DOCS_DIR / "data" / "dashboard.summary.json"
MONTHLY_ARCHIVE_DIR = DOCS_DIR / "data" / "monthly"
MONTHLY_ARCHIVE_INDEX_PATH = MONTHLY_ARCHIVE_DIR / "index.json"
MANUAL_UPDATE_MODE = "manual-web"
LEADS_WORKBOOK_PATH = DATA_SOURCE_DIR / "NEV+ICE_xsai.xlsm"
ARRIVAL_WORKBOOK_PATH = DATA_SOURCE_DIR / "NEV+ICE_ldai.xlsx"
ACCESS_LOG_ROOT = PROJECT_ROOT / ".runtime" / "access_logs"
ACCESS_LOG_LOCK = threading.Lock()
ACCESS_LOG_API_PATHS = {
    "/api/dashboard-data",
    "/api/dashboard-summary",
    "/api/dashboard-archive",
    "/api/update-data",
}


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
    if result.get("skippedRefresh"):
        if auto_publish and publish_status in {"success", "no_changes"}:
            return f"数据已是最新业务日期：{business_date}，已检查发布链路。"
        return f"数据已是最新业务日期：{business_date}。"
    if auto_publish and publish_status == "success":
        return f"手动兜底更新完成，业务日期：{business_date}，并已自动发布到 GitHub。"
    if auto_publish and publish_status == "no_changes":
        return f"手动兜底更新完成，业务日期：{business_date}，未检测到新的可发布变更。"
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


def build_current_dashboard_result(business_date: date) -> dict[str, object] | None:
    try:
        summary = load_json_payload(DASHBOARD_SUMMARY_PATH)
    except Exception:
        return None

    current_report_date = str(summary.get("reportDate") or "").strip()
    expected_report_date = format_business_date(business_date)
    if current_report_date != expected_report_date:
        return None

    if not summary_inputs_match_current_sources(summary):
        return None

    return {
        "businessDate": expected_report_date,
        "dashboardChanged": False,
        "summaryChanged": False,
        "skippedRefresh": True,
        "skipReason": "dashboard-already-current",
    }


def summary_inputs_match_current_sources(summary: dict[str, object]) -> bool:
    inputs = summary.get("inputs")
    if not isinstance(inputs, dict):
        return False

    expected_mtimes = {
        "workbookModifiedAt": LEADS_WORKBOOK_PATH,
        "arrivalWorkbookModifiedAt": ARRIVAL_WORKBOOK_PATH,
    }
    for key, path in expected_mtimes.items():
        recorded_mtime = str(inputs.get(key) or "").strip()
        if not recorded_mtime:
            return False
        try:
            current_mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            return False
        if recorded_mtime != current_mtime:
            return False
    return True


def normalize_month_key(value: str | None) -> str | None:
    text = str(value or "").strip()
    if len(text) != 7 or text[4] != "-":
        return None
    year_text, month_text = text.split("-", 1)
    if not (year_text.isdigit() and month_text.isdigit()):
        return None
    month_value = int(month_text)
    if not 1 <= month_value <= 12:
        return None
    return f"{int(year_text):04d}-{month_value:02d}"


def resolve_archived_dashboard_path(month_key: str) -> Path:
    return MONTHLY_ARCHIVE_DIR / month_key / "dashboard.json"


def resolve_archived_summary_path(month_key: str) -> Path:
    return MONTHLY_ARCHIVE_DIR / month_key / "dashboard.summary.json"


def parse_iso_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_source_updated_at(payload: dict[str, Any], summary: dict[str, Any]) -> datetime | None:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    inputs = summary.get("inputs") if isinstance(summary.get("inputs"), dict) else {}
    for value in (
        meta.get("workbookModifiedAt"),
        inputs.get("workbookModifiedAt"),
        inputs.get("arrivalWorkbookModifiedAt"),
    ):
        parsed = parse_iso_datetime(value)
        if parsed is not None:
            return parsed
    return None


def build_docs_data_url(path: Path) -> str:
    relative_path = path.resolve().relative_to(DOCS_DIR.resolve())
    return "./" + relative_path.as_posix()


def month_dates_for(value: date) -> list[date]:
    _, last_day = calendar.monthrange(value.year, value.month)
    return [date(value.year, value.month, day) for day in range(1, last_day + 1)]


def previous_month_aligned(value: date) -> date | None:
    previous_year = value.year if value.month > 1 else value.year - 1
    previous_month_value = value.month - 1 if value.month > 1 else 12
    _, previous_last_day = calendar.monthrange(previous_year, previous_month_value)
    if value.day > previous_last_day:
        return None
    return date(previous_year, previous_month_value, value.day)


def format_axis_date(value: date | None) -> str:
    return "-" if value is None else f"{value.month}/{value.day}"


def format_sheet_date(value: date | None) -> str:
    return "-" if value is None else f"{value.year}/{value.month}/{value.day}"


def build_blank_month_payload(payload: dict[str, Any], summary: dict[str, Any], month_date: date) -> dict[str, Any]:
    blank_payload = copy.deepcopy(payload)
    generated_at = str(summary.get("generatedAt") or datetime.now().isoformat(timespec="seconds"))
    month_label = f"{month_date.year} 年 {month_date.month} 月"
    month_start = month_date.replace(day=1)
    month_end_day = calendar.monthrange(month_date.year, month_date.month)[1]
    month_end = month_date.replace(day=month_end_day)

    meta = blank_payload.setdefault("meta", {})
    meta.update(
        {
            "generatedAt": generated_at,
            "reportDate": month_start.isoformat(),
            "reportDateLabel": f"{month_label}待更新",
            "dataRangeStart": month_start.isoformat(),
            "dataRangeEnd": month_end.isoformat(),
            "blankMonth": True,
            "blankMonthReason": "新月份数据尚未刷新。",
        }
    )

    dashboards = blank_payload.get("dashboards")
    if isinstance(dashboards, dict):
        for dashboard in dashboards.values():
            blank_dashboard_for_month(dashboard, month_start)

    return blank_payload


def build_blank_month_summary(summary: dict[str, Any], blank_payload: dict[str, Any], month_date: date) -> dict[str, Any]:
    blank_summary = copy.deepcopy(summary)
    generated_at = str(summary.get("generatedAt") or datetime.now().isoformat(timespec="seconds"))
    month_start = month_date.replace(day=1)
    dashboards = blank_payload.get("dashboards", {})
    analysis = blank_payload.get("analysis", {})
    issues = analysis.get("issues", []) if isinstance(analysis, dict) else []
    blank_summary.update(
        {
            "generatedAt": generated_at,
            "reportDate": month_start.isoformat(),
            "reportDateLabel": f"{month_start.year} 年 {month_start.month} 月待更新",
            "blankMonth": True,
            "warnings": ["新月份数据尚未刷新，当前为占位空白面板。"],
            "stats": {
                "dashboardCount": len(dashboards) if isinstance(dashboards, dict) else 0,
                "sectionCounts": {
                    dashboard_id: len(dashboard.get("sections", []))
                    for dashboard_id, dashboard in dashboards.items()
                    if isinstance(dashboard, dict)
                }
                if isinstance(dashboards, dict)
                else {},
                "sheetCount": analysis.get("sheetCount", 0) if isinstance(analysis, dict) else 0,
                "issueCount": len(issues) if isinstance(issues, list) else 0,
            },
        }
    )
    return blank_summary


def blank_dashboard_for_month(dashboard: Any, month_start: date) -> None:
    if not isinstance(dashboard, dict):
        return

    if dashboard.get("pageType") == "brief" or dashboard.get("id") == "brief":
        dashboard["headline"] = ""
        briefing = dashboard.get("briefing")
        if isinstance(briefing, dict):
            briefing.update(
                {
                    "headline": f"{month_start.month} 月数据待更新",
                    "dateLabel": f"{month_start.month:02d}",
                    "reportDate": month_start.isoformat(),
                    "sections": [],
                    "generatedText": "",
                    "arrivalBrief": {"kind": "arrival", "title": "来店简报", "lines": [], "sourceSheets": []},
                }
            )
        return

    sections = dashboard.get("sections")
    if not isinstance(sections, list):
        return

    for section in sections:
        if not isinstance(section, dict):
            continue
        trend = section.get("trend")
        if isinstance(trend, dict):
            blank_trend_for_month(trend, month_start)


def replace_month_in_title(value: Any, month_start: date) -> Any:
    if not isinstance(value, str):
        return value
    import re

    return re.sub(r"\d{1,2}\s*月", f"{month_start.month}月", value)


def replace_month_strings(value: Any, month_start: date) -> Any:
    if isinstance(value, dict):
        for key, item in list(value.items()):
            value[key] = replace_month_strings(item, month_start)
        return value
    if isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = replace_month_strings(item, month_start)
        return value
    return replace_month_in_title(value, month_start)


def blank_trend_for_month(trend: dict[str, Any], month_start: date) -> None:
    dates = month_dates_for(month_start)
    previous_dates = [previous_month_aligned(item) for item in dates]
    labels = [format_axis_date(item) for item in dates]
    empty_values = ["-"] * len(dates)

    trend["chartTitle"] = replace_month_in_title(trend.get("chartTitle"), month_start)
    trend["tableTitle"] = replace_month_in_title(trend.get("tableTitle"), month_start)

    summary_items = trend.get("summary", {}).get("items")
    if isinstance(summary_items, list):
        for item in summary_items:
            if not isinstance(item, dict):
                continue
            item["value"] = None
            item["displayValue"] = "-"
            if "note" in item:
                item["note"] = ""

    matrix = trend.get("matrix")
    if isinstance(matrix, dict):
        matrix["labels"] = labels
        matrix["columnMeta"] = [
            build_column_calendar_meta(current, previous)
            for current, previous in zip(dates, previous_dates)
        ]
        for row in matrix.get("rows", []):
            if not isinstance(row, dict):
                continue
            row_key = str(row.get("key") or "")
            if row_key == "currentDate":
                row["displayValues"] = [format_sheet_date(item) for item in dates]
            elif row_key == "previousDate":
                row["displayValues"] = [format_sheet_date(item) for item in previous_dates]
            else:
                row["displayValues"] = list(empty_values)

    chart = trend.get("chart")
    if isinstance(chart, dict):
        chart["labels"] = labels
        chart["reportDayIndex"] = 0
        chart["dailyAxisMax"] = 1000
        chart["cumulativeAxisMax"] = 1000
        for key, values in list((chart.get("series") or {}).items()):
            if isinstance(values, list):
                chart["series"][key] = [None] * len(dates)
        chart["note"] = ""

    replace_month_strings(trend, month_start)


def write_json_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_docs_path_from_url(value: object) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith("./"):
        text = text[2:]
    if text.startswith("/"):
        text = text.lstrip("/")
    candidate = (DOCS_DIR / text).resolve()
    try:
        candidate.relative_to(DOCS_DIR.resolve())
    except ValueError:
        return None
    return candidate


def find_archive_entry(month_key_value: str) -> dict[str, Any] | None:
    try:
        archive_index = load_json_payload(MONTHLY_ARCHIVE_INDEX_PATH)
    except FileNotFoundError:
        return None
    for item in archive_index.get("months", []):
        if isinstance(item, dict) and normalize_month_key(str(item.get("key") or "")) == month_key_value:
            return item
    return None


def resolve_dashboard_data_path(month_key_value: str | None, kind: str) -> Path:
    if not month_key_value:
        return DASHBOARD_SUMMARY_PATH if kind == "summary" else DASHBOARD_JSON_PATH

    entry = find_archive_entry(month_key_value)
    path_key = "summaryPath" if kind == "summary" else "dashboardPath"
    if entry:
        candidate = resolve_docs_path_from_url(entry.get(path_key))
        if candidate is not None:
            return candidate

    return resolve_archived_summary_path(month_key_value) if kind == "summary" else resolve_archived_dashboard_path(month_key_value)


def ensure_source_month_entry(
    *,
    source_updated_at: datetime,
    payload: dict[str, Any],
    summary: dict[str, Any],
    current_index: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    source_month = month_key(source_updated_at.date())
    blank_dashboard_path = MONTHLY_ARCHIVE_DIR / source_month / "dashboard.json"
    blank_summary_path = MONTHLY_ARCHIVE_DIR / source_month / "dashboard.summary.json"
    blank_payload = build_blank_month_payload(payload, summary, source_updated_at.date())
    blank_summary = build_blank_month_summary(summary, blank_payload, source_updated_at.date())
    write_json_payload(blank_dashboard_path, blank_payload)
    write_json_payload(blank_summary_path, blank_summary)

    month_entries = [item for item in current_index.get("months", []) if isinstance(item, dict)]
    existing_entry = next((item for item in month_entries if normalize_month_key(str(item.get("key") or "")) == source_month), None)
    if existing_entry:
        current_index["latestMonth"] = source_month
        existing_entry.update(
            {
                "dashboardPath": build_docs_data_url(blank_dashboard_path),
                "summaryPath": build_docs_data_url(blank_summary_path),
                "reportDate": source_updated_at.date().isoformat(),
                "reportDateLabel": f"{source_updated_at.year} 年 {source_updated_at.month} 月待更新",
                "generatedAt": blank_summary.get("generatedAt"),
                "liveSourceMonth": True,
                "blankMonth": True,
            }
        )
        return current_index, False

    month_entries.append(
        {
            "key": source_month,
            "year": source_updated_at.year,
            "month": source_updated_at.month,
            "label": f"{source_updated_at.year} 年 {source_updated_at.month} 月",
            "reportDate": source_updated_at.date().isoformat(),
            "reportDateLabel": f"{source_updated_at.year} 年 {source_updated_at.month} 月待更新",
            "dashboardPath": build_docs_data_url(blank_dashboard_path),
            "summaryPath": build_docs_data_url(blank_summary_path),
            "generatedAt": blank_summary.get("generatedAt"),
            "liveSourceMonth": True,
            "blankMonth": True,
        }
    )
    month_entries.sort(key=lambda item: str(item.get("key") or ""), reverse=True)
    current_index.update(
        {
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "latestMonth": source_month,
            "months": month_entries,
        }
    )
    return current_index, True


def archive_current_dashboard_month() -> dict[str, Any]:
    payload = load_json_payload(DASHBOARD_JSON_PATH)
    summary = load_json_payload(DASHBOARD_SUMMARY_PATH)
    archive_info = write_monthly_archive(
        payload,
        summary,
        archive_root=MONTHLY_ARCHIVE_DIR,
        index_path=MONTHLY_ARCHIVE_INDEX_PATH,
        docs_root=DOCS_DIR,
    )
    archived_month = str(archive_info.get("monthKey") or "")
    source_updated_at = get_source_updated_at(payload, summary)
    open_month = archived_month
    new_month_opened = False

    if source_updated_at is not None and source_updated_at.day == 1:
        source_month = month_key(source_updated_at.date())
        if source_month != archived_month:
            current_index = load_json_payload(MONTHLY_ARCHIVE_INDEX_PATH)
            updated_index, new_month_opened = ensure_source_month_entry(
                source_updated_at=source_updated_at,
                payload=payload,
                summary=summary,
                current_index=current_index,
            )
            write_json_payload(MONTHLY_ARCHIVE_INDEX_PATH, updated_index)
            open_month = source_month

    return {
        "status": "success",
        "message": (
            f"已保存 {archived_month} 为历史数据，并开启 {open_month} 面板。"
            if new_month_opened
            else f"已保存 {archived_month} 为历史数据。"
        ),
        "archivedMonthKey": archived_month,
        "openMonthKey": open_month,
        "newMonthOpened": new_month_opened,
        "sourceUpdatedAt": source_updated_at.isoformat(timespec="seconds") if source_updated_at else "",
        "archive": archive_info,
    }


def should_log_access(method: str, request_path: str) -> bool:
    if method.upper() not in {"GET", "HEAD", "POST"}:
        return False

    path = urlparse(request_path).path or "/"
    if path.startswith("/api/"):
        return path in ACCESS_LOG_API_PATHS

    suffix = Path(path).suffix.lower()
    return suffix in {"", ".html"}


def resolve_client_ip(headers, client_address: tuple[str, int] | tuple[str, ...]) -> tuple[str, str, str]:
    remote_addr = str(client_address[0]) if client_address else ""
    forwarded_for = str(headers.get("X-Forwarded-For") or "").strip()
    forwarded_ip = ""
    if forwarded_for:
        forwarded_ip = forwarded_for.split(",", 1)[0].strip()
    for candidate in (
        str(headers.get("CF-Connecting-IP") or "").strip(),
        forwarded_ip,
        str(headers.get("X-Real-IP") or "").strip(),
        remote_addr,
    ):
        if candidate:
            return candidate, remote_addr, forwarded_for
    return "", remote_addr, forwarded_for


def build_access_log_path(root: Path, now: datetime) -> Path:
    return root / f"visits-{now.strftime('%Y%m%d')}.jsonl"


def append_access_log(root: Path, payload: dict[str, object]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    timestamp_text = str(payload.get("timestamp") or "")
    try:
        now = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        now = datetime.now()
    log_path = build_access_log_path(root, now)
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    with ACCESS_LOG_LOCK:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)


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
            business_date = parse_business_date()
            current_result = build_current_dashboard_result(business_date)
            if current_result is not None:
                self.log(f"本地数据已是最新业务日期 {current_result['businessDate']}，跳过上游抓取。")
                result = current_result
            else:
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
                    business_date_text = str(partial_result.get("businessDate") or "")
                    error_message = f"数据已更新，但自动发布失败：{exc}"
                    result_payload = {
                        **partial_result,
                        "publishStatus": "error",
                        "publishRemote": self._publish_remote,
                        "publishBranch": self._publish_branch,
                        "publishCommitMessage": resolve_publish_commit_message(
                            business_date=business_date_text,
                            mode=MANUAL_UPDATE_MODE,
                            explicit_message=self._publish_commit_message,
                        ),
                    }
                    if isinstance(exc, PublishError):
                        result_payload.update(
                            {
                                "publishPhase": exc.phase,
                                "publishExitCode": exc.exit_code,
                                "publishCommand": exc.command,
                                "publishErrorOutput": exc.output,
                            }
                        )
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
        self._response_status_code = 200
        self._access_logged = False
        self._access_request_path = ""
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
        self.log_access()

    def send_response(self, code: int, message: str | None = None):
        self._response_status_code = code
        super().send_response(code, message)

    def log_access(self) -> None:
        if self._access_logged:
            return
        if not getattr(self.server, "access_log_enabled", True):
            return
        request_path = self._access_request_path or self.path
        if not should_log_access(self.command, request_path):
            return

        client_ip, remote_addr, forwarded_for = resolve_client_ip(self.headers, self.client_address)
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "clientIp": client_ip,
            "remoteAddr": remote_addr,
            "forwardedFor": forwarded_for,
            "method": self.command,
            "path": request_path,
            "statusCode": self._response_status_code,
            "userAgent": str(self.headers.get("User-Agent") or ""),
            "referer": str(self.headers.get("Referer") or ""),
        }
        try:
            append_access_log(getattr(self.server, "access_log_root", ACCESS_LOG_ROOT), payload)
            self._access_logged = True
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"[serve_dashboard] 访问日志写入失败：{exc}", file=sys.stderr)

    def do_OPTIONS(self):
        self._access_request_path = self.path
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        self._access_request_path = self.path
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/update-status":
            self._send_json(
                {
                    "available": False,
                    "running": False,
                    "status": "idle",
                    "message": "手动兜底更新功能已迁移到附魔工作台，请改用附魔工作台中的工具。",
                    "result": None,
                    "error": "",
                    "updatedAt": datetime.now().isoformat(timespec="seconds"),
                }
            )
            return
        if parsed.path == "/api/dashboard-data":
            requested_month = normalize_month_key(query.get("month", [""])[0])
            target_path = resolve_dashboard_data_path(requested_month, "dashboard")
            try:
                self._send_json(load_json_payload(target_path))
            except FileNotFoundError:
                target_name = f"{requested_month}/dashboard.json" if requested_month else DASHBOARD_JSON_PATH.name
                self._send_json({"error": f"dashboard data not found: {target_name}"}, status_code=404)
            return
        if parsed.path == "/api/dashboard-summary":
            requested_month = normalize_month_key(query.get("month", [""])[0])
            target_path = resolve_dashboard_data_path(requested_month, "summary")
            try:
                self._send_json(load_json_payload(target_path))
            except FileNotFoundError:
                target_name = f"{requested_month}/dashboard.summary.json" if requested_month else DASHBOARD_SUMMARY_PATH.name
                self._send_json({"error": f"dashboard summary not found: {target_name}"}, status_code=404)
            return
        if parsed.path == "/api/dashboard-archive":
            try:
                self._send_json(load_json_payload(MONTHLY_ARCHIVE_INDEX_PATH))
            except FileNotFoundError:
                self._send_json({"latestMonth": "", "months": []})
            return
        super().do_GET()

    def do_POST(self):
        self._access_request_path = self.path
        parsed = urlparse(self.path)
        if parsed.path == "/api/update-data":
            self._send_json(
                {
                    "available": False,
                    "running": False,
                    "status": "idle",
                    "message": "手动兜底更新功能已迁移到附魔工作台，请改用附魔工作台中的工具。",
                    "result": None,
                    "error": "",
                    "updatedAt": datetime.now().isoformat(timespec="seconds"),
                },
                status_code=409,
            )
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
    access_log_group = parser.add_mutually_exclusive_group()
    access_log_group.add_argument(
        "--access-log",
        dest="access_log",
        action="store_true",
        default=True,
        help="Enable server-side access logging for page/API visits (default: on).",
    )
    access_log_group.add_argument(
        "--no-access-log",
        dest="access_log",
        action="store_false",
        help="Disable server-side access logging.",
    )
    parser.add_argument(
        "--access-log-dir",
        default=str(ACCESS_LOG_ROOT),
        help="Directory used to store access log JSONL files (default: .runtime/access_logs).",
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
            httpd.access_log_enabled = args.access_log
            httpd.access_log_root = Path(args.access_log_dir)
            url = f"http://{args.host}:{args.port}"
            print(f"Serving {DOCS_DIR} at {url}")
            print("Clean URLs such as /docs or /AI_Digest fall back to index.html. Press Ctrl+C to exit.")
            print(
                "Dashboard data APIs are available at /api/dashboard-data, /api/dashboard-summary "
                "and /api/dashboard-archive. Write actions moved to Enchant Workbench."
            )
            if args.access_log:
                print(f"Access log is enabled. Visits will be appended to {httpd.access_log_root}.")
            else:
                print("Access log is disabled.")
            if args.auto_publish:
                print(
                    "定时更新发布配置仍保持为 "
                    f"{args.publish_remote}/{args.publish_branch}."
                )
            else:
                print("当前本地服务会话下，定时更新发布仍保持禁用。")
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
