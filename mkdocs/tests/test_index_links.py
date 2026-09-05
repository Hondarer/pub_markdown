#!/usr/bin/env python3
"""索引の実ファイル解決と TOC から HTML/docx へのリンク変換を検証する。"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


FILTER_ROOT = Path(__file__).resolve().parents[2] / "bin" / "pandoc-filters"
PANDOC = shutil.which("pandoc")


@unittest.skipUnless(PANDOC, "pandoc is required")
class IndexLinkTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.docs = self.root / "docs"
        self.source = self.write("docs/README.md")
        self.write("extra/README.md")
        self.environment = os.environ.copy()
        self.environment.update({
            "PUB_MARKDOWN_MAIN_MDROOT": str(self.docs),
            "SOURCE_FILE": str(self.source),
            "SUBFOLDER_DOCS_PATHS": "extra|extra|{}".format(self.root / "extra"),
            "MERGE_SUBFOLDER_DOCS": "extra=extra",
            "DOCUMENT_LANG": "ja",
            "DOCUMENT_DETAILS": "false",
            "PUB_MARKDOWN_TOC_OUTPUT_CACHE_DIR": str(self.root / "cache"),
        })
        (self.root / "cache").mkdir()

    def write(self, relative):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# {}\n".format(path.parent.name), encoding="utf-8")
        return path

    def render(self, body, extension="html", toc=False):
        command = [PANDOC, "-f", "markdown", "-t", "html" if extension == "html" else "json"]
        if toc:
            command.append("--lua-filter={}".format(FILTER_ROOT / "insert-toc.lua"))
        command.append("--lua-filter={}".format(FILTER_ROOT / ("link-to-" + extension + ".lua")))
        return subprocess.run(
            command, input=body, text=True, encoding="utf-8", capture_output=True,
            check=True, env=self.environment,
        ).stdout

    def assert_link(self, target, expected):
        for extension in ("html", "docx"):
            with self.subTest(target=target, extension=extension):
                output = self.render("[link]({})\n".format(target), extension)
                destination = expected.replace("{ext}", extension)
                if extension == "html":
                    self.assertIn('<a href="{}">link</a>'.format(destination), output)
                    self.assertNotIn("<code>", output)
                else:
                    document = json.loads(output)
                    inline = document["blocks"][0]["c"][0]
                    self.assertEqual(inline["t"], "Link")
                    self.assertEqual(inline["c"][2][0], destination)

    def test_index_aliases_and_mixed_case_names(self):
        for directory, filename, expected in (
            ("readme", "README.md", "index"),
            ("skill", "SKILL.md", "index"),
            ("mixed", "ReadMe.MD", "index"),
            ("mixed-skill", "Skill.MD", "index"),
            ("actual", "INDEX.MD", "INDEX"),
        ):
            self.write("docs/{}/{}".format(directory, filename))
            self.assert_link(directory + "/index.md", directory + "/" + expected + ".{ext}")

    def test_index_priority_preserves_other_documents(self):
        for filename in ("INDEX.md", "README.md", "SKILL.md"):
            self.write("docs/all/" + filename)
        self.assert_link("all/index.md", "all/INDEX.{ext}")
        self.assert_link("all/README.md", "all/README.{ext}")
        self.assert_link("all/SKILL.md", "all/SKILL.{ext}")
        for filename in ("README.md", "SKILL.md"):
            self.write("docs/pair/" + filename)
        self.assert_link("pair/index.md", "pair/index.{ext}")
        self.assert_link("pair/README.md", "pair/index.{ext}")
        self.assert_link("pair/SKILL.md", "pair/SKILL.{ext}")

    def test_merged_root_and_suffix(self):
        self.assert_link("extra/index.md?from=guide.md#part.md", "extra/index.{ext}?from=guide.md#part.md")
        self.environment["SOURCE_FILE"] = str(self.root / "extra" / "README.md")
        self.assert_link("index.md", "index.{ext}")
        self.assert_link("../index.md", "../index.{ext}")

    def test_real_path_precedes_virtual_path(self):
        self.write("docs/extra/INDEX.md")
        self.assert_link("extra/index.md", "extra/INDEX.{ext}")

    def test_unresolved_and_outside_links_remain_unlinked(self):
        self.write("outside/README.md")
        for target in ("missing/index.md", "extra/missing.md", "../outside/index.md"):
            for extension in ("html", "docx"):
                with self.subTest(target=target, extension=extension):
                    output = self.render("[link]({})\n".format(target), extension)
                    if extension == "html":
                        self.assertNotIn("<a ", output)
                        self.assertIn("<code>{}</code>".format(target), output)
                    else:
                        self.assertNotIn('"t":"Link"', output)
                        self.assertIn('"t":"Code"', output)

    def test_toc_links_survive_both_filters(self):
        self.write("docs/readme/README.md")
        self.write("docs/skill/SKILL.md")
        self.write("docs/actual/index.md")
        for extension in ("html", "docx"):
            with self.subTest(extension=extension):
                output = self.render("\\toc depth=1 exclude-basedir=true\n", extension, toc=True)
                for directory in ("readme", "skill", "actual", "extra"):
                    self.assertIn(directory + "/index." + extension, output)
                self.assertNotIn("<code>", output)
                self.assertNotIn('"t":"Code"', output)


if __name__ == "__main__":
    unittest.main()
