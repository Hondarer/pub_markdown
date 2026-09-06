#!/usr/bin/env python3
"""mkdocs による動的発行のステージング処理に関する単体テスト。"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from git_link import PublishFacts  # noqa: E402

from stage_livedocs import (  # noqa: E402
    Document,
    PathMapper,
    StageIndex,
    _norm_key,
    _repo_progress_label,
    build_front_matter,
    convert_captions,
    convert_implicit_figures,
    create_git_resolver,
    generate_nav_files,
    is_auto_set_author_enabled,
    is_auto_set_date_enabled,
    is_git_link_enabled,
    resolve_document_git_link,
    resolve_document_publish_info,
    rewrite_links,
    stage,
    stage_index,
    stage_single,
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

    def test_publish_info_is_added(self):
        document = self._document(staged_rel="guide/usage.md")
        document.publish_author = "first, second et al."
        document.publish_date = "Sat, 06 Sep 2026 12:34:56 +0900 5927f1d"
        self.assertEqual(
            build_front_matter(document, "ja", True),
            '---\nauthor: "first, second et al."\n'
            'date: "Sat, 06 Sep 2026 12:34:56 +0900 5927f1d"\n---',
        )

    def test_publish_info_does_not_overwrite_the_source_front_matter(self):
        # set-meta.lua が文書側のメタデータを上書きしないことにそろえる。
        document = self._document(staged_rel="guide/usage.md")
        document.front_matter = '---\nauthor: "明示著者"\n---'
        document.fields = {"author": "明示著者"}
        document.publish_author = "first"
        document.publish_date = "Sat, 06 Sep 2026 12:34:56 +0900 5927f1d"
        self.assertEqual(
            build_front_matter(document, "ja", True),
            '---\nauthor: "明示著者"\n'
            'date: "Sat, 06 Sep 2026 12:34:56 +0900 5927f1d"\n---',
        )

    def test_empty_publish_info_adds_nothing(self):
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


class GitLinkFrontMatterTest(unittest.TestCase):
    """``git-url`` / ``git-provider`` のフロント マター出力。"""

    def _document(self, staged_rel="guide/usage.md"):
        document = Document("/source/usage.md", "guide/usage.md")
        document.staged_rel = staged_rel
        document.body = "本文だけです。\n"
        return document

    def test_adds_git_url_and_provider(self):
        document = self._document()
        document.git_url = "https://github.com/owner/repo/blob/abc123/docs/usage.md"
        document.git_provider = "github"
        self.assertEqual(
            build_front_matter(document, "ja", True),
            '---\n'
            'git-url: "https://github.com/owner/repo/blob/abc123/docs/usage.md"\n'
            'git-provider: "github"\n'
            '---',
        )

    def test_appends_to_existing_front_matter(self):
        document = self._document()
        document.front_matter = '---\nsummary: "説明"\n---'
        document.fields = {"summary": "説明"}
        document.git_url = "https://github.com/owner/repo/blob/abc123/docs/usage.md"
        document.git_provider = "github"
        self.assertEqual(
            build_front_matter(document, "ja", True),
            '---\n'
            'summary: "説明"\n'
            'git-url: "https://github.com/owner/repo/blob/abc123/docs/usage.md"\n'
            'git-provider: "github"\n'
            '---',
        )

    def test_no_git_url_keeps_front_matter_unchanged(self):
        document = self._document()
        self.assertEqual(build_front_matter(document, "ja", True), "")


class GitLinkResolutionTest(unittest.TestCase):
    """``gitLinkEnable`` の判定と ``git-origin`` による解決対象の差し替え。"""

    class _FakeResolver:
        def __init__(self):
            self.targets = []

        def resolve(self, path):
            self.targets.append(path)
            return "https://example.test/blob/abc/x", "git"

    class _FakePublishResolver:
        """``resolve_publish_facts`` の呼び出し先を記録するだけの差し替え。"""

        def __init__(self):
            self.targets = []

        def resolve_publish_facts(self, path):
            self.targets.append(path)
            return PublishFacts(
                tracked=True, dirty=False, authors=["first"],
                committer_date="Sat, 06 Sep 2026 12:34:56 +0900", short_sha="5927f1d",
            )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_git_link_enabled_defaults_to_true(self):
        self.assertTrue(is_git_link_enabled({}))
        self.assertTrue(is_git_link_enabled({"gitLinkEnable": "true"}))
        self.assertFalse(is_git_link_enabled({"gitLinkEnable": "false"}))

    def test_auto_set_flags_default_to_true(self):
        self.assertTrue(is_auto_set_author_enabled({}))
        self.assertFalse(is_auto_set_author_enabled({"autoSetAuthor": "false"}))
        self.assertTrue(is_auto_set_date_enabled({}))
        self.assertFalse(is_auto_set_date_enabled({"autoSetDate": "false"}))

    def test_resolver_is_created_while_any_feature_needs_git(self):
        config_path = os.path.join(self.workspace, "pub_markdown.config.yaml")
        self.assertIsNotNone(create_git_resolver({}, config_path))
        # 単一ページ リンクだけを止めても、発行者と発行日時のために resolver は要る。
        self.assertIsNotNone(
            create_git_resolver({"gitLinkEnable": "false"}, config_path)
        )
        self.assertIsNone(create_git_resolver({
            "gitLinkEnable": "false",
            "autoSetAuthor": "false",
            "autoSetDate": "false",
        }, config_path))

    def test_disabled_git_link_clears_git_fields(self):
        document = Document(os.path.join(self.workspace, "a.md"), "a.md")
        document.git_url = "https://example.test/stale"
        resolve_document_git_link(
            document, self.workspace, self._FakeResolver(), enabled=False
        )
        self.assertEqual(document.git_url, "")
        self.assertEqual(document.git_provider, "")

    def test_disabled_resolver_clears_git_fields(self):
        document = Document(os.path.join(self.workspace, "a.md"), "a.md")
        document.git_url = "https://example.test/stale"
        resolve_document_git_link(document, self.workspace, None)
        self.assertEqual(document.git_url, "")
        self.assertEqual(document.git_provider, "")

    def test_git_origin_replaces_the_resolution_target(self):
        origin = os.path.join(self.workspace, "prod", "include", "calc.h")
        os.makedirs(os.path.dirname(origin))
        with open(origin, "w", encoding="utf-8") as handle:
            handle.write("/* calc */\n")

        document = Document(os.path.join(self.workspace, "docs", "Files", "calc.h.md"),
                            "calc/Files/calc.h.md")
        for hint in ("prod/include/calc.h", "prod\\include\\calc.h"):
            with self.subTest(hint=hint):
                document.fields = {"git-origin": hint}
                resolver = self._FakeResolver()
                resolve_document_git_link(document, self.workspace, resolver)
                self.assertEqual(resolver.targets, [origin])

    def test_missing_git_origin_falls_back_to_the_document_itself(self):
        document = Document(os.path.join(self.workspace, "docs", "a.md"), "a.md")
        document.fields = {"git-origin": "prod/include/missing.h"}
        resolver = self._FakeResolver()
        resolve_document_git_link(document, self.workspace, resolver)
        self.assertEqual(resolver.targets, [document.real_path])

    def test_publish_info_ignores_git_origin(self):
        # 静的発行は get_file_author.sh / get_file_date.sh へ発行対象の md を
        # そのまま渡すため、git-origin による差し替えは行わない。
        origin = os.path.join(self.workspace, "prod", "include", "calc.h")
        os.makedirs(os.path.dirname(origin))
        with open(origin, "w", encoding="utf-8") as handle:
            handle.write("/* calc */\n")

        document = Document(os.path.join(self.workspace, "docs", "Files", "calc.h.md"),
                            "calc/Files/calc.h.md")
        document.fields = {"git-origin": "prod/include/calc.h"}
        resolver = self._FakePublishResolver()
        resolve_document_publish_info(document, resolver)
        self.assertEqual(resolver.targets, [document.real_path])

    def test_publish_info_is_cleared_without_resolver(self):
        document = Document(os.path.join(self.workspace, "a.md"), "a.md")
        document.publish_author = "stale"
        document.publish_date = "stale"
        resolve_document_publish_info(document, None)
        self.assertEqual(document.publish_author, "")
        self.assertEqual(document.publish_date, "")

    def test_disabled_flags_clear_each_side(self):
        document = Document(os.path.join(self.workspace, "a.md"), "a.md")
        resolver = self._FakePublishResolver()
        resolve_document_publish_info(document, resolver, auto_author=False)
        self.assertEqual(document.publish_author, "")
        self.assertTrue(document.publish_date)

        resolve_document_publish_info(document, resolver, auto_date=False)
        self.assertTrue(document.publish_author)
        self.assertEqual(document.publish_date, "")


ROOT_NAV_YAML = """use_index_title: true
sort:
  by: filename
  direction: asc
  type: alphabetical
  ignore_case: true
  sections: mixed
