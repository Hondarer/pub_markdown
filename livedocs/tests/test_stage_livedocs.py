#!/usr/bin/env python3
"""mkdocs による動的発行のステージング処理に関する単体テスト。"""

import os
import sys
import tempfile
import unittest

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from stage_livedocs import (  # noqa: E402
    Document,
    PathMapper,
    build_front_matter,
    convert_captions,
    convert_implicit_figures,
    generate_nav_files,
    rewrite_links,
)


class BuildFrontMatterTest(unittest.TestCase):
    def _document(self, staged_rel="guide/index.md", body="# ガイド\n"):
        document = Document("/source/README.md", "guide/README.md")
        document.staged_rel = staged_rel
        document.body = body
        return document

    def test_index_uses_first_heading_when_title_is_missing(self):
        document = self._document()
        self.assertEqual(
            build_front_matter(document, "ja", True),
            '---\ntitle: "ガイド"\n---',
        )

    def test_index_keeps_explicit_title(self):
        document = self._document()
        document.front_matter = '---\ntitle: "明示タイトル"\n---'
        document.fields = {"title": "明示タイトル"}
        self.assertEqual(
            build_front_matter(document, "ja", True),
            document.front_matter,
        )

    def test_index_without_heading_keeps_title_unset(self):
        document = self._document(body="本文だけです。\n")
        self.assertEqual(build_front_matter(document, "ja", True), "")

    def test_non_index_does_not_add_heading_as_title(self):
        document = self._document(staged_rel="guide/usage.md")
        self.assertEqual(build_front_matter(document, "ja", True), "")

    def test_short_title_still_takes_priority(self):
        document = self._document()
        document.fields = {
            "short-title-ja-details": "短い名称",
            "short-title-en": "Short title",
        }
        self.assertEqual(
            build_front_matter(document, "ja", True),
            '---\ntitle: "短い名称"\n---',
        )
        self.assertEqual(
            build_front_matter(document, "en", False),
            '---\ntitle: "Short title"\n---',
        )


