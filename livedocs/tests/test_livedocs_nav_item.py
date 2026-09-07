#!/usr/bin/env python3
"""ドロワー板見出しの上書きの保守条件に関する単体テスト。

``theme/partials/nav-item.html`` は mkdocs-material の同名 partial の複製です。
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

# 取り込み元の mkdocs-material のバージョンと、そのときの partials/nav-item.html。
# 上流が変わったら、差分を確認して theme/partials/nav-item.html へ取り込み直し、
# ここの値を更新する。
UPSTREAM_MATERIAL_VERSION = "9.7.7"
UPSTREAM_NAV_ITEM_SHA256 = "89895208f22d68ce405a4bcb6649b9150eba5bbb04663a6cb3f93f02daf1d2f7"

OVERRIDE_NAV_ITEM = os.path.join(MKDOCS_DIR, "theme", "partials", "nav-item.html")


def _find_upstream_nav_item():
    """インストール済み mkdocs-material の ``partials/nav-item.html`` を探す。"""
    for entry in sys.path:
        candidate = os.path.join(entry, "material", "templates", "partials", "nav-item.html")
        if os.path.isfile(candidate):
            return candidate
    return None


class UpstreamNavItemTest(unittest.TestCase):
    def test_pinned_version_matches_requirements(self):
        requirements = os.path.join(MKDOCS_DIR, "requirements.txt")
        with open(requirements, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("mkdocs-material=={}".format(UPSTREAM_MATERIAL_VERSION), text)

    def test_upstream_nav_item_is_unchanged(self):
        upstream = _find_upstream_nav_item()
        if upstream is None:
            self.skipTest("mkdocs-material が同じ環境に無いため上流を確認できません")
        with open(upstream, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        self.assertEqual(
            digest,
            UPSTREAM_NAV_ITEM_SHA256,
            "mkdocs-material の partials/nav-item.html が変わりました。"
            " theme/partials/nav-item.html へ差分を取り込み直し、"
            " このテストの UPSTREAM_NAV_ITEM_SHA256 を更新してください。",
        )


class OverrideNavItemTest(unittest.TestCase):
    def _read(self):
        with open(OVERRIDE_NAV_ITEM, "r", encoding="utf-8") as handle:
            return handle.read()

    def test_override_only_replaces_the_panel_title_block(self):
        """板自身の見出しブロックだけを差し替えていること。"""
        text = self._read()
        # 上流の単一 <label class="md-nav__title" ...> 見出しは無くなっている。
        self.assertNotIn('<label class="md-nav__title" for="{{ path }}">', text)
        # "<" の戻る操作は、トグル用チェックボックスに紐づく label のまま残す。
        self.assertIn(
            '<label class="md-nav__icon md-icon" for="{{ path }}" tabindex="0"></label>',
            text,
        )
        # フォルダー名は index があれば実リンクになる。
        self.assertIn('<div class="md-nav__title">', text)
        self.assertIn('<a href="{{ index.url | url }}">{{ render_title(nav_item) }}</a>', text)
        # 上流の構造は保つ (macro 群、index 判定、実リンク+トグルの兄弟構造、
        # 子要素の再帰呼び出しなど)。
        for marker in (
            "{% macro render_status(nav_item, type) %}",
            "{% macro render_title(nav_item) %}",
            "{% macro render_content(nav_item, ref) %}",
            "{% macro render_pruned(nav_item, ref) %}",
            "{% macro render(nav_item, path, level, parent) %}",
            "{% set _ = namespace(index = none) %}",
            "if item.is_index and _.index is none",
            '<input class="md-nav__toggle md-toggle {{ indeterminate }}" type="checkbox" id="{{ path }}" {{ checked }}>',
            '<div class="md-nav__link md-nav__container">',
            '<a href="{{ index.url | url }}" class="md-nav__link {{ class }}">',
            '{% if not index or item != index %}',
            "{% elif nav_item == page %}",
        ):
            self.assertIn(marker, text)

    def test_back_icon_and_index_link_are_siblings_not_nested(self):
        """戻るアイコンと索引リンクを兄弟として並べ、入れ子にしないこと。

        上流がすぐ上のブロック (nav_item 自身の一覧行) で既に使っている
        「実リンクの <a> とトグル用 <label> を兄弟にする」形へ合わせる。
        label の中に a を入れ子にする形は避ける (挙動はブラウザーの label
        既定動作で動くとしても、意図が読み取りにくい)。
        """
        text = self._read()
        match = re.search(
            r'<div class="md-nav__title">([\s\S]*?)</div>\s*\n\s*<ul class="md-nav__list"',
            text,
        )
        self.assertIsNotNone(match, "板見出しのブロックが見つからない")
        block = match.group(1)
        self.assertNotRegex(block, r"<label[^>]*>\s*<a\b")
        self.assertIn('<label class="md-nav__icon md-icon"', block)
        self.assertIn("{% if index %}", block)

    def test_title_link_has_no_class_to_avoid_row_padding(self):
        """タイトルの <a> に .md-nav__link を付けないこと。

        .md-nav__link はドロワー内の一覧行向けに padding や
        display: flex を持つ。板見出し (.md-nav__title) は固定の高さと
        余白を自前で持つため、.md-nav__link を付けると二重の余白と
        レイアウト崩れが起きる。
        """
        text = self._read()
        self.assertIn('<a href="{{ index.url | url }}">{{ render_title(nav_item) }}</a>', text)
        self.assertNotIn(
            '<a href="{{ index.url | url }}" class="md-nav__link">{{ render_title(nav_item) }}</a>',
            text,
        )


if __name__ == "__main__":
    unittest.main()
