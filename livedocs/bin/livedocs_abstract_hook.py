#!/usr/bin/env python3
"""mkdocs による動的発行で、フロント マターの概要 (abstract) を本文へ挿入する。

静的発行 (Pandoc) の ``styles/html/html-template.html`` は ``abstract`` /
``abstract-title`` フロント マターを、タイトル (``$title$`` の H1) の直後・
本文の前に描画する。mkdocs はフロント マターを自前でパースするため
``page.meta`` にはステージング処理の変更なしに ``abstract`` / ``abstract-title``
が届くが、配置だけは本文の HTML 化後に補う必要がある。

mkdocs-material のテーマ (``partials/content.html``) が H1 を合成するのは
``page.content`` に ``<h1`` が無い場合だけで、この docsfw のドキュメントは
ほとんどが本文側に ``# 見出し`` を持つため、``page.content`` には既に
``<h1>`` が含まれている。テーマを上書きしてブロックを差し込む方式では
本文側の H1 より前に出てしまい Pandoc の見た目と一致しないため、
``on_page_content`` (Markdown を HTML化した直後・テンプレート適用前) で
最初の ``</h1>`` の直後へ正規表現で挿入する。

設計は docs/livedocs-design.md の「概要 (Abstract)」節を参照。
"""

from __future__ import annotations

import html as html_module
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_H1_BLOCK_RE = re.compile(r"<h1\b[^>]*>.*?</h1>", re.IGNORECASE | re.DOTALL)


def _render_abstract_markdown(text, config):
    """概要本文を、サイト本文と同じ Markdown 拡張で HTML へ変換する。

    Pandoc は ``abstract`` を Markdown として解釈するため、mkdocs 側も
    ``config["markdown_extensions"]`` / ``config["mdx_configs"]`` (mkdocs
    コア自身がページ本文を変換する際と同じ設定) をそのまま使い、見た目を揃える。
    """
    import markdown

    converter = markdown.Markdown(
        extensions=config["markdown_extensions"],
        extension_configs=config["mdx_configs"],
    )
    return converter.convert(text)


def _build_abstract_block(meta, config):
    """``page.meta`` から概要ブロックの HTML を組み立てる。"""
    abstract_title = meta.get("abstract-title", "")
    abstract_html = _render_abstract_markdown(meta["abstract"], config)
    return (
        '<div class="abstract">\n'
        '<div class="abstract-title">{}</div>\n'
        "{}\n"
        "</div>"
    ).format(html_module.escape(abstract_title), abstract_html)


def on_page_content(html, page, config, files, **kwargs):
    """概要ブロックを、最初の H1 の直後 (無ければ先頭) へ挿入する。"""
    meta = getattr(page, "meta", None) or {}
    if not meta.get("abstract"):
        return html

    block = _build_abstract_block(meta, config)

    match = _H1_BLOCK_RE.search(html)
    if match is None:
        return block + "\n" + html

    return html[: match.end()] + "\n" + block + html[match.end() :]
