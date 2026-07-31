from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
DAILY_SOURCE_ROOT = WORKSPACE_ROOT / "日报取数平台"
LEADS_ICE_DIR = DAILY_SOURCE_ROOT / "日报线索ICE源"
LEADS_ICE_GETDATA = LEADS_ICE_DIR / "getdata.py"

TARGET_REPORT_KEY = "ice_national_daily"
SAME_PERIOD_REPORT_KEY = "ice_national_daily_same_period"
SAME_PERIOD_REPORT_NAME = "全国按日ICE-同期"


def load_leads_ice_module():
    if not LEADS_ICE_GETDATA.exists():
        raise FileNotFoundError(f"未找到 ICE 线索取数脚本：{LEADS_ICE_GETDATA}")

    for path in (LEADS_ICE_DIR, DAILY_SOURCE_ROOT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)

    spec = importlib.util.spec_from_file_location("ai_digest_leads_ice_getdata", LEADS_ICE_GETDATA)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块：{LEADS_ICE_GETDATA}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def patch_report_configs() -> None:
    report_configs_module = sys.modules.get("report_fetcher.report_configs")
    if report_configs_module is None:
        raise RuntimeError("未加载 report_fetcher.report_configs，无法扩展 ICE 线索导出配置。")

    report_configs = getattr(report_configs_module, "REPORT_CONFIGS", None)
    if not isinstance(report_configs, dict):
        raise RuntimeError("report_fetcher.report_configs.REPORT_CONFIGS 不可用，无法扩展 ICE 线索导出配置。")

    base_config = report_configs.get(TARGET_REPORT_KEY)
    if not isinstance(base_config, dict):
        raise RuntimeError(f"ICE 线索导出配置缺少报表 key：{TARGET_REPORT_KEY}")

    same_period_config = copy.deepcopy(base_config)
    same_period_config.update(
        {
            "enabled": False,
            "report_name": SAME_PERIOD_REPORT_NAME,
            "start_date": {"rule": "same_month_last_year_first_day"},
            "end_date": {"rule": "same_day_last_year"},
        }
    )
    report_configs[SAME_PERIOD_REPORT_KEY] = same_period_config


def main() -> int:
    module = load_leads_ice_module()
    patch_report_configs()
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
