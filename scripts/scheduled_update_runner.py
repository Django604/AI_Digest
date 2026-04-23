from __future__ import annotations

import argparse
import json
import queue
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # pragma: no cover - Windows Python normally ships with tkinter
    tk = None
    ttk = None

try:
    from .fetch_daily_data import format_business_date, parse_business_date, run_update
except ImportError:  # pragma: no cover - script entrypoint fallback
    from fetch_daily_data import format_business_date, parse_business_date, run_update


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEDULED_RUNTIME_ROOT = PROJECT_ROOT / ".runtime" / "scheduled_update"
WINDOW_TITLE = "AI Digest 定时更新"
AUTO_START_SECONDS = 120
FINISH_AUTO_CLOSE_SECONDS = 180


@dataclass(frozen=True)
class ProgressUpdate:
    progress: int
    message: str


PROGRESS_RULES: tuple[tuple[str, int, str], ...] = (
    ("定时更新任务启动", 2, "任务已启动，准备开始更新。"),
    ("开始抓取：NEV 全国按日", 8, "正在抓取 NEV 全国按日。"),
    ("抓取完成：NEV 全国按日", 20, "NEV 全国按日抓取完成。"),
    ("开始抓取：ICE 全国按日 + 十五代轩逸", 28, "正在抓取 ICE 全国按日与十五代轩逸。"),
    ("抓取完成：ICE 全国按日 + 十五代轩逸", 42, "ICE 全国按日与十五代轩逸抓取完成。"),
    ("开始抓取：NEV 来店本期 + 同期", 50, "正在抓取 NEV 来店本期与同期。"),
    ("抓取完成：NEV 来店本期 + 同期", 64, "NEV 来店本期与同期抓取完成。"),
    ("开始抓取：ICE 来店本期 + 同期", 72, "正在抓取 ICE 来店本期与同期。"),
    ("抓取完成：ICE 来店本期 + 同期", 84, "ICE 来店本期与同期抓取完成。"),
    ("回填工作表：", 90, "正在回填工作簿。"),
    ("dashboard.json updated", 96, "正在重建 dashboard.json。"),
    ("dashboard.json unchanged", 96, "dashboard.json 无需改写。"),
    ("dashboard.summary.json updated", 98, "正在更新 dashboard.summary.json。"),
    ("dashboard.summary.json unchanged", 98, "dashboard.summary.json 无需改写。"),
    ("更新流程完成。", 100, "更新流程完成。"),
)


def build_start_message(started_at: datetime) -> str:
    started_label = started_at.strftime("%Y-%m-%d %H:%M:%S")
    return (
        "AI Digest 每日自动更新已启动。\n\n"
        f"启动时间：{started_label}（北京时间）\n"
        "更新流程：\n"
        "1. 抓取 7 张线索 / 来店日报表\n"
        "2. 回填 NEV+ICE_xsai.xlsm 与 NEV+ICE_ldai.xlsx\n"
        "3. 重建 dashboard.json 与 dashboard.summary.json\n"
        "4. 执行过程中会持续显示当前进度与最终结果\n\n"
        "你可以立即点击“开始更新”，如果 2 分钟内未点击，系统会自动继续执行。"
    )


def build_waiting_status(seconds_remaining: int) -> str:
    return f"将在 {seconds_remaining} 秒后自动开始，你也可以立即点击“开始更新”。"


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
        f"日志文件：{log_path}\n\n"
        f"窗口会在 {FINISH_AUTO_CLOSE_SECONDS} 秒后自动关闭。"
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
        f"窗口会在 {FINISH_AUTO_CLOSE_SECONDS} 秒后自动关闭。"
    )


def infer_progress_update(message: str, current_progress: int) -> ProgressUpdate:
    progress = current_progress
    display_message = message
    for pattern, rule_progress, rule_message in PROGRESS_RULES:
        if pattern in message:
            progress = max(progress, rule_progress)
            display_message = rule_message
            break
    return ProgressUpdate(progress=progress, message=display_message)


class FileLogger:
    def __init__(self, log_path: Path, sink: Callable[[str], None] | None = None) -> None:
        self.log_path = log_path
        self.messages: list[str] = []
        self.sink = sink

    def __call__(self, message: str) -> None:
        timestamped = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        self.messages.append(timestamped)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(timestamped + "\n")
        if self.sink is not None:
            self.sink(message)


def build_run_dir(started_at: datetime) -> Path:
    return SCHEDULED_RUNTIME_ROOT / started_at.strftime("%Y%m%d_%H%M%S")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


class NullProgressWindow:
    def __init__(self) -> None:
        self._start_event = threading.Event()
        self._start_event.set()

    def wait_for_start(self) -> None:
        self._start_event.wait()

    def start_running(self, *, auto_started: bool) -> None:
        pass

    def report_log(self, message: str) -> None:
        pass

    def finish_success(self, summary_text: str) -> None:
        pass

    def finish_error(self, summary_text: str) -> None:
        pass

    def run(self) -> None:
        pass


