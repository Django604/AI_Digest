from __future__ import annotations

from datetime import date
import sys
import types
import unittest

from scripts.run_leads_nev_exports import (
    BUSINESS_STATUS_LABEL_PARAMETER_NAME,
    BUSINESS_STATUS_LABEL_TEXT,
    BUSINESS_STATUS_PARAMETER_NAME,
    SAME_PERIOD_FIRST_DAY_RULE,
    SAME_PERIOD_LAST_DAY_RULE,
    SAME_PERIOD_REPORT_KEY,
    SAME_PERIOD_REPORT_NAME,
    TARGET_REPORT_KEY,
    patch_date_resolver,
    patch_report_configs,
)


class RunLeadsNevExportsTests(unittest.TestCase):
    def test_patch_date_resolver_supports_same_period_dates_and_leap_day(self) -> None:
        delegated_calls = []

        def original_resolver(config_value, fallback, business_date=None):
            delegated_calls.append((config_value, fallback, business_date))
            return "delegated"

        models_module = types.SimpleNamespace(
            _resolve_date_value=original_resolver,
            parse_business_date=lambda value: value if isinstance(value, date) else date.fromisoformat(value),
        )
        original_module = sys.modules.get("report_fetcher.models")
        sys.modules["report_fetcher.models"] = models_module
        try:
            patch_date_resolver()
            resolver = models_module._resolve_date_value
            self.assertEqual(
                resolver({"rule": SAME_PERIOD_FIRST_DAY_RULE}, "fallback", "2026-07-30"),
                "2025-07-01",
            )
            self.assertEqual(
                resolver({"rule": SAME_PERIOD_LAST_DAY_RULE}, "fallback", "2026-07-30"),
                "2025-07-31",
            )
            self.assertEqual(
                resolver({"rule": SAME_PERIOD_FIRST_DAY_RULE}, "fallback", "2024-02-29"),
                "2023-02-01",
            )
            self.assertEqual(
                resolver({"rule": SAME_PERIOD_LAST_DAY_RULE}, "fallback", "2024-02-29"),
                "2023-02-28",
            )
            self.assertEqual(resolver({"rule": "yesterday"}, "fallback", "2026-07-30"), "delegated")
            self.assertEqual(delegated_calls, [({"rule": "yesterday"}, "fallback", "2026-07-30")])
        finally:
            if original_module is None:
                sys.modules.pop("report_fetcher.models", None)
            else:
                sys.modules["report_fetcher.models"] = original_module

    def test_patch_report_configs_clears_national_daily_business_status_filter(self) -> None:
        report_configs_module = types.SimpleNamespace(
            REPORT_CONFIGS={
                TARGET_REPORT_KEY: {
                    "parameterized_prepare_parameters": {
                        "core_filters": {
                            "区域显示": "0",
                            BUSINESS_STATUS_PARAMETER_NAME: ["营业店"],
                        },
                        "static_labels": {},
                    },
                },
                "store_current_period": {
                    "parameterized_prepare_parameters": {
                        BUSINESS_STATUS_PARAMETER_NAME: ["营业店"],
                    },
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

        national_parameters = report_configs_module.REPORT_CONFIGS[TARGET_REPORT_KEY]["parameterized_prepare_parameters"]
        same_period_config = report_configs_module.REPORT_CONFIGS[SAME_PERIOD_REPORT_KEY]
        same_period_parameters = same_period_config["parameterized_prepare_parameters"]
        self.assertEqual(national_parameters["core_filters"][BUSINESS_STATUS_PARAMETER_NAME], [])
        self.assertEqual(
            national_parameters["static_labels"][BUSINESS_STATUS_LABEL_PARAMETER_NAME],
            BUSINESS_STATUS_LABEL_TEXT,
        )
        self.assertEqual(same_period_config["report_name"], SAME_PERIOD_REPORT_NAME)
        self.assertEqual(same_period_config["start_date"], {"rule": SAME_PERIOD_FIRST_DAY_RULE})
        self.assertEqual(same_period_config["end_date"], {"rule": SAME_PERIOD_LAST_DAY_RULE})
        self.assertEqual(same_period_parameters["core_filters"][BUSINESS_STATUS_PARAMETER_NAME], [])
        self.assertIsNot(same_period_config, report_configs_module.REPORT_CONFIGS[TARGET_REPORT_KEY])
        self.assertIsNot(same_period_parameters, national_parameters)
        self.assertEqual(
            report_configs_module.REPORT_CONFIGS["store_current_period"]["parameterized_prepare_parameters"][
                BUSINESS_STATUS_PARAMETER_NAME
            ],
            ["营业店"],
        )

    def test_patch_report_configs_supports_flat_parameter_templates(self) -> None:
        report_configs_module = types.SimpleNamespace(
            REPORT_CONFIGS={
                TARGET_REPORT_KEY: {
                    "parameterized_prepare_parameters": {
                        "区域显示": "0",
                        BUSINESS_STATUS_PARAMETER_NAME: ["营业店"],
                    },
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

        parameters = report_configs_module.REPORT_CONFIGS[TARGET_REPORT_KEY]["parameterized_prepare_parameters"]
        same_period_parameters = report_configs_module.REPORT_CONFIGS[SAME_PERIOD_REPORT_KEY][
            "parameterized_prepare_parameters"
        ]
        self.assertEqual(parameters[BUSINESS_STATUS_PARAMETER_NAME], [])
        self.assertEqual(parameters[BUSINESS_STATUS_LABEL_PARAMETER_NAME], BUSINESS_STATUS_LABEL_TEXT)
        self.assertEqual(same_period_parameters[BUSINESS_STATUS_PARAMETER_NAME], [])
        self.assertEqual(
            same_period_parameters[BUSINESS_STATUS_LABEL_PARAMETER_NAME],
            BUSINESS_STATUS_LABEL_TEXT,
        )


if __name__ == "__main__":
    unittest.main()
