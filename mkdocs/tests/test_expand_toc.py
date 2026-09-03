#!/usr/bin/env python3
"""``\\toc`` 展開の字下げと入れ子リストに関する単体テスト。"""

import glob
import os
import sys
import unittest

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

for site in glob.glob(
    os.path.join(os.path.dirname(__file__), "..", ".venv", "lib", "python*", "site-packages")
):
    if site not in sys.path:
        sys.path.append(site)

try:
    import markdown
except ImportError:
    markdown = None

from expand_toc import DocIndex, expand_toc_commands, render_toc  # noqa: E402


def _nested_index():
    index = DocIndex()
    index.add("c-platform/index.md", "README.md", "cplat")
    index.add("c-platform/api-cheatsheet.md", "api-cheatsheet.md", "API チート シート")
    index.add("c-platform/functional-spec/index.md", "README.md", "cplat 機能仕様")
    index.add(
        "c-platform/functional-spec/argparser.md",
        "argparser.md",
        "argparser 機能仕様",
    )
    index.add("c-platform/functional-spec/nested/index.md", "README.md", "入れ子")
    index.add("c-platform/functional-spec/nested/deep.md", "deep.md", "深い文書")
    index.add("c-platform/sibling.md", "sibling.md", "兄弟")
    return index


def _unlimited_exclude_basedir():
    return {
        "depth": -1,
        "exclude": [],
        "basedir": "",
        "exclude-basedir": True,
    }


class RenderTocIndentTest(unittest.TestCase):
    def setUp(self):
        self.index = _nested_index()
        self.rendered = render_toc(
            self.index,
            "c-platform/index.md",
            _unlimited_exclude_basedir(),
        )
        self.lines = self.rendered.split("\n")

    def _line_containing(self, needle):
        matches = [line for line in self.lines if needle in line]
        self.assertEqual(len(matches), 1, matches)
        return matches[0]

    def test_child_uses_four_space_indent(self):
        child = self._line_containing("[argparser.md]")
        self.assertTrue(child.startswith("    - "))
        self.assertFalse(child.startswith("     - "))

    def test_grandchild_uses_eight_space_indent(self):
        grandchild = self._line_containing("[deep.md]")
        self.assertTrue(grandchild.startswith("        - "))
        self.assertFalse(grandchild.startswith("         - "))

    def test_sibling_stays_at_top_level(self):
        sibling = self._line_containing("[sibling.md]")
        self.assertTrue(sibling.startswith("- "))
        self.assertFalse(sibling.startswith(" "))

    def test_expand_toc_commands_replaces_toc_line(self):
        text = "## 文書一覧\n\n\\toc depth=-1 exclude-basedir=true\n"
        result = expand_toc_commands(text, self.index, "c-platform/index.md")
        self.assertNotIn("\\toc", result)
        self.assertIn("    - 📄 [argparser.md](functional-spec/argparser.md)", result)
        self.assertIn(
            "        - 📄 [deep.md](functional-spec/nested/deep.md)",
            result,
        )


@unittest.skipUnless(markdown is not None, "Python-Markdown が必要です")
class RenderTocMarkdownNestingTest(unittest.TestCase):
    def test_python_markdown_nests_children_and_keeps_siblings(self):
        rendered = render_toc(
            _nested_index(),
            "c-platform/index.md",
            _unlimited_exclude_basedir(),
        )
        html = markdown.markdown(rendered, extensions=["nl2br", "md_in_html"])

        self.assertIn("cplat 機能仕様<ul>", html)
        self.assertIn("入れ子<ul>", html)
        self.assertRegex(
            html,
            r"cplat 機能仕様<ul>[\s\S]*argparser\.md[\s\S]*deep\.md"
            r"[\s\S]*</ul>\s*</li>\s*<li>📄 <a href=\"sibling\.md\">",
        )


if __name__ == "__main__":
    unittest.main()
