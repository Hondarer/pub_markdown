#!/usr/bin/env python3
"""meta viewport の上書きに関する単体テスト。

``theme/main.html`` は Material の ``site_meta`` ブロックの出力を置き換えて、
meta viewport へ ``viewport-fit=cover`` を足します。置き換え元の文字列が
上流で変わると空振りするため、その文字列が今も存在することを確認します。
"""

import os
import re
import sys
import unittest

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from vendor_assets import MKDOCS_DIR  # noqa: E402

# theme/main.html が置き換える文字列。Material の base.html が出力する
# meta viewport と一致している必要がある。
UPSTREAM_VIEWPORT_META = '<meta name="viewport" content="width=device-width,initial-scale=1">'
DOCSFW_VIEWPORT_META = (
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
)

OVERRIDE_MAIN = os.path.join(MKDOCS_DIR, "theme", "main.html")


def _find_upstream_base():
    """インストール済み mkdocs-material の ``base.html`` を探す。"""
    for entry in sys.path:
        candidate = os.path.join(entry, "material", "templates", "base.html")
        if os.path.isfile(candidate):
            return candidate
    return None


class ViewportOverrideTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(OVERRIDE_MAIN, "r", encoding="utf-8") as handle:
            cls.main = handle.read()

    def test_override_extends_base_and_replaces_site_meta(self):
        """base.html を継承し、site_meta の出力を置き換えること。"""
        self.assertIn('{% extends "base.html" %}', self.main)
        self.assertRegex(self.main, r"\{% block site_meta %\}[\s\S]*\{\{ super\(\) \}\}")
        self.assertRegex(self.main, r"\{%-? filter replace\(")

    def test_override_replaces_the_upstream_viewport_meta(self):
        """置き換えの前後の文字列を持ち、cover を足すこと。"""
        self.assertIn(UPSTREAM_VIEWPORT_META, self.main)
        self.assertIn(DOCSFW_VIEWPORT_META, self.main)

    def test_viewport_meta_is_not_appended(self):
        """後置きでは iOS に効かないため、meta を足す形にしないこと。

        実機では extrahead へ後置きしても env(safe-area-inset-bottom) が 0 の
        ままでした。置き換えで meta viewport を 1 つに保ちます。
        """
        self.assertNotIn("{% block extrahead %}", self.main)

    def test_upstream_base_still_emits_the_replaced_meta(self):
        """上流の base.html が、置き換え元の文字列を今も出力すること。"""
        upstream = _find_upstream_base()
        if upstream is None:
            self.skipTest("mkdocs-material が同じ環境に無いため上流を確認できません")
        with open(upstream, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn(
            UPSTREAM_VIEWPORT_META,
            text,
            "mkdocs-material の base.html の meta viewport が変わりました。"
            " theme/main.html の置き換え元の文字列と、このテストの"
            " UPSTREAM_VIEWPORT_META を更新してください。",
        )
        site_meta = re.search(r"\{% block site_meta %\}([\s\S]*?)\{% endblock %\}", text)
        self.assertIsNotNone(site_meta)
        self.assertIn(UPSTREAM_VIEWPORT_META, site_meta.group(1))


if __name__ == "__main__":
    unittest.main()
