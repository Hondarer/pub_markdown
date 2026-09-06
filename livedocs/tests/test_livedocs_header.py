#!/usr/bin/env python3
"""ヘッダー上書きの保守条件に関する単体テスト。

``theme/partials/header.html`` は mkdocs-material の同名 partial の複製です。
上流が変わったことに気付けるよう、取り込み時の内容ハッシュを記録しておきます。
"""

import hashlib
import os
import re
import sys
import unittest

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from vendor_assets import MKDOCS_DIR  # noqa: E402

# 取り込み元の mkdocs-material のバージョンと、そのときの partials/header.html。
# 上流が変わったら、差分を確認して theme/partials/header.html へ取り込み直し、
# ここの値を更新する。
UPSTREAM_MATERIAL_VERSION = "9.7.7"
UPSTREAM_HEADER_SHA256 = "8cf3fb15bcf969ff596649616fd99366b3c31c08d57a86d05308efc16d8fa75f"

OVERRIDE_HEADER = os.path.join(MKDOCS_DIR, "theme", "partials", "header.html")
LINKS_PARTIAL = os.path.join(MKDOCS_DIR, "theme", "partials", "docsfw-header-links.html")
META_PARTIAL = os.path.join(MKDOCS_DIR, "theme", "partials", "docsfw-header-meta.html")
META_CSS = os.path.join(MKDOCS_DIR, "assets", "docsfw-header-meta.css")
LIVEDOCS_CSS = os.path.join(MKDOCS_DIR, "assets", "docsfw-livedocs.css")


def _find_upstream_header():
    """インストール済み mkdocs-material の ``partials/header.html`` を探す。"""
    for entry in sys.path:
        candidate = os.path.join(entry, "material", "templates", "partials", "header.html")
        if os.path.isfile(candidate):
            return candidate
    return None


