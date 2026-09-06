#!/usr/bin/env python3
"""概要 (abstract) 挿入フックの単体テスト。"""

import os
import sys
import unittest
from types import SimpleNamespace

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from livedocs_abstract_hook import on_page_content  # noqa: E402

CONFIG = {
    "markdown_extensions": ["toc", "tables", "fenced_code"],
    "mdx_configs": {},
}


def _page(meta):
    return SimpleNamespace(meta=meta)


class OnPageContentTest(unittest.TestCase):
    def test_no_abstract_leaves_html_untouched(self):
        html = "<h1>タイトル</h1>\n<p>本文</p>"
        result = on_page_content(html, _page({}), CONFIG, None)
        self.assertEqual(result, html)

    def test_inserts_right_after_the_first_h1(self):
        html = "<h1>タイトル</h1>\n<p>本文</p>"
        result = on_page_content(html, _page({"abstract": "概要"}), CONFIG, None)
        self.assertTrue(result.startswith("<h1>タイトル</h1>\n"))
        self.assertIn('<div class="abstract">', result)
        self.assertIn("<p>本文</p>", result)
        # 概要ブロックは H1 の直後、本文より前に来る。
        self.assertLess(result.index('<div class="abstract">'), result.index("<p>本文</p>"))

    def test_prepends_when_no_h1_is_present(self):
        html = "<p>本文</p>"
        result = on_page_content(html, _page({"abstract": "概要"}), CONFIG, None)
        self.assertTrue(result.startswith('<div class="abstract">'))
        self.assertIn("<p>本文</p>", result)

    def test_abstract_body_is_rendered_as_markdown(self):
        html = "<h1>タイトル</h1>"
        result = on_page_content(html, _page({"abstract": "**強調**"}), CONFIG, None)
        self.assertIn("<strong>強調</strong>", result)

    def test_missing_abstract_title_stays_empty(self):
        html = "<h1>タイトル</h1>"
        result = on_page_content(html, _page({"abstract": "概要"}), CONFIG, None)
        self.assertIn('<div class="abstract-title"></div>', result)

    def test_abstract_title_is_html_escaped_and_not_markdown_rendered(self):
        html = "<h1>タイトル</h1>"
        meta = {"abstract": "概要", "abstract-title": "<Abstract>"}
        result = on_page_content(html, _page(meta), CONFIG, None)
        self.assertIn('<div class="abstract-title">&lt;Abstract&gt;</div>', result)


if __name__ == "__main__":
    unittest.main()
