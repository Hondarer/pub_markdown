#!/usr/bin/env python3
"""mkdocs による動的発行の設定生成に関する単体テスト。"""

import os
import sys
import tempfile
import unittest

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from vendor_assets import (  # noqa: E402
    HEADER_ICONS,
    MKDOCS_DIR,
    STYLES_HTML_DIR,
    generate_mkdocs_yml,
    resolve_hooks_dir,
    resolve_site_name,
    vendor_header_icons,
    vendor_theme,
    vendor_own_assets,
)
from stage_livedocs import VENDORED_FILES  # noqa: E402


class ResolveSiteNameTest(unittest.TestCase):
    def _workspace(self, root, config_body=None):
        """``<root>/sample-workspace`` を作り、必要なら設定ファイルを置く。"""
        workspace = os.path.join(root, "sample-workspace")
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
                resolve_site_name(workspace, config_path), "sample-workspace"
            )

    def test_falls_back_when_config_is_missing(self):
        with tempfile.TemporaryDirectory() as root:
            workspace, config_path = self._workspace(root)
            self.assertEqual(
                resolve_site_name(workspace, config_path), "sample-workspace"
            )

    def test_falls_back_when_site_name_is_empty(self):
        with tempfile.TemporaryDirectory() as root:
            workspace, config_path = self._workspace(root, "siteName:\n")
            self.assertEqual(
                resolve_site_name(workspace, config_path), "sample-workspace"
            )

    def test_ignores_trailing_slash_on_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            workspace, config_path = self._workspace(root, "mdRoot: docs\n")
            self.assertEqual(
                resolve_site_name(workspace + os.sep, config_path),
                "sample-workspace",
            )


