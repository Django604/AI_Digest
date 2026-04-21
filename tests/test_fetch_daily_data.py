from __future__ import annotations

import json
import shutil
import unittest
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook

from scripts.build_dashboard import ARRIVAL_BOOK, LEADS_BOOK, safe_close_workbook
from scripts.fetch_daily_data import (
    ARRIVAL_SHEET_MAPPINGS,
    LEADS_SHEET_MAPPINGS,
    SHEET_MAPPINGS,
    parse_business_date,
    rebuild_dashboard,
    replace_workbook_sheets,
    resolve_export_path,
)


class FetchDailyDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path("tests/.tmp/fetch-daily-data")
        shutil.rmtree(self.temp_root, ignore_errors=True)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_parse_business_date_supports_compact_format(self) -> None:
        self.assertEqual(parse_business_date("20260420"), date(2026, 4, 20))

    def test_resolve_export_path_uses_business_date_suffix(self) -> None:
        output_dir = self.temp_root / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "全国按日-0419.xlsx").write_text("old", encoding="utf-8")
        expected = output_dir / "全国按日-0420.xlsx"
        expected.write_text("new", encoding="utf-8")

        resolved = resolve_export_path(output_dir, "全国按日", date(2026, 4, 20))

        self.assertEqual(resolved, expected)

    def test_resolve_export_path_supports_alias_report_names(self) -> None:
        output_dir = self.temp_root / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)
        expected = output_dir / "专营店本期-0420.xlsx"
        expected.write_text("alias", encoding="utf-8")

        resolved = resolve_export_path(output_dir, ("NEV本期", "专营店本期"), date(2026, 4, 20))

        self.assertEqual(resolved, expected)

    def test_replace_workbook_sheets_overwrites_target_sheets(self) -> None:
        leads_path = self.temp_root / "NEV+ICE_xsai.xlsx"
        workbook = Workbook()
        default_sheet = workbook.active
        workbook.remove(default_sheet)
        for mapping in SHEET_MAPPINGS:
            ws = workbook.create_sheet(mapping.target_sheet)
            ws["A1"] = "旧值"
            ws["B2"] = "待清空"
            ws.merge_cells("A1:B1")
        workbook.save(leads_path)
        workbook.close()

        export_paths: dict[str, Path] = {}
        for index, mapping in enumerate(SHEET_MAPPINGS, start=1):
            export_path = self.temp_root / f"{mapping.result_label}.xlsx"
            export_wb = Workbook()
            export_ws = export_wb.active
            export_ws.title = "导出"
            export_ws["A1"] = mapping.result_label
            export_ws["A2"] = index
            export_ws["C3"] = f"sheet-{index}"
            export_ws.merge_cells("A1:C1")
            export_wb.save(export_path)
            export_wb.close()
            export_paths[mapping.target_sheet] = export_path

        replace_workbook_sheets(leads_path, export_paths, SHEET_MAPPINGS, log=lambda _message: None)

        updated = load_workbook(leads_path)
        try:
            for index, mapping in enumerate(SHEET_MAPPINGS, start=1):
                ws = updated[mapping.target_sheet]
                self.assertEqual(ws["A1"].value, mapping.result_label)
                self.assertEqual(ws["A2"].value, index)
                self.assertEqual(ws["C3"].value, f"sheet-{index}")
                self.assertIn("A1:C1", {str(item) for item in ws.merged_cells.ranges})
                self.assertIsNone(ws["B2"].value)
        finally:
            safe_close_workbook(updated)

    def test_replace_workbook_sheets_supports_macro_and_non_macro_targets(self) -> None:
        macro_path = self.temp_root / "NEV+ICE_xsai.xlsm"
        arrival_path = self.temp_root / "NEV+ICE_ldai.xlsx"

        for workbook_path, mappings in ((macro_path, LEADS_SHEET_MAPPINGS), (arrival_path, ARRIVAL_SHEET_MAPPINGS)):
            workbook = Workbook()
            default_sheet = workbook.active
            workbook.remove(default_sheet)
            for mapping in mappings:
                ws = workbook.create_sheet(mapping.target_sheet)
                ws["A1"] = "旧值"
            workbook.save(workbook_path)
            workbook.close()

            export_paths: dict[str, Path] = {}
            for mapping in mappings:
                export_path = self.temp_root / f"{mapping.target_sheet}.xlsx"
                export_wb = Workbook()
                export_ws = export_wb.active
                export_ws.title = "导出"
                export_ws["A1"] = mapping.target_sheet
                export_wb.save(export_path)
                export_wb.close()
                export_paths[mapping.target_sheet] = export_path

            replace_workbook_sheets(
                workbook_path,
                export_paths,
                mappings,
                log=lambda _message: None,
                keep_vba=workbook_path.suffix.lower() == ".xlsm",
            )

            updated = load_workbook(workbook_path, keep_vba=workbook_path.suffix.lower() == ".xlsm")
            try:
                for mapping in mappings:
                    self.assertEqual(updated[mapping.target_sheet]["A1"].value, mapping.target_sheet)
            finally:
                safe_close_workbook(updated)

    def test_rebuild_dashboard_uses_business_date_override(self) -> None:
        out_path = self.temp_root / "dashboard.json"
        summary_path = self.temp_root / "dashboard.summary.json"

        result = rebuild_dashboard(
            business_date=date(2026, 4, 20),
            leads_path=LEADS_BOOK,
            arrival_path=ARRIVAL_BOOK,
            out_path=out_path,
            summary_path=summary_path,
            log=lambda _message: None,
        )

        payload = json.loads(out_path.read_text(encoding="utf-8"))
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["meta"]["reportDate"], "2026-04-20")
        self.assertEqual(summary["reportDate"], "2026-04-20")
        self.assertIn("dashboardChanged", result)
        self.assertIn("summaryChanged", result)


if __name__ == "__main__":
    unittest.main()
