"""MkDocs で H5 以降の見出しと配下の本文に、静的発行と同じ字下げクラスを付ける。"""

import re
import sys
import unittest
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

#### Next item

Back to item.
"""


def render(source=SOURCE):
    return markdown.markdown(source, extensions=["tables", "attr_list", "admonition", "toc",
                                                 HeadingIndentExtension()])


class HeadingIndentTest(unittest.TestCase):
    def test_headings_and_bodies_get_the_indent_class(self):
        html = render()
        self.assertRegex(html, r'<h5 class="docsfw-heading-indent-1" id="level-five">')
        # attr_list で指定したクラスは残す。
        self.assertRegex(html, r'<h6 class="custom docsfw-heading-indent-2" id="level-six">')
        wrappers = re.findall(r'<div class="(docsfw-heading-indent-\d)">', html)
        self.assertEqual(wrappers, ["docsfw-heading-indent-1", "docsfw-heading-indent-2"])

    def test_table_and_admonition_are_inside_the_body_but_nested_headings_are_untouched(self):
        html = render()
        body = re.search(r'<div class="docsfw-heading-indent-1">(.*)</div>\s*<h6', html, re.S).group(1)
        self.assertIn("<table>", body)
        self.assertIn('class="admonition note"', body)
        # 本文の中の見出しは字下げの対象外で、囲みも作らない。
        self.assertRegex(body, r'<h5 id="nested-heading">')

    def test_body_under_shallow_headings_is_not_wrapped(self):
        html = render()
        self.assertIn("<p>Under item.</p>", html)
        self.assertRegex(html, r'</div>\s*<h4 id="next-item">Next item</h4>\s*<p>Back to item.</p>')

    def test_on_config_registers_the_extension_once(self):
        config = SimpleNamespace(markdown_extensions=["toc"])
        on_config(config)
        on_config(config)
        self.assertEqual(sum(isinstance(item, HeadingIndentExtension)
                             for item in config.markdown_extensions), 1)


if __name__ == "__main__":
    unittest.main()