class HooksDirTest(unittest.TestCase):
    """``hooks:`` のパスが docsfw の実際の配置から求まることを確認する。"""

    HOOK_NAMES = (
        "livedocs_doxygen_hook.py",
        "livedocs_versioned_hook.py",
        "livedocs_autostage_hook.py",
    )

    def _hooks_in(self, livedocs_dir):
        """生成した ``mkdocs.yml`` の ``hooks:`` に並ぶパスを返す。"""
        generate_mkdocs_yml(livedocs_dir, False)
        with open(os.path.join(livedocs_dir, "mkdocs.yml"), "r", encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        start = lines.index("hooks:")
        return [line.strip().lstrip("- ") for line in lines[start + 1:] if line.startswith("  - ")]

    def test_points_at_the_real_bin_directory(self):
        with tempfile.TemporaryDirectory() as root:
            livedocs_dir = os.path.join(root, "pages", "livedocs")
            os.makedirs(livedocs_dir)
            hooks_ref = resolve_hooks_dir(livedocs_dir)
            self.assertEqual(
                os.path.normpath(os.path.join(livedocs_dir, hooks_ref)),
                os.path.join(MKDOCS_DIR, "bin"),
            )

    def test_uses_forward_slashes(self):
        with tempfile.TemporaryDirectory() as root:
            livedocs_dir = os.path.join(root, "pages", "livedocs")
            os.makedirs(livedocs_dir)
            self.assertNotIn("\\", resolve_hooks_dir(livedocs_dir))

    def test_generated_hooks_exist_for_the_default_layout(self):
        with tempfile.TemporaryDirectory() as root:
            livedocs_dir = os.path.join(root, "pages", "livedocs")
            os.makedirs(livedocs_dir)
            hooks = self._hooks_in(livedocs_dir)
            self.assertEqual(len(hooks), len(self.HOOK_NAMES))
            for hook, name in zip(hooks, self.HOOK_NAMES):
                self.assertTrue(hook.endswith(name), hook)
                self.assertTrue(os.path.isfile(os.path.join(livedocs_dir, hook)), hook)

    def test_generated_hooks_exist_for_a_relocated_livedocs_dir(self):
        """``--livedocsDir`` が既定の 2 階層下でなくても実ファイルを指す。"""
        with tempfile.TemporaryDirectory() as root:
            livedocs_dir = os.path.join(root, "elsewhere")
            os.makedirs(livedocs_dir)
            for hook in self._hooks_in(livedocs_dir):
                self.assertTrue(os.path.isfile(os.path.join(livedocs_dir, hook)), hook)


class HeaderIconsTest(unittest.TestCase):
    """ヘッダーの単一ページ リンクで使うアイコンの配置。"""

    def test_all_icons_exist_in_docsfw_styles(self):
        for name in HEADER_ICONS:
            self.assertTrue(
                os.path.isfile(os.path.join(STYLES_HTML_DIR, name)),
                "{} が styles/html にありません".format(name),
            )

    def test_copies_every_icon(self):
        with tempfile.TemporaryDirectory() as root:
            assets_dir = os.path.join(root, "assets")
            self.assertEqual(vendor_header_icons(assets_dir), len(HEADER_ICONS))
            for name in HEADER_ICONS:
                self.assertTrue(os.path.isfile(os.path.join(assets_dir, name)), name)
            # 2 回目は内容が同じため何もコピーしない。
            self.assertEqual(vendor_header_icons(assets_dir), 0)

    def test_icons_are_kept_by_the_staging_cleanup(self):
        """``remove_stale`` が消さないように ``VENDORED_FILES`` にあること。"""
        for name in HEADER_ICONS:
            self.assertIn("assets/{}".format(name), VENDORED_FILES)


class VendorThemeTest(unittest.TestCase):
    """テーマ上書きのコピーと、正本から消えた上書きの掃除。"""

    def test_copies_the_override_partials(self):
        with tempfile.TemporaryDirectory() as root:
            livedocs_dir = os.path.join(root, "pages", "livedocs")
            vendor_theme(livedocs_dir)
            for name in ("header.html", "docsfw-header-links.html",
                         "docsfw-header-meta.html"):
                self.assertTrue(
                    os.path.isfile(os.path.join(livedocs_dir, "theme", "partials", name)),
                    name,
                )

    def test_removes_overrides_that_are_gone_from_the_source(self):
        with tempfile.TemporaryDirectory() as root:
            livedocs_dir = os.path.join(root, "pages", "livedocs")
            partials = os.path.join(livedocs_dir, "theme", "partials")
            os.makedirs(partials)
            stale = os.path.join(partials, "actions.html")
            with open(stale, "w", encoding="utf-8") as handle:
                handle.write("{# 過去の上書き #}\n")

            vendor_theme(livedocs_dir)
            self.assertFalse(os.path.exists(stale))
            self.assertTrue(os.path.isfile(os.path.join(partials, "header.html")))

    def test_header_meta_css_is_copied_registered_and_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            assets = os.path.join(root, "assets")
            vendor_own_assets(assets)
            generate_mkdocs_yml(root, False)
            with open(os.path.join(root, "mkdocs.yml"), encoding="utf-8") as handle:
                config = handle.read()
            name = "docsfw-header-meta.css"
            self.assertTrue(os.path.isfile(os.path.join(assets, name)))
            self.assertIn("assets/" + name, config)
            self.assertIn("assets/" + name, VENDORED_FILES)

    def test_collapsible_assets_are_copied_registered_and_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            assets = os.path.join(root, 'assets')
            vendor_own_assets(assets)
            generate_mkdocs_yml(root, False)
            with open(os.path.join(root, 'mkdocs.yml'), encoding='utf-8') as handle:
                config = handle.read()
            for extension in ('js', 'css'):
                name = 'docsfw-collapsible-list.' + extension
                self.assertTrue(os.path.isfile(os.path.join(assets, name)))
                self.assertIn('assets/' + name, config)
                self.assertIn('assets/' + name, VENDORED_FILES)


if __name__ == "__main__":
    unittest.main()
