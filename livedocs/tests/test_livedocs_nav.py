#!/usr/bin/env python3
"""狭い画面のドロワーで、ページ内目次を文書ツリーの続きに並べる条件の単体テスト。

Material は既定フォントで約 1220px 未満のとき ``.md-nav--primary`` とその配下の
``.md-nav`` を絶対配置の板にします。板の外へ置いた要素は背面に隠れるため、
``docsfw-responsive-nav.js`` は目次を一覧 (``.md-nav__list``) の中へ入れます。
その前提と、板向けの体裁を戻す CSS を固定します。
"""

import os
import re
import sys
import unittest

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from vendor_assets import MKDOCS_DIR  # noqa: E402

LIVEDOCS_CSS = os.path.join(MKDOCS_DIR, "assets", "docsfw-livedocs.css")
RESPONSIVE_NAV_JS = os.path.join(MKDOCS_DIR, "assets", "docsfw-responsive-nav.js")

# Material のモバイル ドロワーが効き始める幅。打ち消し用の media はこの値にそろえる。
MATERIAL_DRAWER_BREAKPOINT = "76.234375em"


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class CombinedTocPlacementTest(unittest.TestCase):
    """目次の移動先が、文書ツリーの一覧の中であること。"""

    def test_toc_is_appended_to_the_primary_nav_list(self):
        text = _read(RESPONSIVE_NAV_JS)
        self.assertIn(".md-sidebar--primary nav.md-nav--primary > .md-nav__list", text)

    def test_container_is_a_list_item_of_the_primary_nav(self):
        text = _read(RESPONSIVE_NAV_JS)
        self.assertRegex(
            text,
            r"createElement\(\s*'li'\s*\)[\s\S]{0,200}?"
            + re.escape("'md-nav__item docsfw-combined-toc'"),
        )


class CombinedTocStyleTest(unittest.TestCase):
    """板とスライド パネル向けの体裁を、目次の範囲だけ戻すこと。"""

    def _drawer_block(self):
        text = _read(LIVEDOCS_CSS)
        match = re.search(
            r"@media screen and \(max-width:\s*"
            + re.escape(MATERIAL_DRAWER_BREAKPOINT)
            + r"\)\s*\{([\s\S]*?)\n\}",
            text,
        )
        self.assertIsNotNone(match, "Material と同じ境界の media が無い")
        return match.group(1)

    def test_nested_toc_navigations_are_static(self):
        block = self._drawer_block()
        self.assertRegex(
            block,
            re.escape(".md-nav--primary .docsfw-combined-toc .md-nav")
            + r"\s*\{[^}]*position:\s*static",
        )

    def test_toc_items_have_no_drawer_separator(self):
        block = self._drawer_block()
        self.assertRegex(
            block,
            re.escape(".md-nav--primary .docsfw-combined-toc .md-nav__item")
            + r"\s*\{[^}]*border-top:\s*0",
        )

    def test_toc_links_drop_the_drawer_padding(self):
        block = self._drawer_block()
        self.assertRegex(
            block,
            re.escape(".md-nav--primary .docsfw-combined-toc .md-nav__link")
            + r"\s*\{[^}]*padding:\s*0\s*!important",
        )

    def test_primary_list_disables_scroll_snapping(self):
        block = self._drawer_block()
        self.assertRegex(
            block,
            re.escape(".md-nav--primary > .md-nav__list")
            + r"\s*\{[^}]*scroll-snap-type:\s*none",
        )


if __name__ == "__main__":
    unittest.main()
