"""Pandoc HTML のヘッダーとドロワーに対するソース契約テスト。"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PandocUiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = (ROOT / "styles/html/html-template.html").read_text(encoding="utf-8")
        cls.simple = (ROOT / "styles/html/html-simple-template.html").read_text(encoding="utf-8")
        cls.style = (ROOT / "styles/html/html-style.css").read_text(encoding="utf-8")
        cls.ui_style = (ROOT / "styles/html/docsfw-ui.css").read_text(encoding="utf-8")
        cls.nav = (ROOT / "styles/html/docsfw-nav.js").read_text(encoding="utf-8")
        cls.publisher = (ROOT / "bin/pub_markdown_core.sh").read_text(encoding="utf-8")

    def test_standard_template_has_material_style_header(self):
        for marker in (
            'class="docsfw-header"',
            'id="docsfw-hamburger"',
            'class="docsfw-header-button docsfw-logo"',
            'class="docsfw-header-title"',
            'class="docsfw-header-actions"',
            'id="docsfw-search-container"',
        ):
            self.assertIn(marker, self.template)
        self.assertNotIn('class="navbar navbar-static-top"', self.template)

    def test_simple_template_is_not_given_site_chrome(self):
        self.assertNotIn('class="docsfw-header"', self.simple)
        self.assertNotIn('id="docsfw-hamburger"', self.simple)

    def test_header_and_drawer_share_current_dimensions(self):
        self.assertIn("--docsfw-header-body-height: 48px", self.style)
        self.assertIn("--docsfw-header-height: 60px", self.style)
        self.assertIn("scroll-margin-top: 84px", self.style)
        self.assertIn("--docsfw-drawer-width: min(80vw, 320px)", self.ui_style)
        self.assertIn("height: calc(100dvh - var(--docsfw-header-height))", self.ui_style)
        self.assertIn("border-right: 1px solid var(--docsfw-header-border)", self.ui_style)

    def test_breakpoints_match_livedocs(self):
        for marker in (
            "(max-width: 1624px)",
            "(max-width: 76.234375em)",
            "(max-width: 59.984375em)",
        ):
            self.assertIn(marker, self.ui_style)
        self.assertIn("(min-width: 1625px)", self.nav)
        self.assertIn("(max-width: 76.234375em)", self.nav)

    def test_search_and_navigation_flags_are_independent(self):
        self.assertIn('htmlSearchEnable=$(parse_yaml "$config_content" "htmlSearchEnable")', self.publisher)
        self.assertIn('htmlNavTreeEnable=$(parse_yaml "$config_content" "htmlNavTreeEnable")', self.publisher)
        self.assertIn('docsfw-search-enable=true', self.publisher)
        self.assertIn('docsfw-nav-enable=true', self.publisher)
        self.assertIn('docsfw-drawer-enable=true', self.publisher)

    def test_site_name_and_self_contained_asset_base_are_supplied(self):
        self.assertIn('siteName=$(parse_yaml "$config_content" "siteName")', self.publisher)
        self.assertIn('siteName=$(basename "${workspaceFolder%/}")', self.publisher)
        self.assertIn('docsfw-site-name=${siteName}', self.publisher)
        self.assertIn('docsfw-variant=${langElement}${details_suffix}', self.publisher)
        self.assertIn('docsfw-asset-base=../${up_dir}html/', self.publisher)


if __name__ == "__main__":
    unittest.main()
