#!/usr/bin/env python3
"""mkdocs による動的発行の自動再同期に関する単体テスト。"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

import livedocs_autostage_hook as autostage  # noqa: E402


class FakeTimer:
    """明示的に起床できる ``threading.Timer`` の代替。"""

    created = []

    def __init__(self, interval, function):
        self.interval = interval
        self.function = function
        self.daemon = False
        self.cancelled = False
        self.started = False
        self.__class__.created.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if not self.cancelled:
            self.function()


class AutoStagerTest(unittest.TestCase):
    def setUp(self):
        FakeTimer.created = []
        self.container = object()
        self.build_index = mock.patch.object(
            autostage, "build_stage_index", return_value=self.container
        )
        self.stage_index = mock.patch.object(
            autostage,
            "stage_index",
            return_value=SimpleNamespace(changed=True),
        )
        self.stage_single = mock.patch.object(
            autostage,
            "stage_single",
            return_value=SimpleNamespace(found=True, updated=True),
        )
        self.build_index_mock = self.build_index.start()
        self.stage_index_mock = self.stage_index.start()
        self.stage_single_mock = self.stage_single.start()
        self.addCleanup(self.build_index.stop)
        self.addCleanup(self.stage_index.stop)
        self.addCleanup(self.stage_single.stop)

        self.stager = autostage._AutoStager(
            "/workspace",
            "/workspace/.vscode/pub_markdown.config.yaml",
            "/output",
            "ja",
            True,
            "ja-details",
            timer_factory=FakeTimer,
            restage_delay=120,
        )
        self.rebuild_requests = 0

        def request_rebuild():
            self.rebuild_requests += 1

        self.stager.set_rebuild_request(request_rebuild)
        self.addCleanup(self.stager.close)

    def _fire_latest_timer(self):
        timer = FakeTimer.created[-1]
        self.assertTrue(timer.started)
        timer.fire()
        return timer

    def _publish(self, during_build=None, fail=False):
        def builder():
            if during_build is not None:
                during_build()
            if fail:
                raise RuntimeError("build failed")

        wrapped = self.stager.wrap_builder(builder)
        if fail:
            with self.assertRaisesRegex(RuntimeError, "build failed"):
                wrapped()
        else:
            wrapped()

    def test_content_changes_share_one_two_minute_timer(self):
        first = self.stager.note_modified()
        second = self.stager.note_modified()

        self.assertEqual((first, second), (1, 2))
        self.assertEqual(len(FakeTimer.created), 1)
        self.assertEqual(FakeTimer.created[0].interval, 120)
        self.assertEqual(self.stager.state()["timer_kind"], "index")

    def test_stable_publication_stops_without_another_timer(self):
        generation = self.stager.note_modified()
        self.stager.handle_modified("/workspace/docs/a.md", generation)
        self._fire_latest_timer()

        self.assertTrue(self.stager.state()["waiting_for_publish"])
        self.assertEqual(self.rebuild_requests, 1)

        self._publish()

        state = self.stager.state()
        self.assertEqual(state["detected"], state["indexed"])
        self.assertEqual(state["output"], state["published"])
        self.assertFalse(state["waiting_for_publish"])
        self.assertIsNone(state["timer_kind"])

    def test_change_during_build_waits_for_followup_publication(self):
        generation = self.stager.note_modified()
        self.stager.handle_modified("/workspace/docs/a.md", generation)
        self._fire_latest_timer()
        timer_count_before_build = len(FakeTimer.created)

        def change_during_build():
            next_generation = self.stager.note_modified()
            self.stager.handle_modified("/workspace/docs/b.md", next_generation)

        self._publish(during_build=change_during_build)

        state = self.stager.state()
        self.assertTrue(state["waiting_for_publish"])
        self.assertIsNone(state["timer_kind"])
        self.assertEqual(len(FakeTimer.created), timer_count_before_build)

        self._publish()

        state = self.stager.state()
        self.assertFalse(state["waiting_for_publish"])
        self.assertEqual(state["timer_kind"], "index")
        self.assertEqual(len(FakeTimer.created), timer_count_before_build + 1)
        self.assertEqual(FakeTimer.created[-1].interval, 120)

    def test_followup_timer_converges_after_changes_stop(self):
        generation = self.stager.note_modified()
        self.stager.handle_modified("/workspace/docs/a.md", generation)
        self._fire_latest_timer()

        def change_during_build():
            next_generation = self.stager.note_modified()
            self.stager.handle_modified("/workspace/docs/b.md", next_generation)

        self._publish(during_build=change_during_build)
        self._publish()

        self.stage_index_mock.return_value = SimpleNamespace(changed=False)
        self._fire_latest_timer()

        state = self.stager.state()
        self.assertEqual(state["detected"], state["indexed"])
        self.assertEqual(state["output"], state["published"])
        self.assertFalse(state["waiting_for_publish"])
        self.assertIsNone(state["timer_kind"])

    def test_detected_change_is_not_lost_while_debounce_is_pending(self):
        generation = self.stager.note_modified()
        self.stager.handle_modified("/workspace/docs/a.md", generation)
        self._fire_latest_timer()

        pending_generation = None

        def detect_without_staging():
            nonlocal pending_generation
            pending_generation = self.stager.note_modified()

        self._publish(during_build=detect_without_staging)

        state = self.stager.state()
        self.assertTrue(state["waiting_for_publish"])
        self.assertIsNone(state["timer_kind"])

        self.stager.handle_modified("/workspace/docs/b.md", pending_generation)
        self._publish()

        state = self.stager.state()
        self.assertFalse(state["waiting_for_publish"])
        self.assertEqual(state["timer_kind"], "index")

    def test_failed_site_build_retries_after_two_minutes(self):
        generation = self.stager.note_modified()
        self.stager.handle_modified("/workspace/docs/a.md", generation)
        self._fire_latest_timer()

        self._publish(fail=True)

        self.assertTrue(self.stager.state()["waiting_for_publish"])
        self.assertEqual(self.stager.state()["timer_kind"], "site")
        requests_before_retry = self.rebuild_requests
        self._fire_latest_timer()
        self.assertEqual(self.rebuild_requests, requests_before_retry + 1)

    def test_structural_change_cancels_delayed_index_timer(self):
        self.stager.note_modified()
        delayed = FakeTimer.created[-1]
        generation = self.stager.note_structural_change()

        self.assertTrue(delayed.cancelled)
        self.stager.handle_structural_change(generation)
        self.assertTrue(self.stager.state()["waiting_for_publish"])
        self.assertIsNone(self.stager.state()["timer_kind"])


if __name__ == "__main__":
    unittest.main()
