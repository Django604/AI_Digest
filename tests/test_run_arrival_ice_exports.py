from __future__ import annotations

import copy
import types
import unittest
from dataclasses import dataclass

from scripts.run_arrival_ice_exports import (
    TARGET_CROSSTAB_SHEET,
    TARGET_REPORT_KEYS,
    patch_report_config_builder,
)


@dataclass(frozen=True)
class FakeReportConfig:
    key: str
    crosstab_sheet_name: str
    request_metadata: dict


class RunArrivalIceExportsTests(unittest.TestCase):
    def test_patch_report_config_builder_pins_only_target_thumbnail_uri(self) -> None:
        original_config = FakeReportConfig(
            key="store_batch_vehicle_summary_本期_来店",
            crosstab_sheet_name="E3S报表样式",
            request_metadata={
                "export_crosstab": {
                    "thumbnail_uris": {
                        "来店批次分车系汇总表": "/thumb/views/_0/sheet2",
                        TARGET_CROSSTAB_SHEET: "/thumb/views/_0/_T",
                    }
                }
            },
        )
        untouched_config = FakeReportConfig(
            key="store_batch_vehicle_summary_本期_自然",
            crosstab_sheet_name="E3S报表样式",
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

        self.assertEqual(patched_target.crosstab_sheet_name, "E3S报表样式")
        self.assertEqual(
            patched_target.request_metadata["export_crosstab"]["thumbnail_uris"],
            {TARGET_CROSSTAB_SHEET: "/thumb/views/_0/_T"},
        )
        self.assertEqual(
            patched_untouched.request_metadata["export_crosstab"]["thumbnail_uris"],
            untouched_config.request_metadata["export_crosstab"]["thumbnail_uris"],
        )
        self.assertEqual(set(TARGET_REPORT_KEYS), {"store_batch_vehicle_summary_本期_来店", "store_batch_vehicle_summary_同期_来店"})


if __name__ == "__main__":
    unittest.main()
