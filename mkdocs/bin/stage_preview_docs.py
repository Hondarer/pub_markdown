#!/usr/bin/env python3
"""mkdocs プレビュー用に Markdown を収集し、前処理してステージングする。

docsfw の ``bin/pub_markdown_core.sh`` が発行時に行う入力側の処理のうち、
プレビューに必要なものだけを再現します。

処理の流れを次に示します。

1. ``.vscode/pub_markdown.config.yaml`` から ``mdRoot`` と ``mergeSubfolderDocs`` を解決する
2. 主 mdRoot と追加ドキュメント サブフォルダーから Markdown と画像を収集する
3. ``pub_markdown.skip: true`` のファイルを除外する
4. 言語タグと詳細タグを解決する
5. ``README.md`` / ``SKILL.md`` を ``index.md`` へ正規化する
6. ``\\toc`` を索引リストへ展開する
7. リンクを実パスから仮想パスへ書き換える
8. docsfw 固有の記法を mkdocs 向けへ変換する
9. 内容が変わったファイルだけを書き出す

使用方法:

    python3 stage_preview_docs.py --workspaceFolder=/path/to/workspace
"""

import argparse
import os
import posixpath
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from expand_toc import DocIndex, expand_toc_commands  # noqa: E402
from lang_details_filter import filter_lang_details  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PREVIEW_LANG = "ja"
PREVIEW_DETAILS = True

MARKDOWN_EXTENSIONS = (".md", ".markdown")
ASSET_EXTENSIONS = (
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".pdf", ".drawio", ".yaml", ".yml", ".json",
)
MAGIC_FILES = ("pubpart.yaml", "pubchild.yaml", "publocal.yaml")

# bin/vendor_assets.py が配置するファイル。ステージングの掃除対象から外す。
VENDORED_PREFIXES = ("assets/plantuml/", "assets/mermaid/")
VENDORED_FILES = (
    "assets/docsfw-plantuml.js",
    "assets/docsfw-mermaid.js",
    "assets/docsfw-mathjax.js",
    "assets/docsfw-preview.css",
)

# 既定の環境変数。.vscode/settings.json の定義と一致させる。
DEFAULT_FRAMEWORK_HOMES = {
    "DOCSFW_HOME": "framework/docsfw",
    "DOXYFW_HOME": "framework/doxyfw",
    "MAKEFW_HOME": "framework/makefw",
    "TESTFW_HOME": "framework/testfw",
}

_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
_FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
_H1_RE = re.compile(r"^#\s+(.+?)\s*$")
_PAGEBREAK_RE = re.compile(r"^[ \t]*\\(?:newpage|pagebreak)[ \t]*$")
_LINK_RE = re.compile(r"(!?)\[((?:[^\[\]]|\[[^\]]*\])*)\]\(([^()\s]*(?:\([^()]*\)[^()\s]*)*)\)")
_CAPTION_RE = re.compile(r"^(Table|CodeBlock):[ \t]*(.*)$")
_ATTR_TAIL_RE = re.compile(r"\s*\{#([A-Za-z0-9_:.-]+)\}\s*$")
_DEPRECATED_RE = re.compile(r"^([ \t]*)>[ \t]*\[!DEPRECATED\][ \t]*$")
_COLLAPSIBLE_OPEN_RE = re.compile(r"^:{3,}[ \t]*\{\.collapsible-list(?:[ \t][^}]*)?\}[ \t]*$")
_COLLAPSIBLE_CLOSE_RE = re.compile(r"^:{3,}[ \t]*$")

DOCUMENT_LINK_EXTENSIONS = (".md", ".markdown", ".rmd", ".tmd", ".rst")


# ----------------------------------------------------------------------------
# 設定の読み込み
# ----------------------------------------------------------------------------