class GenerateNavFilesTest(unittest.TestCase):
    def test_root_enables_index_titles_without_publocal(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source")
            output = os.path.join(tmp, "output")
            os.makedirs(source)

            generated = generate_nav_files(output, source, [], ["guide"])

            self.assertEqual(generated, 1)
            with open(os.path.join(output, ".nav.yml"), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "use_index_title: true\n")

    def test_root_combines_index_titles_with_publocal_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source")
            output = os.path.join(tmp, "output")
            os.makedirs(source)
            with open(os.path.join(source, "publocal.yaml"), "w", encoding="utf-8") as handle:
                handle.write("order:\n  - README.md\n  - guide\n")

            generate_nav_files(output, source, [], [""])

            with open(os.path.join(output, ".nav.yml"), encoding="utf-8") as handle:
                self.assertEqual(
                    handle.read(),
                    "use_index_title: true\nnav:\n  - index.md\n  - guide\n  - ...\n",
                )


class RewriteLinksTest(unittest.TestCase):
    def _document(self, body):
        document = Document(
            "/workspace/docs/guide/source.md",
            "guide/source.md",
        )
        document.body = body
        return document

    def test_rewrites_link_to_logical_tree_target(self):
        document = self._document("[入口](../README.md)\n")
        mapper = PathMapper("/workspace/docs", [])
        real_to_staged = {
            os.path.normcase(os.path.normpath("/workspace/docs/README.md")): "index.md",
        }

        self.assertEqual(
            rewrite_links(document.body, document, mapper, real_to_staged),
            "[入口](../index.md)\n",
        )

    def test_renders_unresolved_relative_reference_without_link(self):
        document = self._document(
            "[README](../../../README.md)\n"
            "[ヘッダー](../prod/include/)\n"
            "[サンプル](file_copy_sample.c)\n"
        )
        mapper = PathMapper("/workspace/docs", [])

        self.assertEqual(
            rewrite_links(document.body, document, mapper, {}),
            "README (`../../../README.md`)\n"
            "ヘッダー (`../prod/include/`)\n"
            "サンプル (`file_copy_sample.c`)\n",
        )

    def test_keeps_non_relative_and_image_links(self):
        document = self._document(
            "[外部](https://example.com/docs)\n"
            "[見出し](#section)\n"
            "[Doxygen](../../../doxygen/example/index.html)\n"
            "![画像](missing.png)\n"
            "```md\n"
            "[コード](../outside.md)\n"
            "```\n"
        )
        mapper = PathMapper("/workspace/docs", [])

        self.assertEqual(
            rewrite_links(document.body, document, mapper, {}),
            document.body,
        )


class ConvertCaptionsTest(unittest.TestCase):
    def test_wraps_diagram_fence_and_caption_into_figure(self):
        source = (
            "```mermaid\n"
            "sequenceDiagram\n"
            "```\n"
            "\n"
            "CodeBlock: Mermaid のキャプション\n"
        )
        self.assertEqual(
            convert_captions(source),
            '<figure class="docsfw-figure" markdown="1">\n'
            "\n"
            "```mermaid\n"
            "sequenceDiagram\n"
            "```\n"
            "\n"
            '<figcaption class="docsfw-caption" markdown="span">'
            "Mermaid のキャプション</figcaption>\n"
            "\n"
            "</figure>\n",
        )

    def test_moves_label_to_figure_id(self):
        source = (
            "```plantuml\n"
            "@startuml\n"
            "@enduml\n"
            "```\n"
            "\n"
            "CodeBlock: ラベル付き {#fig:sample}\n"
        )
        result = convert_captions(source)
        self.assertIn('<figure class="docsfw-figure" id="fig:sample" markdown="1">', result)
        self.assertIn(
            '<figcaption class="docsfw-caption" markdown="span">ラベル付き</figcaption>',
            result,
        )

    def test_keeps_multiline_caption_in_figcaption(self):
        source = (
            "```mermaid\n"
            "sequenceDiagram\n"
            "```\n"
            "\n"
            "CodeBlock: 1 行目\n"
            "2 行目\n"
        )
        self.assertIn(
            '<figcaption class="docsfw-caption" markdown="span">1 行目\n'
            "2 行目</figcaption>",
            convert_captions(source),
        )

    def test_keeps_paragraph_caption_for_source_code_and_table(self):
        source = (
            "```c\n"
            "int main(void);\n"
            "```\n"
            "\n"
            "CodeBlock: ソースのキャプション\n"
            "\n"
            "Table: 表のキャプション\n"
        )
        self.assertEqual(
            convert_captions(source),
            "```c\n"
            "int main(void);\n"
            "```\n"
            "\n"
            "ソースのキャプション\n"
            "{: .docsfw-caption }\n"
            "\n"
            "表のキャプション\n"
            "{: .docsfw-caption }\n",
        )

    def test_keeps_diagram_without_caption(self):
        source = (
            "```mermaid\n"
            "sequenceDiagram\n"
            "```\n"
            "\n"
            "つぎの段落。\n"
        )
        self.assertEqual(convert_captions(source), source)

    def test_ignores_caption_separated_from_diagram_by_text(self):
        source = (
            "```mermaid\n"
            "sequenceDiagram\n"
            "```\n"
            "\n"
            "あいだの段落。\n"
            "\n"
            "CodeBlock: キャプション\n"
        )
        result = convert_captions(source)
        self.assertNotIn("<figure", result)
        self.assertIn("{: .docsfw-caption }", result)


class ConvertImplicitFiguresTest(unittest.TestCase):
    def test_converts_lone_image_paragraph(self):
        self.assertEqual(
            convert_implicit_figures("![draw.io のテスト](images/x.drawio.svg)\n"),
            '<figure class="docsfw-figure" markdown="1">\n'
            "\n"
            "![draw.io のテスト](images/x.drawio.svg)\n"
            "\n"
            '<figcaption class="docsfw-caption" markdown="span">'
            "draw.io のテスト</figcaption>\n"
            "\n"
            "</figure>\n",
        )

    def test_moves_label_to_figure_and_keeps_other_attributes(self):
        result = convert_implicit_figures("![幅つき](images/y.svg){#fig:a width=50%}\n")
        self.assertIn('<figure class="docsfw-figure" id="fig:a" markdown="1">', result)
        self.assertIn("![幅つき](images/y.svg){width=50%}", result)

    def test_keeps_image_without_alternative_text(self):
        source = "![](images/x.svg)\n"
        self.assertEqual(convert_implicit_figures(source), source)

    def test_keeps_image_followed_by_text(self):
        source = "![図](images/x.svg)\nつづきの本文。\n"
        self.assertEqual(convert_implicit_figures(source), source)

    def test_keeps_image_inside_fence(self):
        source = (
            "```md\n"
            "![コード例](images/x.svg)\n"
            "```\n"
        )
        self.assertEqual(convert_implicit_figures(source), source)


if __name__ == "__main__":
    unittest.main()
