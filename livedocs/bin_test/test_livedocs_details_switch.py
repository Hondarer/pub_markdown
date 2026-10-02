#!/usr/bin/env python3
"""通常版と詳細版の同時配信と、ヘッダーの切り替え。"""

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
THEME_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "theme"))
sys.path.insert(0, BIN_DIR)

# 取り込み元の mkdocs-material のバージョンと、そのときの partials/nav.html。
# 上流が変わったら、差分を確認して theme/partials/nav.html へ取り込み直し、
# ここの値を更新する。
UPSTREAM_MATERIAL_VERSION = "9.7.7"
UPSTREAM_NAV_SHA256 = "af33f6e032f632eb055c365eb5f1a975bf8456152fa768e69a1aad6d470b843f"

OVERRIDE_NAV = os.path.join(THEME_DIR, "partials", "nav.html")


def _find_upstream_nav():
    """インストール済み mkdocs-material の ``partials/nav.html`` を探す。"""
    for entry in sys.path:
        candidate = os.path.join(entry, "material", "templates", "partials", "nav.html")
        if os.path.isfile(candidate):
            return candidate
    return None


class UpstreamNavTest(unittest.TestCase):
    def test_pinned_version_matches_requirements(self):
        requirements = os.path.join(os.path.dirname(THEME_DIR), "requirements.txt")
        with open(requirements, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("mkdocs-material=={}".format(UPSTREAM_MATERIAL_VERSION), text)

    def test_upstream_nav_is_unchanged(self):
        upstream = _find_upstream_nav()
        if upstream is None:
            self.skipTest("mkdocs-material が同じ環境に無いため上流を確認できません")
        with open(upstream, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        self.assertEqual(
            digest,
            UPSTREAM_NAV_SHA256,
            "mkdocs-material の partials/nav.html が変わりました。"
            " theme/partials/nav.html へ差分を取り込み直し、"
            " このテストの UPSTREAM_NAV_SHA256 を更新してください。",
        )

    def test_override_keeps_the_upstream_frame(self):
        with open(OVERRIDE_NAV, "r", encoding="utf-8") as handle:
            text = handle.read()
        for marker in (
            "md-nav--primary",
            '{% include "partials/logo.html" %}',
            "data-md-scrollfix",
            "config.repo_url",
            "variant_nav.section.children",
        ):
            self.assertIn(marker, text)


class HeaderSwitchRenderTest(unittest.TestCase):
    def _render(self, url, language):
        try:
            from jinja2 import Environment, FileSystemLoader
        except ImportError:
            self.skipTest("jinja2 が同じ環境に無いためテンプレートを描画できません")
        env = Environment(loader=FileSystemLoader(THEME_DIR))
        env.filters["url"] = lambda value: "/" + str(value).lstrip("/")

        def d_filter(value, default=None, boolean=False):
            del boolean
            if value:
                return value
            return default

        env.filters["d"] = d_filter
        template = env.get_template("partials/docsfw-header-links.html")
        return template.render(
            config=SimpleNamespace(
                theme={"language": language},
                extra={
                    "livedocs_variants": ["ja-details", "ja"],
                    "livedocs_variant": "ja-details",
                },
            ),
            page=SimpleNamespace(url=url, meta={}),
            doxygen_livedocs_url=None,
        )

    def test_details_page_links_to_the_overview(self):
        html = self._render("ja-details/guide/setup/", "ja")
        self.assertIn('href="/ja/guide/setup/"', html)
        self.assertIn("概要版を表示", html)
        self.assertIn("docsfw-overview-icon.svg", html)
        self.assertNotIn("詳細版を表示", html)

    def test_overview_page_links_to_the_details(self):
        html = self._render("ja/guide/setup/", "en")
        self.assertIn('href="/ja-details/guide/setup/"', html)
        self.assertIn("Show detailed version", html)
        self.assertIn("docsfw-details-icon.svg", html)


class LandingIndexTest(unittest.TestCase):
    def test_writes_a_redirect_and_does_not_replace_a_real_index(self):
        try:
            from livedocs_versioned_hook import landing_index_html, write_landing_index
        except ImportError:
            self.skipTest("mkdocs が同じ環境に無いため転送ページを確認できません")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(write_landing_index(tmp, "ja-details", "ja", "Kit (ja-details)"))
            with open(os.path.join(tmp, "index.html"), encoding="utf-8") as handle:
                text = handle.read()
            self.assertEqual(text, landing_index_html("ja-details", "ja", "Kit (ja-details)"))
            self.assertIn('url=ja-details/', text)
            self.assertIn("location.replace", text)
            self.assertFalse(write_landing_index(tmp, "ja", "ja", "other"))
            with open(os.path.join(tmp, "index.html"), encoding="utf-8") as handle:
                self.assertIn("Kit (ja-details)", handle.read())


class BuiltSiteSwitchTest(unittest.TestCase):
    def test_pages_link_to_the_counterpart_and_hide_its_nav(self):
        try:
            import mkdocs  # noqa: F401
            import mkdocs_awesome_nav  # noqa: F401
        except ImportError:
            self.skipTest("mkdocs が同じ環境に無いためサイトをビルドできません")

        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src")
            for variant, marker in (("ja-details", "詳細トップ"), ("ja", "概要トップ")):
                os.makedirs(os.path.join(src, variant))
                with open(os.path.join(src, variant, "index.md"), "w", encoding="utf-8") as handle:
                    handle.write("---\ntitle: {}\n---\n# {}\n".format(marker, marker))
                with open(os.path.join(src, variant, "guide.md"), "w", encoding="utf-8") as handle:
                    handle.write("---\ntitle: 手順\n---\n# 手順\n{}\n".format(marker))
            with open(os.path.join(src, ".nav.yml"), "w", encoding="utf-8") as handle:
                handle.write("nav:\n  - ja-details\n  - ja\n")
            hook = os.path.join(BIN_DIR, "livedocs_versioned_hook.py")
            with open(os.path.join(tmp, "mkdocs.yml"), "w", encoding="utf-8") as handle:
                handle.write(
                    "site_name: Fixture\n"
                    "docs_dir: src\n"
                    "site_dir: site\n"
                    "use_directory_urls: true\n"
                    "theme:\n"
                    "  name: material\n"
                    "  custom_dir: \"{theme}\"\n"
                    "  language: ja\n"
                    "  font: false\n"
                    "  features:\n"
                    "    - navigation.indexes\n"
                    "validation:\n"
                    "  nav:\n"
                    "    omitted_files: ignore\n"
                    "plugins:\n"
                    "  - search\n"
                    "  - awesome-nav\n"
                    "extra:\n"
                    "  livedocs_site_name: Fixture\n"
                    "  livedocs_variant: ja-details\n"
                    "  livedocs_variants: [ja-details, ja]\n"
                    "hooks:\n"
                    "  - \"{hook}\"\n".format(theme=THEME_DIR.replace(os.sep, "/"), hook=hook.replace(os.sep, "/"))
                )
            completed = subprocess.run(
                [sys.executable, "-m", "mkdocs", "build", "--strict"],
                cwd=tmp,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                timeout=90,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + "\n" + completed.stderr,
            )
            with open(
                os.path.join(tmp, "site", "ja-details", "guide", "index.html"),
                encoding="utf-8",
            ) as handle:
                details = handle.read()
            with open(
                os.path.join(tmp, "site", "ja", "guide", "index.html"),
                encoding="utf-8",
            ) as handle:
                overview = handle.read()
            with open(os.path.join(tmp, "site", "index.html"), encoding="utf-8") as handle:
                landing = handle.read()

        self.assertIn("概要版を表示", details)
        self.assertIn("ja/guide/", details)
        self.assertIn("Fixture (ja-details)", details)
        self.assertNotIn("概要トップ", details)
        self.assertIn("詳細版を表示", overview)
        self.assertIn("ja-details/guide/", overview)
        self.assertIn("Fixture (ja)", overview)
        self.assertNotIn("詳細トップ", overview)
        self.assertIn("url=ja-details/", landing)


if __name__ == "__main__":
    unittest.main()
