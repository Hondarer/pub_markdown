#!/usr/bin/env python3
"""mkdocs プレビューのステージング処理に関する単体テスト。"""

import os
import sys
import tempfile
import unittest

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from stage_preview_docs import (  # noqa: E402
    Document,
    build_front_matter,
    generate_nav_files,
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


if __name__ == "__main__":
    unittest.main()