class UpstreamHeaderTest(unittest.TestCase):
    def test_pinned_version_matches_requirements(self):
        requirements = os.path.join(MKDOCS_DIR, "requirements.txt")
        with open(requirements, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("mkdocs-material=={}".format(UPSTREAM_MATERIAL_VERSION), text)

    def test_upstream_header_is_unchanged(self):
        upstream = _find_upstream_header()
        if upstream is None:
            self.skipTest("mkdocs-material が同じ環境に無いため上流を確認できません")
        with open(upstream, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        self.assertEqual(
            digest,
            UPSTREAM_HEADER_SHA256,
            "mkdocs-material の partials/header.html が変わりました。"
            " theme/partials/header.html へ差分を取り込み直し、"
            " このテストの UPSTREAM_HEADER_SHA256 を更新してください。",
        )


class OverrideHeaderTest(unittest.TestCase):
    def test_override_only_replaces_the_source_block(self):
        """上流の md-header__source ブロックだけを差し替えていること。"""
        with open(OVERRIDE_HEADER, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn('class="md-header__source"', text)
        self.assertNotIn('{% include "partials/source.html" %}', text)
        self.assertIn('{% include "partials/docsfw-header-links.html" %}', text)
        self.assertIn('{% include "partials/docsfw-header-meta.html" %}', text)
        # 上流の構造は保つ。
        for marker in ('{% include "partials/logo.html" %}',
                       '{% include "partials/search.html" %}',
                       '{% include "partials/palette.html" %}',
                       'data-md-component="header"'):
            self.assertIn(marker, text)

    def test_meta_partial_is_placed_below_the_title(self):
        """発行情報は、ヘッダーの高さを増やさずタイトルの 2 行目へ置くこと。"""
        with open(OVERRIDE_HEADER, "r", encoding="utf-8") as handle:
            text = handle.read()
        meta = text.index('{% include "partials/docsfw-header-meta.html" %}')
        ellipsis_start = text.index('<div class="md-header__ellipsis">')
        ellipsis_end = text.index("      </div>\n    </div>", ellipsis_start)
        palette = text.index('{% include "partials/palette.html" %}')
        links = text.index('{% include "partials/docsfw-header-links.html" %}')
        search = text.index('{% include "partials/search.html" %}')
        self.assertGreater(meta, ellipsis_start)
        self.assertLess(meta, ellipsis_end)
        self.assertLess(palette, links)
        self.assertLess(links, search)

    def test_meta_partial_reads_the_front_matter(self):
        with open(META_PARTIAL, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn('page.meta["author"]', text)
        self.assertIn('page.meta["date"]', text)
        self.assertIn("docsfw-header-meta", text)

    def test_all_header_text_uses_fixed_minimum_pixel_sizes(self):
        """Material の広い画面用 rem 拡大がヘッダーへ及ばないこと。"""
        with open(META_CSS, "r", encoding="utf-8") as handle:
            text = handle.read()
        for selector, size in (
            (".docsfw-header-meta > span", "14px"),
            (".md-header__title", "18px"),
        ):
            self.assertRegex(
                text,
                re.escape(selector) + r"\s*\{[^}]*font-size:\s*" + size,
            )
        self.assertRegex(
            text,
            re.escape(".md-header .md-search__input")
            + r"\s*,\s*"
            + re.escape(".md-header .md-search__suggest")
            + r"\s*\{[^}]*font-family:\s*var\(--md-text-font-family\)"
            + r"[^}]*font-size:\s*16px[^}]*letter-spacing:\s*normal",
        )

    def test_header_metadata_uses_the_second_title_row(self):
        """タイトル領域の既存 48px を 24px ごとの 2 行で使うこと。"""
        with open(META_CSS, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertRegex(
            text,
            re.escape(".docsfw-header-meta")
            + r"\s*\{[^}]*margin-top:\s*2px[^}]*position:\s*absolute[^}]*top:\s*24px",
        )
        self.assertRegex(
            text,
            re.escape(".md-header__topic")
            + r"\s*\{[^}]*height:\s*24px[^}]*line-height:\s*24px[^}]*margin-top:\s*2px",
        )
        self.assertNotIn("max-width: 76.1875em", text)

    def test_search_box_width_uses_fixed_pixel_sizes(self):
        """100em / 125em 以上での html font-size 拡大により検索ボックスが
        さらに広がらないこと (rem ではなく px で固定していること)。"""
        with open(META_CSS, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotRegex(text, r"width:\s*\d+(?:\.\d+)?rem")
        self.assertRegex(
            text,
            r"@media screen and \(min-width:\s*60em\)\s*\{[\s\S]*?"
            + re.escape(".md-header .md-search__inner")
            + r"\s*\{[^}]*width:\s*234px",
        )
        self.assertRegex(
            text,
            r"@media screen and \(min-width:\s*60em\)\s*\{[\s\S]*?"
            + re.escape('[data-md-toggle="search"]:checked ~ .md-header .md-search__inner')
            + r"\s*,\s*"
            + re.escape(".md-header .md-search__scrollwrap")
            + r"\s*\{[^}]*width:\s*468px",
        )

    def test_header_height_and_spacing_use_fixed_pixel_sizes(self):
        """幅だけでなく、ヘッダーの高さと余白も画面幅で広がらないこと。"""
        with open(META_CSS, "r", encoding="utf-8") as handle:
            text = handle.read()
        # コメント中の rem は Material 側の元の値を示すため対象から外す。
        declarations = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        self.assertNotRegex(declarations, r"\d*\.?\d+rem")
        for selector, prop, size in (
            (".md-header__title", "height", "48px"),
            (".md-header__inner", "padding", "0 4px"),
            (".md-header__button", "margin", "4px"),
            (".md-header .md-search__form", "height", "36px"),
            (".md-sidebar", "top", "48px"),
        ):
            self.assertRegex(
                declarations,
                re.escape(selector)
                + r"\s*\{[^}]*"
                + re.escape(prop)
                + r":\s*"
                + re.escape(size)
                + r"\s*;",
            )
        self.assertRegex(
            declarations,
            re.escape(".md-typeset :target")
            + r"\s*\{[^}]*--md-scroll-margin:\s*72px",
        )

    def test_header_title_always_shows_the_document_title(self):
        """本文のスクロール状況によらず、サイト名ではなく文書タイトルを表示すること。"""
        with open(META_CSS, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertRegex(
            text,
            re.escape(".md-header__topic:first-child")
            + r"\s*\{[^}]*display:\s*none",
        )
        self.assertRegex(
            text,
            re.escape(".md-header__topic + .md-header__topic")
            + r"\s*\{[^}]*opacity:\s*1",
        )

    def test_all_header_icons_use_fixed_minimum_pixel_sizes(self):
        """Material の広い画面用 rem 拡大がヘッダーのアイコンへ及ばないこと。"""
        with open(META_CSS, "r", encoding="utf-8") as handle:
            meta_css = handle.read()
        links_css = os.path.join(MKDOCS_DIR, "assets", "docsfw-header-links.css")
        with open(links_css, "r", encoding="utf-8") as handle:
            link_css = handle.read()
        for selector in (
            ".md-header .md-icon > svg",
            ".md-header .md-logo > img",
            ".md-header .md-logo > svg",
            ".md-header .md-search__icon",
        ):
            self.assertRegex(
                meta_css,
                re.escape(selector) + r"\s*,?\s*(?:\n|.)*?height:\s*24px",
            )
        self.assertRegex(
            link_css,
            re.escape(".docsfw-header-links .md-header__button img")
            + r"\s*\{[^}]*height:\s*24px[^}]*width:\s*24px",
        )

    def test_mode_doxygen_and_git_icon_buttons_use_four_pixel_padding(self):
        """24px の右側アイコンだけは既定の 8px より小さい余白を使うこと。"""
        links_css = os.path.join(MKDOCS_DIR, "assets", "docsfw-header-links.css")
        with open(links_css, "r", encoding="utf-8") as handle:
            text = handle.read()
        padding_rule = re.search(
            re.escape(".md-header__option .md-header__button")
            + r"\s*,\s*"
            + re.escape(".docsfw-header-links .md-header__button")
            + r"\s*\{[^}]*\}",
            text,
        )
        self.assertIsNotNone(padding_rule)
        self.assertIn("padding: 4px", padding_rule.group())
        self.assertNotIn("display:", padding_rule.group())
        self.assertRegex(
            text,
            re.escape(".docsfw-header-links .md-header__button")
            + r"\s*\{[^}]*display:\s*flex",
        )

    def test_links_partial_uses_both_single_page_links(self):
        with open(LINKS_PARTIAL, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("doxygen_livedocs_url", text)
        self.assertIn('page.meta["git-url"]', text)
        self.assertIn('target="doxygen-page"', text)
        self.assertIn('target="source-file"', text)
        self.assertIn("ソースを開く", text)
        self.assertIn("View source", text)

    def test_icons_referenced_by_the_partial_are_vendored(self):
        """テンプレートが参照するアイコンが vendor_assets の配置対象であること。"""
        from vendor_assets import HEADER_ICONS

        with open(LINKS_PARTIAL, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("docsfw-doxygen-icon.svg", text)
        # provider 名を差し込む形のため、配置側が 4 種そろっていることで担保する。
        self.assertIsNotNone(re.search(r"docsfw-' ~ provider ~ '-icon\.svg", text))
        for provider in ("git", "github", "gitlab", "gitbucket"):
            self.assertIn("docsfw-{}-icon.svg".format(provider), HEADER_ICONS)


class DrawerTopSpacingTest(unittest.TestCase):
    """左ナビ先頭の 12px 余白が、広い画面とドロワーで同じ値になること。"""

    def _read_css(self):
        with open(LIVEDOCS_CSS, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_wide_layout_uses_twelve_pixel_sidebar_padding(self):
        text = self._read_css()
        self.assertRegex(
            text,
            r"@media screen and \(min-width:\s*1625px\)\s*\{[\s\S]*?"
            + re.escape(".md-sidebar--primary")
            + r"\s*,\s*"
            + re.escape(".md-sidebar--secondary")
            + r"\s*\{[^}]*padding-top:\s*12px",
        )

    def test_drawer_scrollwrap_keeps_the_same_twelve_pixel_inset(self):
        """絶対配置の scrollwrap は親の padding を無視するため、上端へ移す。"""
        text = self._read_css()
        match = re.search(
            r"@media screen and \(max-width:\s*1624px\)\s*\{([\s\S]*?)\n\}",
            text,
        )
        self.assertIsNotNone(match)
        drawer = match.group(1)
        self.assertRegex(
            drawer,
            re.escape(".md-sidebar--primary .md-sidebar__scrollwrap")
            + r"\s*\{[^}]*inset:\s*12px 0 0",
        )
        self.assertNotRegex(
            drawer,
            re.escape(".md-sidebar--primary .md-sidebar__scrollwrap")
            + r"\s*\{[^}]*inset:\s*0\s*;",
        )


if __name__ == "__main__":
    unittest.main()
