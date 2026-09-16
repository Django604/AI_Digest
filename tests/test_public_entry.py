import json
import unittest
import xml.etree.ElementTree as element_tree
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SVG_ENTRY = PROJECT_ROOT / "docs" / "index.svg"
PAGES_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "deploy-pages.yml"
CLOUDFLARE_PAGES_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "deploy-cloudflare-pages.yml"
APP_SCRIPT = PROJECT_ROOT / "docs" / "assets" / "app.js"
STYLESHEET = PROJECT_ROOT / "docs" / "assets" / "styles.css"
FAVICON = PROJECT_ROOT / "docs" / "favicon.ico"
MONTHLY_DATA_DIR = PROJECT_ROOT / "docs" / "data" / "monthly"


class PublicEntryTests(unittest.TestCase):
    def test_svg_entry_is_well_formed_and_loads_versioned_assets(self) -> None:
        root = element_tree.parse(SVG_ENTRY).getroot()
        favicon_root = element_tree.parse(FAVICON).getroot()
        source = SVG_ENTRY.read_text(encoding="utf-8")

        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertEqual(favicon_root.tag, "{http://www.w3.org/2000/svg}svg")
        self.assertIn('rel="icon"', source)
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

    def test_cloudflare_workflow_independently_deploys_the_same_docs_directory(self) -> None:
        workflow = CLOUDFLARE_PAGES_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("group: cloudflare-pages", workflow)
        self.assertIn("cloudflare/wrangler-action@v3", workflow)
        self.assertIn("secrets.CLOUDFLARE_API_TOKEN", workflow)
        self.assertIn("secrets.CLOUDFLARE_ACCOUNT_ID", workflow)
        self.assertIn("pages deploy docs --project-name=django604-ai-digest --branch=main", workflow)
        self.assertIn('      - "docs/**"', workflow)
        self.assertIn('      - "config/dashboard_targets.json"', workflow)

    def test_pages_workflows_stamp_and_display_the_same_submission_time(self) -> None:
        expected_argument = '--submission-time "$(git show -s --format=%cI HEAD)"'
        app_source = APP_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(expected_argument, PAGES_WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn(expected_argument, CLOUDFLARE_PAGES_WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn('`数据提交时间：${formatDateTime(meta.submittedAt)}`', app_source)

    def test_batch_capture_skips_retired_sections(self) -> None:
        source = APP_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('section?.id === "sylphy-15"', source)
        self.assertIn('section?.id === "new-pathfinder"', source)
        self.assertIn("已跳过 ICE 总盘和 2026款探陆趋势图", source)
        self.assertIn('section.kind !== "sylphy15"', source)
        self.assertIn('section?.id !== "sylphy-15"', source)

    def test_lead_control_uses_full_valid_leads_title(self) -> None:
        source = APP_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('title: "全车系有效线索"', source)
        self.assertNotIn('title: "全车系线索"', source)

    def test_brief_cards_keep_secondary_metrics_visible_on_narrow_cards(self) -> None:
        source = APP_SCRIPT.read_text(encoding="utf-8")
        styles = STYLESHEET.read_text(encoding="utf-8")

        self.assertIn('["valid-leads", "；同比"]', source)
        self.assertIn('class="brief-page-secondary-line"', source)
        self.assertIn(".brief-page-secondary-line", styles)
        self.assertIn("white-space: normal;", styles)

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

    def test_backfilled_archives_include_blank_model_valid_leads(self) -> None:
        expected = {
            "2026-07": (
                713233,
                "累计实绩 713,233，累计达成率 106.7%；同比 -18.6%，环比 -6.9%",
            ),
            "2026-08": (
                746565,
                "累计实绩 746,565，累计达成率 112.8%；同比 -20.0%，环比 7.8%（目标取值为H2穿透目标8月值）",
            ),
        }

        for month, (cumulative_actual, brief_line) in expected.items():
            payload = json.loads(
                (MONTHLY_DATA_DIR / month / "dashboard.json").read_text(encoding="utf-8")
            )
            section = payload["dashboards"]["lead-control"]["sections"][0]
            report_index = section["trend"]["chart"]["reportDayIndex"]
            valid_leads_brief = next(
                item
                for item in payload["dashboards"]["brief"]["briefing"]["sections"]
                if item["kind"] == "valid-leads"
            )

            self.assertEqual(
                section["trend"]["chart"]["series"]["cumulativeActual"][report_index],
                cumulative_actual,
            )
            self.assertEqual(valid_leads_brief["lines"], [brief_line])


if __name__ == "__main__":
    unittest.main()
