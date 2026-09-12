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

# Material がナビゲーション内蔵のページ内目次を出し始める幅。
MATERIAL_TOC_BREAKPOINT = "59.984375em"


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


class CombinedTocPlacementTest(unittest.TestCase):
    """目次の移動先が、文書ツリーの一覧の中であること。"""

    def test_toc_is_appended_to_the_primary_nav_list(self):
        text = _read(RESPONSIVE_NAV_JS)
        self.assertIn(".md-sidebar--primary nav.md-nav--primary > .md-nav__list", text)

    def test_narrow_layout_uses_the_visible_panel(self):
        """約 1220px 未満は、表示されている板の一覧へ入れること。

        Material はこの幅でナビゲーションを入れ子の板にする。根の一覧へ入れた
        目次は板の背面に回り、見出しだけが板の行に重なって見える。
        """
        text = _read(RESPONSIVE_NAV_JS)
        self.assertIn("(max-width: " + MATERIAL_DRAWER_BREAKPOINT + ")", text)
        self.assertIn("getVisiblePanelNav()", text)
        self.assertIn("panelList.contains(activeLink)", text)

    def test_section_index_page_uses_the_visible_parent_panel(self):
        """節の索引ページでも、現在リンクが見える親の一覧へ入れること。"""
        text = _read(RESPONSIVE_NAV_JS)
        self.assertNotIn(":scope > nav.md-nav > .md-nav__list", text)

    def test_container_moves_when_the_target_list_changes(self):
        """幅が変わって入れ先が変わったら、器を作り直さず移すこと。"""
        text = _read(RESPONSIVE_NAV_JS)
        self.assertRegex(
            text,
            re.escape("combinedContainer.parentNode !== primaryList")
            + r"[\s\S]{0,120}?"
            + re.escape("primaryList.appendChild(combinedContainer)"),
        )

    def test_container_is_a_list_item_of_the_primary_nav(self):
        text = _read(RESPONSIVE_NAV_JS)
        self.assertRegex(
            text,
            r"createElement\(\s*'li'\s*\)[\s\S]{0,200}?"
            + re.escape("'md-nav__item docsfw-combined-toc'"),
        )


class DrawerInitialPositionTest(unittest.TestCase):
    """ドロワーを開いたとき、幅に対応する現在項目を表示すること。"""

    def test_current_page_lookup_excludes_page_toc(self):
        """現在文書を探すときは、ページ内目次の現在見出しを除くこと。"""
        text = _read(RESPONSIVE_NAV_JS)
        self.assertIn(".md-nav__link--active[href]", text)
        self.assertIn("!links[i].closest('.docsfw-combined-toc')", text)

    def test_opening_drawer_centers_the_selected_item(self):
        text = _read(RESPONSIVE_NAV_JS)
        self.assertIn(".docsfw-combined-toc a.md-nav__link--active", text)
        self.assertIn("addEventListener('change', revealDrawerSelection)", text)
        self.assertIn(
            "activeLink.scrollIntoView({ block: 'center', behavior: 'auto' })",
            text,
        )


class ReloadHashPositionTest(unittest.TestCase):
    """F5 では Material の追跡より URL のフラグメントを優先すること。"""

    def test_reload_with_hash_restores_the_fragment_position(self):
        text = _read(RESPONSIVE_NAV_JS)
        self.assertIn("entries[0].type === 'reload'", text)
        self.assertIn("performance.navigation.type === 1", text)
        self.assertIn("var reloadHash = window.location.hash", text)
        self.assertIn(
            "window.addEventListener('pageshow', restore, { once: true })", text
        )
        self.assertIn(
            "target.scrollIntoView({ block: 'start', behavior: 'auto' })", text
        )
        self.assertIn("if (!window.location.hash || !isReloadNavigation())", text)


