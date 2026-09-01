#!/usr/bin/env python3
"""再生成中も完成済みのプレビュー版を配信する hook のテスト。"""

import os
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from mkdocs.livereload import LiveReloadServer  # noqa: E402
from preview_versioned_hook import (  # noqa: E402
    _VersionStore,
    _make_versioned_app,
    _make_versioned_builder,
)


def _write(root, relative, body):
    path = os.path.join(root, relative)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(body)


def _request(app, path):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    result = app({"PATH_INFO": path}, start_response)
    try:
        body = b"".join(result)
    finally:
        close = getattr(result, "close", None)
        if close is not None:
            close()
    return captured, body


class PreviewVersionedHookTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.initial = os.path.join(self._tmp.name, "initial")
        os.makedirs(self.initial)
        _write(self.initial, "index.html", b"<html><body>old</body></html>")
        # LiveReloadServer.__init__ は bind 前でも socket を作る。純粋な WSGI
        # テストにするため、配信処理が参照する状態だけを設定する。
        self.server = object.__new__(LiveReloadServer)
        self.server.root = self.initial
        self.server.mount_path = "/"
        self.server._wanted_epoch = 1
        self.server._visible_epoch = 1
        self.server._epoch_cond = threading.Condition()
        self.server._watched_paths = {self.initial: 1}
        self.server.error_handler = lambda _code: None
        self.server.application = self.server.serve_request
        self.store = _VersionStore(self.initial)

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()

    def test_serves_completed_version_while_next_version_builds(self):
        started = threading.Event()
        finish = threading.Event()
        config = SimpleNamespace(site_dir=self.initial)

        def builder(build_config):
            _write(build_config.site_dir, "index.html", b"<html><body>partial</body></html>")
            started.set()
            self.assertTrue(finish.wait(timeout=5))
            _write(build_config.site_dir, "index.html", b"<html><body>new</body></html>")

        versioned_builder = _make_versioned_builder(self.server, self.store, config, builder)
        app = _make_versioned_app(self.server, self.store, self.server.get_app())
        thread = threading.Thread(target=versioned_builder)
        thread.start()
        self.assertTrue(started.wait(timeout=5))

        captured, body = _request(app, "/")
        self.assertEqual(captured["status"], "200 OK")
        self.assertIn(b"old", body)
        self.assertNotIn(b"partial", body)

        finish.set()
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        _captured, body = _request(app, "/")
        self.assertIn(b"new", body)
        self.assertNotIn(b"old", body)

    def test_failed_build_keeps_completed_version(self):
        config = SimpleNamespace(site_dir=self.initial)

        def builder(build_config):
            _write(build_config.site_dir, "index.html", b"broken")
            raise RuntimeError("build failed")

        versioned_builder = _make_versioned_builder(self.server, self.store, config, builder)
        with self.assertRaisesRegex(RuntimeError, "build failed"):
            versioned_builder()

        app = _make_versioned_app(self.server, self.store, self.server.get_app())
        _captured, body = _request(app, "/")
        self.assertIn(b"old", body)
        self.assertEqual(config.site_dir, self.initial)

    def test_retired_version_is_kept_until_response_closes(self):
        app = _make_versioned_app(self.server, self.store, self.server.get_app())
        response = app({"PATH_INFO": "/"}, lambda _status, _headers: None)
        first_body = next(iter(response))
        self.assertIn(b"old", first_body)

        candidate = tempfile.mkdtemp(prefix="published_", dir=self._tmp.name)
        _write(candidate, "index.html", b"<html><body>new</body></html>")
        self.store.publish(candidate)
        self.assertTrue(os.path.isdir(self.initial))

        response.close()
        # 初回版のディレクトリは mkdocs 自身が所有するため hook は削除しない。
        self.assertTrue(os.path.isdir(self.initial))

    def test_owned_retired_version_is_removed_after_response_closes(self):
        first = tempfile.mkdtemp(prefix="published_", dir=self._tmp.name)
        second = tempfile.mkdtemp(prefix="published_", dir=self._tmp.name)
        _write(first, "index.html", b"first")
        _write(second, "index.html", b"second")
        self.store.publish(first)

        lease = self.store.acquire()
        self.store.publish(second)
        self.assertTrue(os.path.isdir(first))
        lease.release()
        self.assertFalse(os.path.exists(first))

    def test_delegates_livereload_and_doxygen(self):
        delegated = []

        def delegated_app(environ, start_response):
            delegated.append(environ["PATH_INFO"])
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"delegated"]

        app = _make_versioned_app(self.server, self.store, delegated_app)
        for path in ("/livereload/1/2", "/doxygen", "/doxygen/index.html"):
            _captured, body = _request(app, path)
            self.assertEqual(body, b"delegated")
        self.assertEqual(delegated, ["/livereload/1/2", "/doxygen", "/doxygen/index.html"])

    def test_keeps_redirect_404_and_livereload_injection(self):
        _write(self.initial, "guide/index.html", b"<html><body>guide</body></html>")
        _write(self.initial, "404.html", b"custom missing")
        app = _make_versioned_app(self.server, self.store, self.server.get_app())

        captured, _body = _request(app, "/guide")
        self.assertEqual(captured["status"], "302 Found")
        self.assertEqual(captured["headers"]["Location"], "/guide/")

        captured, body = _request(app, "/missing")
        self.assertEqual(captured["status"], "404 Not Found")
        self.assertEqual(body, b"custom missing")

        _captured, body = _request(app, "/")
        self.assertIn(b"Enabled live reload", body)


if __name__ == "__main__":
    unittest.main()