def parse_config(config_path):
    """``pub_markdown.config.yaml`` から必要なキーだけを読み出す。

    docsfw の ``parse_yaml`` と同じく、行頭のキーと最初のコロン以降を値として扱い、
    コメントを取り除きます。
    """
    values = {}
    if not os.path.isfile(config_path):
        return values

    with open(config_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\r\n")
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            if key != key.strip() or not key.strip():
                continue
            value = re.sub(r"[ \t]*#.*$", "", value).strip()
            values[key.strip()] = value
    return values


def expand_env_vars(path, workspace):
    """``$VAR`` と ``${VAR}`` を展開する。未定義のフレームワーク変数は既定値で補う。"""

    def replace(match):
        name = match.group(1) or match.group(2)
        if name in os.environ and os.environ[name]:
            return os.environ[name]
        if name in DEFAULT_FRAMEWORK_HOMES:
            return os.path.join(workspace, DEFAULT_FRAMEWORK_HOMES[name])
        raise ValueError(
            "mergeSubfolderDocs path references undefined environment variable: {}".format(name)
        )

    return _ENV_VAR_RE.sub(replace, path)


def parse_merge_subfolder_docs(spec, workspace):
    """``alias=path`` のスペース区切り一覧を ``[(alias, 絶対パス)]`` へ変換する。"""
    entries = []
    if not spec:
        return entries

    for item in spec.split():
        if "=" not in item:
            print("Warning: mergeSubfolderDocs entries must use alias=path: {}".format(item))
            continue
        alias, _, raw_path = item.partition("=")
        alias = alias.strip().strip("/")
        raw_path = expand_env_vars(raw_path.strip(), workspace).replace("\\", "/").rstrip("/")
        if not alias or not raw_path:
            print("Warning: mergeSubfolderDocs entries must use non-empty alias and path: {}".format(item))
            continue

        abs_path = raw_path if os.path.isabs(raw_path) else os.path.join(workspace, raw_path)
        abs_path = os.path.normpath(abs_path)
        if not os.path.isdir(abs_path):
            print("Warning: mergeSubfolderDocs path does not exist or is not a directory; skipping: {}".format(raw_path))
            continue
        entries.append((alias, abs_path))

    return entries


# ----------------------------------------------------------------------------
# フロント マター
# ----------------------------------------------------------------------------

def split_front_matter(text):
    """先頭の YAML フロント マターを ``(本文前, 本文)`` に分割する。

    フロント マターが無い場合は ``("", text)`` を返します。
    """
    if not text.startswith("---"):
        return "", text

    lines = text.split("\n")
    if lines[0].strip() != "---":
        return "", text

    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            return "\n".join(lines[: index + 1]), "\n".join(lines[index + 1:])

    return "", text


def parse_front_matter_fields(front_matter):
    """フロント マターの単純な ``key: value`` を辞書へ読み出す。"""
    fields = {}
    for raw_line in front_matter.split("\n")[1:]:
        line = raw_line.rstrip("\r")
        if line.strip() in ("---", "..."):
            break
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key.strip()] = value
    return fields


def resolve_short_title(fields, lang, details):
    """``short-title`` 系フィールドを優先順位付きで解決する。

    ``bin/extract-short-title.sh`` と同じ優先順位です。
    """
    candidates = []
    if lang and lang != "neutral":
        if details:
            candidates.append("short-title-{}-details".format(lang))
        candidates.append("short-title-{}".format(lang))
    if details:
        candidates.append("short-title-details")
    candidates.append("short-title")

    for key in candidates:
        value = fields.get(key)
        if value:
            return value
    return ""


def is_skipped(fields):
    """``pub_markdown.skip: true`` が指定されているかどうかを返す。"""
    return fields.get("pub_markdown.skip", "").lower() == "true"


def first_heading(body):
    """本文から最初のレベル 1 見出しを取り出す。コード フェンス内は無視する。"""
    fence = None
    for raw_line in body.split("\n"):
        line = raw_line.rstrip("\r")
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is not None:
            continue
        heading = _H1_RE.match(line)
        if heading:
            return heading.group(1)
    return ""


# ----------------------------------------------------------------------------
# 実パスと仮想パスの対応
# ----------------------------------------------------------------------------

class PathMapper:
    """実パスと仮想パス (ステージング ルートからの相対パス) を相互に変換する。

    docsfw の ``link-to-html.lua`` の ``real_to_virtual_path`` /
    ``virtual_to_real_path`` と同じ規則です。
    """

    def __init__(self, main_mdroot, subfolders):
        self.main_mdroot = _posix(main_mdroot)
        self.subfolders = [(alias, _posix(path)) for alias, path in subfolders]

    def real_to_virtual(self, real_path):
        """実パスをステージング ルートからの相対パスへ変換する。対象外なら ``None``。"""
        real_path = _posix(os.path.normpath(real_path))
        for alias, root in self.subfolders:
            if real_path == root:
                return alias
            if real_path.startswith(root + "/"):
                return posixpath.join(alias, real_path[len(root) + 1:])
        if real_path == self.main_mdroot:
            return ""
        if real_path.startswith(self.main_mdroot + "/"):
            return real_path[len(self.main_mdroot) + 1:]
        return None

    def virtual_to_real(self, virtual_rel):
        """ステージング ルートからの相対パスを実パスへ変換する。"""
        virtual_rel = posixpath.normpath(virtual_rel) if virtual_rel else ""
        if virtual_rel == ".":
            virtual_rel = ""
        for alias, root in self.subfolders:
            if virtual_rel == alias:
                return root
            if virtual_rel.startswith(alias + "/"):
                return posixpath.join(root, virtual_rel[len(alias) + 1:])
        if not virtual_rel:
            return self.main_mdroot
        return posixpath.join(self.main_mdroot, virtual_rel)