class DrawerWidthTest(unittest.TestCase):
    """ドロワーでは、一覧の右にスクロール バー以外の空きを作らないこと。"""

    def _docsfw_drawer_block(self):
        text = _read(LIVEDOCS_CSS)
        match = re.search(
            r"@media screen and \(max-width:\s*1399px\)\s*\{([\s\S]*?)\n\}",
            text,
        )
        self.assertIsNotNone(match, "docsfw の境界の media が無い")
        return match.group(1)

    def test_scrollbar_gutter_is_not_reserved(self):
        """板の中では板自身の一覧がスクロールし、予約分が余白として残る。"""
        self.assertRegex(
            self._docsfw_drawer_block(),
            re.escape(".md-sidebar--primary .md-sidebar__scrollwrap")
            + r"\s*\{[^}]*scrollbar-gutter:\s*auto",
        )

    def test_content_starts_immediately_below_the_header(self):
        """1 列表示でも3列表示と同じ本文上端を使うこと。"""
        block = self._docsfw_drawer_block()
        self.assertRegex(
            block,
            re.escape(".md-main__inner > .md-content > .md-content__inner")
            + r"\s*\{[^}]*padding-top:\s*0",
        )
        self.assertRegex(
            block,
            re.escape(".md-main__inner")
            + r"\s*\{[^}]*margin-top:\s*0",
        )

    def test_phone_content_uses_pandoc_side_margins(self):
        """767px以下の本文はPandocと同じ左右20pxを使うこと。"""
        text = _read(LIVEDOCS_CSS)
        self.assertRegex(
            text,
            r"@media screen and \(max-width:\s*767px\)\s*\{[\s\S]*?"
            + re.escape(".md-main__inner > .md-content > .md-content__inner")
            + r"\s*\{[^}]*margin-left:\s*20px\s*!important;"
            + r"[^}]*margin-right:\s*20px\s*!important",
        )

    def test_narrow_root_panel_matches_pandoc_dimensions(self):
        """狭幅のルート板はPandocと同じロゴ寸法、行高、アイコン色を使うこと。"""
        text = _read(LIVEDOCS_CSS)
        self.assertRegex(
            text,
            re.escape(".md-nav--primary > .md-nav__title .md-logo > svg")
            + r"\s*\{[^}]*width:\s*24px;[^}]*height:\s*24px",
        )
        self.assertRegex(
            text,
            re.escape(
                ".md-nav--primary > .md-nav__list > .md-nav__item > .md-nav__container"
            )
            + r"\s*\{[^}]*min-height:\s*48px",
        )
        self.assertRegex(
            text,
            r'\[data-md-color-scheme="default"\] '
            + re.escape(".md-nav--primary > .md-nav__title")
            + r"\s*\{[^}]*background-color:\s*#eaeaea;[^}]*color:\s*#777777",
        )
        self.assertRegex(
            text,
            re.escape(
                ".md-nav--primary > .md-nav__list > .md-nav__item"
                " > .md-nav__container\n  > .md-nav__link > .md-nav__icon"
            )
            + r"\s*\{[^}]*color:\s*var\(--md-default-fg-color--light\)"
            + r"[^}]*font-size:\s*18px[^}]*width:\s*18px\s*!important;"
            + r"[^}]*height:\s*18px\s*!important",
        )

    def test_tablet_content_uses_pandoc_side_margins(self):
        """768pxから929pxの本文はPandocと同じ左右30pxを使うこと。"""
        text = _read(LIVEDOCS_CSS)
        self.assertRegex(
            text,
            r"@media screen and \(min-width:\s*768px\) and \(max-width:\s*929px\)"
            r"\s*\{[\s\S]*?\.md-main__inner\s*\{[^}]*max-width:\s*none",
        )
        self.assertRegex(
            text,
            r"@media screen and \(min-width:\s*768px\) and \(max-width:\s*929px\)"
            r"\s*\{[\s\S]*?"
            + re.escape(".md-main__inner > .md-content > .md-content__inner")
            + r"\s*\{[^}]*margin-left:\s*30px\s*!important;"
            + r"[^}]*margin-right:\s*30px\s*!important",
        )

    def test_inner_has_no_side_padding(self):
        """3 ペイン用の 10px は、ドロワーでは一覧と縁の間の空きになる。"""
        block = self._docsfw_drawer_block()
        self.assertRegex(
            block,
            re.escape('[dir="ltr"] .md-sidebar--primary .md-sidebar__inner')
            + r"\s*\{[^}]*padding-right:\s*0",
        )
        self.assertRegex(
            block,
            re.escape('[dir="rtl"] .md-sidebar--primary .md-sidebar__inner')
            + r"\s*\{[^}]*padding-left:\s*0",
        )


