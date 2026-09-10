from __future__ import annotations

import copy
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook

if __package__:
    from .run_leads_nev_exports import (
        LEADS_NEV_DIR,
        LEADS_NEV_GETDATA,
        load_leads_nev_module,
        patch_date_resolver as patch_leads_nev_date_resolver,
        patch_report_configs as patch_leads_nev_report_configs,
    )
else:
    from run_leads_nev_exports import (
        LEADS_NEV_DIR,
        LEADS_NEV_GETDATA,
        load_leads_nev_module,
        patch_date_resolver as patch_leads_nev_date_resolver,
        patch_report_configs as patch_leads_nev_report_configs,
    )


BASE_REPORT_KEY = "national_daily"
PREVIOUS_MONTH_LAST_DAY_RULE = "previous_month_last_day"
DATE_RESOLVER_PATCH_MARKER = "_ai_digest_previous_month_last_day_rule"
CUSTOM_DISPLAY_TYPE = "自定义展示"
CUSTOM_DISPLAY_FIELDS = "到店转化,新增到店量"
UPSTREAM_DATE_NOT_READY_MARKER = "上游 NEV 来店数据尚未发布目标日期"
TARGET_REPORT_DEFINITIONS = (
    (
        "store_current_period",
        "NEV本期",
        {"rule": "current_month_first_day"},
        {"rule": "yesterday"},
    ),
    (
        "store_previous_period",
        "NEV上期",
        {"rule": "previous_month_first_day"},
        {"rule": PREVIOUS_MONTH_LAST_DAY_RULE},
    ),
    (
        "store_same_period",
        "NEV同期",
        {"rule": "same_month_last_year_first_day"},
        {"rule": "same_month_last_year_last_day"},
    ),
)
TARGET_REPORT_KEYS = tuple(item[0] for item in TARGET_REPORT_DEFINITIONS)


def patch_date_resolver() -> None:
    patch_leads_nev_date_resolver()
    models_module = sys.modules.get("report_fetcher.models")
    if models_module is None:
        raise RuntimeError("未加载 report_fetcher.models，无法扩展 NEV 来店上期日期规则。")

    original_resolver = getattr(models_module, "_resolve_date_value", None)
    parse_business_date = getattr(models_module, "parse_business_date", None)
    if not callable(original_resolver) or not callable(parse_business_date):
        raise RuntimeError("report_fetcher.models 日期解析器不可用，无法扩展 NEV 来店上期日期规则。")
    if getattr(original_resolver, DATE_RESOLVER_PATCH_MARKER, False):
        return

    def resolve_date_value(config_value, fallback, business_date=None):
        rule = str(config_value.get("rule", "")).strip() if isinstance(config_value, dict) else ""
        if rule == PREVIOUS_MONTH_LAST_DAY_RULE:
            current_date = parse_business_date(business_date)
            return (current_date.replace(day=1) - timedelta(days=1)).isoformat()
        return original_resolver(config_value, fallback, business_date)

    setattr(resolve_date_value, DATE_RESOLVER_PATCH_MARKER, True)
    models_module._resolve_date_value = resolve_date_value


def replace_choice(config: dict, collection_name: str, label: str, **updates) -> None:
    choices = config.get(collection_name)
    if not isinstance(choices, list):
        raise RuntimeError(f"NEV 全国按日缺少 {collection_name} 配置。")
    for choice in choices:
        if isinstance(choice, dict) and choice.get("label") == label:
            choice.update(updates)
            return
    choices.append({"label": label, **updates})


