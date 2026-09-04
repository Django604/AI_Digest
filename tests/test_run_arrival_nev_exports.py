from __future__ import annotations

import copy
import sys
import types
import unittest
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.run_arrival_nev_exports import (
    TARGET_PARAMETER_TEMPLATE,
    TARGET_REPORT_KEYS,
    TARGET_REPORT_NAME,
    TARGET_REPORT_URL,
    build_chart_data_url,
    capture_daily_rows,
    extract_daily_rows_from_chart_payload,
    extract_simplechart_meta_from_page_result,
    parse_report2_daily_series,
    patch_report_config_builder,
    patch_report_configs,
)


@dataclass(frozen=True)
class FakeReportConfig:
    key: str
    start_date: str
    end_date: str
    parameterized_prepare_parameters: dict | None = None


class RunArrivalNevExportsTests(unittest.TestCase):
    def test_patch_report_config_builder_fetches_full_previous_and_same_months(self) -> None:
        configs = [
            FakeReportConfig("store_current_period", "2026-09-01", "2026-09-03", {"结束时间": "2026-09-03"}),
            FakeReportConfig("store_previous_period", "2026-08-01", "2026-08-03", {"结束时间": "2026-08-03"}),
            FakeReportConfig("store_same_period", "2025-09-01", "2025-09-03", {"结束时间": "2025-09-03"}),
        ]
        module = types.SimpleNamespace(build_report_configs=lambda _args: configs)

        patch_report_config_builder(module)
        actual = module.build_report_configs(types.SimpleNamespace(end_date=None))

        self.assertEqual([item.end_date for item in actual], ["2026-09-03", "2026-08-31", "2025-09-30"])
        self.assertEqual(
            [item.parameterized_prepare_parameters["结束时间"] for item in actual],
            ["2026-09-03", "2026-08-31", "2025-09-30"],
        )

    def test_patch_report_config_builder_respects_explicit_end_date(self) -> None:
        config = FakeReportConfig("store_previous_period", "2026-08-01", "2026-08-15")
        module = types.SimpleNamespace(build_report_configs=lambda _args: [config])

        patch_report_config_builder(module)
        actual = module.build_report_configs(types.SimpleNamespace(end_date="2026-08-15"))

        self.assertEqual(actual, [config])

    def test_patch_report_configs_switches_target_route_and_parameter_template(self) -> None:
        report_configs_module = types.SimpleNamespace(
            REPORT_URL="https://example.com/old",
            REPORT_CONFIGS={
                "store_current_period": {
                    "report_name": "NEV本期",
                    "report_url": "https://example.com/old",
                    "parameterized_prepare_parameters": {"区域显示": "2"},
                },
                "store_same_period": {
                    "report_name": "NEV同期",
                    "report_url": "https://example.com/old",
                    "parameterized_prepare_parameters": {"区域显示": "2"},
                },
                "store_previous_period": {
                    "report_name": "NEV上期",
                    "report_url": "https://example.com/old",
                    "parameterized_prepare_parameters": {"区域显示": "2"},
                },
                "unrelated": {
                    "report_name": "不相关报表",
                    "report_url": "https://example.com/keep",
                    "parameterized_prepare_parameters": {"keep": "1"},
                },
            },
        )

        original_module = sys.modules.get("report_fetcher.report_configs")
        sys.modules["report_fetcher.report_configs"] = report_configs_module
        try:
            patch_report_configs()
        finally:
            if original_module is None:
                sys.modules.pop("report_fetcher.report_configs", None)
            else:
                sys.modules["report_fetcher.report_configs"] = original_module

        self.assertEqual(report_configs_module.REPORT_URL, TARGET_REPORT_URL)
        for report_key in TARGET_REPORT_KEYS:
            config = report_configs_module.REPORT_CONFIGS[report_key]
            self.assertEqual(config["report_url"], TARGET_REPORT_URL)
            self.assertIsNone(config["report_tab"])
            self.assertEqual(config["parameterized_prepare_strategy"], "interact_then_load")
            self.assertEqual(config["parameterized_prepare_parameters"], TARGET_PARAMETER_TEMPLATE)
            self.assertIsNot(config["parameterized_prepare_parameters"], TARGET_PARAMETER_TEMPLATE)

        self.assertEqual(
            report_configs_module.REPORT_CONFIGS["store_current_period"]["report_name"],
            "NEV本期",
        )
        self.assertEqual(
            report_configs_module.REPORT_CONFIGS["unrelated"],
            {
                "report_name": "不相关报表",
                "report_url": "https://example.com/keep",
                "parameterized_prepare_parameters": {"keep": "1"},
            },
        )
        self.assertEqual(TARGET_REPORT_NAME, "来店批次分车系汇总表_按天")

    def test_patch_report_configs_requires_all_target_keys(self) -> None:
        report_configs_module = types.SimpleNamespace(
            REPORT_URL="https://example.com/old",
            REPORT_CONFIGS={"store_current_period": copy.deepcopy(TARGET_PARAMETER_TEMPLATE)},
        )

        original_module = sys.modules.get("report_fetcher.report_configs")
        sys.modules["report_fetcher.report_configs"] = report_configs_module
        try:
            with self.assertRaisesRegex(RuntimeError, "NEV 来店导出配置缺少报表 key"):
                patch_report_configs()
        finally:
            if original_module is None:
                sys.modules.pop("report_fetcher.report_configs", None)
            else:
                sys.modules["report_fetcher.report_configs"] = original_module

    def test_parse_report2_daily_series_decodes_dates_from_custom_chart_html(self) -> None:
        html = """
        <div widgetname="REPORT2">
          <svg>
            <g clip-path="url(#plot)">
              <g transform="translate(41,11)">
                <line y1="434.5" y2="434.5" x1="0" x2="1443"></line>
                <line y1="347.5" y2="347.5" x1="0" x2="1443"></line>
                <line y1="260.5" y2="260.5" x1="0" x2="1443"></line>
                <line y1="173.5" y2="173.5" x1="0" x2="1443"></line>
                <line y1="86.5" y2="86.5" x1="0" x2="1443"></line>
                <line y1="0.5" y2="0.5" x1="0" x2="1443"></line>
              </g>
              <g class="clipSeriesGroup">
                <g transform="translate(41,11)" class="vancharts-series-0 line">
                  <path d="M0,347.7L10,260.9L20,174.1" />
                </g>
              </g>
              <g>
                <text _x="29.67" _y="437.66">0</text>
                <text _x="7.68" _y="350.86">1000</text>
                <text _x="7.68" _y="264.06">2000</text>
                <text _x="7.68" _y="177.26">3000</text>
                <text _x="7.68" _y="90.46">4000</text>
                <text _x="7.68" _y="3.66">5000</text>
                <text _x="38.70" _y="456.66">2026-04-01</text>
                <text _x="176.13" _y="456.66">2026-04-03</text>
              </g>
            </g>
        </div>
        <div widgetname="自定义来店量"></div>
        """

        actual = parse_report2_daily_series(html, date(2026, 4, 1), date(2026, 4, 3))

        self.assertEqual(
            actual,
            [
                (date(2026, 4, 1), 1000),
                (date(2026, 4, 2), 2000),
                (date(2026, 4, 3), 3000),
            ],
        )

    def test_extract_simplechart_meta_from_page_result_reads_chart_id_and_ec_name(self) -> None:
        page_result = [
            [
                {
                    "position": {"x": 0, "y": 1},
                    "value": json_dumps(
                        {
                            "type": "simplechart",
                            "items": [
                                {
                                    "url": "?op=chart&cmd=writer_out_html&sessionID=session-1&chartID=Cells__A2__A2__abc__index__0&sheetIndex=0&ecName=report2",
                                    "simpleChartInShowID": "Cells__A2__A2__abc__index__0",
                                }
                            ],
                        }
                    ),
                }
            ]
        ]

        actual = extract_simplechart_meta_from_page_result(page_result)

        self.assertEqual(actual.chart_id, "Cells__A2__A2__abc__index__0")
        self.assertEqual(actual.ec_name, "REPORT2")

    def test_extract_daily_rows_from_chart_payload_filters_target_range(self) -> None:
        payload = {
            "chartAttr": {
                "series": [
                    {
                        "name": "来店量",
                        "data": [
                            {"originalCategory": "2026-03-31", "y": "99"},
                            {"originalCategory": "2026-04-01", "y": "100"},
                            {"originalCategory": "2026-04-02", "y": "250"},
                            {"originalCategory": "2026-04-03", "y": "300"},
                        ],
                    }
                ]
            }
        }

        actual = extract_daily_rows_from_chart_payload(payload, date(2026, 4, 1), date(2026, 4, 3))

        self.assertEqual(
            actual,
            [
                (date(2026, 4, 1), 100),
                (date(2026, 4, 2), 250),
                (date(2026, 4, 3), 300),
            ],
        )

    def test_build_chart_data_url_reuses_prepare_origin_and_session(self) -> None:
        actual = build_chart_data_url(
            "https://example.com/webroot/decision/view/fit/form/load/content?_=123",
            "session-1",
            "Cells__A2__A2__abc__index__0",
            "REPORT2",
        )

        self.assertIn("/webroot/decision/view/fit/form/chart/data", actual)
        self.assertIn("sessionID=session-1", actual)
        self.assertIn("chartID=Cells__A2__A2__abc__index__0", actual)
        self.assertIn("ecName=REPORT2", actual)

    @patch("scripts.run_arrival_nev_exports.capture_custom_chart_series")
    @patch("scripts.run_arrival_nev_exports.capture_custom_chart_series_via_api")
    def test_capture_daily_rows_switches_to_slow_browser_query_after_missing_dates(
        self,
        capture_via_api: Mock,
        capture_via_browser: Mock,
    ) -> None:
        expected = [(date(2026, 8, 23), 123)]
        capture_via_api.side_effect = RuntimeError("chart.data 返回的自定义来店按日数据缺少日期：2026-08-23")
        capture_via_browser.return_value = expected
        module = types.SimpleNamespace(log=Mock())
        datetest_module = object()
        page = object()
        export_context = object()
        filter_config = object()
        trace_dir = Path("trace")

        actual, browser_query = capture_daily_rows(
            module,
            datetest_module,
            page,
            export_context,
            filter_config,
            trace_dir,
            query_wait_ms=300_000,
        )
        repeated, repeated_browser_query = capture_daily_rows(
            module,
            datetest_module,
            page,
            export_context,
            filter_config,
            trace_dir,
            query_wait_ms=300_000,
            force_browser_query=browser_query,
        )

        self.assertEqual(actual, expected)
        self.assertEqual(repeated, expected)
        self.assertTrue(browser_query)
        self.assertTrue(repeated_browser_query)
        capture_via_api.assert_called_once_with(export_context, filter_config, trace_dir)
        self.assertEqual(capture_via_browser.call_count, 2)
        capture_via_browser.assert_called_with(
            module,
            datetest_module,
            page,
            filter_config,
            trace_dir,
            timeout_ms=300_000,
        )


def json_dumps(value: dict) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