class IntermediateThreeColumnTest(unittest.TestCase):
    """1400px〜1624px は、左右列を 2/3 幅にした中間 3 列であること。

    3 列 PC (1625px 以上) の左 360px/右 315px に対し、この段は
    1.5 倍化前の値である左 240px/右 210px を使う。
    """

    def _block(self):
        text = _read(LIVEDOCS_CSS)
        match = re.search(
            r"@media screen and \(min-width:\s*1400px\)"
            r" and \(max-width:\s*1624px\)\s*\{([\s\S]*?)\n\}",
            text,
        )
        self.assertIsNotNone(match, "中間 3 列の media が無い")
        return match.group(1)

    def test_sidebar_widths_are_two_thirds_of_the_wide_layout(self):
        block = self._block()
        self.assertRegex(
            block,
            re.escape(".md-sidebar--primary") + r"\s*\{[^}]*width:\s*240px",
        )
        self.assertRegex(
            block,
            re.escape(".md-sidebar--secondary") + r"\s*\{[^}]*width:\s*210px",
        )

    def test_grid_max_width_matches_the_narrower_columns(self):
        self.assertRegex(
            self._block(),
            re.escape(".md-grid") + r"\s*\{[^}]*max-width:\s*1370px",
        )


class WideSidebarBottomSpacingTest(unittest.TestCase):
    """1400px 以上の左右ナビは Pandoc と同じ下端余白を持つこと。"""

    def test_sidebar_inner_has_pandoc_bottom_spacing(self):
        text = _read(LIVEDOCS_CSS)
        self.assertRegex(
            text,
            r"@media screen and \(min-width:\s*1400px\)\s*\{[\s\S]*?"
            + re.escape(".md-sidebar--primary .md-sidebar__inner,")
            + r"\s*"
            + re.escape(".md-sidebar--secondary .md-sidebar__inner")
            + r"\s*\{[^}]*padding-bottom:\s*12px",
        )


class FlatDrawerScrollTest(unittest.TestCase):
    """連続一覧のドロワーで、スクロール バーが見出しの下から始まること。

    Material はこの幅を 3 ペインと同じ扱いにし、見出しへ ``position: sticky``
    を当てます。見た目は留まりますが、スクロール領域には見出しが含まれた
    ままのため、スクロール バーが見出しの高さだけ上へ伸びます。
    Pandoc HTML と同じく、スクロール元を一覧へ移した状態を固定します。
    """

    def _flat_drawer_block(self):
        text = _read(LIVEDOCS_CSS)
        match = re.search(
            r"@media screen and \(min-width:\s*76\.25em\)"
            r" and \(max-width:\s*1399px\)\s*\{([\s\S]*?)\n\}",
            text,
        )
        self.assertIsNotNone(match, "連続一覧の帯の media が無い")
        return match.group(1)

    def test_scrollwrap_does_not_scroll(self):
        """ドロワー全体をスクロール元にしないこと。"""
        self.assertRegex(
            self._flat_drawer_block(),
            re.escape(".md-sidebar--primary .md-sidebar__scrollwrap")
            + r"\s*\{[^}]*overflow:\s*hidden",
        )

    def test_list_is_the_scroll_container(self):
        """一覧だけがスクロールすること。"""
        self.assertRegex(
            self._flat_drawer_block(),
            re.escape(".md-nav--primary > .md-nav__list")
            + r"\s*\{[^}]*overflow-y:\s*auto",
        )

    def test_list_keeps_bottom_padding_inside_the_scroll_area(self):
        """スクロール バーを下端へ伸ばしても、一覧の内容下余白を保つこと。"""
        self.assertRegex(
            self._flat_drawer_block(),
            re.escape(".md-nav--primary > .md-nav__list")
            + r"\s*\{[^}]*padding-bottom:\s*12px",
        )

    def test_title_is_not_sticky(self):
        """見出しは高さを分け合う固定領域にすること。"""
        self.assertRegex(
            self._flat_drawer_block(),
            re.escape(".md-nav--primary > .md-nav__title")
            + r"\s*\{[^}]*position:\s*static",
        )

    def test_nav_does_not_keep_the_negative_bottom_margin(self):
        """Material の margin-bottom: -.4rem を戻すこと。

        flex 項目では外側だけが 8px 縮み、border box は親の内側より高いまま
        残る。scrollwrap に 8px 分のスクロール量が生まれ、Material の JS が
        書いた scrollTop の分だけ見出しが上へずれる。
        """
        self.assertRegex(
            self._flat_drawer_block(),
            re.escape(".md-sidebar--primary .md-nav--primary")
            + r"\s*\{[^}]*margin-bottom:\s*0",
        )


