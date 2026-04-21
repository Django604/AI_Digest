from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from copy import copy
from openpyxl import load_workbook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_dashboard import (  # noqa: E402
    ARRIVAL_BOOK,
    LEADS_BOOK,
    OUT_JSON,
    SUMMARY_JSON,
    build_payload,
    build_run_summary,
    coerce_date,
    safe_close_workbook,
    write_json_if_changed,
)


DAILY_SOURCE_ROOT = WORKSPACE_ROOT / "日报取数平台"
NEV_SCRIPT = DAILY_SOURCE_ROOT / "日报线索NEV源" / "getdata.py"
ICE_SCRIPT = DAILY_SOURCE_ROOT / "日报线索ICE源" / "getdata.py"
RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "daily_update"


@dataclass(frozen=True)
class FetchTask:
    label: str
    script_path: Path
    output_subdir: str
    report_keys: tuple[str, ...]


@dataclass(frozen=True)
class SheetUpdateMapping:
    report_name: str
    target_sheet: str


FETCH_TASKS = (
    FetchTask(
        label="NEV 全国按日",
        script_path=NEV_SCRIPT,
        output_subdir="nev",
        report_keys=("national_daily",),
    ),
    FetchTask(
        label="ICE 全国按日 + 十五代轩逸",
        script_path=ICE_SCRIPT,
        output_subdir="ice",
        report_keys=("ice_national_daily", "ice_sylphy15_daily"),
    ),
)

SHEET_MAPPINGS = (
    SheetUpdateMapping(report_name="全国按日", target_sheet="全国按日NEV"),
    SheetUpdateMapping(report_name="全国按日ICE", target_sheet="全国按日ICE"),
    SheetUpdateMapping(report_name="十五代轩逸按日", target_sheet="十五代轩逸按日"),
)


def default_log(message: str) -> None:
    print(message, flush=True)


def parse_business_date(value: str | None = None) -> date:
    if value:
        parsed = coerce_date(value)
        if parsed is None:
            raise ValueError(f"无法识别业务日期：{value}")
        return parsed
    return date.today() - timedelta(days=1)


