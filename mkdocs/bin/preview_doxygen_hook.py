#!/usr/bin/env python3
"""mkdocs プレビューから pages/doxygen を無変換でサーブする。

``mkdocs serve`` の WSGI に ``/doxygen/`` をマウントし、``pages/doxygen/``
をそのまま返す。Markdown 変換もコピーもシンボリック リンクも使わない。
Windows でも同じ経路で、ジャンクションや MAX_PATH を増やさない。

``doxygen-page-url`` フロント マターがあるページでは、対応する Doxygen
HTML への単一ページ リンクをテンプレートへ渡す。

設計は docs/mkdocs-preview-design.md を参照。
"""

from __future__ import annotations

import logging
import mimetypes
import os
import posixpath
import sys
import wsgiref.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage_preview_docs import parse_config  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

log = logging.getLogger("mkdocs.preview_doxygen")

DOXYGEN_URL_PREFIX = "/doxygen"
DOXYGEN_PAGES_PREFIX = "pages/doxygen/"


def doxygen_page_url_to_preview(value):
    """workspace 相対の ``doxygen-page-url`` をプレビューの絶対パスへ変換する。

    ``pages/doxygen/calc_public/calc_8h.html`` -> ``/doxygen/calc_public/calc_8h.html``
    変換できない値は ``None`` を返す。
    """
    if not value:
        return None
    text = str(value).strip().replace("\\", "/")
    if text.startswith(DOXYGEN_PAGES_PREFIX):
        return DOXYGEN_URL_PREFIX + "/" + text[len(DOXYGEN_PAGES_PREFIX):]
    if text.startswith(DOXYGEN_URL_PREFIX + "/"):
        return text
    return None


def is_doxygen_link_enabled(pm_config):
    """``doxygenLinkEnable`` を判定する。未指定は有効 (docsfw と同じ)。"""
    value = (pm_config or {}).get("doxygenLinkEnable", "")
    if value == "":
        return True
    return value.strip().lower() == "true"


def normalize_url_path(url_path):
    """``PATH_INFO`` を POSIX として正規化する。末尾 ``/`` は残さない。"""
    if not url_path.startswith("/"):
        url_path = "/" + url_path
    return posixpath.normpath(url_path)


def is_doxygen_url_path(url_path):
    """``PATH_INFO`` が正規化後も ``/doxygen`` 配下かどうかを返す。"""
    normalized = normalize_url_path(url_path)
    return normalized == DOXYGEN_URL_PREFIX or normalized.startswith(DOXYGEN_URL_PREFIX + "/")


def url_path_to_rel_parts(url_path):
    """``/doxygen/...`` を root からの相対部品へ分解する。不正なら ``None``。

    URL は POSIX。正規化で ``/doxygen`` の外へ出る要求は拒否する。
    末尾 ``/`` は ``index.html`` にする。裸の ``/doxygen`` は ``None``
    (呼び出し側が ``/doxygen/`` へリダイレクトする)。
    """
    trailing_slash = url_path.endswith("/")
    normalized = normalize_url_path(url_path)
    if normalized == DOXYGEN_URL_PREFIX:
        if trailing_slash:
            return ("index.html",)
        return None
    if not normalized.startswith(DOXYGEN_URL_PREFIX + "/"):
        return None
    rel = normalized[len(DOXYGEN_URL_PREFIX) + 1:]
    if trailing_slash:
        rel = posixpath.join(rel, "index.html") if rel else "index.html"
    if rel in ("", ".", "..") or rel.startswith("../"):
        return None
    parts = tuple(part for part in rel.split("/") if part and part != ".")
    if not parts or any(part in (".", "..") for part in parts):
        return None
    return parts


def resolve_doxygen_file(root, url_path):
    """URL パスを ``root`` 配下の実ファイルパスへ解決する。範囲外は ``None``。"""
    parts = url_path_to_rel_parts(url_path)
    if parts is None:
        return None
    root_abs = os.path.abspath(root)
    candidate = os.path.abspath(os.path.join(root_abs, *parts))
    try:
        common = os.path.commonpath([root_abs, candidate])
    except ValueError:
        return None
    if os.path.normcase(common) != os.path.normcase(root_abs):
        return None
    return candidate


def guess_doxygen_content_type(path):
    """mkdocs livereload にそろえた MIME 推定。"""
    if path.endswith((".js", ".JS", ".mjs")):
        return "application/javascript"
    if path.endswith(".gz"):
        return "application/gzip"
    guess, _ = mimetypes.guess_type(path)
    if guess:
        return guess
    return "application/octet-stream"


def serve_doxygen(root, url_path, environ, start_response):
    """``pages/doxygen`` からファイルを返す WSGI アプリ断片。"""
    if url_path == DOXYGEN_URL_PREFIX:
        start_response("302 Found", [("Location", DOXYGEN_URL_PREFIX + "/")])
        return []

    fs_path = resolve_doxygen_file(root, url_path)
    if fs_path is None or not os.path.isfile(fs_path):
        if not url_path.endswith("/"):
            indexed = resolve_doxygen_file(root, url_path + "/")
            if indexed is not None and os.path.isfile(indexed):
                start_response("302 Found", [("Location", url_path + "/")])
                return []
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"404 Not Found"]

    content_type = guess_doxygen_content_type(fs_path)
    content_length = os.path.getsize(fs_path)
    handle = open(fs_path, "rb")
    start_response(
        "200 OK",
        [("Content-Type", content_type), ("Content-Length", str(content_length))],
    )
    return wsgiref.util.FileWrapper(handle)


def _workspace_and_config(config):
    """``mkdocs.yml`` の位置 (``pages/preview/``) からワークスペース ルートを逆算する。"""
    preview_dir = os.path.dirname(os.path.abspath(config["config_file_path"]))
    workspace = os.path.dirname(os.path.dirname(preview_dir))
    config_path = os.path.join(workspace, ".vscode", "pub_markdown.config.yaml")
    return workspace, config_path


_doxygen_link_enabled = None


def on_page_context(context, page, config, nav=None, **kwargs):
    """``doxygen-page-url`` をプレビュー URL としてテンプレートへ渡す。"""
    global _doxygen_link_enabled
    if _doxygen_link_enabled is None:
        _workspace, config_path = _workspace_and_config(config)
        _doxygen_link_enabled = is_doxygen_link_enabled(parse_config(config_path))

    url = None
    if _doxygen_link_enabled and page is not None:
        meta = getattr(page, "meta", None) or {}
        url = doxygen_page_url_to_preview(meta.get("doxygen-page-url"))
    context["doxygen_preview_url"] = url
    return context


def find_doxygen_root(workspace):
    """``pages/doxygen`` があればその絶対パス、無ければ ``None``。"""
    root = os.path.join(workspace, "pages", "doxygen")
    if os.path.isdir(root):
        return os.path.abspath(root)
    return None


def on_serve(server, config, builder=None, **kwargs):
    """``/doxygen/`` を ``pages/doxygen/`` へマウントする。"""
    workspace, _config_path = _workspace_and_config(config)
    doxygen_root = find_doxygen_root(workspace)
    if doxygen_root is None:
        log.info("pages/doxygen が無いため /doxygen/ はマウントしません")
        return server

    inner = server.serve_request

    def app(environ, start_response):
        raw = environ.get("PATH_INFO", "")
        path = raw.encode("latin-1").decode("utf-8", "ignore")
        if is_doxygen_url_path(path):
            return serve_doxygen(doxygen_root, path, environ, start_response)
        return inner(environ, start_response)

    server.set_app(app)
    log.info("pages/doxygen を http の /doxygen/ としてサーブします")
    return server