class MaterialOwnTocTest(unittest.TestCase):
    """Material 内蔵のページ内目次を、約 960px 未満で打ち消すこと。"""

    def _block(self):
        text = _read(LIVEDOCS_CSS)
        match = re.search(
            r"@media screen and \(max-width:\s*"
            + re.escape(MATERIAL_TOC_BREAKPOINT)
            + r"\)\s*\{([\s\S]*?)\n\}",
            text,
        )
        self.assertIsNotNone(match, "Material と同じ境界の media が無い")
        return match.group(1)

    def test_own_toc_label_and_panel_are_hidden(self):
        """docsfw は目次をファイル一覧の続きに並べるため、二重になる。"""
        block = self._block()
        self.assertRegex(
            block,
            re.escape('.md-nav--primary .md-nav__link[for="__toc"]')
            + r"\s*\{[^}]*display:\s*none",
        )
        self.assertRegex(
            block,
            re.escape('.md-nav--primary .md-nav__link[for="__toc"] ~ .md-nav')
            + r"\s*\{[^}]*display:\s*none",
        )

    def test_active_page_keeps_its_own_link(self):
        """Material はラベルへ置き換える際に通常のリンクを隠すため、戻す。"""
        block = self._block()
        self.assertRegex(
            block,
            re.escape('.md-nav--primary .md-nav__link[for="__toc"] + .md-nav__link')
            + r"\s*\{[^}]*display:\s*flex",
        )


class PanelSeparatorTest(unittest.TestCase):
    """板の見出しと一覧の区切り線が、スクロール バーの列まで届くこと。"""

    def _block(self):
        text = _read(LIVEDOCS_CSS)
        match = re.search(
            r"@media screen and \(max-width:\s*"
            + re.escape(MATERIAL_DRAWER_BREAKPOINT)
            + r"\)\s*\{([\s\S]*?)\n\}",
            text,
        )
        self.assertIsNotNone(match, "Material と同じ境界の media が無い")
        return match.group(1)

    def test_separator_is_a_border_not_an_inset_shadow(self):
        """内側の影は padding box の中だけで、スクロール バーの列に届かない。

        線の分だけスクロール バーの上端が高く見えるため、border-top へ移す。
        """
        block = self._block()
        self.assertRegex(
            block,
            re.escape(".md-nav--primary .md-nav__title ~ .md-nav__list")
            + r"\s*\{[^}]*box-shadow:\s*none",
        )
        self.assertRegex(
            block,
            re.escape(".md-nav--primary .md-nav__title ~ .md-nav__list")
            + r"\s*\{[^}]*border-top:\s*1px solid var\(--md-default-fg-color--lightest\)",
        )

    def test_combined_toc_list_has_no_panel_separator(self):
        """目次の一覧は板ではないため、一覧自身には線を出さない。"""
        self.assertRegex(
            self._block(),
            re.escape(".md-nav--primary .docsfw-combined-toc .md-nav__list")
            + r"\s*\{[^}]*border-top:\s*0",
        )

    def test_first_toc_item_keeps_a_separator_under_the_title(self):
        """「目次」の見出しと先頭の項目の間にも区切り線を置くこと。

        Material は見出しの影が区切り線を兼ねる前提で、
        .md-nav--primary .md-nav__title ~ .md-nav__list > :first-child の
        border-top を消す。目次の見出しは影を消しているため、戻さないと
        「目次」と先頭の項目の間だけ線が無くなる。
        """
        self.assertRegex(
            self._block(),
            re.escape(".md-nav--primary .docsfw-combined-toc .md-nav__title ~ .md-nav__list")
            + r"\s*>\s*:first-child\s*\{[^}]*border-top:\s*0\.05rem solid"
            + r"\s*var\(--md-default-fg-color--lightest\)",
        )


class PanelHeaderPointerTest(unittest.TestCase):
    """狭幅の板見出しで、操作できる要素だけをポインター表示にすること。"""

    def test_only_back_icon_uses_pointer_cursor(self):
        text = _read(LIVEDOCS_CSS)
        self.assertRegex(
            text,
            re.escape(".md-nav--primary .md-nav__title")
            + r"\s*\{[^}]*cursor:\s*default",
        )
        self.assertRegex(
            text,
            re.escape(".md-nav--primary .md-nav__title > .md-nav__icon")
            + r"\s*\{[^}]*cursor:\s*pointer",
        )


