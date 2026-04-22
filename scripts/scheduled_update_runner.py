from __future__ import annotations

import argparse
import ctypes
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable

try:
    from .fetch_daily_data import format_business_date, parse_business_date, run_update
except ImportError:  # pragma: no cover - script entrypoint fallback
    from fetch_daily_data import format_business_date, parse_business_date, run_update


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEDULED_RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "scheduled_update"
MESSAGE_BOX_TITLE = "AI Digest 定时更新"
MB_ICONINFORMATION = 0x40
MB_ICONWARNING = 0x30


def build_start_message(started_at: datetime) -> str:
    started_label = started_at.strftime("%Y-%m-%d %H:%M:%S")
    return (
        "AI Digest 每日自动更新已启动。\n\n"
        f"启动时间：{started_label}（北京时间）\n"
        "更新流程：\n"
        "1. 抓取 7 张线索 / 来店日报表\n"
        "2. 回填 NEV+ICE_xsai.xlsm 与 NEV+ICE_ldai.xlsx\n"
        "3. 重建 dashboard.json 与 dashboard.summary.json\n"
        "4. 写入本次运行日志并弹出结果提示框"
    )


def build_success_message(result: dict[str, object], started_at: datetime, finished_at: datetime, log_path: Path) -> str:
    business_date = str(result.get("businessDate") or "")
    runtime_dir = str(result.get("runtimeDir") or "")
    dashboard_changed = "是" if bool(result.get("dashboardChanged")) else "否"
    summary_changed = "是" if bool(result.get("summaryChanged")) else "否"
    duration_seconds = int((finished_at - started_at).total_seconds())
    return (
        "AI Digest 每日自动更新已完成。\n\n"
        f"业务日期：{business_date}\n"
        f"开始时间：{started_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"结束时间：{finished_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"耗时：{duration_seconds} 秒\n"
        f"dashboard.json 有变更：{dashboard_changed}\n"
        f"dashboard.summary.json 有变更：{summary_changed}\n"
        f"运行目录：{runtime_dir}\n"
        f"日志文件：{log_path}"
    )


def build_failure_message(started_at: datetime, finished_at: datetime, log_path: Path, error_text: str) -> str:
    duration_seconds = int((finished_at - started_at).total_seconds())
    return (
        "AI Digest 每日自动更新失败。\n\n"
        f"开始时间：{started_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"结束时间：{finished_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"耗时：{duration_seconds} 秒\n"
        f"错误信息：{error_text}\n"
        f"日志文件：{log_path}\n\n"
        "请先查看日志，再决定是否需要手动重跑。"
    )


def show_message_box(message: str, *, title: str = MESSAGE_BOX_TITLE, style: int = MB_ICONINFORMATION) -> None:
    ctypes.windll.user32.MessageBoxW(None, message, title, style)


class FileLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.messages: list[str] = []

    def __call__(self, message: str) -> None:
        timestamped = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        self.messages.append(timestamped)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(timestamped + "\n")


def build_run_dir(started_at: datetime) -> Path:
    return SCHEDULED_RUNTIME_ROOT / started_at.strftime("%Y%m%d_%H%M%S")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the daily AI Digest update with popup notifications.")
    parser.add_argument("--business-date", default="", help="可选：覆盖业务日期，支持 YYYY-MM-DD / YYYYMMDD")
    parser.add_argument("--headed", action="store_true", help="启用有头模式，便于排查")
    parser.add_argument("--keep-runtime", action="store_true", help="保留抓取运行目录")
    parser.add_argument("--suppress-start-message", action="store_true", help="测试或静默场景下不弹启动提示框")
    parser.add_argument("--suppress-finish-message", action="store_true", help="测试或静默场景下不弹结果提示框")
    return parser.parse_args(argv)


def run_scheduled_update(
    *,
    business_date_text: str = "",
    headless: bool = True,
    keep_runtime: bool = False,
    show_start_message: bool = True,
    show_finish_message: bool = True,
    message_box: Callable[..., None] = show_message_box,
) -> int:
    started_at = datetime.now()
    run_dir = build_run_dir(started_at)
    log_path = run_dir / "scheduled_update.log"
    logger = FileLogger(log_path)
    business_date = parse_business_date(business_date_text or None)

    write_json(
        run_dir / "run_meta.json",
        {
            "startedAt": started_at.isoformat(timespec="seconds"),
            "businessDate": format_business_date(business_date),
            "headless": headless,
            "keepRuntime": keep_runtime,
        },
    )

    if show_start_message:
        message_box(build_start_message(started_at), title=MESSAGE_BOX_TITLE, style=MB_ICONINFORMATION)

    logger(f"定时更新任务启动，业务日期：{format_business_date(business_date)}")
    try:
        result = run_update(
            business_date=business_date,
            log=logger,
            headless=headless,
            keep_runtime=keep_runtime,
        )
    except Exception as exc:
        finished_at = datetime.now()
        error_text = str(exc)
        logger(f"定时更新任务失败：{error_text}")
        logger(traceback.format_exc().rstrip())
        write_json(
            run_dir / "result.json",
            {
                "status": "error",
                "startedAt": started_at.isoformat(timespec="seconds"),
                "finishedAt": finished_at.isoformat(timespec="seconds"),
                "businessDate": format_business_date(business_date),
                "error": error_text,
                "logPath": str(log_path),
            },
        )
        if show_finish_message:
            message_box(
                build_failure_message(started_at, finished_at, log_path, error_text),
                title=MESSAGE_BOX_TITLE,
                style=MB_ICONWARNING,
            )
        return 1

    finished_at = datetime.now()
    logger("定时更新任务完成。")
    write_json(
        run_dir / "result.json",
        {
            "status": "success",
            "startedAt": started_at.isoformat(timespec="seconds"),
            "finishedAt": finished_at.isoformat(timespec="seconds"),
            "businessDate": result.get("businessDate"),
            "runtimeDir": result.get("runtimeDir"),
            "dashboardChanged": bool(result.get("dashboardChanged")),
            "summaryChanged": bool(result.get("summaryChanged")),
            "logPath": str(log_path),
        },
    )
    if show_finish_message:
        message_box(
            build_success_message(result, started_at, finished_at, log_path),
            title=MESSAGE_BOX_TITLE,
            style=MB_ICONINFORMATION,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_scheduled_update(
        business_date_text=args.business_date,
        headless=not args.headed,
        keep_runtime=args.keep_runtime,
        show_start_message=not args.suppress_start_message,
        show_finish_message=not args.suppress_finish_message,
    )


if __name__ == "__main__":
    raise SystemExit(main())
