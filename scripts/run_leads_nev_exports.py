from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
DAILY_SOURCE_ROOT = WORKSPACE_ROOT / "日报取数平台"
LEADS_NEV_DIR = DAILY_SOURCE_ROOT / "日报线索NEV源"
LEADS_NEV_GETDATA = LEADS_NEV_DIR / "getdata.py"

TARGET_REPORT_KEY = "national_daily"
BUSINESS_STATUS_PARAMETER_NAME = "营业状态"
BUSINESS_STATUS_LABEL_PARAMETER_NAME = "营业状态-名称"
BUSINESS_STATUS_LABEL_TEXT = "营业状态："
EMPTY_BUSINESS_STATUS: list[str] = []


def load_leads_nev_module():
    if not LEADS_NEV_GETDATA.exists():
        raise FileNotFoundError(f"未找到 NEV 线索取数脚本：{LEADS_NEV_GETDATA}")

    for path in (LEADS_NEV_DIR, DAILY_SOURCE_ROOT):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)

    spec = importlib.util.spec_from_file_location("ai_digest_leads_nev_getdata", LEADS_NEV_GETDATA)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块：{LEADS_NEV_GETDATA}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def patch_report_configs() -> None:
    report_configs_module = sys.modules.get("report_fetcher.report_configs")
    if report_configs_module is None:
        raise RuntimeError("未加载 report_fetcher.report_configs，无法修正 NEV 线索导出配置。")

    report_configs = getattr(report_configs_module, "REPORT_CONFIGS", None)
    if not isinstance(report_configs, dict):
        raise RuntimeError("report_fetcher.report_configs.REPORT_CONFIGS 不可用，无法修正 NEV 线索导出配置。")

    config = report_configs.get(TARGET_REPORT_KEY)
    if not isinstance(config, dict):
        raise RuntimeError(f"NEV 线索导出配置缺少报表 key：{TARGET_REPORT_KEY}")

    parameter_config = config.get("parameterized_prepare_parameters")
    if not isinstance(parameter_config, dict):
        raise RuntimeError("NEV 全国按日缺少 parameterized_prepare_parameters，无法清空营业状态筛选。")

    core_filters = parameter_config.get("core_filters")
    static_labels = parameter_config.get("static_labels")
    if isinstance(core_filters, dict):
        core_filters[BUSINESS_STATUS_PARAMETER_NAME] = copy.deepcopy(EMPTY_BUSINESS_STATUS)
        if isinstance(static_labels, dict):
            static_labels[BUSINESS_STATUS_LABEL_PARAMETER_NAME] = BUSINESS_STATUS_LABEL_TEXT
        return

    parameter_config[BUSINESS_STATUS_PARAMETER_NAME] = copy.deepcopy(EMPTY_BUSINESS_STATUS)
    parameter_config[BUSINESS_STATUS_LABEL_PARAMETER_NAME] = BUSINESS_STATUS_LABEL_TEXT


def main() -> int:
    module = load_leads_nev_module()
    patch_report_configs()
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
