#!/usr/bin/env python3
"""全文検索の索引を版ごとに分ける処理の単体テスト。

``bin/livedocs_search_hook.py`` は search プラグインの索引を
``<variant>/search/search_index.json`` へ分け、``theme/main.html`` は
``__config.base`` を版のルートへ向けます。テーマの置き換えは Material の
``base.html`` が出力する ``"base": base_url`` に依存するため、上流の
テンプレートとの一致も確認します。
"""

import json
import os
import sys
import tempfile
import unittest

import jinja2

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from livedocs_search_hook import split_search_index, write_variant_indexes  # noqa: E402
from vendor_assets import MKDOCS_DIR  # noqa: E402

OVERRIDE_MAIN = os.path.join(MKDOCS_DIR, "theme", "main.html")


def _find_upstream_base():
    """インストール済み mkdocs-material の ``base.html`` を探す。"""
    for entry in sys.path:
        candidate = os.path.join(entry, "material", "templates", "base.html")
        if os.path.isfile(candidate):
            return candidate
    return None


def _index(*locations):
    return {
        "config": {"lang": ["en"]},
        "docs": [{"location": loc, "title": loc, "text": ""} for loc in locations],
    }


class SplitSearchIndexTest(unittest.TestCase):
    def test_docs_are_split_by_variant_and_relocated(self):
        parts = split_search_index(
            _index("ja/", "ja/a/#x", "ja-details/a/", "other/", "jab/"),
            ["ja", "ja-details"],
        )
        self.assertEqual(["", "a/#x"], [d["location"] for d in parts["ja"]["docs"]])
        self.assertEqual(["a/"], [d["location"] for d in parts["ja-details"]["docs"]])
        self.assertEqual(["other/", "jab/"], [d["location"] for d in parts[None]["docs"]])
        self.assertEqual({"lang": ["en"]}, parts["ja"]["config"])

    def test_write_variant_indexes(self):
        with tempfile.TemporaryDirectory() as site:
            os.makedirs(os.path.join(site, "search"))
            with open(os.path.join(site, "search", "search_index.json"), "w", encoding="utf-8") as handle:
                json.dump(_index("ja/a/", "ja-details/b/"), handle)
            self.assertTrue(write_variant_indexes(site, ["ja", "ja-details"]))
            for variant, expected in (("ja", ["a/"]), ("ja-details", ["b/"]), ("", [])):
                path = os.path.join(site, variant, "search", "search_index.json")
                with open(path, encoding="utf-8") as handle:
                    self.assertEqual(expected, [d["location"] for d in json.load(handle)["docs"]])

    def test_missing_index_is_ignored(self):
        with tempfile.TemporaryDirectory() as site:
            self.assertFalse(write_variant_indexes(site, ["ja"]))


class ConfigBaseOverrideTest(unittest.TestCase):
    """theme/main.html の config ブロックが base を版のルートへ向けること。"""

    UPSTREAM_BLOCK = (
        '{% block config %}<script id="__config" type="application/json">'
        '{{- {"annotate": none, "base": base_url, "features": []} | tojson -}}'
        "</script>{% endblock %}"
    )

    def _render(self, url):
        with open(OVERRIDE_MAIN, encoding="utf-8") as handle:
            main = handle.read()
        env = jinja2.Environment(
            loader=jinja2.ChoiceLoader([
                jinja2.DictLoader({"base.html": self.UPSTREAM_BLOCK, "main.html": main}),
                jinja2.FileSystemLoader(os.path.dirname(OVERRIDE_MAIN)),
            ])
        )
        env.globals["lang"] = {"t": lambda key: key}
        template = env.get_template("main.html")
        text = template.render(
            page={"url": url},
            base_url="../..",
            config={"extra": {"livedocs_variants": ["ja", "ja-details"]}},
        )
        start = text.index(">", text.index('id="__config"')) + 1
        return json.loads(text[start:text.index("</script>", start)])

    def test_variant_page_points_base_to_variant_root(self):
        self.assertEqual("../../ja-details/", self._render("ja-details/a/")["base"])

    def test_other_page_keeps_base(self):
        self.assertEqual("../..", self._render("misc/a/")["base"])

    def test_upstream_base_still_emits_base_url(self):
        """上流の base.html が、置き換え元の ``"base": base_url`` を今も出力すること。"""
        upstream = _find_upstream_base()
        if upstream is None:
            self.skipTest("mkdocs-material が同じ環境に無いため上流を確認できません")
        with open(upstream, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn('"base": base_url,', text)
        self.assertIn("{% block config %}", text)


if __name__ == "__main__":
    unittest.main()
