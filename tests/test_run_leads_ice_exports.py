from __future__ import annotations

from datetime import date
import sys
import types
import unittest

from scripts.run_leads_ice_exports import (
    SAME_PERIOD_DAY_RULE,
    SAME_PERIOD_FIRST_DAY_RULE,
    SAME_PERIOD_REPORT_KEY,
    SAME_PERIOD_REPORT_NAME,
    TARGET_REPORT_KEY,
    patch_date_resolver,
    patch_report_configs,
)


class RunLeadsIceExportsTests(unittest.TestCase):
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
                resolver({"rule": SAME_PERIOD_DAY_RULE}, "fallback", "2026-07-30"),
                "2025-07-30",
            )
            self.assertEqual(
                resolver({"rule": SAME_PERIOD_FIRST_DAY_RULE}, "fallback", "2024-02-29"),
                "2023-02-01",
            )
            self.assertEqual(
                resolver({"rule": SAME_PERIOD_DAY_RULE}, "fallback", "2024-02-29"),
                "2023-02-28",
            )
            self.assertEqual(resolver({"rule": "yesterday"}, "fallback", "2026-07-30"), "delegated")
            self.assertEqual(delegated_calls, [({"rule": "yesterday"}, "fallback", "2026-07-30")])
        finally:
            if original_module is None:
                sys.modules.pop("report_fetcher.models", None)
            else:
                sys.modules["report_fetcher.models"] = original_module

    def test_patch_report_configs_adds_independent_same_period_report(self) -> None:
        base_config = {
            "enabled": True,
            "report_name": "全国按日ICE",
            "start_date": {"rule": "current_month_first_day"},
            "end_date": {"rule": "business_date"},
            "parameterized_prepare_parameters": {"区域显示": "0"},
        }
        report_configs_module = types.SimpleNamespace(
            REPORT_CONFIGS={TARGET_REPORT_KEY: base_config},
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

        same_period_config = report_configs_module.REPORT_CONFIGS[SAME_PERIOD_REPORT_KEY]
        self.assertEqual(same_period_config["report_name"], SAME_PERIOD_REPORT_NAME)
        self.assertEqual(same_period_config["start_date"], {"rule": SAME_PERIOD_FIRST_DAY_RULE})
        self.assertEqual(same_period_config["end_date"], {"rule": SAME_PERIOD_DAY_RULE})
        self.assertFalse(same_period_config["enabled"])
        self.assertIsNot(same_period_config, base_config)
        self.assertIsNot(
            same_period_config["parameterized_prepare_parameters"],
            base_config["parameterized_prepare_parameters"],
        )
        self.assertEqual(base_config["report_name"], "全国按日ICE")
        self.assertEqual(base_config["start_date"], {"rule": "current_month_first_day"})


if __name__ == "__main__":
    unittest.main()
