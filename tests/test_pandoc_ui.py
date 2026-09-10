"""Pandoc HTML のヘッダーとドロワーに対するソース契約テスト。"""

from pathlib import Path
import re
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
        cls.livedocs_style = (ROOT / "livedocs/assets/docsfw-livedocs.css").read_text(
            encoding="utf-8"
        )
        cls.livedocs_pandoc_style = (
            ROOT / "livedocs/assets/docsfw-pandoc-style.css"
        ).read_text(encoding="utf-8")
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
        self.assertIn("padding-top: calc(var(--docsfw-header-height) + 8px)", self.style)
        self.assertIn("scroll-margin-top: 84px", self.style)
        self.assertIn("--docsfw-drawer-width: min(80vw, 320px)", self.ui_style)
        self.assertIn("height: calc(100dvh - var(--docsfw-header-height))", self.ui_style)
        self.assertIn("border-right: 1px solid var(--docsfw-header-border)", self.ui_style)

    def test_narrow_page_toc_rows_match_material_dimensions(self):
        """最狭ドロワーのページ内目次は 45px のリンクと 1px の区切りにすること。"""
        self.assertRegex(
            self.ui_style,
            re.escape("#docsfw-page-toc.docsfw-combined-toc a")
            + r"\s*\{[^}]*min-height:\s*45px;"
            + r"[^}]*padding:\s*12px 16px;"
            + r"[^}]*line-height:\s*21px;"
            + r"[^}]*margin-top:\s*0;"
            + r"[^}]*border-top:\s*0",
        )
        self.assertRegex(
            self.ui_style,
            re.escape("#docsfw-page-toc.docsfw-combined-toc li")
            + r"\s*\{[^}]*border-top:\s*1px solid var\(--docsfw-divider\)",
        )
        self.assertRegex(
            self.ui_style,
            re.escape(
                "#docsfw-page-toc.docsfw-combined-toc > ul > li:first-child"
            )
            + r"\s*\{[^}]*border-top:\s*0",
        )

    def test_header_right_icons_are_twenty_pixels(self):
        """ヘッダー右上の操作アイコンは 20px、左端のロゴとメニューは 24px であること。"""
        self.assertRegex(
            self.style,
            r"\.docsfw-header-action img\s*,\s*#docsfw-theme-toggle svg"
            r"\s*\{[^}]*width:\s*20px[^}]*height:\s*20px",
        )
        self.assertRegex(
            self.style,
            r"\.docsfw-header-button svg\s*,\s*\.docsfw-drawer-logo svg"
            r"\s*\{[^}]*width:\s*24px[^}]*height:\s*24px",
        )
        self.assertRegex(
            self.style,
            r"\.docsfw-logo-icon\s*\{[^}]*width:\s*24px[^}]*height:\s*24px",
        )
        self.assertRegex(
            self.ui_style,
            r"\.docsfw-search-icon svg\s*,\s*\.docsfw-search-back svg"
            r"\s*\{[^}]*width:\s*20px[^}]*height:\s*20px",
        )
        self.assertRegex(
            self.ui_style,
            r"\.docsfw-search-form::before\s*\{[^}]*width:\s*20px[^}]*height:\s*20px",
        )

    def test_dark_logo_icon_uses_white_foreground(self):
        """ダークの Pandoc ロゴは MkDocs ヘッダーと同じ白系であること。"""
        dark = (ROOT / "styles/html/docsfw-pandoc-icon.svg").read_text(encoding="utf-8")
        light = (ROOT / "styles/html/docsfw-pandoc-icon-light.svg").read_text(encoding="utf-8")
        self.assertIn('fill="#ffffff"', dark)
        self.assertNotRegex(dark, r'fill="#4093[Dd][Aa]"')
        self.assertIn('fill="#000000"', light)

    def test_details_switch_icon_matches_material_palette_button(self):
        """概要／詳細切り替えはテーマ別の無彩色と Material のホバー表現を使うこと。"""
        self.assertRegex(
            self.style,
            r"\.docsfw-details-icon\s*\{[^}]*filter:\s*brightness\(0\)",
        )
        self.assertRegex(
            self.style,
            r'html\[data-md-color-scheme="slate"\] \.docsfw-details-icon'
            r"\s*\{[^}]*filter:\s*brightness\(0\) invert\(1\)",
        )
        self.assertRegex(
            self.style,
            r"\.docsfw-header-button\s*,\s*\.docsfw-header-action > a\s*,"
            r"\s*#docsfw-theme-toggle\s*\{[^}]*transition:\s*opacity 0\.25s",
        )
        self.assertRegex(
            self.style,
            r"\.docsfw-header-button:hover\s*,"
            r"\s*\.docsfw-header-action > a:hover\s*,"
            r"\s*#docsfw-theme-toggle:hover\s*\{"
            r"[^}]*color:\s*inherit[^}]*opacity:\s*0\.7",
        )

    def test_abstract_title_uses_heading_color(self):
        """概要タイトルは通常の見出しと同じテーマ追従色であること。"""
        self.assertRegex(
            self.style,
            r"\.abstract-title\s*\{[^}]*color:\s*var\(--docsfw-muted\)",
        )

    def test_table_caption_uses_body_width_and_eight_pixel_gap(self):
        self.assertRegex(
            self.style,
            r"\.docsfw-table-caption\s*\{[^}]*margin:\s*12px 0 8px",
        )
        self.assertRegex(
            self.style,
            r"\.docsfw-table-caption \+ table\s*\{[^}]*margin-top:\s*0",
        )
        self.assertIn(
            ".docsfw-table-caption + .md-typeset__scrollwrap",
            self.livedocs_style,
        )
        self.assertIn(
            "> .md-typeset__table > table",
            self.livedocs_style,
        )
        self.assertRegex(
            self.livedocs_style,
            r"\.docsfw-caption code\s*\{[^}]*line-height:\s*16\.5px",
        )

    def test_livedocs_table_cells_match_pandoc_dimensions(self):
        font_stack = (
            "font-family: 'Segoe UI', 'Meiryo UI', 'Hiragino Sans', "
            "'Hiragino Kaku Gothic ProN', sans-serif"
        )
        self.assertIn(font_stack, re.sub(r"\s+", " ", self.style))
        self.assertIn(font_stack, re.sub(r"\s+", " ", self.livedocs_style))
        self.assertIn(font_stack, re.sub(r"\s+", " ", self.livedocs_pandoc_style))
        table_rule = re.search(
            r"\.md-typeset table:not\(\[class\]\)\s*\{([^}]*)\}",
            self.livedocs_pandoc_style,
        )
        self.assertIsNotNone(table_rule)
        self.assertIn("border: 0", table_rule.group(1))
        self.assertIn("font-feature-settings: normal", table_rule.group(1))
        self.assertRegex(
            self.livedocs_pandoc_style,
            r"table:not\(\[class\]\) th\s*\{[^}]*min-width:\s*0",
        )
        self.assertRegex(
            self.livedocs_pandoc_style,
            r"table:not\(\[class\]\) th,\s*"
            r"\.md-typeset table:not\(\[class\]\) td\s*"
            r"\{[^}]*box-sizing:\s*content-box",
        )

    def test_table_caption_filter_is_used_only_for_html(self):
        lines = self.publisher.splitlines()
        listing_indices = [
            index for index, line in enumerate(lines)
            if "pandoc-filters/listing-caption-style.lua" in line
        ]
        self.assertEqual(len(listing_indices), 6)

        html_count = 0
        for index in listing_indices:
            output_line = next(
                line for line in lines[index:]
                if " -t html " in line or " -t docx " in line
            )
            has_table_filter = (
                index + 1 < len(lines)
                and "pandoc-filters/table-caption-style.lua" in lines[index + 1]
            )
            if " -t html " in output_line:
                html_count += 1
                self.assertTrue(has_table_filter)
            else:
                self.assertFalse(has_table_filter)

        self.assertEqual(html_count, 4)

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
