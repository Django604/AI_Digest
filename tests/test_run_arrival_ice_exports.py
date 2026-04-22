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
        patched_configs = module.build_effective_report_configs(None, [])

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
            {"store_batch_vehicle_summary_本期_来店", "store_batch_vehicle_summary_同期_来店"},
        )


if __name__ == "__main__":
    unittest.main()
