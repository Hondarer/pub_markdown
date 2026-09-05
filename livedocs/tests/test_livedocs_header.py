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

    def test_meta_partial_is_placed_before_the_palette_toggle(self):
        """発行者と発行日時を、静的発行と同じくアイコン群より前に出していること。"""
        with open(OVERRIDE_HEADER, "r", encoding="utf-8") as handle:
            text = handle.read()
        meta = text.index('{% include "partials/docsfw-header-meta.html" %}')
        palette = text.index('{% include "partials/palette.html" %}')
        links = text.index('{% include "partials/docsfw-header-links.html" %}')
        search = text.index('{% include "partials/search.html" %}')
        self.assertLess(meta, palette)
        self.assertLess(palette, links)
        self.assertLess(links, search)

    def test_meta_partial_reads_the_front_matter(self):
        with open(META_PARTIAL, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn('page.meta["author"]', text)
        self.assertIn('page.meta["date"]', text)
        self.assertIn("docsfw-header-meta", text)

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


if __name__ == "__main__":
    unittest.main()
