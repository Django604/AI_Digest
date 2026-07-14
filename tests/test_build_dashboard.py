from __future__ import annotations

import calendar
import json
from datetime import date
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from openpyxl import Workbook, load_workbook

from scripts.build_dashboard import (
    ARRIVAL_BOOK,
    LEADS_BOOK,
    MONTHLY_ARCHIVE_DIR,
    NEV_CORE_MODELS,
    NEV_DETAIL_MODELS,
    OUT_JSON,
    SUMMARY_JSON,
    apply_preserved_input_modified_times,
    build_arrival_series,
    build_column_meta,
    build_payload,
    build_run_summary,
    build_nev_section,
    file_mtime_iso,
    get_day_calendar_meta,
    load_preserved_input_modified_times,
    load_arrival_daily_sheet,
    load_ice_daily,
    load_nev_daily,
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

    def test_nev_model_groups_keep_new_pathfinder_out_of_core_total(self) -> None:
        core_model_names = [model_name for _, _, model_name in NEV_CORE_MODELS]
        detail_model_names = [model_name for _, _, model_name in NEV_DETAIL_MODELS]

        self.assertEqual(core_model_names, ["NX8", "N7", "N6", "天籁·鸿蒙座舱"])
        self.assertEqual(detail_model_names, [*core_model_names, "新探陆"])

    def test_new_pathfinder_section_follows_existing_nev_models(self) -> None:
        sections = self.payload["dashboards"]["nev"]["sections"]

        self.assertEqual([section["title"] for section in sections][-2:], ["天籁·鸿蒙座舱", "新探陆"])
        self.assertEqual(sections[-1]["id"], "new-pathfinder")

    def test_new_pathfinder_section_includes_all_current_month_source_data(self) -> None:
        section = next(
            item for item in self.payload["dashboards"]["nev"]["sections"]
            if item["id"] == "new-pathfinder"
        )
        matrix = section["trend"]["matrix"]
        rows = {row["key"]: row["displayValues"] for row in matrix["rows"]}
        values_by_date = dict(zip(matrix["labels"], rows["actual"]))

        self.assertEqual(values_by_date["7/10"], "2")
        self.assertEqual(values_by_date["7/11"], "0")
        self.assertEqual(values_by_date["7/13"], "0")

    def test_new_pathfinder_without_targets_displays_placeholders(self) -> None:
        section = next(
            item for item in self.payload["dashboards"]["nev"]["sections"]
            if item["id"] == "new-pathfinder"
        )
        cards = {card["label"]: card for card in section["summary"]["cards"]}
        matrix_rows = {row["key"]: row for row in section["trend"]["matrix"]["rows"]}

        self.assertEqual(cards["累计目标"]["displayValue"], "-")
        self.assertEqual(cards["累计达成率"]["displayValue"], "-")
        self.assertEqual(cards["当日目标"]["displayValue"], "-")
        self.assertEqual(cards["当日达成率"]["displayValue"], "-")
        self.assertTrue(all(value == "-" for value in matrix_rows["target"]["displayValues"]))
        self.assertTrue(all(value is None for value in section["trend"]["chart"]["series"]["target"]))

    def test_new_pathfinder_targets_are_used_when_available(self) -> None:
        report_date = date(2026, 7, 16)
        current_actuals = {
            date(2026, 7, 15): {"newLeads": 4, "arrivals": 1},
            report_date: {"newLeads": 6, "arrivals": 2},
        }
        current_targets = {
            date(2026, 7, 15): 5,
            report_date: 10,
        }

        section = build_nev_section(
            "new-pathfinder",
            "新探陆",
            report_date,
            current_actuals,
            {},
            current_targets,
        )
        cards = {card["label"]: card for card in section["summary"]["cards"]}

        self.assertEqual(cards["累计目标"]["displayValue"], "15")
        self.assertEqual(cards["累计达成率"]["displayValue"], "66.7%")
        self.assertEqual(cards["当日目标"]["displayValue"], "10")
        self.assertEqual(cards["当日达成率"]["displayValue"], "60.0%")

    def test_nev_total_excludes_new_pathfinder_actuals(self) -> None:
        sections = {
            section["id"]: section
            for section in self.payload["dashboards"]["nev"]["sections"]
        }
        core_cumulative = sum(
            sections[section_id]["summary"]["cards"][0]["value"]
            for section_id, _, _ in NEV_CORE_MODELS
        )
        new_pathfinder_cumulative = sections["new-pathfinder"]["summary"]["cards"][0]["value"]
        nev_total_cumulative = sections["nev-total"]["summary"]["cards"][0]["value"]

        self.assertEqual(nev_total_cumulative, core_cumulative)
        self.assertGreater(new_pathfinder_cumulative, 0)
        self.assertNotEqual(nev_total_cumulative, core_cumulative + new_pathfinder_cumulative)

    def test_lead_control_includes_new_pathfinder_valid_leads(self) -> None:
        current_date = date(2026, 7, 10)
        workbook = load_workbook(LEADS_BOOK, data_only=True)
        try:
            nev_daily = load_nev_daily(
                workbook["全国按日NEV"],
                current_date.replace(day=1),
                current_date,
            )
            ice_daily = load_ice_daily(
                workbook["全国按日ICE"],
                current_date.replace(day=1),
                current_date,
            )
        finally:
            workbook.close()

        core_nev_valid = sum(
            nev_daily.get(model_name, {}).get(current_date, {}).get("validLeads") or 0
            for _, _, model_name in NEV_CORE_MODELS
        )
        new_pathfinder_valid = (
            nev_daily.get("新探陆", {}).get(current_date, {}).get("validLeads") or 0
        )
        expected_all_vehicle_valid = (
            core_nev_valid
            + new_pathfinder_valid
            + (ice_daily.get(current_date, {}).get("validLeads") or 0)
        )
        lead_control = self.payload["dashboards"]["lead-control"]["sections"][0]
        actual_all_vehicle_valid = lead_control["trend"]["chart"]["series"]["actual"][current_date.day - 1]

        self.assertEqual(new_pathfinder_valid, 1)
        self.assertEqual(actual_all_vehicle_valid, expected_all_vehicle_valid)

    def test_daily_brief_uses_separate_new_pathfinder_section(self) -> None:
        sections = self.payload["dashboards"]["brief"]["briefing"]["sections"]
        sections_by_kind = {section["kind"]: section for section in sections}

        self.assertEqual(
            [section["kind"] for section in sections],
            ["intro", "nev", "sylphy15", "new-pathfinder", "arrival"],
        )
        self.assertEqual(sections_by_kind["new-pathfinder"]["title"], "新探陆线索")
        self.assertIn("新探陆累计实绩 2", sections_by_kind["new-pathfinder"]["lines"][0])
        self.assertIn("累计达成率 -", sections_by_kind["new-pathfinder"]["lines"][0])
        self.assertFalse(any("新探陆" in line for line in sections_by_kind["nev"]["lines"]))

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
        self.assertEqual(summary["inputs"]["workbookModifiedAt"], file_mtime_iso(LEADS_BOOK))
        self.assertEqual(summary["inputs"]["arrivalWorkbookModifiedAt"], file_mtime_iso(ARRIVAL_BOOK))

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

    def test_preserved_times_override_dashboard_and_summary_file_mtimes(self) -> None:
        preserved_times = {
            "workbookModifiedAt": "2026-07-14T09:06:37",
            "arrivalWorkbookModifiedAt": "2026-07-14T09:06:38",
        }
        payload = {
            **self.payload,
            "meta": {**self.payload["meta"]},
        }

        apply_preserved_input_modified_times(payload, preserved_times)
        summary = build_run_summary(
            payload,
            LEADS_BOOK,
            ARRIVAL_BOOK,
            OUT_JSON,
            SUMMARY_JSON,
            True,
            input_modified_times=preserved_times,
        )

        self.assertEqual(payload["meta"]["workbookModifiedAt"], preserved_times["workbookModifiedAt"])
        self.assertEqual(summary["inputs"]["workbookModifiedAt"], preserved_times["workbookModifiedAt"])
        self.assertEqual(
            summary["inputs"]["arrivalWorkbookModifiedAt"],
            preserved_times["arrivalWorkbookModifiedAt"],
        )

    def test_load_preserved_times_reads_consistent_committed_outputs(self) -> None:
        temp_dir = Path("tests/.tmp/preserved-input-times")
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            dashboard_path = temp_dir / "dashboard.json"
            summary_path = temp_dir / "dashboard.summary.json"
            dashboard_path.write_text(
                json.dumps({"meta": {"workbookModifiedAt": "2026-07-14T09:06:37"}}),
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "inputs": {
                            "workbookModifiedAt": "2026-07-14T09:06:37",
                            "arrivalWorkbookModifiedAt": "2026-07-14T09:06:38",
                        }
                    }
                ),
                encoding="utf-8",
            )

            preserved_times = load_preserved_input_modified_times(dashboard_path, summary_path)

            self.assertEqual(preserved_times["workbookModifiedAt"], "2026-07-14T09:06:37")
            self.assertEqual(preserved_times["arrivalWorkbookModifiedAt"], "2026-07-14T09:06:38")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_load_preserved_times_rejects_inconsistent_leads_time(self) -> None:
        temp_dir = Path("tests/.tmp/inconsistent-preserved-input-times")
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            dashboard_path = temp_dir / "dashboard.json"
            summary_path = temp_dir / "dashboard.summary.json"
            dashboard_path.write_text(
                json.dumps({"meta": {"workbookModifiedAt": "2026-07-14T09:06:37"}}),
                encoding="utf-8",
            )
            summary_path.write_text(
                json.dumps(
                    {
                        "inputs": {
                            "workbookModifiedAt": "2026-07-14T01:07:00",
                            "arrivalWorkbookModifiedAt": "2026-07-14T09:06:38",
                        }
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "dashboard 与 summary 中的线索工作簿时间不一致"):
                load_preserved_input_modified_times(dashboard_path, summary_path)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_load_preserved_times_rejects_missing_or_malformed_metadata(self) -> None:
        temp_dir = Path("tests/.tmp/malformed-preserved-input-times")
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            dashboard_path = temp_dir / "dashboard.json"
            summary_path = temp_dir / "dashboard.summary.json"
            dashboard_path.write_text(json.dumps({"meta": {}}), encoding="utf-8")
            summary_path.write_text(json.dumps({"inputs": {}}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "不是有效的 ISO 本地时间"):
                load_preserved_input_modified_times(dashboard_path, summary_path)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_pages_workflow_preserves_committed_input_modified_times(self) -> None:
        workflow = (Path(__file__).parents[1] / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        self.assertIn("--preserve-input-modified-times", workflow)

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
