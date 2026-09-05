#!/usr/bin/env python3
"""docsfw の HTML/docx リンク フィルターの回帰テスト。"""

import os
import shutil
import subprocess
import unittest


MKDOCS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCSFW_ROOT = os.path.abspath(os.path.join(MKDOCS_ROOT, ".."))
WORKSPACE_ROOT = os.path.abspath(os.path.join(DOCSFW_ROOT, "..", ".."))
FILTER_ROOT = os.path.join(DOCSFW_ROOT, "bin", "pandoc-filters")
PANDOC = shutil.which("pandoc")


@unittest.skipUnless(PANDOC, "pandoc is required")
class LinkFilterTest(unittest.TestCase):
    def setUp(self):
        self.environment = os.environ.copy()
        self.environment.update(
            {
                "PUB_MARKDOWN_MAIN_MDROOT": os.path.join(WORKSPACE_ROOT, "docs"),
                "SUBFOLDER_DOCS_PATHS": "\n".join(
                    [
                        "c-modernization-kit|app/c-modernization-kit/docs|{}".format(
                            os.path.join(WORKSPACE_ROOT, "app", "c-modernization-kit", "docs")
                        ),
                        "general|app/general/docs|{}".format(
                            os.path.join(WORKSPACE_ROOT, "app", "general", "docs")
                        ),
                    ]
                ),
            }
        )

    def _run(self, filter_name, source_file, body, output_format):
        environment = self.environment.copy()
        environment["SOURCE_FILE"] = source_file
        result = subprocess.run(
            [
                PANDOC,
                "-f",
                "markdown",
                "-t",
                output_format,
                "--lua-filter={}".format(os.path.join(FILTER_ROOT, filter_name)),
            ],
            input=body,
            text=True,
            capture_output=True,
            check=True,
            env=environment,
        )
        return result.stdout

    def test_html_filter_rewrites_resolved_link_and_unlinks_external_reference(self):
        source_file = os.path.join(
            WORKSPACE_ROOT, "app", "c-modernization-kit", "docs", "github-actions.md"
        )
        html = self._run(
            "link-to-html.lua",
            source_file,
            "[規範](../../general/docs/vscode-variables.md)\n"
            "[ルート README](../../../README.md)\n",
            "html",
        )

        self.assertIn(
            '<a href="../general/vscode-variables.html">規範</a>',
            html,
        )
        self.assertIn("ルート README", html)
        self.assertIn("<code>../../../README.md</code>", html)
        self.assertNotIn('href="../../../README.md"', html)

    def test_readme_link_uses_logical_index_path(self):
        source_file = os.path.join(
            WORKSPACE_ROOT, "app", "c-modernization-kit", "docs", "github-actions.md"
        )
        html = self._run(
            "link-to-html.lua",
            source_file,
            "[共通文書](../../general/docs/README.md)\n",
            "html",
        )

        self.assertIn(
            '<a href="../general/index.html">共通文書</a>',
            html,
        )

    def test_docx_filter_uses_docx_target_and_unlinks_external_reference(self):
        source_file = os.path.join(
            WORKSPACE_ROOT, "app", "c-modernization-kit", "docs", "github-actions.md"
        )
        native = self._run(
            "link-to-docx.lua",
            source_file,
            "[規範](../../general/docs/vscode-variables.md)\n"
            "[サンプル](file_copy_sample.c)\n",
            "native",
        )

        self.assertIn("../general/vscode-variables.docx", native)
        self.assertIn('Code ( "" , [] , [] ) "file_copy_sample.c"', native)
        self.assertIn("Link", native)

        external_native = self._run(
            "link-to-docx.lua",
            source_file,
            "[サンプル](file_copy_sample.c)\n",
            "native",
        )
        self.assertNotIn("Link", external_native)

    def test_doxygen_relative_link_is_preserved(self):
        source_file = os.path.join(DOCSFW_ROOT, "docs", "README.md")
        html = self._run(
            "link-to-html.lua",
            source_file,
            "[Doxygen](../../../doxygen/example/index.html)\n",
            "html",
        )

        self.assertIn(
            '<a href="../../../doxygen/example/index.html">Doxygen</a>',
            html,
        )


if __name__ == "__main__":
    unittest.main()
