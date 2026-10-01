#!/usr/bin/env python3
"""進捗の定期表示、生成完了、失敗時のスレッド停止を確認する。"""

import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from mkdocs.commands.build import build
from mkdocs.config import load_config

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from livedocs_progress import ProgressReporter  # noqa: E402


class ProgressReporterTest(unittest.TestCase):
    def test_default_waits_ten_seconds_between_reports(self):
        reporter = ProgressReporter(mock.Mock(), "Preparing")
        with mock.patch.object(reporter._stop, "wait", side_effect=[False, True]) as wait:
            reporter._run()
        self.assertEqual(wait.call_args_list, [mock.call(10.0), mock.call(10.0)])
        reporter._emit.assert_called_once_with("Preparing")

    def test_reports_while_a_single_file_is_still_processing(self):
        messages = []
        emitted = threading.Event()

        def emit(message):
            messages.append(message)
            if message == "Rendering Markdown 0/2 pages":
                emitted.set()

        reporter = ProgressReporter(emit, "Rendering Markdown", interval=0.01)
        with reporter:
            reporter.set_phase("Rendering Markdown", 2, unit="pages")
            self.assertTrue(emitted.wait(1.0))
            self.assertEqual("Rendering Markdown 0/2 pages", messages[-1])
            reporter.advance()
            reporter.report()
            self.assertEqual("Rendering Markdown 1/2 pages", messages[-1])
            self.assertNotIn("slow.md", messages[-1])
        self.assertIsNone(reporter._thread)

    def test_unknown_total_reports_actual_count_without_paths(self):
        messages = []
        with ProgressReporter(messages.append, "Building navigation") as reporter:
            reporter.set_phase("Building navigation", unit="folders visited", count=True)
            reporter.advance()
            reporter.advance()
            reporter.report()
            self.assertEqual("Building navigation 2 folders visited", messages[-1])
            reporter.set_phase("Rendering HTML", 3, unit="pages")
            reporter.advance()
            reporter.report()
            self.assertEqual("Rendering HTML 1/3 pages", messages[-1])

    def test_quiet_does_not_emit_or_start_a_thread(self):
        emit = mock.Mock()
        with ProgressReporter(emit, "Preparing", enabled=False) as reporter:
            reporter.set_phase("Rendering", 1)
            reporter.advance()
            reporter.report()
        emit.assert_not_called()
        self.assertIsNone(reporter._thread)

    def test_exception_stops_the_thread(self):
        reporter = ProgressReporter(mock.Mock(), "Preparing", interval=0.01)
        with self.assertRaisesRegex(ValueError, "failed"):
            with reporter:
                worker = reporter._thread
                raise ValueError("failed")
        self.assertFalse(worker.is_alive())
        reporter.close()


class MkDocsProgressTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        docs = root / "docs"
        docs.mkdir()
        (docs / "index.md").write_text("# Home\n", encoding="utf-8")
        (docs / "other.md").write_text("# Other\n", encoding="utf-8")
        (docs / "draft.md").write_text("# Draft\n", encoding="utf-8")
        hook = Path(BIN_DIR, "livedocs_progress_hook.py").as_posix()
        config_file = root / "mkdocs.yml"
        config_file.write_text(
            "site_name: Progress test\nplugins: []\ndraft_docs: draft.md\n"
            "hooks:\n  - " + hook + "\n",
            encoding="utf-8",
        )
        self.config = load_config(config_file=str(config_file))
        self.progress_start = self.config.plugins.events["pre_build"][0]
        self.addCleanup(self.config.plugins.on_shutdown)

    def test_build_and_rebuild_reset_counts_and_stop_reporting(self):
        self.config.plugins.on_startup(command="build", dirty=False)
        with self.assertLogs("mkdocs.livedocs_progress", level="INFO") as captured:
            build(self.config)
            self.assertIsNone(self.progress_start.__globals__["_progress"])
            build(self.config)
        lines = "\n".join(captured.output)
        self.assertEqual(2, lines.count("Rendering Markdown 2/2 pages"))
        self.assertEqual(2, lines.count("Rendering HTML 2/2 pages"))
        self.assertNotIn("経過", lines)
        self.assertIsNone(self.progress_start.__globals__["_progress"])

    def test_navigation_counts_folders_and_restores_instrumented_methods(self):
        from mkdocs.structure.files import File
        from mkdocs.structure.pages import Page
        from mkdocs_awesome_nav.nav.context import MkdocsFilesContext
        config_file = Path(self.config.config_file_path)
        config_file.write_text(config_file.read_text().replace("plugins: []", "plugins: [awesome-nav]"))
        folder = Path(self.config.docs_dir, "nested")
        folder.mkdir()
        (folder / "index.md").write_text("# Nested\n", encoding="utf-8")
        config = load_config(config_file=str(config_file))
        originals = (MkdocsFilesContext.visit, File.copy_file, Page.validate_anchor_links)
        config.plugins.on_startup(command="build", dirty=False)
        with self.assertLogs("mkdocs.livedocs_progress", level="INFO") as captured:
            build(config)
        lines = "\n".join(captured.output)
        self.assertIn("Building navigation 1 folders visited", lines)
        self.assertIn("Validating links 3/3 pages", lines)
        self.assertEqual(originals, (MkdocsFilesContext.visit, File.copy_file, Page.validate_anchor_links))
        self.assertNotIn("nested/", lines)
        self.assertFalse(self.progress_start.__globals__["_patches"])

    def test_navigation_failure_restores_visit_method(self):
        from mkdocs_awesome_nav.nav.context import MkdocsFilesContext
        config_file = Path(self.config.config_file_path)
        config_file.write_text(config_file.read_text().replace("plugins: []", "plugins: [awesome-nav]"))
        config = load_config(config_file=str(config_file))
        original = MkdocsFilesContext.visit
        config.plugins.on_startup(command="build", dirty=False)
        with mock.patch.object(MkdocsFilesContext, "__init__", side_effect=ValueError("failed")):
            with self.assertRaisesRegex(ValueError, "failed"):
                build(config)
        self.assertIs(original, MkdocsFilesContext.visit)
        self.assertIsNone(self.progress_start.__globals__["_progress"])
        self.assertFalse(self.progress_start.__globals__["_patches"])

    def test_material_search_reports_indexed_entries(self):
        config_file = Path(self.config.config_file_path)
        config_file.write_text(config_file.read_text().replace("plugins: []", "theme: material\nplugins: [search]"))
        config = load_config(config_file=str(config_file))
        config.plugins.on_startup(command="build", dirty=False)
        with self.assertLogs("mkdocs.livedocs_progress", level="INFO") as captured:
            build(config)
        entries = config.plugins["material/search"].search_index.entries
        self.assertGreater(len(entries), 0)
        self.assertIn("Writing search index {} indexed entries".format(len(entries)),
                      "\n".join(captured.output))
        self.assertIsNone(self.progress_start.__globals__["_progress"])

    def test_serve_counts_draft_pages(self):
        self.config.plugins.on_startup(command="serve", dirty=False)
        with self.assertLogs("mkdocs.livedocs_progress", level="INFO") as captured:
            build(self.config, serve_url="http://127.0.0.1:8000/")
        self.assertIn("Rendering Markdown 3/3 pages", "\n".join(captured.output))
        self.assertIn("Rendering HTML 3/3 pages", "\n".join(captured.output))

    def test_build_failure_stops_reporting(self):
        self.config.plugins.on_startup(command="build", dirty=False)
        with mock.patch("mkdocs.structure.pages.Page.render", side_effect=ValueError("failed")):
            with self.assertRaisesRegex(ValueError, "failed"):
                build(self.config)
        self.assertIsNone(self.progress_start.__globals__["_progress"])

    def test_dirty_rebuild_without_changed_pages_still_counts_link_validation(self):
        self.config.plugins.on_startup(command="build", dirty=False)
        build(self.config)
        self.config.plugins.on_startup(command="build", dirty=True)
        with self.assertLogs("mkdocs.livedocs_progress", level="INFO") as captured:
            build(self.config, dirty=True)
        lines = "\n".join(captured.output)
        self.assertIn("Rendering Markdown 0/0 pages", lines)
        self.assertIn("Validating links 2/2 pages", lines)
        self.assertNotIn("templates 4/2", lines)

    def test_failures_in_later_phases_restore_methods_and_stop_reporting(self):
        from mkdocs.commands import build as build_module
        from mkdocs.structure.files import File
        from mkdocs.structure.pages import Page
        targets = [(File, "copy_file"), (build_module, "_build_theme_template"),
                   (Page, "validate_anchor_links")]
        self.config.plugins.on_startup(command="build", dirty=False)
        originals = [getattr(owner, name) for owner, name in targets]
        for owner, name in targets:
            with self.subTest(phase=name):
                with mock.patch.object(owner, name, side_effect=ValueError("failed")):
                    with self.assertRaisesRegex(ValueError, "failed"):
                        build(self.config)
                self.assertEqual(originals, [getattr(o, n) for o, n in targets])
                self.assertIsNone(self.progress_start.__globals__["_progress"])
                self.assertFalse(self.progress_start.__globals__["_patches"])

    def test_dirty_rebuild_counts_only_changed_pages(self):
        self.config.plugins.on_startup(command="build", dirty=False)
        build(self.config)
        other = Path(self.config.docs_dir, "other.md")
        other.write_text("# Changed\n", encoding="utf-8")
        future = time.time() + 2
        os.utime(other, (future, future))
        self.config.plugins.on_startup(command="serve", dirty=True)
        with self.assertLogs("mkdocs.livedocs_progress", level="INFO") as captured:
            build(self.config, serve_url="http://127.0.0.1:8000/", dirty=True)
        lines = "\n".join(captured.output)
        # draft.md は最初の build で生成されず、serve で初めて対象になる。
        self.assertIn("Rendering Markdown 2/2 pages", lines)
        self.assertIn("Rendering HTML 2/2 pages", lines)


if __name__ == "__main__":
    unittest.main()
