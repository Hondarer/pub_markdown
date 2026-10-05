"""heading-content-indent.lua が H5 以降の見出しと配下の本文に字下げクラスを付けることを検証する。"""

import re
import subprocess
import unittest
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

##### Second five

Body second.

#### Next item

Back to item.
"""


def render(to="html"):
    # 発行処理と同じく、表のキャプションを表の外へ移してから字下げする。
    return subprocess.run(
        ["pandoc", "-f", "markdown", "-t", to, "--wrap=none", "--shift-heading-level-by=-1",
         "--lua-filter", str(FILTERS / "table-caption-style.lua"),
         "--lua-filter", str(FILTERS / "heading-content-indent.lua")],
        input=MARKDOWN, encoding="utf-8", capture_output=True, check=True).stdout


class HeadingContentIndentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = render()

    def test_headings_get_the_indent_class_of_their_level(self):
        self.assertRegex(self.html, r'<h4 class="docsfw-heading-indent-1" id="level-five">')
        self.assertRegex(self.html, r'<h5 class="docsfw-heading-indent-2" id="level-six">')
        self.assertRegex(self.html, r'<h3 id="item">')
        self.assertRegex(self.html, r'<h3 id="next-item">')

    def test_body_until_the_next_heading_is_wrapped_and_headings_stay_outside(self):
        wrappers = re.findall(r'<div class="(docsfw-heading-indent-\d)">(.*?)</div>\s*<h', self.html, re.S)
        self.assertEqual([name for name, _ in wrappers],
                         ["docsfw-heading-indent-1", "docsfw-heading-indent-2", "docsfw-heading-indent-1"])
        for _, body in wrappers:
            self.assertNotRegex(body, r"<h[1-6]")
        self.assertIn("Body five.", wrappers[0][1])
        self.assertIn("Body six.", wrappers[1][1])
        self.assertIn("Body second.", wrappers[2][1])

    def test_table_and_caption_are_inside_the_indented_body(self):
        body = re.search(r'<div class="docsfw-heading-indent-1">(.*?)</div>\s*<h5', self.html, re.S).group(1)
        self.assertRegex(body, re.compile(r'docsfw-table-caption[^>]*>\s*caption five\s*</div>\s*<table', re.S))

    def test_body_under_shallow_headings_is_not_wrapped(self):
        self.assertRegex(self.html, r"<p>Under item.</p>")
        self.assertRegex(self.html, r'</div>\s*<h3 id="next-item">[^<]*</h3>\s*<p>Back to item.</p>')

    def test_non_html_output_is_unchanged(self):
        self.assertNotIn("docsfw-heading-indent", render("native"))


if __name__ == "__main__":
    unittest.main()