class ScheduledUpdateWindow:
    def __init__(
        self,
        *,
        started_at: datetime,
        show_start_message: bool,
        show_finish_message: bool,
        auto_start_seconds: int = AUTO_START_SECONDS,
        finish_auto_close_seconds: int = FINISH_AUTO_CLOSE_SECONDS,
    ) -> None:
        if tk is None or ttk is None:
            raise RuntimeError("当前 Python 环境缺少 tkinter，无法显示定时更新进度窗口。")

        self.show_start_message = show_start_message
        self.show_finish_message = show_finish_message
        self.auto_start_seconds = auto_start_seconds
        self.finish_auto_close_seconds = finish_auto_close_seconds
        self.start_deadline = started_at.timestamp() + auto_start_seconds
        self.start_message = build_start_message(started_at)
        self.started_running = False
        self.finished = False
        self.progress_value = 0
        self._finish_close_deadline: float | None = None
        self._start_event = threading.Event()
        self._updates: queue.Queue[tuple[str, str]] = queue.Queue()

        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry("560x420")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_requested)

        self.header_var = tk.StringVar(value="AI Digest 每日自动更新")
        self.body_var = tk.StringVar(value=self.start_message if show_start_message else "AI Digest 每日自动更新已自动开始。")
        self.status_var = tk.StringVar(
            value=build_waiting_status(auto_start_seconds) if show_start_message else "正在准备执行更新任务。"
        )
        self.progress_label_var = tk.StringVar(value="尚未开始")
        self.footer_var = tk.StringVar(value="")

        container = ttk.Frame(self.root, padding=20)
        container.pack(fill="both", expand=True)

        ttk.Label(container, textvariable=self.header_var, font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w")
        ttk.Label(container, textvariable=self.body_var, wraplength=500, justify="left").pack(anchor="w", pady=(14, 12))
        ttk.Label(container, textvariable=self.status_var, wraplength=500, justify="left", foreground="#1f4e79").pack(
            anchor="w", pady=(0, 12)
        )

        self.progress_bar = ttk.Progressbar(container, mode="determinate", maximum=100, value=0, length=500)
        self.progress_label = ttk.Label(container, textvariable=self.progress_label_var)

        if not show_start_message:
            self._set_progress_widgets_visible(True)
            self.start_running(auto_started=False)
        else:
            self._set_progress_widgets_visible(False)

        button_bar = ttk.Frame(container)
        button_bar.pack(fill="x", pady=(18, 0))
        self.start_button = ttk.Button(button_bar, text="开始更新", command=self._start_by_click)
        self.start_button.pack(side="left")
        self.close_button = ttk.Button(button_bar, text="关闭", command=self._close_window)
        self.close_button.pack(side="right")
        self.close_button.pack_forget()

        ttk.Label(container, textvariable=self.footer_var, wraplength=500, justify="left", foreground="#666666").pack(
            anchor="w", pady=(16, 0)
        )

        self.root.after(200, self._drain_updates)
        if show_start_message:
            self.root.after(500, self._tick_start_countdown)
        self.root.after(200, self._focus_window)

    def _focus_window(self) -> None:
        try:
            self.root.lift()
            self.root.focus_force()
        except Exception:
            return

    def _set_progress_widgets_visible(self, visible: bool) -> None:
        if visible:
            self.progress_bar.pack(anchor="w", pady=(6, 4))
            self.progress_label.pack(anchor="w")
        else:
            self.progress_bar.pack_forget()
            self.progress_label.pack_forget()

    def _tick_start_countdown(self) -> None:
        if self.started_running or self.finished:
            return
        remaining = max(0, int(self.start_deadline - datetime.now().timestamp()))
        self.status_var.set(build_waiting_status(remaining))
        self.footer_var.set("若 2 分钟内未点击，系统会自动继续执行。")
        if remaining <= 0:
            self._start_execution(auto_started=True)
            return
        self.root.after(1000, self._tick_start_countdown)

    def _start_by_click(self) -> None:
        self._start_execution(auto_started=False)

    def _start_execution(self, *, auto_started: bool) -> None:
        if self.started_running:
            return
        self.started_running = True
        self._set_progress_widgets_visible(True)
        self.start_button.configure(state="disabled")
        self.progress_label_var.set("准备开始")
        self.start_running(auto_started=auto_started)
        self._start_event.set()

    def wait_for_start(self) -> None:
        self._start_event.wait()

    def start_running(self, *, auto_started: bool) -> None:
        self.progress_value = max(self.progress_value, 1)
        self.progress_bar.configure(value=self.progress_value)
        if auto_started:
            self.status_var.set("已超过 2 分钟未确认，系统已自动开始执行更新。")
        else:
            self.status_var.set("更新任务已开始执行，请保持窗口开启直到完成。")
        self.progress_label_var.set("当前进度：1%")
        self.footer_var.set("更新过程中窗口不会消失，完成后会在同一窗口展示结果。")

    def report_log(self, message: str) -> None:
        self._updates.put(("log", message))

    def finish_success(self, summary_text: str) -> None:
        self._updates.put(("success", summary_text))

    def finish_error(self, summary_text: str) -> None:
        self._updates.put(("error", summary_text))

    def _drain_updates(self) -> None:
        while True:
            try:
                kind, payload = self._updates.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                update = infer_progress_update(payload, self.progress_value)
                self.progress_value = update.progress
                self.progress_bar.configure(value=self.progress_value)
                self.status_var.set(update.message)
                self.progress_label_var.set(f"当前进度：{self.progress_value}%")
            elif kind == "success":
                self._finish(summary_text=payload, success=True)
            elif kind == "error":
                self._finish(summary_text=payload, success=False)
        if not self.finished:
            self.root.after(200, self._drain_updates)

    def _finish(self, *, summary_text: str, success: bool) -> None:
        self.finished = True
        self.progress_value = 100 if success else max(self.progress_value, 100)
        self.progress_bar.configure(value=self.progress_value)
        self.progress_label_var.set("当前进度：100%")
        self.status_var.set("更新已完成。" if success else "更新执行失败。")
        self.body_var.set(summary_text if self.show_finish_message else ("更新已完成。" if success else "更新执行失败。"))
        self.start_button.pack_forget()
        self.close_button.pack(side="right")
        if self.show_finish_message:
            self._finish_close_deadline = datetime.now().timestamp() + self.finish_auto_close_seconds
            self._tick_finish_countdown()
        else:
            self.root.after(300, self._close_window)

    def _tick_finish_countdown(self) -> None:
        if not self.finished or self._finish_close_deadline is None:
            return
        remaining = max(0, int(self._finish_close_deadline - datetime.now().timestamp()))
        self.footer_var.set(f"窗口会在 {remaining} 秒后自动关闭，你也可以手动关闭。")
        if remaining <= 0:
            self._close_window()
            return
        self.root.after(1000, self._tick_finish_countdown)

    def _on_close_requested(self) -> None:
        if not self.finished:
            self.footer_var.set("更新尚未完成，窗口暂不允许关闭。")
            return
        self._close_window()

    def _close_window(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            return

    def run(self) -> None:
        self.root.mainloop()


def create_progress_window(
    *,
    started_at: datetime,
    show_start_message: bool,
    show_finish_message: bool,
) -> ScheduledUpdateWindow | NullProgressWindow:
    if not show_start_message and not show_finish_message:
        return NullProgressWindow()
    return ScheduledUpdateWindow(
        started_at=started_at,
        show_start_message=show_start_message,
        show_finish_message=show_finish_message,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the daily AI Digest update with popup notifications.")
    parser.add_argument("--business-date", default="", help="可选：覆盖业务日期，支持 YYYY-MM-DD / YYYYMMDD")
    parser.add_argument("--headed", action="store_true", help="启用有头模式，便于排查")
    parser.add_argument("--keep-runtime", action="store_true", help="保留抓取运行目录")
    parser.add_argument("--suppress-start-message", action="store_true", help="测试或静默场景下不显示启动提示窗口")
    parser.add_argument("--suppress-finish-message", action="store_true", help="测试或静默场景下不显示完成结果窗口")
    return parser.parse_args(argv)


def run_scheduled_update(
    *,
    business_date_text: str = "",
    headless: bool = True,
    keep_runtime: bool = False,
    show_start_message: bool = True,
    show_finish_message: bool = True,
) -> int:
    started_at = datetime.now()
    run_dir = build_run_dir(started_at)
    log_path = run_dir / "scheduled_update.log"
    progress_window = create_progress_window(
        started_at=started_at,
        show_start_message=show_start_message,
        show_finish_message=show_finish_message,
    )
    logger = FileLogger(log_path, sink=progress_window.report_log)
    business_date = parse_business_date(business_date_text or None)
    result_holder: dict[str, object] = {"exit_code": 1}

    write_json(
        run_dir / "run_meta.json",
        {
            "startedAt": started_at.isoformat(timespec="seconds"),
            "businessDate": format_business_date(business_date),
            "headless": headless,
            "keepRuntime": keep_runtime,
        },
    )

    if not show_start_message:
        progress_window.start_running(auto_started=False)

    def worker() -> None:
        progress_window.wait_for_start()
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
            progress_window.finish_error(build_failure_message(started_at, finished_at, log_path, error_text))
            result_holder["exit_code"] = 1
            return

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
        progress_window.finish_success(build_success_message(result, started_at, finished_at, log_path))
        result_holder["exit_code"] = 0

    worker_thread = threading.Thread(target=worker, daemon=True, name="scheduled-update-runner")
    worker_thread.start()
    progress_window.run()
    worker_thread.join()
    return int(result_holder["exit_code"])


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