def _posix(path):
    return path.replace("\\", "/")


# ----------------------------------------------------------------------------
# 収集
# ----------------------------------------------------------------------------

class Document:
    """収集した 1 ファイル分の情報。"""

    def __init__(self, real_path, virtual_rel):
        self.real_path = real_path
        self.virtual_rel = virtual_rel
        self.source_name = posixpath.basename(virtual_rel)
        self.staged_rel = virtual_rel
        self.front_matter = ""
        self.body = ""
        self.fields = {}
        self.title = ""


def collect_sources(workspace, main_mdroot, subfolders):
    """主 mdRoot と追加ドキュメント サブフォルダーからファイルを収集する。

    :return: ``(markdown ドキュメント一覧, アセット一覧)``。
             アセットは ``(実パス, 仮想相対パス)`` の組。
    """
    roots = [(None, main_mdroot)]
    roots.extend(subfolders)

    documents = []
    assets = []

    for alias, root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
            dirnames.sort()
            for filename in sorted(filenames):
                if filename in MAGIC_FILES:
                    continue
                real_path = os.path.join(dirpath, filename)
                relative = _posix(os.path.relpath(real_path, root))
                virtual_rel = posixpath.join(alias, relative) if alias else relative
                lower = filename.lower()
                if lower.endswith(MARKDOWN_EXTENSIONS):
                    documents.append(Document(real_path, virtual_rel))
                elif lower.endswith(ASSET_EXTENSIONS):
                    assets.append((real_path, virtual_rel))

    return documents, assets


def resolve_staged_names(documents):
    """``README.md`` / ``SKILL.md`` を ``index.md`` へ正規化する。

    優先順位は ``index.md`` > ``README.md`` > ``SKILL.md`` です。
    同一ディレクトリに上位候補があるファイルは、元の名前のまま残ります。
    """
    by_dir = {}
    for document in documents:
        vdir = posixpath.dirname(document.virtual_rel)
        by_dir.setdefault(vdir, {})[document.source_name.lower()] = document

    for vdir, entries in by_dir.items():
        if "index.md" in entries:
            continue
        promoted = entries.get("readme.md") or entries.get("skill.md")
        if promoted is None:
            continue
        promoted.staged_rel = posixpath.join(vdir, "index.md") if vdir else "index.md"


# ----------------------------------------------------------------------------
# 本文の変換
# ----------------------------------------------------------------------------

def _norm_key(path):
    """辞書のキーとして使えるように実パスを正規化する。"""
    return os.path.normcase(os.path.normpath(path))


def rewrite_links(text, document, mapper, real_to_staged):
    """相対リンクを、ステージング後のツリーに合わせて書き換える。

    docsfw の ``link-to-html.lua`` と同じく、まず ``\\toc`` を含むファイル自身の
    実パスを基準に解決し、見つからない場合は仮想パス経由で解決します。
    ``.md`` 拡張子は mkdocs が解決するため、そのまま残します。
    """
    source_dir_real = os.path.dirname(document.real_path)
    source_dir_virtual = posixpath.dirname(document.virtual_rel)
    staged_dir = posixpath.dirname(document.staged_rel)

    def resolve(target):
        path, _, suffix = _split_link_suffix(target)
        if not path or path.startswith("/") or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", path):
            return None

        candidates = [os.path.join(source_dir_real, path)]
        virtual_target = posixpath.normpath(posixpath.join(source_dir_virtual, path))
        candidates.append(mapper.virtual_to_real(virtual_target))

        for candidate in candidates:
            staged = real_to_staged.get(_norm_key(candidate))
            if staged is not None:
                relative = posixpath.relpath(staged, staged_dir) if staged_dir else staged
                return relative + suffix
        return None

    def replace(match):
        bang, label, target = match.group(1), match.group(2), match.group(3)
        rewritten = resolve(target)
        if rewritten is None:
            return match.group(0)
        return "{}[{}]({})".format(bang, label, rewritten)

    return _apply_outside_fences(text, lambda line: _LINK_RE.sub(replace, line))


