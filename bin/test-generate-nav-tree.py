#!/usr/bin/env python3
"""generate-nav-tree.py の子並びが ``\\toc`` と同じ規則になることの単体テスト。"""

import os
import sys
import tempfile
import unittest

BIN_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BIN_DIR)


def _load_generate_nav_tree():
    """ハイフン付きファイル名のモジュールを読み込む。"""
    import importlib.util

    path = os.path.join(BIN_DIR, "generate-nav-tree.py")
    spec = importlib.util.spec_from_file_location("generate_nav_tree_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


nav = _load_generate_nav_tree()


def child_urls(tree):
    """直下の子を、ファイルはファイル名、フォルダーはディレクトリ名で返す。"""
    names = []
    for child in tree["children"]:
        if "children" in child:
            names.append((child.get("path") or "").rstrip("/").split("/")[-1])
        else:
            names.append(os.path.basename(child["url"]))
    return names


class TocSortNameTest(unittest.TestCase):
    def test_html_files_become_md_source_names(self):
        self.assertEqual(nav.toc_sort_name("guide.html"), "guide.md")
        self.assertEqual(nav.toc_sort_name("GUIDE.HTML"), "GUIDE.md")
        self.assertEqual(nav.toc_sort_name("sample"), "sample")
        self.assertEqual(nav.toc_sort_name("foo.include"), "foo.include")


class BuildTreeOrderTest(unittest.TestCase):
    def setUp(self):
        nav.SRC_ROOT = None
        nav.MERGE_MAP.clear()
        nav._order_cache.clear()

    def tearDown(self):
        nav.SRC_ROOT = None
        nav.MERGE_MAP.clear()
        nav._order_cache.clear()

    def test_mixes_files_and_directories_like_toc(self):
        pages = {
            "index.html": "Root",
            "guide.html": "Guide",
            "rsvg-convert.html": "rsvg",
            "search-and-nav.html": "search",
            "guidelines/index.html": "Guidelines",
            "sample/index.html": "Sample",
        }
        tree = nav.build_tree(pages, prefix="")
        self.assertEqual(
            child_urls(tree),
            ["guide.html", "guidelines", "rsvg-convert.html", "sample", "search-and-nav.html"],
        )

    def test_md_extension_sorts_after_directory_between_html_and_md(self):
        pages = {
            "index.html": "Root",
            "foo.html": "Foo",
            "foo.include/index.html": "Include",
        }
        tree = nav.build_tree(pages, prefix="")
        self.assertEqual(child_urls(tree), ["foo.include", "foo.html"])

    def test_publocal_order_comes_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "publocal.yaml"), "w", encoding="utf-8") as handle:
                handle.write("order:\n  - search-and-nav.md\n  - sample/\n")
            nav.SRC_ROOT = tmp
            pages = {
                "index.html": "Root",
                "guide.html": "Guide",
                "search-and-nav.html": "search",
                "sample/index.html": "Sample",
            }
            tree = nav.build_tree(pages, prefix="")
            self.assertEqual(child_urls(tree), ["search-and-nav.html", "sample", "guide.html"])


if __name__ == "__main__":
    unittest.main()
