import unittest
import xml.etree.ElementTree as element_tree
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SVG_ENTRY = PROJECT_ROOT / "docs" / "index.svg"
PAGES_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "deploy-pages.yml"
APP_SCRIPT = PROJECT_ROOT / "docs" / "assets" / "app.js"


class PublicEntryTests(unittest.TestCase):
    def test_svg_entry_is_well_formed_and_loads_versioned_assets(self) -> None:
        root = element_tree.parse(SVG_ENTRY).getroot()
        source = SVG_ENTRY.read_text(encoding="utf-8")

        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIn('id="app-styles"', source)
        self.assertIn('./assets/styles.css?v=" + cacheBust', source)
        self.assertIn('./assets/app.js?v=" + cacheBust', source)

    def test_svg_entry_contains_required_dashboard_mount_points(self) -> None:
        source = SVG_ENTRY.read_text(encoding="utf-8")

        for element_id in (
            "report-date-highlight",
            "meta-strip",
            "tab-list",
            "dashboard-root",
            "dashboard-template",
            "section-template",
            "month-picker-toggle",
        ):
            self.assertIn(f'id="{element_id}"', source)

    def test_pages_workflow_builds_and_uploads_without_cdn_dependency(self) -> None:
        workflow = PAGES_WORKFLOW.read_text(encoding="utf-8")

        build_position = workflow.index("- name: Build dashboard data")
        configure_position = workflow.index("- name: Configure Pages")
        upload_position = workflow.index("- name: Upload artifact")
        self.assertLess(build_position, configure_position)
        self.assertLess(configure_position, upload_position)
        self.assertNotIn("jsDelivr", workflow)
        self.assertNotIn("purge_jsdelivr_cache.py", workflow)

    def test_batch_capture_skips_sylphy_15(self) -> None:
        source = APP_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('section?.id === "sylphy-15"', source)
        self.assertIn("已跳过 ICE 总盘与十五代轩逸趋势图", source)

    def test_current_month_uses_live_dashboard_and_explicit_month_uses_archive(self) -> None:
        source = APP_SCRIPT.read_text(encoding="utf-8")
        start = source.index('function buildDashboardRequest(monthKey = "")')
        end = source.index("function applyLoadedDashboardState", start)
        request_source = source[start:end]
        current_source, archive_source = request_source.split(
            "const archiveEntry = getArchiveEntry(normalizedMonthKey);",
            1,
        )

        self.assertIn("const primaryUrl = state.dashboardDataUrl;", current_source)
        self.assertNotIn("liveDashboardPath", current_source)
        self.assertIn("./data/monthly/${normalizedMonthKey}/dashboard.json", archive_source)
        self.assertIn(
            'requestMode === "current" ? (reportMonthKey || liveMonthKey)',
            source,
        )


if __name__ == "__main__":
    unittest.main()