def _split_link_suffix(target):
    """リンク先を ``(パス, 区切り, アンカーやクエリ)`` に分割する。"""
    match = re.match(r"^([^#?]*)(.*)$", target)
    return match.group(1), "", match.group(2)


def _apply_outside_fences(text, transform):
    """コード フェンスの外側の行にだけ ``transform`` を適用する。"""
    out = []
    fence = None
    for line in text.split("\n"):
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            out.append(line)
            continue
        out.append(line if fence is not None else transform(line))
    return "\n".join(out)


def convert_captions(text):
    """``Table:`` / ``CodeBlock:`` キャプションを attr_list 付きの段落へ変換する。

    docsfw は Pandoc のキャプション記法として扱いますが、mkdocs では
    ``.docsfw-caption`` クラスを付けた段落として表現します。
    ``{#fig:xxx}`` などのラベルは id として残します。

    attr_list はブロック要素の属性を、段落の直後の属性だけの行から読み取ります。
    """
    lines = text.split("\n")
    out = []
    fence = None
    index = 0

    while index < len(lines):
        line = lines[index]
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            out.append(line)
            index += 1
            continue

        if fence is not None:
            out.append(line)
            index += 1
            continue

        caption_match = _CAPTION_RE.match(line)
        at_paragraph_start = not out or not out[-1].strip()
        if caption_match and at_paragraph_start:
            paragraph = [caption_match.group(2).strip()]
            index += 1
            while index < len(lines) and lines[index].strip() and not _FENCE_RE.match(lines[index]):
                paragraph.append(lines[index])
                index += 1

            attrs = [".docsfw-caption"]
            last = paragraph[-1]
            label_match = _ATTR_TAIL_RE.search(last)
            if label_match:
                attrs.insert(0, "#" + label_match.group(1))
                paragraph[-1] = last[: label_match.start()].rstrip()
            # attr_list はブロック要素に対して、属性だけの行を要求する。
            paragraph.append("{{: {} }}".format(" ".join(attrs)))
            out.extend(paragraph)
            continue

        out.append(line)
        index += 1

    return "\n".join(out)


def convert_deprecated_alerts(text):
    """``> [!DEPRECATED]`` を ``!!! deprecated`` の admonition へ変換する。

    markdown-callouts の github-callouts は GitHub 標準の 5 種類だけを扱うため、
    docsfw が独自に追加している DEPRECATED はここで変換します。
    見出しは admonition.lua と同じ "Deprecated" にそろえます。
    """
    if "[!DEPRECATED]" not in text:
        return text

    lines = text.split("\n")
    out = []
    index = 0

    while index < len(lines):
        match = _DEPRECATED_RE.match(lines[index])
        if not match:
            out.append(lines[index])
            index += 1
            continue

        index += 1
        content = []
        while index < len(lines) and lines[index].lstrip().startswith(">"):
            stripped = lines[index].lstrip()[1:]
            if stripped.startswith(" "):
                stripped = stripped[1:]
            content.append(stripped)
            index += 1

        out.append('!!! deprecated "Deprecated"')
        out.append("")
        for entry in content:
            out.append(("    " + entry) if entry.strip() else "")

    return "\n".join(out)


def strip_collapsible_list_fences(text):
    """``::: {.collapsible-list open-level=N}`` の Pandoc fenced div を取り除く。

    doxybook2 向けテンプレート (``index.tmpl`` など) はこの記法を直接出力するが、
    mkdocs (Python-Markdown) には対応する拡張が無く、そのまま表示されてしまう。
    ``\\toc`` 展開 (``expand_toc.py``) が折り畳み表示を実装しないのと同じく、
    プレビューでは開始行と対応する終了行だけを取り除き、中身のリストは
    折り畳み無しの通常リストとして表示する。
    """
    if ":::" not in text:
        return text

    lines = text.split("\n")
    out = []
    fence = None
    index = 0

    while index < len(lines):
        line = lines[index]
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            out.append(line)
            index += 1
            continue

        if fence is not None:
            out.append(line)
            index += 1
            continue

        if _COLLAPSIBLE_OPEN_RE.match(line):
            index += 1
            while index < len(lines) and not _COLLAPSIBLE_CLOSE_RE.match(lines[index]):
                out.append(lines[index])
                index += 1
            index += 1  # 終了行 (:::) を読み飛ばす
            continue

        out.append(line)
        index += 1

    return "\n".join(out)