def format_business_date(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def build_business_suffix(value: date) -> str:
    return value.strftime("%m%d")


def build_task_output_dir(task: FetchTask, run_root: Path) -> Path:
    return run_root / task.output_subdir / "exports"


def resolve_export_path(output_dir: Path, report_name: str, business_date: date) -> Path:
    suffix = build_business_suffix(business_date)
    candidates = sorted(output_dir.glob(f"{report_name}-{suffix}.*"))
    if not candidates:
        raise FileNotFoundError(f"未找到导出文件：{report_name}-{suffix}.*（目录：{output_dir}）")
    return candidates[0]


def stream_subprocess(command: list[str], cwd: Path, log: Callable[[str], None], prefix: str) -> None:
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        text = line.rstrip()
        if text:
            log(f"[{prefix}] {text}")
    exit_code = process.wait()
    if exit_code != 0:
        raise RuntimeError(f"{prefix} 执行失败，退出码：{exit_code}")


def run_fetch_task(
    task: FetchTask,
    *,
    business_date: date,
    runtime_root: Path,
    log: Callable[[str], None],
    headless: bool,
    username: str | None,
    password: str | None,
    chrome_path: str | None,
) -> Path:
    output_dir = build_task_output_dir(task, runtime_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        task.script_path.name,
        "--business-date",
        format_business_date(business_date),
        "--output-dir",
        str(output_dir.parent),
        "--output-folder-name",
        output_dir.name,
        "--report-keys",
        ",".join(task.report_keys),
    ]
    command.append("--headless" if headless else "--headed")
    if username:
        command.extend(["--username", username])
    if password:
        command.extend(["--password", password])
    if chrome_path:
        command.extend(["--chrome-path", chrome_path])

    log(f"开始抓取：{task.label}")
    stream_subprocess(command, task.script_path.parent, log, task.label)
    log(f"抓取完成：{task.label}")
    return output_dir


def clear_worksheet(target_ws) -> None:
    merged_ranges = [str(item) for item in target_ws.merged_cells.ranges]
    for merged in merged_ranges:
        target_ws.unmerge_cells(merged)
    for row in target_ws.iter_rows():
        for cell in row:
            cell.value = None
            cell._style = copy(cell._style)
    target_ws.row_dimensions.clear()
    target_ws.column_dimensions.clear()


def copy_worksheet_contents(source_ws, target_ws) -> None:
    clear_worksheet(target_ws)
    for column_letter, dimension in source_ws.column_dimensions.items():
        target_ws.column_dimensions[column_letter] = copy(dimension)
    for row_index, dimension in source_ws.row_dimensions.items():
        target_ws.row_dimensions[row_index] = copy(dimension)

    for row in source_ws.iter_rows():
        for source_cell in row:
            target_cell = target_ws.cell(row=source_cell.row, column=source_cell.column)
            target_cell.value = source_cell.value
            if source_cell.has_style:
                target_cell._style = copy(source_cell._style)
            if source_cell.number_format:
                target_cell.number_format = source_cell.number_format
            if source_cell.font:
                target_cell.font = copy(source_cell.font)
            if source_cell.fill:
                target_cell.fill = copy(source_cell.fill)
            if source_cell.border:
                target_cell.border = copy(source_cell.border)
            if source_cell.alignment:
                target_cell.alignment = copy(source_cell.alignment)
            if source_cell.protection:
                target_cell.protection = copy(source_cell.protection)

    for merged in source_ws.merged_cells.ranges:
        target_ws.merge_cells(str(merged))


def replace_workbook_sheets(
    leads_path: Path,
    export_paths: dict[str, Path],
    *,
    log: Callable[[str], None],
) -> None:
    workbook = load_workbook(leads_path, keep_vba=True)
    sources = {
        mapping.target_sheet: load_workbook(export_paths[mapping.report_name], data_only=False)
        for mapping in SHEET_MAPPINGS
    }
    try:
        for mapping in SHEET_MAPPINGS:
            target_ws = workbook[mapping.target_sheet]
            source_wb = sources[mapping.target_sheet]
            source_ws = source_wb[source_wb.sheetnames[0]]
            log(f"回填工作表：{mapping.target_sheet} <- {mapping.report_name}")
            copy_worksheet_contents(source_ws, target_ws)

        temp_path = leads_path.with_name(f"{leads_path.stem}.updating{leads_path.suffix}")
        workbook.save(temp_path)
        temp_path.replace(leads_path)
    finally:
        safe_close_workbook(workbook)
        for source in sources.values():
            safe_close_workbook(source)


def rebuild_dashboard(
    *,
    business_date: date,
    leads_path: Path,
    arrival_path: Path,
    out_path: Path,
    summary_path: Path,
    log: Callable[[str], None],
) -> dict[str, str | bool]:
    payload = build_payload(leads_path, arrival_path, report_date_override=business_date)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    changed, existing_payload = write_json_if_changed(
        out_path,
        payload,
        encoding="utf-8",
        volatile_field_paths=(("meta", "generatedAt"),),
    )
    if not changed and existing_payload is not None:
        payload = existing_payload

    summary_payload = build_run_summary(payload, leads_path, arrival_path, out_path, summary_path, changed)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_changed, _ = write_json_if_changed(
        summary_path,
        summary_payload,
        encoding="utf-8",
        volatile_field_paths=(("generatedAt",),),
    )
    log(f"dashboard.json {'updated' if changed else 'unchanged'}: {out_path}")
    log(f"dashboard.summary.json {'updated' if summary_changed else 'unchanged'}: {summary_path}")
    return {
        "dashboardChanged": changed,
        "summaryChanged": summary_changed,
    }


def build_runtime_dir(business_date: date) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return RUNTIME_ROOT / f"{business_date.strftime('%Y%m%d')}_{timestamp}"


def run_update(
    *,
    business_date: date | None = None,
    leads_path: Path = LEADS_BOOK,
    arrival_path: Path = ARRIVAL_BOOK,
    out_path: Path = OUT_JSON,
    summary_path: Path = SUMMARY_JSON,
    log: Callable[[str], None] = default_log,
    headless: bool = True,
    username: str | None = None,
    password: str | None = None,
    chrome_path: str | None = None,
    keep_runtime: bool = False,
) -> dict[str, object]:
    resolved_business_date = business_date or parse_business_date()
    runtime_dir = build_runtime_dir(resolved_business_date)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    log(f"本次业务日期：{format_business_date(resolved_business_date)}")
    log(f"运行目录：{runtime_dir}")

    export_paths: dict[str, Path] = {}
    succeeded = False
    try:
        for task in FETCH_TASKS:
            output_dir = run_fetch_task(
                task,
                business_date=resolved_business_date,
                runtime_root=runtime_dir,
                log=log,
                headless=headless,
                username=username,
                password=password,
                chrome_path=chrome_path,
            )
            for mapping in SHEET_MAPPINGS:
                if mapping.report_name in export_paths:
                    continue
                try:
                    export_paths[mapping.report_name] = resolve_export_path(output_dir, mapping.report_name, resolved_business_date)
                except FileNotFoundError:
                    continue

        missing_reports = [mapping.report_name for mapping in SHEET_MAPPINGS if mapping.report_name not in export_paths]
        if missing_reports:
            raise RuntimeError(f"缺少导出结果：{', '.join(missing_reports)}")

        replace_workbook_sheets(leads_path, export_paths, log=log)
        rebuild_summary = rebuild_dashboard(
            business_date=resolved_business_date,
            leads_path=leads_path,
            arrival_path=arrival_path,
            out_path=out_path,
            summary_path=summary_path,
            log=log,
        )
        result = {
            "businessDate": format_business_date(resolved_business_date),
            "runtimeDir": str(runtime_dir),
            "exports": {name: str(path) for name, path in export_paths.items()},
            **rebuild_summary,
        }
        log("更新流程完成。")
        succeeded = True
        return result
    finally:
        if succeeded and not keep_runtime and runtime_dir.exists():
            shutil.rmtree(runtime_dir, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch daily browser reports and update AI Digest workbooks.")
    parser.add_argument("--business-date", default="", help="业务日期，默认取今天的 N-1，支持 YYYY-MM-DD / YYYYMMDD")
    parser.add_argument("--username", default="", help="可选：覆盖默认登录账号")
    parser.add_argument("--password", default="", help="可选：覆盖默认登录密码")
    parser.add_argument("--chrome-path", default="", help="可选：指定 Chrome 路径")
    parser.add_argument("--headed", action="store_true", help="启用有头模式，便于调试")
    parser.add_argument("--keep-runtime", action="store_true", help="保留运行时导出与 trace 目录")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_update(
        business_date=parse_business_date(args.business_date or None),
        log=default_log,
        headless=not args.headed,
        username=args.username or None,
        password=args.password or None,
        chrome_path=args.chrome_path or None,
        keep_runtime=args.keep_runtime,
    )
    print(result, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
