#!/usr/bin/env python3
"""``\\toc`` 展開の字下げと入れ子リストに関する単体テスト。"""

import glob
import os
import sys
import unittest
import tempfile
import subprocess
import shutil
from pathlib import Path

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

from expand_toc import DocIndex, expand_toc_commands, render_toc, parse_toc_params  # noqa: E402
from stage_livedocs import convert_collapsible_list_fences  # noqa: E402


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


class CollapsibleTest(unittest.TestCase):
    def test_open_levels_and_multiple_commands(self):
        for value in (None, "0", "1", "2", "-1", "invalid"):
            command = r"\toc depth=-1" + (" open-level=" + value if value else "")
            result = expand_toc_commands(command + "\n\n" + command, _nested_index(), "c-platform/index.md")
            self.assertEqual(result.count('class="collapsible-list"'), 2)
            self.assertEqual(result.count('data-open-level='), 2 if value else 0)
            if value:
                self.assertIn('data-open-level="' + value + '"', result)

    def test_code_examples_are_unchanged(self):
        text = '````markdown\n```\n\\toc depth=-1\n::: {.collapsible-list}\n- item\n:::\n```\n````'
        self.assertEqual(expand_toc_commands(text, _nested_index(), "c-platform/index.md"), text)
        self.assertEqual(convert_collapsible_list_fences(text), text)

    def test_manual_nested_containers_and_code(self):
        text = ':::: {.collapsible-list open-level=1}\n- outer\n\n::: {.collapsible-list open-level=-1}\n- inner\n:::\n\n```text\n:::\n```\n::::'
        result = convert_collapsible_list_fences(text)
        self.assertEqual(result.count('<div '), 2)
        self.assertEqual(result.count('</div>'), 2)
        self.assertIn('data-open-level="1"', result)
        self.assertIn('data-open-level="-1"', result)
        self.assertIn('```text\n:::\n```', result)

    def test_empty_and_excluded_index(self):
        index = _nested_index()
        params = parse_toc_params('depth=-1 exclude="README.md"')
        result = render_toc(index, "c-platform/index.md", params)
        self.assertIn('- 📁 c-platform\n', result)
        self.assertNotIn('](index.md)', result)
        self.assertEqual(render_toc(DocIndex(), 'index.md', parse_toc_params('')), '')

    def test_basedir_depth_and_multiple_exclusions(self):
        params = parse_toc_params('basedir="functional-spec" depth=0 exclude-basedir=true exclude="argparser.md" exclude="nested/*"')
        self.assertEqual(render_toc(_nested_index(), "c-platform/index.md", params), '')
        params = parse_toc_params('basedir="functional-spec" depth=0 exclude-basedir=true')
        result = render_toc(_nested_index(), "c-platform/index.md", params)
        self.assertIn('(functional-spec/argparser.md)', result)
        self.assertIn('(functional-spec/nested/index.md)', result)
        self.assertNotIn('deep.md', result)

    def test_depth_zero_keeps_directories_with_nested_documents(self):
        index = _nested_index()
        index.add("overview.md", "overview.md", "概要")
        result = render_toc(
            index,
            "index.md",
            parse_toc_params("depth=0 exclude-basedir=true"),
        )
        self.assertIn("- 📁 [c-platform](c-platform/index.md)", result)
        self.assertIn("- 📄 [overview.md](overview.md)", result)
        self.assertNotIn("api-cheatsheet.md", result)
        self.assertNotIn("functional-spec", result)

    @unittest.skipUnless(markdown is not None, "Python-Markdown が必要です")
    def test_wrapper_preserves_markdown_links_and_nesting(self):
        result = expand_toc_commands(r'\toc depth=-1 open-level=1', _nested_index(), "c-platform/index.md")
        html = markdown.markdown(result, extensions=['md_in_html', 'nl2br'])
        self.assertIn('<div class="collapsible-list" data-open-level="1">', html)
        self.assertIn('<a href="functional-spec/nested/deep.md">', html)
        self.assertEqual(html.count('<ul>'), 4)

    @unittest.skipUnless(shutil.which('bash'), 'Bash が必要です')
    def test_pandoc_index_generator_parity(self):
        with tempfile.TemporaryDirectory(prefix='docsfw-toc-') as directory:
            root = Path(directory) / 'tree'
            index = DocIndex()
            for name in ('README.md', 'a.md', 'sub/README.md', 'sub/b.md', 'sub/deep/c.md'):
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('# ' + name + '\n', encoding='utf-8')
                staged = 'tree/' + name.replace('README.md', 'index.md')
                index.add(staged, file.name, name)
            script = Path(BIN_DIR).parents[1] / 'bin/pandoc-filters/insert-toc.sh'
            for options in ('depth=-1', 'depth=-1 exclude="sub/*"',
                            'depth=-1 basedir="sub"'):
                with self.subTest(options=options):
                    params = parse_toc_params(options)
                    current = root / params['basedir'] / '.toc-dummy.md' if params['basedir'] else root / 'README.md'
                    result = subprocess.run(['bash', str(script), str(params['depth']), str(current),
                                             'neutral', ','.join(params['exclude']), params['basedir'],
                                             str(params['exclude-basedir']).lower()],
                                            capture_output=True, text=True, check=True)
                    expected = result.stdout.replace('README.md)', 'index.md)').replace('<br/>     ', '<br/>' + '&nbsp;' * 5)
                    self.assertEqual(render_toc(index, 'tree/index.md', params).strip(), expected.strip())


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