"""


class GenerateNavFilesTest(unittest.TestCase):
    def test_root_enables_index_titles_without_publocal(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source")
            output = os.path.join(tmp, "output")
            os.makedirs(source)

            generated = generate_nav_files(output, source, [], ["guide"])

            self.assertEqual(generated, 2)
            with open(os.path.join(output, ".nav.yml"), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), ROOT_NAV_YAML)

    def test_directory_names_preserved_and_index_title_restored(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source")
            output = os.path.join(tmp, "output")
            os.makedirs(source)
            names = ["cmd", "include", "libsrc", "MixedCase", "my-dir", "my_dir", "a'b"]
            if os.name != "nt":
                names.append('a"b')
            generate_nav_files(output, source, [], names)
            for name in names:
                with open(os.path.join(output, name, ".nav.yml"), encoding="utf-8") as handle:
                    self.assertEqual(json.loads(handle.read().split(": ", 1)[1]), name)
            with open(os.path.join(output, "cmd", "index.md"), "w", encoding="utf-8") as handle:
                handle.write('---\ntitle: "Commands"\n---\n')
            generate_nav_files(output, source, [], names)
            with open(os.path.join(output, "cmd", ".nav.yml"), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "use_index_title: true\n")
            self.assertEqual(generate_nav_files(output, source, [], names), 0)

    def test_intermediate_directory_configs_survive_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            container = SimpleNamespace(main_mdroot=tmp, subfolders=[], kept=[], assets=[])
            with patch("stage_livedocs.write_documents", return_value=(0, {"src/cmd/tool/page.md"})):
                stage_index(container, tmp, quiet=True)
            for name in ("src", "src/cmd", "src/cmd/tool"):
                with open(os.path.join(tmp, name, ".nav.yml"), encoding="utf-8") as handle:
                    self.assertEqual(json.loads(handle.read().split(": ", 1)[1]), name.split("/")[-1])

    def test_single_index_update_refreshes_directory_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "source.md")
            output = os.path.join(tmp, "output")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write("# Commands\n")
            document = Document(source, "cmd/index.md")
            document.staged_rel = "cmd/index.md"
            container = SimpleNamespace(
                by_real_path={_norm_key(source): document},
                lang="ja", details=True, workspace=tmp, git_resolver=None,
                git_link_enabled=True, auto_set_author=True, auto_set_date=True,
                main_mdroot=tmp, subfolders=[],
            )
            generate_nav_files(output, tmp, [], ["cmd"])
            with patch("stage_livedocs.resolve_document_git_link"), patch(
                "stage_livedocs._render_document", return_value='---\ntitle: "Commands"\n---\n'
            ):
                result = stage_single(container, output, source)
            self.assertTrue(result.updated)
            with open(os.path.join(output, "cmd", ".nav.yml"), encoding="utf-8") as handle:
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
                    ROOT_NAV_YAML + "nav:\n  - index.md\n  - guide\n  - ...\n",
                )


class StageIndexMergeRootsTest(unittest.TestCase):
    def test_merge_roots_matches_subfolder_aliases(self):
        subfolders = [
            ("general", "/workspace/app/general/docs"),
            ("c-platform", "/workspace/app/c-platform/docs"),
        ]
        container = StageIndex(
            workspace="/workspace",
            config_path="/workspace/.vscode/pub_markdown.config.yaml",
            main_mdroot="/workspace/docs",
            subfolders=subfolders,
            mapper=None,
            kept=[],
            assets=[],
            index=None,
            real_to_staged={},
            by_real_path={},
            lang="ja",
            details=True,
            variant="ja",
        )
        self.assertEqual(container.merge_roots, frozenset({"general", "c-platform"}))

    def test_merge_roots_is_empty_without_subfolders(self):
        container = StageIndex(
            workspace="/workspace",
            config_path="/workspace/.vscode/pub_markdown.config.yaml",
            main_mdroot="/workspace/docs",
            subfolders=[],
            mapper=None,
            kept=[],
            assets=[],
            index=None,
            real_to_staged={},
            by_real_path={},
            lang="ja",
            details=True,
            variant="ja",
        )
        self.assertEqual(container.merge_roots, frozenset())


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


class StageProgressTest(unittest.TestCase):
    """フル ステージングの進捗行。``quiet`` では出さない。"""

    def _workspace(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        workspace = tmp.name
        docs = os.path.join(workspace, "docs")
        os.makedirs(docs)
        with open(os.path.join(docs, "page.md"), "w", encoding="utf-8") as handle:
            handle.write("# Page\n")
        with open(os.path.join(docs, "skip.md"), "w", encoding="utf-8") as handle:
            handle.write("---\npub_markdown.skip: true\n---\n# Skip\n")
        vscode = os.path.join(workspace, ".vscode")
        os.makedirs(vscode)
        with open(os.path.join(vscode, "pub_markdown.config.yaml"), "w", encoding="utf-8") as handle:
            handle.write(
                "mdRoot: docs\n"
                "gitLinkEnable: false\n"
                "autoSetAuthor: false\n"
                "autoSetDate: false\n"
            )
        out_dir = os.path.join(workspace, "pages", "livedocs", "src")
        os.makedirs(out_dir)
        config_path = os.path.join(vscode, "pub_markdown.config.yaml")
        return workspace, out_dir, config_path

    def test_quiet_prints_nothing(self):
        workspace, out_dir, config_path = self._workspace()
        captured = io.StringIO()
        with redirect_stdout(captured):
            stage(workspace, out_dir, config_path, quiet=True)
        self.assertEqual(captured.getvalue(), "")

    def test_progress_lines_before_completion(self):
        workspace, out_dir, config_path = self._workspace()
        captured = io.StringIO()
        with redirect_stdout(captured):
            stage(workspace, out_dir, config_path, quiet=False)
        lines = [line for line in captured.getvalue().splitlines()
                 if not line.startswith("Warning:")]
        self.assertEqual(lines[0], "staging: variant ja-details")
        self.assertEqual(lines[1], "staging: collected 2 documents, 0 assets")
        self.assertEqual(lines[2], "staging: writing")
        self.assertTrue(
            lines[3].startswith("staged: variant ja-details, 1 documents, 0 assets,")
        )
        self.assertEqual(len(lines), 4)

    def test_repo_progress_label_uses_workspace_relative_path(self):
        workspace = os.path.join("repo", "root")
        self.assertEqual(_repo_progress_label(workspace, workspace), ".")
        self.assertEqual(
            _repo_progress_label(workspace, os.path.join(workspace, "framework", "docsfw")),
            "framework/docsfw",
        )


if __name__ == "__main__":
    unittest.main()
