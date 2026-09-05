#!/usr/bin/env python3
"""mkdocs による動的発行の設定生成に関する単体テスト。"""

import os
import sys
import tempfile
import unittest

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from vendor_assets import resolve_site_name  # noqa: E402


class ResolveSiteNameTest(unittest.TestCase):
    def _workspace(self, root, config_body=None):
        """``<root>/c-modernization-kit`` を作り、必要なら設定ファイルを置く。"""
        workspace = os.path.join(root, "c-modernization-kit")
        config_path = os.path.join(workspace, ".vscode", "pub_markdown.config.yaml")
        os.makedirs(os.path.dirname(config_path))
        if config_body is not None:
            with open(config_path, "w", encoding="utf-8") as handle:
                handle.write(config_body)
        return workspace, config_path

    def test_uses_site_name_from_config(self):
        with tempfile.TemporaryDirectory() as root:
            workspace, config_path = self._workspace(
                root, "mdRoot: docs\nsiteName: my-workspace\n"
            )
            self.assertEqual(resolve_site_name(workspace, config_path), "my-workspace")

    def test_falls_back_to_workspace_folder_name(self):
        with tempfile.TemporaryDirectory() as root:
            workspace, config_path = self._workspace(root, "mdRoot: docs\n")
            self.assertEqual(
                resolve_site_name(workspace, config_path), "c-modernization-kit"
            )

    def test_falls_back_when_config_is_missing(self):
        with tempfile.TemporaryDirectory() as root:
            workspace, config_path = self._workspace(root)
            self.assertEqual(
                resolve_site_name(workspace, config_path), "c-modernization-kit"
            )

    def test_falls_back_when_site_name_is_empty(self):
        with tempfile.TemporaryDirectory() as root:
            workspace, config_path = self._workspace(root, "siteName:\n")
            self.assertEqual(
                resolve_site_name(workspace, config_path), "c-modernization-kit"
            )

    def test_ignores_trailing_slash_on_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            workspace, config_path = self._workspace(root, "mdRoot: docs\n")
            self.assertEqual(
                resolve_site_name(workspace + os.sep, config_path),
                "c-modernization-kit",
            )


if __name__ == "__main__":
    unittest.main()
