"""MkDocs で H5 以降の見出しと配下の本文に、静的発行と同じ字下げクラスを付ける。"""

import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import markdown

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from livedocs_heading_indent_hook import HeadingIndentExtension, on_config

SOURCE = """# Title

#### Item

Under item.

##### Level five

Body five.

| a | b |
|---|---|
| 1 | 2 |

!!! note
    ##### Nested heading

    Inside admonition.

###### Level six {: .custom }

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

INDENT_1 = "docsfw-heading-indent-1"
INDENT_2 = "docsfw-heading-indent-2"


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


def render(source=SOURCE):
    return markdown.markdown(source, extensions=["tables", "attr_list", "admonition", "toc",
                                                 HeadingIndentExtension()])


def top_level(html):
    parser = TopLevel()
    parser.feed(html)
    return parser.items


class HeadingIndentTest(unittest.TestCase):
    def test_top_level_structure_matches_the_static_output(self):
        self.assertEqual(top_level(render()), [
            ("h1", "", []),
            ("h4", "", []),
            ("p", "", []),
            ("h5", INDENT_1, []),
            # 表と admonition も本文の div に入る。
            ("div", INDENT_1, ["p", "table", "div"]),
            # attr_list で指定したクラスは残す。
            ("h6", "custom " + INDENT_2, []),
            # 本文の途中の水平線は本文と同じ字下げにする。
            ("div", INDENT_2, ["p", "hr", "p"]),
            # 上位の見出しの直前の水平線は、その見出しの字下げにする。
            ("div", INDENT_1, ["hr"]),
            ("h5", INDENT_1, []),
            ("div", INDENT_1, ["p"]),
            ("hr", "", []),
            ("h4", "", []),
            ("p", "", []),
            ("h5", INDENT_1, []),
            ("div", INDENT_1, ["p"]),
            # 文書の末尾の水平線は字下げしない。
            ("hr", "", []),
        ])

    def test_headings_inside_the_body_are_untouched(self):
        self.assertIn('<h5 id="nested-heading">Nested heading</h5>', render())

    def test_on_config_registers_the_extension_once(self):
        config = SimpleNamespace(markdown_extensions=["toc"])
        on_config(config)
        on_config(config)
        self.assertEqual(sum(isinstance(item, HeadingIndentExtension)
                             for item in config.markdown_extensions), 1)


if __name__ == "__main__":
    unittest.main()
