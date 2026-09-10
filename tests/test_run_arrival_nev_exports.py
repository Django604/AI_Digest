from __future__ import annotations

import sys
import types
import unittest
from datetime import date
from pathlib import Path

from openpyxl import Workbook

from scripts.run_arrival_nev_exports import (
    BASE_REPORT_KEY,
    CUSTOM_DISPLAY_FIELDS,
    CUSTOM_DISPLAY_TYPE,
    LEADS_NEV_DIR,
    LEADS_NEV_GETDATA,
    PREVIOUS_MONTH_LAST_DAY_RULE,
    TARGET_REPORT_DEFINITIONS,
    TARGET_REPORT_KEYS,
    UPSTREAM_DATE_NOT_READY_MARKER,
    patch_date_resolver,
    patch_report_configs,
    validate_export_date_range,
)


def build_base_config() -> dict:
    return {
        "enabled": True,
        "report_name": "全国按日",
        "report_url": "https://example.com/national-daily",
        "start_date": {"rule": "previous_month_first_day"},
        "end_date": {"rule": "yesterday"},
        "parameterized_prepare_parameters": {
            "core_filters": {
                "区域显示": "3",
                "营业状态": ["营业"],
            },
            "display_options": {
                "时间统计方式": "0",
                "展示类型": "全量展示",
                "展示字段": "",
            },
            "summary_flags": {
                "车系汇总": True,
            },
            "static_labels": {},
        },
        "combo_parameters": [
            {"label": "时间统计方式：", "value": "全部"},
            {"label": "区域显示：", "value": "小区"},
            {"label": "指标展示：", "value": "全量展示"},
        ],
        "tag_combo_parameters": [],
        "checkbox_parameters": [
            {"label": "基准车系汇总", "checked": True},
        ],
    }


class RunArrivalNevExportsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_path = Path("tests/.tmp/nev-arrival-export.xlsx")
        self.temp_path.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.temp_path.unlink(missing_ok=True)

    def test_arrival_exports_reuse_leads_nev_source(self) -> None:
        self.assertEqual(LEADS_NEV_DIR.name, "日报线索NEV源")
        self.assertEqual(LEADS_NEV_GETDATA, LEADS_NEV_DIR / "getdata.py")

    def test_patch_report_configs_clones_national_daily_with_requested_filters(self) -> None:
        base_config = build_base_config()
        report_configs_module = types.SimpleNamespace(REPORT_CONFIGS={BASE_REPORT_KEY: base_config})
        original_module = sys.modules.get("report_fetcher.report_configs")
        sys.modules["report_fetcher.report_configs"] = report_configs_module
        try:
            patch_report_configs()
        finally:
            if original_module is None:
                sys.modules.pop("report_fetcher.report_configs", None)
            else:
                sys.modules["report_fetcher.report_configs"] = original_module

        self.assertEqual(TARGET_REPORT_KEYS, tuple(item[0] for item in TARGET_REPORT_DEFINITIONS))
        self.assertEqual(report_configs_module.REPORT_CONFIGS[BASE_REPORT_KEY], base_config)
        for report_key, report_name, start_date, end_date in TARGET_REPORT_DEFINITIONS:
            with self.subTest(report_key=report_key):
                config = report_configs_module.REPORT_CONFIGS[report_key]
                parameters = config["parameterized_prepare_parameters"]
                combo_values = {item["label"]: item["value"] for item in config["combo_parameters"]}
                tag_values = {item["label"]: item["value"] for item in config["tag_combo_parameters"]}
                checkbox_values = {
                    item["label"]: item["checked"] for item in config["checkbox_parameters"]
                }

                self.assertEqual(config["report_name"], report_name)
                self.assertEqual(config["report_url"], base_config["report_url"])
                self.assertEqual(config["start_date"], start_date)
                self.assertEqual(config["end_date"], end_date)
                self.assertEqual(parameters["core_filters"]["区域显示"], "0")
                self.assertEqual(parameters["core_filters"]["营业状态"], [])
                self.assertEqual(parameters["display_options"]["时间统计方式"], "3")
                self.assertEqual(parameters["display_options"]["展示类型"], CUSTOM_DISPLAY_TYPE)
                self.assertEqual(parameters["display_options"]["展示字段"], CUSTOM_DISPLAY_FIELDS)
                self.assertFalse(parameters["summary_flags"]["车系汇总"])
                self.assertEqual(combo_values["时间统计方式："], "日")
                self.assertEqual(combo_values["区域显示："], "全国")
                self.assertEqual(combo_values["指标展示："], CUSTOM_DISPLAY_TYPE)
                self.assertEqual(tag_values["指标筛选："], CUSTOM_DISPLAY_FIELDS)
                self.assertFalse(checkbox_values["基准车系汇总"])

    def test_patch_date_resolver_adds_previous_month_last_day(self) -> None:
        def original_resolver(config_value, fallback, _business_date=None):
            return fallback if not isinstance(config_value, dict) else str(config_value.get("rule") or fallback)

        models_module = types.SimpleNamespace(
            _resolve_date_value=original_resolver,
            parse_business_date=lambda value=None: value if isinstance(value, date) else date.fromisoformat(value),
        )
        original_module = sys.modules.get("report_fetcher.models")
        sys.modules["report_fetcher.models"] = models_module
        try:
            patch_date_resolver()
            actual = models_module._resolve_date_value(
                {"rule": PREVIOUS_MONTH_LAST_DAY_RULE},
                "fallback",
                date(2026, 9, 10),
            )
        finally:
            if original_module is None:
                sys.modules.pop("report_fetcher.models", None)
            else:
                sys.modules["report_fetcher.models"] = original_module

        self.assertEqual(actual, "2026-08-31")

    def test_validate_export_date_range_requires_every_configured_day(self) -> None:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet["C1"] = "日期"
        worksheet["E1"] = "到店转化"
        worksheet["E2"] = "新增到店量"
        worksheet["C3"] = date(2026, 9, 1)
        worksheet["E3"] = 10
        worksheet["C4"] = date(2026, 9, 3)
        worksheet["E4"] = 20
        workbook.save(self.temp_path)
        workbook.close()

        with self.assertRaisesRegex(RuntimeError, UPSTREAM_DATE_NOT_READY_MARKER):
            validate_export_date_range(
                self.temp_path,
                "2026-09-01",
                "2026-09-03 23:59:59",
            )


if __name__ == "__main__":
    unittest.main()
