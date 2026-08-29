#!/usr/bin/env python3
"""mkdocs serve 中に、元の Markdown の変更を検知してステージングし直す。

``mkdocs serve`` は既定で ``docs_dir`` (``pages/preview/src/``) だけを監視する。
執筆中に編集するのは元の Markdown (``app/*/docs`` 等) であり、そのままでは
ステージング (``stage_preview_docs.py``) を手動で再実行しない限り反映されない。

mkdocs 1.6.1 の ``LiveReloadServer.watch(path, func=None)`` は、変更された
ファイルのパスを受け取れるカスタム コールバックを渡せない (``func`` は
``None`` かビルダー本体のみ、それ以外は ``TypeError``)。そのため、この
hook は mkdocs 本体の Observer とは別に、自前の ``watchdog`` Observer を
``on_serve`` イベントで登録し、変更されたファイルを 1 件ずつ捕捉する。

変更が既知の Markdown 1 件の内容変更であれば、``stage_single`` による軽量な
単一ファイル再ステージングだけを行う。ファイルの作成/削除/移動など構成が
変わる変更では、索引 (``\\toc`` の一覧やリンク解決表) を作り直すフル
ステージングにフォールバックする。索引の鮮度は意図的に間引いており、
一定回数の単一ファイル再ステージングごとにもフル ステージングを挟んで
再同期する。

ステージング結果は ``docs_dir`` に書き込まれるため、mkdocs 標準の
``docs_dir`` 監視がそれを検知し、通常どおりページの再ビルドとブラウザーの
自動リロードを行う。

設計は docs/mkdocs-preview-design.md を参照。
"""

import logging
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage_preview_docs import (  # noqa: E402
    build_stage_index,
    parse_config,
    parse_merge_subfolder_docs,
    stage,
    stage_single,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

log = logging.getLogger("mkdocs.preview_autostage")

# 変更の連続保存をまとめるためのデバウンス間隔。
_DEBOUNCE_SECONDS = 0.4

# 単一ファイル再ステージングをこの回数行うごとに、索引再同期のためフル
# ステージングを 1 回挟む。索引の鮮度は間引いてよいという前提での簡易な目安。
_FULL_RESTAGE_EVERY = 20

_MARKDOWN_EXTENSIONS = (".md", ".markdown")


def _workspace_and_config(config):
    """``mkdocs.yml`` の位置 (``pages/preview/``) からワークスペース ルートを逆算する。"""
    preview_dir = os.path.dirname(os.path.abspath(config["config_file_path"]))
    workspace = os.path.dirname(os.path.dirname(preview_dir))
    config_path = os.path.join(workspace, ".vscode", "pub_markdown.config.yaml")
    return workspace, config_path


def _source_roots(workspace, config_path):
    """``mdRoot`` と ``mergeSubfolderDocs`` から、元 Markdown の監視対象ディレクトリを求める。

    ``stage_preview_docs.py`` の ``build_stage_index`` が使う規則と同じもの。
    """
    pm_config = parse_config(config_path)
    md_root = pm_config.get("mdRoot") or "docs"
    roots = [os.path.normpath(os.path.join(workspace, md_root))]
    for _alias, path in parse_merge_subfolder_docs(pm_config.get("mergeSubfolderDocs"), workspace):
        roots.append(path)
    return [root for root in roots if os.path.isdir(root)]


class _AutoStager:
    """索引をキャッシュしつつ、単一ファイル再ステージングとフル ステージングを仲介する。"""

    def __init__(self, workspace, config_path, out_dir):
        self._workspace = workspace
        self._config_path = config_path
        self._out_dir = out_dir
        self._lock = threading.Lock()
        self._container = build_stage_index(workspace, config_path)
        self._since_full_restage = 0

    def _full_restage_locked(self):
        # 既存の stage() (build_stage_index + write_documents + nav 生成 +
        # remove_stale) をそのまま使う。索引の再構築は 2 度になるが、
        # フル ステージングは構成変化時と一定間隔ごとの再同期にしか
        # 発生しないため、単純さと正しさ (remove_stale による掃除) を優先する。
        stage(self._workspace, self._out_dir, self._config_path, quiet=True)
        self._container = build_stage_index(self._workspace, self._config_path)
        self._since_full_restage = 0
        log.info("フル ステージングを実行しました (索引を再同期)。")

    def handle_modified(self, real_path):
        with self._lock:
            result = stage_single(self._container, self._out_dir, real_path)
            if result is None:
                # 索引に無いファイル。新規追加などの構成変化とみなしフル ステージングへ。
                self._full_restage_locked()
                return

            self._since_full_restage += 1
            if self._since_full_restage >= _FULL_RESTAGE_EVERY:
                self._full_restage_locked()

    def handle_structural_change(self):
        with self._lock:
            self._full_restage_locked()


def _is_markdown(path):
    return path.lower().endswith(_MARKDOWN_EXTENSIONS)


def _make_handler(stager):
    from watchdog.events import FileSystemEventHandler

    class _Handler(FileSystemEventHandler):
        def __init__(self):
            super().__init__()
            self._timers = {}
            self._timers_lock = threading.Lock()

        def _debounced(self, key, action):
            with self._timers_lock:
                existing = self._timers.get(key)
                if existing is not None:
                    existing.cancel()
                timer = threading.Timer(_DEBOUNCE_SECONDS, action)
                timer.daemon = True
                self._timers[key] = timer
                timer.start()

        def on_modified(self, event):
            if event.is_directory or not _is_markdown(event.src_path):
                return
            real_path = os.path.abspath(event.src_path)
            self._debounced(real_path, lambda: stager.handle_modified(real_path))

        def on_created(self, event):
            self._on_structural(event)

        def on_deleted(self, event):
            self._on_structural(event)

        def on_moved(self, event):
            self._on_structural(event)

        def _on_structural(self, event):
            path = getattr(event, "dest_path", "") or event.src_path
            if event.is_directory or _is_markdown(path):
                self._debounced("__structural__", stager.handle_structural_change)

    return _Handler()


# mkdocs の on_shutdown はパラメーターを受け取らないため、on_serve で
# 起動した Observer への参照をモジュール グローバルに保持しておく。
_observer = None


def on_serve(server, config, builder=None, **kwargs):
    global _observer

    workspace, config_path = _workspace_and_config(config)
    out_dir = config["docs_dir"]

    stager = _AutoStager(workspace, config_path, out_dir)
    handler = _make_handler(stager)

    from watchdog.observers.polling import PollingObserver

    observer = PollingObserver()
    for root in _source_roots(workspace, config_path):
        observer.schedule(handler, root, recursive=True)
    observer.daemon = True
    observer.start()

    # 強制終了など on_shutdown が呼ばれない経路でも、daemon スレッドのため
    # プロセス終了時に残らない。
    _observer = observer

    return server


def on_shutdown(**kwargs):
    if _observer is not None:
        _observer.stop()
        _observer.join()