def remove_page_breaks(text):
    """``\\newpage`` と ``\\pagebreak`` の行を取り除く。"""
    if "\\newpage" not in text and "\\pagebreak" not in text:
        return text
    return "\n".join(
        line for line in text.split("\n") if not _PAGEBREAK_RE.match(line)
    )


def build_front_matter(document):
    """``short-title`` を ``title`` として補ったフロント マターを組み立てる。

    mkdocs はナビゲーションとページ タイトルに ``title`` を使用します。
    docsfw の ``short-title`` は索引とナビゲーションだけに効くため、完全には一致しません。
    """
    short_title = resolve_short_title(document.fields, PREVIEW_LANG, PREVIEW_DETAILS)
    if not short_title or document.fields.get("title"):
        return document.front_matter

    escaped = short_title.replace("\\", "\\\\").replace('"', '\\"')
    title_line = 'title: "{}"'.format(escaped)

    if not document.front_matter:
        return "---\n{}\n---".format(title_line)

    lines = document.front_matter.split("\n")
    return "\n".join(lines[:-1] + [title_line, lines[-1]])


# ----------------------------------------------------------------------------
# 書き出し
# ----------------------------------------------------------------------------

def read_text(path):
    """UTF-8 として読み込み、改行を LF に正規化する。"""
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read().replace("\r\n", "\n").replace("\r", "\n")


def write_if_changed(path, content):
    """内容が変わったときだけ書き出す。

    mkdocs の監視が不要な再ビルドを起こさないよう、更新時刻を保つことが目的です。
    """
    if os.path.isfile(path):
        try:
            if read_text(path) == content:
                return False
        except OSError:
            pass

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return True


def copy_asset_if_changed(src, dst):
    """内容が変わったときだけアセットをコピーする。"""
    if os.path.isfile(dst):
        src_stat = os.stat(src)
        dst_stat = os.stat(dst)
        if src_stat.st_size == dst_stat.st_size and int(src_stat.st_mtime) == int(dst_stat.st_mtime):
            return False

    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    shutil.copy2(src, dst)
    return True


def parse_publocal_order(path):
    """``publocal.yaml`` の ``order:`` を一覧として読み出す。"""
    order = []
    in_order = False
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\r\n")
            if not in_order:
                if re.match(r"^order:\s*(#.*)?$", line):
                    in_order = True
                continue
            if line and not line.startswith((" ", "\t", "-")):
                break
            item = re.match(r"^\s*-\s*(.+?)\s*(?:#.*)?$", line)
            if item:
                order.append(item.group(1).strip().strip("\"'"))
    return order


def generate_nav_files(out_dir, main_mdroot, subfolders, staged_dirs):
    """``publocal.yaml`` の ``order:`` を mkdocs-awesome-nav の ``.nav.yml`` へ変換する。

    本ワークスペースには現在 ``publocal.yaml`` が存在しないため、この経路は
    将来 ``order:`` を導入したときのためのフックです。

    :return: 生成した ``.nav.yml`` の数。
    """
    mapper = PathMapper(main_mdroot, subfolders)
    generated = 0

    for staged_dir in staged_dirs:
        real_dir = mapper.virtual_to_real(staged_dir)
        publocal = os.path.join(real_dir, "publocal.yaml")
        if not os.path.isfile(publocal):
            continue
        order = parse_publocal_order(publocal)
        if not order:
            continue

        entries = []
        for name in order:
            if name.lower() in ("readme.md", "skill.md"):
                name = "index.md"
            entries.append("  - {}".format(name))
        entries.append("  - ...")

        target = os.path.join(out_dir, staged_dir, ".nav.yml") if staged_dir else os.path.join(out_dir, ".nav.yml")
        if write_if_changed(target, "nav:\n" + "\n".join(entries) + "\n"):
            generated += 1

    return generated


def is_vendored(relative):
    """``bin/vendor_assets.py`` が配置したファイルかどうかを返す。"""
    return relative in VENDORED_FILES or relative.startswith(VENDORED_PREFIXES)


def remove_stale(out_dir, keep_relative):
    """前回の実行で作られ、今回は対象外になったファイルを削除する。

    ``bin/vendor_assets.py`` が配置したアセットは削除しません。
    """
    removed = 0
    for dirpath, dirnames, filenames in os.walk(out_dir, topdown=False):
        for filename in filenames:
            full = os.path.join(dirpath, filename)
            relative = _posix(os.path.relpath(full, out_dir))
            if is_vendored(relative):
                continue
            if relative not in keep_relative:
                os.remove(full)
                removed += 1
        for dirname in dirnames:
            full = os.path.join(dirpath, dirname)
            if not os.listdir(full):
                os.rmdir(full)
    return removed


