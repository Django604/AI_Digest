from __future__ import annotations

import calendar
import json
from datetime import date
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from openpyxl import Workbook

from scripts.build_dashboard import (
    ARRIVAL_BOOK,
    LEADS_BOOK,
    MONTHLY_ARCHIVE_DIR,
    OUT_JSON,
    SUMMARY_JSON,
    build_arrival_series,
    build_column_meta,
    build_payload,
    build_run_summary,
    get_day_calendar_meta,
    load_arrival_daily_sheet,
    validate_report_date_cell,
    validate_sheet_headers,
    validate_workbook_structure,
    write_monthly_archive,
    write_json_if_changed,
)


class BuildDashboardPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = build_payload(LEADS_BOOK, ARRIVAL_BOOK)
        report_date = date.fromisoformat(cls.payload["meta"]["reportDate"])
        previous_year = report_date.year if report_date.month > 1 else report_date.year - 1
        previous_month = report_date.month - 1 if report_date.month > 1 else 12
        previous_month_end = date(
            previous_year,
            previous_month,
            calendar.monthrange(previous_year, previous_month)[1],
        )
        cls.previous_month_payload = build_payload(
            LEADS_BOOK,
            ARRIVAL_BOOK,
            report_date_override=previous_month_end,
        )
        cls.previous_month_key = f"{previous_month_end.year:04d}-{previous_month_end.month:02d}"
        cls.previous_month_archive_path = MONTHLY_ARCHIVE_DIR / cls.previous_month_key / "dashboard.json"
        cls.previous_month_archive_payload = (
            json.loads(cls.previous_month_archive_path.read_text(encoding="utf-8"))
            if cls.previous_month_archive_path.exists()
            else None
        )

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

    def test_build_run_summary_includes_archive_outputs_when_provided(self) -> None:
        summary = build_run_summary(
            self.payload,
            LEADS_BOOK,
            ARRIVAL_BOOK,
            OUT_JSON,
            SUMMARY_JSON,
            True,
            archive_info={
                "monthKey": "2026-04",
                "dashboardPath": "./data/monthly/2026-04/dashboard.json",
                "summaryPath": "./data/monthly/2026-04/dashboard.summary.json",
                "indexPath": "./data/monthly/index.json",
                "dashboardChanged": True,
                "summaryChanged": False,
                "indexChanged": True,
            },
        )
        self.assertEqual(summary["outputs"]["archiveMonth"], "2026-04")
        self.assertEqual(summary["outputs"]["archiveIndexJson"], "./data/monthly/index.json")
        self.assertTrue(summary["outputs"]["archiveDashboardChanged"])

    def test_arrival_dashboard_uses_nev_daily_arrivals_for_nev_actual_row(self) -> None:
        if self.previous_month_archive_payload is None:
            self.skipTest(f"missing monthly archive payload for {self.previous_month_key}")
        trend = self.previous_month_archive_payload["dashboards"]["arrival"]["sections"][0]["trend"]
        rows = {row["key"]: row["displayValues"] for row in trend["matrix"]["rows"]}
        report_index = trend["chart"]["reportDayIndex"]

        self.assertIn("nevActual", rows)
        self.assertNotEqual(rows["nevActual"][report_index], "-")

    def test_arrival_dashboard_keeps_first_day_for_ice_actual_row(self) -> None:
        if self.previous_month_archive_payload is None:
            self.skipTest(f"missing monthly archive payload for {self.previous_month_key}")
        trend = self.previous_month_archive_payload["dashboards"]["arrival"]["sections"][0]["trend"]
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

    def test_write_monthly_archive_creates_snapshot_and_index(self) -> None:
        temp_dir = Path("tests/.tmp/monthly-archive")
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            archive_root = temp_dir / "monthly"
            index_path = archive_root / "index.json"
            expected_month = self.payload["meta"]["reportDate"][:7]
            summary_payload = build_run_summary(
                self.payload,
                LEADS_BOOK,
                ARRIVAL_BOOK,
                OUT_JSON,
                SUMMARY_JSON,
                True,
            )

            archive_info = write_monthly_archive(
                self.payload,
                summary_payload,
                archive_root=archive_root,
                index_path=index_path,
                docs_root=temp_dir,
            )

            self.assertEqual(archive_info["monthKey"], expected_month)
            self.assertTrue((archive_root / expected_month / "dashboard.json").exists())
            self.assertTrue((archive_root / expected_month / "dashboard.summary.json").exists())
            index_payload = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(index_payload["latestMonth"], expected_month)
            self.assertEqual(index_payload["months"][0]["dashboardPath"], f"./monthly/{expected_month}/dashboard.json")
        finally:
            shutil.rmtree(temp_dir.parent, ignore_errors=True)


class BuildDashboardValidationTests(unittest.TestCase):
    def test_day_calendar_meta_distinguishes_holiday_weekend_makeup_and_regular_workday(self) -> None:
        self.assertEqual(get_day_calendar_meta(date(2026, 5, 4))["dayType"], "holiday")
        self.assertEqual(get_day_calendar_meta(date(2026, 5, 5))["dayType"], "holiday")
        self.assertEqual(get_day_calendar_meta(date(2026, 5, 9))["dayType"], "makeupWorkday")
        self.assertEqual(get_day_calendar_meta(date(2026, 5, 10))["dayType"], "weekend")
        self.assertEqual(get_day_calendar_meta(date(2026, 5, 11))["dayType"], "regularWorkday")

    def test_build_column_meta_marks_makeup_workday_without_weekend_or_holiday_flags(self) -> None:
        meta = build_column_meta(date(2026, 5, 9), date(2026, 4, 9))

        self.assertTrue(meta["highlightCurrent"])
        self.assertTrue(meta["isCurrentMakeupWorkday"])
        self.assertFalse(meta["isCurrentHoliday"])
        self.assertFalse(meta["isCurrentWeekend"])
        self.assertEqual(meta["currentDayType"], "makeupWorkday")

    def test_arrival_previous_cumulative_stops_at_last_available_previous_day(self) -> None:
        series = build_arrival_series(
            date(2026, 5, 5),
            {
                date(2026, 5, 1): 10,
                date(2026, 5, 2): 20,
                date(2026, 5, 3): 30,
                date(2026, 5, 4): 40,
                date(2026, 5, 5): 50,
            },
            {
                date(2025, 5, 1): 100,
                date(2025, 5, 2): 200,
                date(2025, 5, 3): 300,
            },
        )

        self.assertEqual(series["previousReportIndex"], 2)
        self.assertEqual(series["previousCumulative"][:6], [100, 300, 600, None, None, None])

    def test_arrival_previous_cumulative_stays_empty_when_no_previous_data_exists(self) -> None:
        series = build_arrival_series(
            date(2026, 5, 1),
            {
                date(2026, 5, 1): 10,
            },
            {},
        )

        self.assertIsNone(series["previousReportIndex"])
        self.assertTrue(all(value is None for value in series["previousCumulative"]))

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