class DrawerCloseTest(unittest.TestCase):
    """ドロワーを開いた状態から、外を押しても目次を押しても閉じられること。"""

    def _docsfw_drawer_block(self):
        text = _read(LIVEDOCS_CSS)
        match = re.search(
            r"@media screen and \(max-width:\s*1399px\)\s*\{([\s\S]*?)\n\}",
            text,
        )
        self.assertIsNotNone(match, "docsfw の境界の media が無い")
        return match.group(1)

    def test_overlay_covers_the_docsfw_breakpoint(self):
        """Material の覆いは 76.2344em 未満だけのため、1399px まで広げること。

        覆いが無い幅では、本文を押してもドロワーが閉じない。
        """
        block = self._docsfw_drawer_block()
        self.assertRegex(
            block,
            re.escape('[data-md-toggle="drawer"]:checked ~ .md-overlay')
            + r"\s*\{[^}]*width:\s*100%",
        )

    def test_toc_link_click_unchecks_the_drawer_toggle(self):
        """ページ内目次はページ遷移が無いため、JS で閉じること。"""
        text = _read(RESPONSIVE_NAV_JS)
        self.assertIn(".docsfw-combined-toc a", text)
        self.assertRegex(
            text,
            re.escape("getElementById('__drawer')") + r"[\s\S]{0,120}?checked = false",
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

    def test_toc_separator_has_symmetric_medium_drawer_spacing(self):
        """中幅では区切り線の上下を同じ 12px 空けること。"""
        text = _read(LIVEDOCS_CSS)
        self.assertRegex(
            text,
            re.escape(".docsfw-combined-toc") + r"\s*\{[^}]*margin:\s*0",
        )
        self.assertRegex(
            text,
            r"@media screen and \(min-width:\s*76\.25em\) and "
            r"\(max-width:\s*1399px\)\s*\{[\s\S]*?"
            + re.escape(".docsfw-combined-toc")
            + r"\s*\{[^}]*margin-top:\s*12px",
        )

    def test_panel_toc_has_no_content_bottom_spacing(self):
        """板では最後の行の下に余白を置かず、Pandoc の板と同じにすること。

        Material は一覧の padding-bottom: 0.4rem を .md-nav の
        margin-bottom: -0.4rem で打ち消すが、スクロール範囲は負のマージンを
        含めない。目次は一覧の最後の項目のため、対を外側の階層でそろえて 0 に
        しないと、最後の行の下に 0.4rem が残る。
        """
        block = self._drawer_block()
        self.assertRegex(
            block,
            re.escape(".md-nav--primary .docsfw-combined-toc > .md-nav")
            + r"\s*\{[^}]*margin-bottom:\s*0",
        )
        self.assertRegex(
            block,
            re.escape(
                ".md-nav--primary .docsfw-combined-toc > .md-nav > .md-nav__list"
            )
            + r"\s*\{[^}]*padding-bottom:\s*0",
        )

    def test_nested_toc_navigations_are_static(self):
        block = self._drawer_block()
        self.assertRegex(
            block,
            re.escape(".md-nav--primary .docsfw-combined-toc .md-nav")
            + r"\s*\{[^}]*position:\s*static",
        )

    def test_toc_keeps_the_drawer_row_style(self):
        """行の余白と区切り線は、この幅のものをそのまま使うこと。

        Material の .md-nav--primary .md-nav__link の padding がタップ領域を、
        .md-nav--secondary の階層別 padding-left がインデントを持つ。打ち消すと
        行が潰れ、階層も分からなくなる。
        """
        block = self._drawer_block()
        self.assertNotRegex(
            block,
            re.escape(".md-nav--primary .docsfw-combined-toc .md-nav__link")
            + r"\s*\{[^}]*padding",
        )
        self.assertNotRegex(
            block,
            re.escape(".md-nav--primary .docsfw-combined-toc .md-nav__item")
            + r"\s*\{[^}]*border-top",
        )

    def test_toc_title_aligns_with_the_rows(self):
        block = self._drawer_block()
        self.assertRegex(
            block,
            re.escape(".md-nav--primary .docsfw-combined-toc .md-nav__title")
            + r"\s*\{[^}]*padding:\s*0\.6rem 0\.8rem",
        )

    def test_toc_list_is_not_an_independent_scroll_area(self):
        block = self._drawer_block()
        self.assertRegex(
            block,
            re.escape(".md-nav--primary .docsfw-combined-toc .md-nav__list")
            + r"\s*\{[^}]*overflow:\s*visible",
        )

    def test_primary_list_disables_scroll_snapping(self):
        """打ち消す相手と同じ形にすること。

        Material の指定は .md-nav--primary .md-nav__title ~ .md-nav__list
        (クラス 3 個) で、.md-nav--primary > .md-nav__list (クラス 2 個) では
        詳細度で負ける。負けると目次の見出しがスナップ点になり、一覧を末尾まで
        送れない。
        """
        block = self._drawer_block()
        self.assertRegex(
            block,
            re.escape(".md-nav--primary .md-nav__title ~ .md-nav__list")
            + r"\s*\{[^}]*scroll-snap-type:\s*none",
        )


if __name__ == "__main__":
    unittest.main()
