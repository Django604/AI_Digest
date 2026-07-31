from __future__ import annotations

import copy
import importlib.util
import sys
from calendar import monthrange
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
DAILY_SOURCE_ROOT = WORKSPACE_ROOT / "日报取数平台"
LEADS_NEV_DIR = DAILY_SOURCE_ROOT / "日报线索NEV源"
LEADS_NEV_GETDATA = LEADS_NEV_DIR / "getdata.py"

TARGET_REPORT_KEY = "national_daily"
SAME_PERIOD_REPORT_KEY = "national_daily_same_period"
SAME_PERIOD_REPORT_NAME = "全国按日-同期"
BUSINESS_STATUS_PARAMETER_NAME = "营业状态"
BUSINESS_STATUS_LABEL_PARAMETER_NAME = "营业状态-名称"
BUSINESS_STATUS_LABEL_TEXT = "营业状态："
EMPTY_BUSINESS_STATUS: list[str] = []
SAME_PERIOD_FIRST_DAY_RULE = "same_month_last_year_first_day"
SAME_PERIOD_DAY_RULE = "same_day_last_year"
DATE_RESOLVER_PATCH_MARKER = "_ai_digest_same_period_date_rules"


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


def patch_date_resolver() -> None:
    models_module = sys.modules.get("report_fetcher.models")
    if models_module is None:
        raise RuntimeError("未加载 report_fetcher.models，无法扩展 NEV 线索同期日期规则。")

    original_resolver = getattr(models_module, "_resolve_date_value", None)
    parse_business_date = getattr(models_module, "parse_business_date", None)
    if not callable(original_resolver) or not callable(parse_business_date):
        raise RuntimeError("report_fetcher.models 日期解析器不可用，无法扩展 NEV 线索同期日期规则。")
    if getattr(original_resolver, DATE_RESOLVER_PATCH_MARKER, False):
        return

    def resolve_date_value(config_value, fallback: str, business_date: str | date | None = None) -> str:
        rule = str(config_value.get("rule", "")).strip() if isinstance(config_value, dict) else ""
        if rule in (SAME_PERIOD_FIRST_DAY_RULE, SAME_PERIOD_DAY_RULE):
            current_date = parse_business_date(business_date)
            target_year = current_date.year - 1
            target_day = (
                1
                if rule == SAME_PERIOD_FIRST_DAY_RULE
                else min(current_date.day, monthrange(target_year, current_date.month)[1])
            )
            return date(target_year, current_date.month, target_day).strftime("%Y-%m-%d")
        return original_resolver(config_value, fallback, business_date)

    setattr(resolve_date_value, DATE_RESOLVER_PATCH_MARKER, True)
    setattr(models_module, "_resolve_date_value", resolve_date_value)


def patch_report_configs() -> None:
    report_configs_module = sys.modules.get("report_fetcher.report_configs")
    if report_configs_module is None:
        raise RuntimeError("未加载 report_fetcher.report_configs，无法修正 NEV 线索导出配置。")

    report_configs = getattr(report_configs_module, "REPORT_CONFIGS", None)
    if not isinstance(report_configs, dict):
        raise RuntimeError("report_fetcher.report_configs.REPORT_CONFIGS 不可用，无法修正 NEV 线索导出配置。")

    base_config = report_configs.get(TARGET_REPORT_KEY)
    if not isinstance(base_config, dict):
        raise RuntimeError(f"NEV 线索导出配置缺少报表 key：{TARGET_REPORT_KEY}")

    same_period_config = copy.deepcopy(base_config)
    same_period_config.update(
        {
            "enabled": False,
            "report_name": SAME_PERIOD_REPORT_NAME,
            "start_date": {"rule": SAME_PERIOD_FIRST_DAY_RULE},
            "end_date": {"rule": SAME_PERIOD_DAY_RULE},
        }
    )
    report_configs[SAME_PERIOD_REPORT_KEY] = same_period_config

    for report_key in (TARGET_REPORT_KEY, SAME_PERIOD_REPORT_KEY):
        parameter_config = report_configs[report_key].get("parameterized_prepare_parameters")
        if not isinstance(parameter_config, dict):
            raise RuntimeError(f"NEV 全国按日缺少 parameterized_prepare_parameters：{report_key}")

        core_filters = parameter_config.get("core_filters")
        static_labels = parameter_config.get("static_labels")
        if isinstance(core_filters, dict):
            core_filters[BUSINESS_STATUS_PARAMETER_NAME] = copy.deepcopy(EMPTY_BUSINESS_STATUS)
            if isinstance(static_labels, dict):
                static_labels[BUSINESS_STATUS_LABEL_PARAMETER_NAME] = BUSINESS_STATUS_LABEL_TEXT
            continue

        parameter_config[BUSINESS_STATUS_PARAMETER_NAME] = copy.deepcopy(EMPTY_BUSINESS_STATUS)
        parameter_config[BUSINESS_STATUS_LABEL_PARAMETER_NAME] = BUSINESS_STATUS_LABEL_TEXT


def main() -> int:
    module = load_leads_nev_module()
    patch_date_resolver()
    patch_report_configs()
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
