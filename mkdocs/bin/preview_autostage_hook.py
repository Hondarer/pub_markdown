#!/usr/bin/env python3
"""元の Markdown を再ステージングし、mkdocs の完成版を最終状態へ収束させる。"""

import logging
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage_preview_docs import (  # noqa: E402
    DEFAULT_PREVIEW_VARIANT,
    build_stage_index,
    parse_config,
    parse_merge_subfolder_docs,
    parse_preview_variant,
    stage_index,
    stage_single,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

log = logging.getLogger("mkdocs.preview_autostage")

_DEBOUNCE_SECONDS = 0.4
_INDEX_RESTAGE_DELAY_SECONDS = 120.0
_MARKDOWN_EXTENSIONS = (".md", ".markdown")


def _workspace_and_config(config):
    """``mkdocs.yml`` の位置からワークスペース ルートを逆算する。"""
    preview_dir = os.path.dirname(os.path.abspath(config["config_file_path"]))
    workspace = os.path.dirname(os.path.dirname(preview_dir))
    config_path = os.path.join(workspace, ".vscode", "pub_markdown.config.yaml")
    return workspace, config_path


def _source_roots(workspace, config_path):
    """元 Markdown の監視対象ディレクトリを求める。"""
    pm_config = parse_config(config_path)
    md_root = pm_config.get("mdRoot") or "docs"
    roots = [os.path.normpath(os.path.join(workspace, md_root))]
    for _alias, path in parse_merge_subfolder_docs(pm_config.get("mergeSubfolderDocs"), workspace):
        roots.append(path)
    return [root for root in roots if os.path.isdir(root)]


def _preview_lang_details(config):
    """生成済み設定から言語、details、バリアント名を取得する。"""
    extra = config.get("extra") or {}
    variant = extra.get("preview_variant") or DEFAULT_PREVIEW_VARIANT
    lang, details, name = parse_preview_variant(variant)
    return lang, details, name


class _AutoStager:
    """変更、索引、ステージング出力、公開サイトの世代を管理する。"""

    def __init__(self, workspace, config_path, out_dir, lang, details, variant,
                 timer_factory=threading.Timer,
                 restage_delay=_INDEX_RESTAGE_DELAY_SECONDS):
        self._workspace = workspace
        self._config_path = config_path
        self._out_dir = out_dir
        self._lang = lang
        self._details = details
        self._variant = variant
        self._timer_factory = timer_factory
        self._restage_delay = restage_delay

        self._state_lock = threading.RLock()
        self._stage_lock = threading.Lock()
        self._container = build_stage_index(
            workspace, config_path, lang=lang, details=details, variant=variant
        )

        self._detected_generation = 0
        self._staged_generation = 0
        self._index_generation = 0
        self._next_output_epoch = 0
        self._latest_output_epoch = 0
        self._published_output_epoch = 0
        self._active_batches = 0

        self._waiting_for_publish = False
        self._required_publish_epoch = 0
        self._timer = None
        self._timer_token = 0
        self._timer_kind = None
        self._request_rebuild = None
        self._closed = False

    def set_rebuild_request(self, callback):
        """LiveReload のサイト再生成要求コールバックを設定する。"""
        self._request_rebuild = callback

    def note_modified(self):
        """内容変更を処理待ちとして記録し、その世代を返す。"""
        with self._state_lock:
            self._detected_generation += 1
            generation = self._detected_generation
            if not self._waiting_for_publish and self._timer is None:
                self._schedule_locked("index")
            return generation

    def note_structural_change(self):
        """作成、削除、移動を記録し、遅延中の索引再同期を取り消す。"""
        with self._state_lock:
            self._detected_generation += 1
            self._cancel_timer_locked()
            return self._detected_generation

    def _schedule_locked(self, kind):
        if self._closed or self._timer is not None:
            return
        self._timer_token += 1
        token = self._timer_token
        timer = self._timer_factory(
            self._restage_delay,
            lambda: self._timer_fired(token, kind),
        )
        timer.daemon = True
        self._timer = timer
        self._timer_kind = kind
        timer.start()
        log.info("%d 秒後に%sを予約しました。",
                 int(self._restage_delay),
                 "サイト再生成" if kind == "site" else "索引再同期")

    def _cancel_timer_locked(self):
        self._timer_token += 1
        if self._timer is not None:
            self._timer.cancel()
        self._timer = None
        self._timer_kind = None

    def _timer_fired(self, token, kind):
        with self._state_lock:
            if self._closed or token != self._timer_token:
                return
            self._timer = None
            self._timer_kind = None

        if kind == "site":
            self._request_site_rebuild()
            return

        with self._state_lock:
            generation = self._detected_generation
        self._full_restage(generation, "遅延した索引再同期")

    def _begin_batch(self):
        with self._state_lock:
            self._next_output_epoch += 1
            epoch = self._next_output_epoch
            self._active_batches += 1
            return epoch

    def _finish_batch(self, epoch, updated):
        with self._state_lock:
            self._active_batches -= 1
            if updated:
                self._latest_output_epoch = max(self._latest_output_epoch, epoch)

    def handle_modified(self, real_path, generation):
        """既知ファイルを単一ファイル単位で再ステージングする。"""
        epoch = self._begin_batch()
        result = None
        try:
            with self._stage_lock:
                result = stage_single(self._container, self._out_dir, real_path)
        except Exception:
            log.exception("単一ファイルの再ステージングに失敗しました: %s", real_path)
        finally:
            self._finish_batch(epoch, bool(result and result.updated))

        request_rebuild = False
        if result is not None:
            with self._state_lock:
                self._staged_generation = max(self._staged_generation, generation)
                request_rebuild = self._evaluate_wait_locked()

        if request_rebuild:
            self._request_site_rebuild()

        if result is not None and not result.found:
            with self._state_lock:
                self._cancel_timer_locked()
            self._full_restage(generation, "索引にないファイルの検出")

    def handle_structural_change(self, generation):
        """ファイル構成の変更を即時に全体再同期する。"""
        self._full_restage(generation, "ファイル構成の変更")

    def _full_restage(self, generation, reason):
        epoch = self._begin_batch()
        result = None
        try:
            with self._stage_lock:
                new_container = build_stage_index(
                    self._workspace,
                    self._config_path,
                    lang=self._lang,
                    details=self._details,
                    variant=self._variant,
                )
                result = stage_index(new_container, self._out_dir, quiet=True)
                self._container = new_container
        except Exception:
            log.exception("%sに失敗しました。", reason)
        finally:
            self._finish_batch(epoch, bool(result and result.changed))

        if result is None:
            with self._state_lock:
                if not self._closed and self._timer is None:
                    self._schedule_locked("index")
            return

        request_rebuild = False
        with self._state_lock:
            self._staged_generation = max(self._staged_generation, generation)
            self._index_generation = max(self._index_generation, generation)
            self._waiting_for_publish = True
            self._required_publish_epoch = self._latest_output_epoch
            request_rebuild = self._evaluate_wait_locked()

        log.info("%sを実行しました (索引世代 %d)。", reason, generation)
        if request_rebuild:
            self._request_site_rebuild()

    def _complete_cycle_locked(self):
        self._waiting_for_publish = False
        self._required_publish_epoch = 0
        if self._detected_generation > self._index_generation and self._timer is None:
            self._schedule_locked("index")

    def _evaluate_wait_locked(self):
        """公開待ちを評価し、サイト再生成が必要かどうかを返す。"""
        if not self._waiting_for_publish or self._active_batches > 0:
            return False
        if self._staged_generation < self._detected_generation:
            return False
        caught_up = (
            self._published_output_epoch >= self._required_publish_epoch
            and self._published_output_epoch >= self._latest_output_epoch
        )
        if caught_up:
            self._complete_cycle_locked()
            return False
        return True

    def wrap_builder(self, builder):
        """完成版の公開後にサイト生成完了を記録する関数を返す。"""
        def tracked_builder(*args, **kwargs):
            with self._state_lock:
                snapshot = self._latest_output_epoch
                started_during_batch = self._active_batches > 0
            succeeded = False
            try:
                result = builder(*args, **kwargs)
                succeeded = True
                return result
            finally:
                self.site_build_finished(snapshot, started_during_batch, succeeded)

        return tracked_builder

    def site_build_finished(self, snapshot, started_during_batch, succeeded):
        """完成版公開後に公開世代を進め、必要なら次周期を予約する。"""
        request_rebuild = False
        with self._state_lock:
            if succeeded and not started_during_batch:
                self._published_output_epoch = max(self._published_output_epoch, snapshot)

            if not self._waiting_for_publish:
                return

            if succeeded and not started_during_batch:
                request_rebuild = self._evaluate_wait_locked()
            elif not succeeded and self._staged_generation >= self._detected_generation \
                    and self._timer is None:
                self._schedule_locked("site")
            elif self._active_batches == 0 \
                    and self._staged_generation >= self._detected_generation:
                request_rebuild = True

        if request_rebuild:
            self._request_site_rebuild()

    def _request_site_rebuild(self):
        callback = self._request_rebuild
        if callback is not None and not self._closed:
            callback()

    def close(self):
        """未実行タイマーを取り消し、新しい処理の予約を止める。"""
        with self._state_lock:
            self._closed = True
            self._cancel_timer_locked()

    def state(self):
        """テストと診断用に現在の世代と待機状態を返す。"""
        with self._state_lock:
            return {
                "detected": self._detected_generation,
                "staged": self._staged_generation,
                "indexed": self._index_generation,
                "output": self._latest_output_epoch,
                "published": self._published_output_epoch,
                "waiting_for_publish": self._waiting_for_publish,
                "timer_kind": self._timer_kind,
            }


def _is_markdown(path):
    return path.lower().endswith(_MARKDOWN_EXTENSIONS)


def _make_handler(stager):
    from watchdog.events import FileSystemEventHandler

    class _Handler(FileSystemEventHandler):
        def __init__(self):
            super().__init__()
            self._timers = {}
            self._timers_lock = threading.Lock()
            self._closed = False

        def _debounced(self, key, action):
            with self._timers_lock:
                if self._closed:
                    return
                existing = self._timers.get(key)
                if existing is not None:
                    existing.cancel()
                timer = None

                def invoke():
                    try:
                        action()
                    finally:
                        with self._timers_lock:
                            if self._timers.get(key) is timer:
                                self._timers.pop(key, None)

                timer = threading.Timer(_DEBOUNCE_SECONDS, invoke)
                timer.daemon = True
                self._timers[key] = timer
                timer.start()

        def on_modified(self, event):
            if event.is_directory or not _is_markdown(event.src_path):
                return
            real_path = os.path.abspath(event.src_path)
            generation = stager.note_modified()
            self._debounced(real_path, lambda: stager.handle_modified(real_path, generation))

        def on_created(self, event):
            self._on_structural(event)

        def on_deleted(self, event):
            self._on_structural(event)

        def on_moved(self, event):
            self._on_structural(event)

        def _on_structural(self, event):
            path = getattr(event, "dest_path", "") or event.src_path
            if event.is_directory or _is_markdown(path):
                generation = stager.note_structural_change()
                self._debounced(
                    "__structural__",
                    lambda: stager.handle_structural_change(generation),
                )

        def close(self):
            with self._timers_lock:
                self._closed = True
                for timer in self._timers.values():
                    timer.cancel()
                self._timers.clear()

    return _Handler()


def _request_server_rebuild(server):
    """LiveReloadServer へスレッド安全にサイト再生成を要求する。"""
    with server._rebuild_cond:
        server._want_rebuild = True
        server._rebuild_cond.notify_all()


_observer = None
_handler = None
_stager = None


def on_serve(server, config, builder=None, **kwargs):
    global _observer, _handler, _stager

    workspace, config_path = _workspace_and_config(config)
    out_dir = config["docs_dir"]
    lang, details, variant = _preview_lang_details(config)

    stager = _AutoStager(workspace, config_path, out_dir, lang, details, variant)
    stager.set_rebuild_request(lambda: _request_server_rebuild(server))
    handler = _make_handler(stager)

    # preview_versioned_hook が先に設定した builder を包む。この関数から
    # 戻った時点は、候補サイトの生成だけでなく完成版の公開も完了している。
    if server.builder is not None:
        server.builder = stager.wrap_builder(server.builder)

    from watchdog.observers.polling import PollingObserver

    observer = PollingObserver()
    for root in _source_roots(workspace, config_path):
        observer.schedule(handler, root, recursive=True)
    observer.daemon = True
    observer.start()

    _observer = observer
    _handler = handler
    _stager = stager
    return server


def on_shutdown(**kwargs):
    global _observer, _handler, _stager

    if _stager is not None:
        _stager.close()
    if _handler is not None:
        _handler.close()
    if _observer is not None:
        _observer.stop()
        _observer.join()
    _observer = None
    _handler = None
    _stager = None
