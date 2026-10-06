"""heading-content-indent.lua が H5 以降の見出しと配下の本文に字下げクラスを付けることを検証する。"""

import re
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILTERS = ROOT / "bin_internal/pandoc-filters"

MARKDOWN = """# Title

#### Item

Under item.

##### Level five

Body five.

| a | b |
|---|---|
| 1 | 2 |

Table: caption five

###### Level six

Body six.

---

After rule.

---

##### Second five

Body second.

---

#### Next item

Back to item.

##### Last five

Last body.

---
"""


class TopLevel(HTMLParser):
    """最上位の要素を (タグ, class, 子要素のタグ) の並びとして集める。"""

    VOID = {"hr", "br", "img", "col", "input"}

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.items = []

    def handle_starttag(self, tag, attrs):
        if self.depth == 0:
            self.items.append((tag, dict(attrs).get("class") or "", []))
        elif self.depth == 1:
            self.items[-1][2].append(tag)
        if tag not in self.VOID:
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.depth == 0:
            self.items.append((tag, dict(attrs).get("class") or "", []))
        elif self.depth == 1:
            self.items[-1][2].append(tag)

    def handle_endtag(self, tag):
        if tag not in self.VOID:
            self.depth -= 1


def top_level(html):
    parser = TopLevel()
    parser.feed(html)
    return parser.items


def render(to="html"):
    # 発行処理と同じく、表のキャプションを表の外へ移してから字下げする。
    return subprocess.run(
        ["pandoc", "-f", "markdown", "-t", to, "--wrap=none", "--shift-heading-level-by=-1",
         "--lua-filter", str(FILTERS / "table-caption-style.lua"),
         "--lua-filter", str(FILTERS / "heading-content-indent.lua")],
        input=MARKDOWN, encoding="utf-8", capture_output=True, check=True).stdout


INDENT_1 = "docsfw-heading-indent-1"
INDENT_2 = "docsfw-heading-indent-2"


class HeadingContentIndentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = render()
        cls.items = top_level(cls.html)

    def test_top_level_structure(self):
        self.assertEqual(self.items, [
            ("h3", "", []),
            ("p", "", []),
            ("h4", INDENT_1, []),
            # 表のキャプションと表も本文の div に入る。
            ("div", INDENT_1, ["p", "div", "table"]),
            ("h5", INDENT_2, []),
            # 本文の途中の水平線は本文と同じ字下げにする。
            ("div", INDENT_2, ["p", "hr", "p"]),
            # 上位の見出しの直前の水平線は、その見出しの字下げにする。
            ("div", INDENT_1, ["hr"]),
            ("h4", INDENT_1, []),
            ("div", INDENT_1, ["p"]),
            ("hr", "", []),
            ("h3", "", []),
            ("p", "", []),
            ("h4", INDENT_1, []),
            ("div", INDENT_1, ["p"]),
            # 文書の末尾の水平線は字下げしない。
            ("hr", "", []),
        ])

    def test_headings_keep_their_ids(self):
        self.assertRegex(self.html, r'<h4 class="docsfw-heading-indent-1" id="level-five">')
        self.assertRegex(self.html, r'<h5 class="docsfw-heading-indent-2" id="level-six">')

    def test_table_caption_stays_next_to_the_table(self):
        self.assertRegex(self.html, re.compile(
            r'docsfw-table-caption[^>]*>\s*caption five\s*</div>\s*<table', re.S))

    def test_non_html_output_is_unchanged(self):
        self.assertNotIn("docsfw-heading-indent", render("native"))


if __name__ == "__main__":
    unittest.main()
