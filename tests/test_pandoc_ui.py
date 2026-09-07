"""Pandoc HTML のヘッダーとドロワーに対するソース契約テスト。"""

from pathlib import Path
import subprocess
import tempfile
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
            "(max-width: 1399px)",
            "(max-width: 76.234375em)",
            "(max-width: 59.984375em)",
        ):
            self.assertIn(marker, self.ui_style)
        self.assertIn("(min-width: 1400px)", self.nav)
        self.assertIn("(max-width: 76.234375em)", self.nav)

    def test_intermediate_three_column_breakpoint(self):
        """1400px〜1624px は、左右列を 2/3 幅にした中間 3 列であること。"""
        self.assertIn("(min-width: 1400px) and (max-width: 1624px)", self.style)
        self.assertIn("grid-template-columns: 240px 870px 210px", self.style)
        self.assertIn("grid-template-columns: 360px 870px 315px", self.style)
        self.assertIn("(min-width: 1400px)", self.ui_style)

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

    def test_copied_variant_updates_navigation_title(self):
        start = self.publisher.index("set_html_lang_attributes() {")
        end = self.publisher.index("\n}", start) + 2
        function = self.publisher[start:end]
        with tempfile.TemporaryDirectory() as directory:
            html = Path(directory) / "copy.html"
            html.write_text('<html lang="ja"><span class="docsfw-drawer-site-name">'
                            'Site (example) (ja)</span></html>', encoding="utf-8")
            subprocess.run(["bash", "-c", function +
                            '\ndetails_suffix=-details\nset_html_lang_attributes "$1" en',
                            "test", str(html)], check=True)
            result = html.read_text(encoding="utf-8")
            self.assertIn('lang="en"', result)
            self.assertIn('Site (example) (en-details)</span>', result)

    def test_back_to_top_matches_material(self):
        self.assertIn('<button type="button" id="docsfw-top" hidden>', self.template)
        self.assertIn('M13 20h-2V8l-5.5 5.5-1.42-1.42L12 4.16l7.92 7.92-1.42 1.42L13 8z',
                      self.template)
        self.assertNotIn('<a href="#" id="docsfw-top"', self.template)
        self.assertIn("ページトップへ戻る", self.nav)
        self.assertNotIn("ページの先頭へ戻る", self.nav)
        self.assertIn("addEventListener('resize'", self.nav)
        self.assertIn("top: calc(var(--docsfw-header-height) + 16px)", self.ui_style)
        self.assertIn("--docsfw-accent-bg: #ffffff", self.style)
        self.assertIn("--docsfw-accent-bg: #1f2129", self.style)

    def test_default_toc_matches_source_heading_level_three(self):
        start = self.publisher.index('if [[ "$htmlTocDepth" == "" ]]')
        end = self.publisher.index('\n# 設定ファイルに mathLatexEnable', start)
        setup = self.publisher[start:end]
        source = '# Title\n\n## Level two\n\n### Level three\n\n#### Level four\n'
        for configured, includes_four in [("", False), ("3", True)]:
            result = subprocess.run(
                ["bash", "-c", 'htmlTocDepth="$1"; htmlTocEnable=true\n' + setup +
                 '\npandoc -s "${html_toc_args[@]}" --shift-heading-level-by=-1 -t html',
                 "test", configured], input=source, text=True, capture_output=True, check=True)
            self.assertIn('id="toc-level-three"', result.stdout)
            self.assertEqual('id="toc-level-four"' in result.stdout, includes_four)
            self.assertIn('id="level-four"', result.stdout)


if __name__ == "__main__":
    unittest.main()