# ----------------------------------------------------------------------------
# メイン
# ----------------------------------------------------------------------------

def stage(workspace, out_dir, config_path, quiet=False):
    """収集から書き出しまでを実行する。

    :return: ``(ドキュメント数, 更新数, 生成した .nav.yml 数)``。
    """
    config = parse_config(config_path)
    md_root_name = config.get("mdRoot") or "docs"
    main_mdroot = os.path.normpath(os.path.join(workspace, md_root_name))
    subfolders = parse_merge_subfolder_docs(config.get("mergeSubfolderDocs"), workspace)
    mapper = PathMapper(main_mdroot, subfolders)

    documents, assets = collect_sources(workspace, main_mdroot, subfolders)

    kept = []
    for document in documents:
        try:
            raw = read_text(document.real_path)
        except OSError as error:
            print("Warning: cannot read {}: {}".format(document.real_path, error))
            continue

        front_matter, body = split_front_matter(raw)
        fields = parse_front_matter_fields(front_matter)
        if is_skipped(fields):
            continue

        document.front_matter = front_matter
        document.fields = fields
        document.body = filter_lang_details(body, PREVIEW_LANG, PREVIEW_DETAILS)
        document.title = (
            resolve_short_title(fields, PREVIEW_LANG, PREVIEW_DETAILS)
            or first_heading(document.body)
            or posixpath.splitext(document.source_name)[0]
        )
        kept.append(document)

    resolve_staged_names(kept)

    index = DocIndex()
    real_to_staged = {}
    for document in kept:
        index.add(document.staged_rel, document.source_name, document.title)
        real_to_staged[_norm_key(document.real_path)] = document.staged_rel
    for real_path, virtual_rel in assets:
        real_to_staged[_norm_key(real_path)] = virtual_rel

    keep_relative = set()
    updated = 0

    for document in kept:
        body = rewrite_links(document.body, document, mapper, real_to_staged)
        body = expand_toc_commands(body, index, document.staged_rel)
        body = strip_collapsible_list_fences(body)
        body = convert_deprecated_alerts(body)
        body = convert_captions(body)
        body = remove_page_breaks(body)

        front_matter = build_front_matter(document)
        content = (front_matter + "\n" + body) if front_matter else body
        if not content.endswith("\n"):
            content += "\n"

        if write_if_changed(os.path.join(out_dir, document.staged_rel), content):
            updated += 1
        keep_relative.add(document.staged_rel)

    for real_path, virtual_rel in assets:
        if copy_asset_if_changed(real_path, os.path.join(out_dir, virtual_rel)):
            updated += 1
        keep_relative.add(virtual_rel)

    staged_dirs = sorted({posixpath.dirname(rel) for rel in keep_relative})
    nav_count = generate_nav_files(out_dir, main_mdroot, subfolders, staged_dirs)
    for staged_dir in staged_dirs:
        candidate = posixpath.join(staged_dir, ".nav.yml") if staged_dir else ".nav.yml"
        if os.path.isfile(os.path.join(out_dir, candidate)):
            keep_relative.add(candidate)

    removed = remove_stale(out_dir, keep_relative)

    if not quiet:
        print("staged: {} documents, {} assets, {} updated, {} removed, {} nav files".format(
            len(kept), len(assets), updated, removed, nav_count))

    return len(kept), updated, nav_count


def main(argv=None):
    parser = argparse.ArgumentParser(description="mkdocs プレビュー用に Markdown をステージングする")
    parser.add_argument("--workspaceFolder", dest="workspace", required=True)
    parser.add_argument("--out", dest="out", default=None,
                        help="ステージング先。既定は <workspaceFolder>/pages/preview/src")
    parser.add_argument("--configFile", dest="config", default=None,
                        help="既定は <workspaceFolder>/.vscode/pub_markdown.config.yaml")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    workspace = os.path.abspath(args.workspace)
    config_path = args.config or os.path.join(workspace, ".vscode", "pub_markdown.config.yaml")
    out_dir = args.out or os.path.join(workspace, "pages", "preview", "src")
    os.makedirs(out_dir, exist_ok=True)

    try:
        stage(workspace, os.path.abspath(out_dir), config_path, quiet=args.quiet)
    except ValueError as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
