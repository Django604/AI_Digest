from __future__ import annotations

import copy
import types
import unittest
from dataclasses import dataclass

from scripts.run_arrival_ice_exports import (
    TARGET_EXPORT_SHEET,
    TARGET_REPORT_KEYS,
    TARGET_THUMBNAIL_SHEET,
    patch_report_config_builder,
    switch_tableau_view_to_daily,
)


@dataclass(frozen=True)
class FakeReportConfig:
    key: str
    start_date: str
    end_date: str
    bi_target_url: str
    crosstab_sheet_name: str
    single_select_parameters: tuple
    request_metadata: dict


class RunArrivalIceExportsTests(unittest.TestCase):
    def test_switch_tableau_view_to_daily_rewrites_sheet2_fragment(self) -> None:
        source_url = (
            "https://e3s-bi.dongfeng-nissan.com.cn/#/views/_0/sheet2"
            "?3Adisplay_spinner=yes&%3Aembed=y#21"
        )

        actual = switch_tableau_view_to_daily(source_url)

        self.assertIn("/_T?3Adisplay_spinner=yes", actual)
        self.assertNotIn("/sheet2?", actual)

    def test_patch_report_config_builder_targets_daily_thumbnail_and_export_sheet(self) -> None:
        original_config = FakeReportConfig(
            key="store_batch_vehicle_summary_本期_来店",
            start_date="2026-09-01",
            end_date="2026-09-03",
            bi_target_url=(
                "https://e3s-bi.dongfeng-nissan.com.cn/#/views/_0/sheet2"
                "?3Adisplay_spinner=yes&%3Aembed=y#21"
            ),
            crosstab_sheet_name="E3S报表样式",
            single_select_parameters=(types.SimpleNamespace(label="显示二网业绩"), types.SimpleNamespace(label="车系类型")),
            request_metadata={
                "export_crosstab": {
                    "thumbnail_uris": {
                        "来店批次分车系汇总表": "/thumb/views/_0/sheet2",
                        TARGET_THUMBNAIL_SHEET: "/thumb/views/_0/_T",
                    }
                }
            },
        )
        untouched_config = FakeReportConfig(
            key="store_batch_vehicle_summary_本期_自然",
            start_date="2026-09-01",
            end_date="2026-09-03",
            bi_target_url=original_config.bi_target_url,
            crosstab_sheet_name="E3S报表样式",
            single_select_parameters=original_config.single_select_parameters,
            request_metadata=copy.deepcopy(original_config.request_metadata),
        )

        module = types.SimpleNamespace()

        def builder(_args, _report_keys):
            return [original_config, untouched_config]

        module.build_effective_report_configs = builder

        patch_report_config_builder(module)
        patched_configs = module.build_effective_report_configs(types.SimpleNamespace(end_date=None), [])

        self.assertEqual(len(patched_configs), 2)
        patched_target, patched_untouched = patched_configs

        self.assertEqual(
            patched_target.request_metadata["export_crosstab"]["thumbnail_uris"],
            {TARGET_THUMBNAIL_SHEET: "/thumb/views/_0/_T"},
        )
        self.assertIn("/_T?3Adisplay_spinner=yes", patched_target.bi_target_url)
        self.assertEqual(patched_target.crosstab_sheet_name, TARGET_EXPORT_SHEET)
        self.assertEqual(patched_target.single_select_parameters, ())
        self.assertEqual(
            patched_untouched.request_metadata["export_crosstab"]["thumbnail_uris"],
            untouched_config.request_metadata["export_crosstab"]["thumbnail_uris"],
        )
        self.assertEqual(patched_untouched.bi_target_url, untouched_config.bi_target_url)
        self.assertEqual(
            [item.label for item in patched_untouched.single_select_parameters],
            [item.label for item in untouched_config.single_select_parameters],
        )
        self.assertEqual(
            set(TARGET_REPORT_KEYS),
            {
                "store_batch_vehicle_summary_本期_来店",
                "store_batch_vehicle_summary_上期_来店",
                "store_batch_vehicle_summary_同期_来店",
            },
        )

    def test_patch_report_config_builder_fetches_full_previous_and_same_months(self) -> None:
        def make_config(key: str, start_date: str, end_date: str) -> FakeReportConfig:
            return FakeReportConfig(
                key=key,
                start_date=start_date,
                end_date=end_date,
                bi_target_url="https://example.com/#/views/_0/sheet2",
                crosstab_sheet_name="E3S报表样式",
                single_select_parameters=(),
                request_metadata={
                    "export_crosstab": {
                        "thumbnail_uris": {TARGET_THUMBNAIL_SHEET: "/thumb/views/_0/_T"}
                    }
                },
            )

        configs = [
            make_config("store_batch_vehicle_summary_本期_来店", "2026-09-01", "2026-09-03"),
            make_config("store_batch_vehicle_summary_上期_来店", "2026-08-01", "2026-08-03"),
            make_config("store_batch_vehicle_summary_同期_来店", "2025-09-01", "2025-09-03"),
        ]
        module = types.SimpleNamespace(build_effective_report_configs=lambda _args, _keys: configs)

        patch_report_config_builder(module)
        actual = module.build_effective_report_configs(types.SimpleNamespace(end_date=None), [])

        self.assertEqual([item.end_date for item in actual], ["2026-09-03", "2026-08-31", "2025-09-30"])

    def test_patch_report_config_builder_respects_explicit_end_date(self) -> None:
        config = FakeReportConfig(
            key="store_batch_vehicle_summary_上期_来店",
            start_date="2026-08-01",
            end_date="2026-08-15",
            bi_target_url="https://example.com/#/views/_0/sheet2",
            crosstab_sheet_name="E3S报表样式",
            single_select_parameters=(),
            request_metadata={
                "export_crosstab": {
                    "thumbnail_uris": {TARGET_THUMBNAIL_SHEET: "/thumb/views/_0/_T"}
                }
            },
        )
        module = types.SimpleNamespace(build_effective_report_configs=lambda _args, _keys: [config])

        patch_report_config_builder(module)
        actual = module.build_effective_report_configs(types.SimpleNamespace(end_date="2026-08-15"), [])

        self.assertEqual(actual[0].end_date, "2026-08-15")


if __name__ == "__main__":
    unittest.main()
