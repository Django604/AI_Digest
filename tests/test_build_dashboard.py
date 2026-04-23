from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from openpyxl import Workbook

from scripts.build_dashboard import (
    ARRIVAL_BOOK,
    LEADS_BOOK,
    OUT_JSON,
    SUMMARY_JSON,
    build_payload,
    build_run_summary,
    load_arrival_daily_sheet,
    validate_report_date_cell,
    validate_sheet_headers,
    validate_workbook_structure,
    write_json_if_changed,
)


class BuildDashboardPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build_payload(LEADS_BOOK, ARRIVAL_BOOK)

    def test_expected_dashboards_exist(self) -> None:
        self.assertEqual(
            set(self.payload["dashboards"].keys()),
            {"brief", "lead-control", "nev", "ice", "arrival"},
        )

    def test_lead_control_row_order_is_stable(self) -> None:
        trend = self.payload["dashboards"]["lead-control"]["sections"][0]["trend"]
        self.assertEqual(
            trend["matrix"]["visibleRowKeys"],
            [
                "previousActual",
                "previousCumulative",
                "actual",
                "cumulativeActual",
                "dayDelta",
                "cumulativeDelta",
            ],
        )

    def test_cumulative_actual_never_uses_na_placeholder(self) -> None:
        for dashboard in self.payload["dashboards"].values():
            for section in dashboard.get("sections", []):
                rows = section.get("trend", {}).get("matrix", {}).get("rows", [])
                for row in rows:
                    if row.get("key") == "cumulativeActual":
                        self.assertNotIn("#N/A", row.get("displayValues", []))

    def test_build_run_summary_contains_dashboard_counts(self) -> None:
        summary = build_run_summary(
            self.payload,
            LEADS_BOOK,
            ARRIVAL_BOOK,
            OUT_JSON,
            SUMMARY_JSON,
            False,
        )
        self.assertEqual(summary["reportDate"], self.payload["meta"]["reportDate"])
        self.assertEqual(summary["outputs"]["dashboardStatus"], "unchanged")
        self.assertEqual(summary["stats"]["dashboardCount"], 5)
        self.assertEqual(summary["stats"]["sectionCounts"]["lead-control"], 1)

    def test_arrival_dashboard_uses_nev_daily_arrivals_for_nev_actual_row(self) -> None:
        trend = self.payload["dashboards"]["arrival"]["sections"][0]["trend"]
        rows = {row["key"]: row["displayValues"] for row in trend["matrix"]["rows"]}
        report_index = trend["chart"]["reportDayIndex"]

        self.assertIn("nevActual", rows)
        self.assertNotEqual(rows["nevActual"][report_index], "-")

    def test_arrival_dashboard_keeps_first_day_for_ice_actual_row(self) -> None:
        trend = self.payload["dashboards"]["arrival"]["sections"][0]["trend"]
        rows = {row["key"]: row["displayValues"] for row in trend["matrix"]["rows"]}

        self.assertIn("iceActual", rows)
        self.assertNotEqual(rows["iceActual"][0], "-")

    def test_write_json_if_changed_ignores_generated_at_only(self) -> None:
        original = {
            "meta": {"generatedAt": "2026-04-15T16:00:00", "reportDate": "2026-04-15"},
            "dashboards": {"brief": {"id": "brief"}},
        }
        regenerated = {
            "meta": {"generatedAt": "2026-04-15T16:05:00", "reportDate": "2026-04-15"},
            "dashboards": {"brief": {"id": "brief"}},
        }

        temp_dir = Path("tests/.tmp/write-json-if-changed")
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            json_path = temp_dir / "dashboard.json"
            json_path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")
            changed, existing_payload = write_json_if_changed(
                json_path,
                regenerated,
                volatile_field_paths=(("meta", "generatedAt"),),
            )

            self.assertFalse(changed)
            self.assertEqual(existing_payload, original)
            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["meta"]["generatedAt"], original["meta"]["generatedAt"])
        finally:
            shutil.rmtree(temp_dir.parent, ignore_errors=True)


class BuildDashboardValidationTests(unittest.TestCase):
    def test_load_arrival_daily_sheet_supports_sheets_without_header_row(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet["A1"] = "2026年4月1日"
        sheet["B1"] = 1187
        sheet["A2"] = "2026年4月2日"
        sheet["B2"] = 1006

        actual = load_arrival_daily_sheet(sheet)

        self.assertEqual(list(actual.values())[:2], [1187, 1006])

    def test_validate_workbook_structure_requires_expected_sheets(self) -> None:
        leads = Workbook()
        arrival = Workbook()
        with self.assertRaisesRegex(ValueError, "线索工作簿 缺少必需工作表"):
            validate_workbook_structure(leads, arrival)

    def test_validate_sheet_headers_requires_expected_columns(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "目标竖版"
        sheet["A2"] = "不是合计"
        with self.assertRaisesRegex(ValueError, "缺少必需列"):
            validate_sheet_headers(sheet, 2, ("合计",), sheet.title)

    def test_validate_report_date_cell_uses_summary_fallback_when_formula_cache_missing(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "参数"
        sheet["C2"] = "not-a-date"
        self.assertIsNotNone(validate_report_date_cell(workbook))

    def test_validate_report_date_cell_requires_valid_date_without_fallback(self) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "参数"
        sheet["C2"] = "not-a-date"
        with patch("scripts.build_dashboard.read_json_file", return_value=None):
            with self.assertRaisesRegex(ValueError, "参数!C2 未读取到有效日期"):
                validate_report_date_cell(workbook)


if __name__ == "__main__":
    unittest.main()
