#!/usr/bin/env python3
"""mkdocs の再生成中も、直前に完成した版を配信する。

mkdocs 1.6.1 の LiveReloadServer は、再生成中の通常 HTTP 要求を待機させる。
この hook は生成先を版ごとの一時ディレクトリへ分離し、生成成功後だけ公開版を
切り替える。通常 HTTP 要求は要求開始時の公開版を参照し、応答が完了するまで
その版を削除しない。

``/livereload/`` と ``/doxygen/`` は先に登録された WSGI アプリへ委譲する。
設計は docs/mkdocs-preview-design.md を参照。
"""

import logging
import os
import shutil
import tempfile
import threading

from mkdocs.livereload import LiveReloadServer

log = logging.getLogger("mkdocs.preview_versioned")


class _Version:
    """生成済みサイト 1 版と、その版を使用中の応答数を保持する。"""

    def __init__(self, root, owned):
        self.root = os.path.abspath(root)
        self.owned = owned
        self.readers = 0
        self.retired = False


class _Lease:
    """HTTP 応答が特定の公開版を使用中であることを表す。"""

    def __init__(self, store, version):
        self._store = store
        self.version = version
        self._released = False

    def release(self):
        if self._released:
            return
        self._released = True
        self._store.release(self.version)


class _VersionStore:
    """公開版を切り替え、使用されなくなった一時版を削除する。"""

    def __init__(self, initial_root):
        self._lock = threading.Lock()
        self._active = _Version(initial_root, owned=False)
        self._versions = [self._active]

    def acquire(self):
        with self._lock:
            version = self._active
            version.readers += 1
            return _Lease(self, version)

    def publish(self, root):
        with self._lock:
            previous = self._active
            current = _Version(root, owned=True)
            self._versions.append(current)
            self._active = current
            previous.retired = True
            cleanup = self._take_cleanup_locked()
        self._cleanup(cleanup)

    def release(self, version):
        with self._lock:
            version.readers -= 1
            cleanup = self._take_cleanup_locked()
        self._cleanup(cleanup)

    def close(self):
        with self._lock:
            for version in self._versions:
                version.retired = True
            cleanup = self._take_cleanup_locked()
        self._cleanup(cleanup)

    def _take_cleanup_locked(self):
        cleanup = []
        keep = []
        for version in self._versions:
            removable = version.owned and version.retired and version.readers == 0
            if removable:
                cleanup.append(version.root)
            else:
                keep.append(version)
        self._versions = keep
        return cleanup

    @staticmethod
    def _cleanup(paths):
        for path in paths:
            try:
                shutil.rmtree(path)
            except FileNotFoundError:
                pass
            except OSError as error:
                log.warning("使用済みプレビュー版を削除できませんでした: %s: %s", path, error)


class _SnapshotServer:
    """LiveReloadServer の配信処理へ、固定した公開版を見せる facade。"""

    def __init__(self, server, root, epoch):
        self._server = server
        self.root = root
        self.mount_path = server.mount_path
        self._wanted_epoch = epoch
        self._visible_epoch = epoch
        self._epoch_cond = threading.Condition()
        self._watched_paths = server._watched_paths

    def serve_request(self, environ, start_response):
        return LiveReloadServer.serve_request(self, environ, start_response)

    def _serve_request(self, environ, start_response):
        return LiveReloadServer._serve_request(self, environ, start_response)

    def error_handler(self, code):
        if code not in (404, 500):
            return None
        error_page = os.path.join(self.root, "{}.html".format(code))
        try:
            with open(error_page, "rb") as handle:
                return handle.read()
        except OSError:
            return None

    def __getattr__(self, name):
        return getattr(self._server, name)


class _LeasedIterable:
    """WSGI 応答を閉じるまで公開版の lease を保持する。"""

    def __init__(self, iterable, lease):
        self._iterable = iterable
        self._iterator = iter(iterable)
        self._lease = lease
        self._closed = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return next(self._iterator)
        except StopIteration:
            self.close()
            raise
        except BaseException:
            self.close()
            raise

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            close = getattr(self._iterable, "close", None)
            if close is not None:
                close()
        finally:
            self._lease.release()


def _is_delegated_path(path):
    return path.startswith("/livereload/") or path == "/doxygen" or path.startswith("/doxygen/")


def _make_versioned_app(server, store, delegated_app):
    def app(environ, start_response):
        path = environ.get("PATH_INFO", "")
        if _is_delegated_path(path):
            return delegated_app(environ, start_response)

        lease = store.acquire()
        with server._epoch_cond:
            epoch = server._visible_epoch
        snapshot = _SnapshotServer(server, lease.version.root, epoch)
        try:
            result = snapshot.serve_request(environ, start_response)
        except BaseException:
            lease.release()
            raise
        return _LeasedIterable(result, lease)

    return app


def _make_versioned_builder(server, store, config, builder):
    def versioned_builder():
        candidate = tempfile.mkdtemp(prefix="mkdocs_preview_")
        original_site_dir = config.site_dir
        try:
            config.site_dir = candidate
            builder(config)
        except BaseException:
            shutil.rmtree(candidate, ignore_errors=True)
            raise
        finally:
            config.site_dir = original_site_dir

        # 通常 HTTP 要求は store だけを参照する。server.root は、先に登録された
        # WSGI アプリと mkdocs の診断情報も新しい公開版へそろえるため更新する。
        server.root = candidate
        store.publish(candidate)

    return versioned_builder


_stores = []


def on_serve(server, config, builder=None, **kwargs):
    if builder is None:
        return server

    store = _VersionStore(server.root)
    delegated_app = server.get_app()
    server.builder = _make_versioned_builder(server, store, config, builder)
    server.set_app(_make_versioned_app(server, store, delegated_app))
    _stores.append(store)
    return server


def on_shutdown(**kwargs):
    while _stores:
        _stores.pop().close()
