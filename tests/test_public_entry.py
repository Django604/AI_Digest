import unittest
import xml.etree.ElementTree as element_tree
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SVG_ENTRY = PROJECT_ROOT / "docs" / "index.svg"
PAGES_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "deploy-pages.yml"


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

    def test_pages_workflow_purges_cdn_after_build_and_before_upload(self) -> None:
        workflow = PAGES_WORKFLOW.read_text(encoding="utf-8")

        build_position = workflow.index("- name: Build dashboard data")
        purge_position = workflow.index("- name: Purge jsDelivr cache")
        configure_position = workflow.index("- name: Configure Pages")
        self.assertLess(build_position, purge_position)
        self.assertLess(purge_position, configure_position)
        self.assertIn("run: python scripts/purge_jsdelivr_cache.py", workflow)


if __name__ == "__main__":
    unittest.main()