def patch_report_configs() -> None:
    patch_leads_nev_report_configs()
    report_configs_module = sys.modules.get("report_fetcher.report_configs")
    if report_configs_module is None:
        raise RuntimeError("未加载 report_fetcher.report_configs，无法创建 NEV 来店导出配置。")

    report_configs = getattr(report_configs_module, "REPORT_CONFIGS", None)
    if not isinstance(report_configs, dict):
        raise RuntimeError("report_fetcher.report_configs.REPORT_CONFIGS 不可用，无法创建 NEV 来店导出配置。")
    base_config = report_configs.get(BASE_REPORT_KEY)
    if not isinstance(base_config, dict):
        raise RuntimeError(f"NEV 来店导出配置缺少基础报表 key：{BASE_REPORT_KEY}")

    for report_key, report_name, start_date, end_date in TARGET_REPORT_DEFINITIONS:
        config = copy.deepcopy(base_config)
        config.update(
            {
                "enabled": False,
                "report_name": report_name,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        parameter_config = config.get("parameterized_prepare_parameters")
        if not isinstance(parameter_config, dict):
            raise RuntimeError("NEV 全国按日缺少 parameterized_prepare_parameters 配置。")
        core_filters = parameter_config.get("core_filters")
        display_options = parameter_config.get("display_options")
        summary_flags = parameter_config.get("summary_flags")
        if not all(isinstance(item, dict) for item in (core_filters, display_options, summary_flags)):
            raise RuntimeError("NEV 全国按日参数分组不完整，无法配置来店导出。")

        core_filters["区域显示"] = "0"
        display_options.update(
            {
                "时间统计方式": "3",
                "展示类型": CUSTOM_DISPLAY_TYPE,
                "展示字段": CUSTOM_DISPLAY_FIELDS,
            }
        )
        summary_flags["车系汇总"] = False
        replace_choice(config, "combo_parameters", "时间统计方式：", value="日")
        replace_choice(config, "combo_parameters", "区域显示：", value="全国")
        replace_choice(config, "combo_parameters", "指标展示：", value=CUSTOM_DISPLAY_TYPE)
        replace_choice(config, "tag_combo_parameters", "指标筛选：", value=CUSTOM_DISPLAY_FIELDS)
        replace_choice(config, "checkbox_parameters", "基准车系汇总", checked=False)
        report_configs[report_key] = config


def load_export_dates(excel_path: Path) -> set[date]:
    workbook = load_workbook(excel_path, data_only=True, read_only=True)
    try:
        worksheet = workbook[workbook.sheetnames[0]]
        date_column = None
        for row in worksheet.iter_rows(min_row=1, max_row=min(worksheet.max_row, 5), values_only=True):
            for column_index, value in enumerate(row, start=1):
                if str(value).strip() == "日期":
                    date_column = column_index
                    break
            if date_column is not None:
                break
        if date_column is None:
            raise RuntimeError(f"NEV 来店导出缺少日期列：{excel_path}")

        result: set[date] = set()
        for row in worksheet.iter_rows(values_only=True):
            if len(row) < date_column:
                continue
            value = row[date_column - 1]
            if isinstance(value, datetime):
                result.add(value.date())
            elif isinstance(value, date):
                result.add(value)
        return result
    finally:
        workbook.close()


def validate_export_date_range(excel_path: Path, start_date: str, end_date: str) -> None:
    start = date.fromisoformat(start_date.split()[0])
    end = date.fromisoformat(end_date.split()[0])
    actual_dates = load_export_dates(excel_path)
    missing_dates: list[date] = []
    current_date = start
    while current_date <= end:
        if current_date not in actual_dates:
            missing_dates.append(current_date)
        current_date += timedelta(days=1)
    if missing_dates:
        missing_text = ", ".join(item.isoformat() for item in missing_dates[:5])
        if len(missing_dates) > 5:
            missing_text += f" 等 {len(missing_dates)} 天"
        raise RuntimeError(
            f"{UPSTREAM_DATE_NOT_READY_MARKER}：{end.isoformat()}；导出缺少日期：{missing_text}"
        )


def patch_export_validation(module) -> None:
    original_export = module.export_report_via_api

    def export_report_via_api(*args, **kwargs):
        excel_path = Path(original_export(*args, **kwargs))
        filter_config = kwargs.get("filter_config")
        if filter_config is None:
            raise RuntimeError("NEV 来店导出缺少 filter_config，无法校验日期范围。")
        validate_export_date_range(
            excel_path,
            filter_config.start_date,
            filter_config.end_date,
        )
        return excel_path

    module.export_report_via_api = export_report_via_api


def main() -> int:
    module = load_leads_nev_module()
    patch_date_resolver()
    patch_report_configs()
    patch_export_validation(module)
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
