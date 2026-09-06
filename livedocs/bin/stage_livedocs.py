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

    python3 stage_livedocs.py --workspaceFolder=/path/to/workspace
    python3 stage_livedocs.py --workspaceFolder=/path/to/workspace --variant en
"""

import argparse
from dataclasses import dataclass
import json
import os
import posixpath
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from expand_toc import DocIndex, expand_toc_commands, collapsible_open_tag, parse_toc_params  # noqa: E402
from git_link import GitLinkResolver, parse_host_provider_map  # noqa: E402
from publish_info import build_publish_info  # noqa: E402
from lang_details_filter import filter_lang_details  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_LIVEDOCS_VARIANT = "ja-details"
LIVEDOCS_VARIANTS = ("ja", "ja-details", "en", "en-details")

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
    "assets/docsfw-responsive-nav.js",
    "assets/docsfw-svg-download.js",
    "assets/docsfw-collapsible-list.js",
    "assets/docsfw-collapsible-list.css",
    "assets/docsfw-code-expander.js",
    "assets/docsfw-code-expander.css",
    "assets/docsfw-livedocs.css",
    "assets/docsfw-pandoc-style.css",
    "assets/docsfw-header-links.css",
    "assets/docsfw-header-meta.css",
    "assets/docsfw-doxygen-icon.svg",
    "assets/docsfw-git-icon.svg",
    "assets/docsfw-github-icon.svg",
    "assets/docsfw-gitlab-icon.svg",
    "assets/docsfw-gitbucket-icon.svg",
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
# figure で包む対象のフェンス。字下げされたフェンス (リスト内など) は
# md_in_html が生の HTML として扱えないため、行頭のものだけを対象にする。
_DIAGRAM_FENCE_RE = re.compile(r"^(?:```+|~~~+)[ \t]*(plantuml|mermaid)\b")
# 段落が画像 1 個だけで構成される行。Pandoc の implicit_figures と同じ条件。
_IMAGE_ONLY_RE = re.compile(
    r"^!\[((?:[^\[\]]|\[[^\]]*\])*)\]"
    r"\(([^()\s]*(?:\([^()]*\)[^()\s]*)*)\)"
    r"[ \t]*(\{[^}]*\})?[ \t]*$"
)
_ATTR_TAIL_RE = re.compile(r"\s*\{#([A-Za-z0-9_:.-]+)\}\s*$")
_DEPRECATED_RE = re.compile(r"^([ \t]*)>[ \t]*\[!DEPRECATED\][ \t]*$")
_COLLAPSIBLE_OPEN_RE = re.compile(r"^:{3,}[ \t]*\{\.collapsible-list(?:[ \t][^}]*)?\}[ \t]*$")
_COLLAPSIBLE_CLOSE_RE = re.compile(r"^:{3,}[ \t]*$")
_DOXYGEN_REL_RE = re.compile(r"(?:\.\./)+doxygen/")

DOCUMENT_LINK_EXTENSIONS = (".md", ".markdown", ".rmd", ".tmd", ".rst")


def parse_livedocs_variant(variant):
    """バリアント名を ``(lang, details, variant)`` へ分解する。

    ``ja`` / ``en`` は詳細ブロックを除き、``*-details`` は残します。
    ``make docs`` の出力ディレクトリ名と同じ 4 値だけを受け付けます。
    """
    name = (variant or DEFAULT_LIVEDOCS_VARIANT).strip()
    if name not in LIVEDOCS_VARIANTS:
        raise ValueError(
            "unknown livedocs variant: {} (expected {})".format(
                name, ", ".join(LIVEDOCS_VARIANTS)
            )
        )
    if name.endswith("-details"):
        return name[: -len("-details")], True, name
    return name, False, name


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


def is_flag_enabled(config, key):
    """真偽値の設定を判定する。未指定は有効 (docsfw と同じ)。"""
    value = (config or {}).get(key, "")
    if value == "":
        return True
    return value.strip().lower() == "true"


def is_git_link_enabled(config):
    """``gitLinkEnable`` を判定する。未指定は有効 (docsfw と同じ)。"""
    return is_flag_enabled(config, "gitLinkEnable")


def is_auto_set_author_enabled(config):
    """``autoSetAuthor`` を判定する。未指定は有効 (docsfw と同じ)。"""
    return is_flag_enabled(config, "autoSetAuthor")


def is_auto_set_date_enabled(config):
    """``autoSetDate`` を判定する。未指定は有効 (docsfw と同じ)。"""
    return is_flag_enabled(config, "autoSetDate")


def create_git_resolver(config, config_path):
    """git 由来の情報が 1 つでも要るなら ``GitLinkResolver`` を作る。不要なら ``None``。

    単一ページ リンク、発行者、発行日時は同じリポジトリ走査を共有します。
    このため ``gitLinkEnable`` が無効でも、``autoSetAuthor`` か ``autoSetDate`` が
    有効であれば resolver を作ります。blob URL を出すかどうかは
    ``is_git_link_enabled()`` で別に判定します。

    自己ホスト用の ``gitLinkHostProvider`` は、``pub_markdown.config.yaml`` と
    同じ ``.vscode/`` にある ``git_link.yaml`` から読みます。
    """
    if not (is_git_link_enabled(config)
            or is_auto_set_author_enabled(config)
            or is_auto_set_date_enabled(config)):
        return None
    git_link_config = parse_config(
        os.path.join(os.path.dirname(config_path), "git_link.yaml")
    )
    return GitLinkResolver(parse_host_provider_map(git_link_config.get("gitLinkHostProvider")))


def resolve_document_git_link(document, workspace, resolver, enabled=True):
    """``document`` の Git 単一ページ リンクを解決し、結果を保持させる。

    doxyfw 生成 md はフロント マターに ``git-origin`` (元ソースのワークスペース
    相対パス) を持ちます。実体があれば md 自身ではなく元ソースを解決対象にします
    (``pub_markdown_core.sh`` の ``resolve_git_link_target`` と同じ)。
    """
    document.git_url = ""
    document.git_provider = ""
    if resolver is None or not enabled:
        return

    target = document.real_path
    origin = document.fields.get("git-origin")
    if origin:
        candidate = os.path.join(workspace, origin.replace("\\", "/"))
        if os.path.isfile(candidate):
            target = candidate

    url, provider = resolver.resolve(target)
    if url:
        document.git_url = url
        document.git_provider = provider


def resolve_document_publish_info(document, resolver, auto_author=True, auto_date=True):
    """``document`` の発行者と発行日時を解決し、結果を保持させる。

    解決対象は ``document.real_path`` 自身です。Git 単一ページ リンクのような
    ``git-origin`` への差し替えは行いません。静的発行も
    ``get_file_author.sh`` / ``get_file_date.sh`` へ発行対象の md をそのまま渡すため、
    doxyfw の生成 md では ``date`` がファイルの更新時刻へ、``author`` が空になります。
    その挙動もそろえます。
    """
    document.publish_author = ""
    document.publish_date = ""
    if resolver is None or not (auto_author or auto_date):
        return

    facts = resolver.resolve_publish_facts(document.real_path)
    document.publish_author, document.publish_date = build_publish_info(
        document.real_path, facts, auto_author, auto_date
    )


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
        self.git_url = ""
        self.git_provider = ""
        self.publish_author = ""
        self.publish_date = ""


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

    論理ツリー外の相対リンクは、プレビューへ外部ファイルを追加せず、表示文字列
    と元のリンク先を残した非リンクの参照へ変換します。画像リンクは表示を壊さ
    ないため、この変換の対象外です。
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
        if rewritten is not None:
            return "{}[{}]({})".format(bang, label, rewritten)

        path, _, _ = _split_link_suffix(target)
        if (
            bang
            or not _is_relative_link_path(path)
            or _DOXYGEN_REL_RE.match(path)
        ):
            return match.group(0)
        return "{} (`{}`)".format(label, target)

    return _apply_outside_fences(text, lambda line: _LINK_RE.sub(replace, line))


def rewrite_doxygen_livedocs_links(text):
    """docsfw 発行レイアウト向けの Doxygen 相対リンクを ``/doxygen/`` へ写す。

    ``../../../doxygen/cplat_public/index.html`` や生 HTML の
    ``href="../../../../doxygen/.../dependency/index.html"`` が対象。
    mkdocs は ``use_directory_urls: true`` のため ``../`` の段数が合わず、
    サイトルート絶対パスへ置き換えて WSGI マウントへ届ける。
    """
    if "doxygen/" not in text:
        return text
    return _apply_outside_fences(text, lambda line: _DOXYGEN_REL_RE.sub("/doxygen/", line))


def _split_link_suffix(target):
    """リンク先を ``(パス, 区切り, アンカーやクエリ)`` に分割する。"""
    match = re.match(r"^([^#?]*)(.*)$", target)
    return match.group(1), "", match.group(2)


def _is_relative_link_path(path):
    """通常の相対ファイル参照として扱えるパスかどうかを返す。"""
    return bool(path) and not path.startswith("/") and not re.match(
        r"^[A-Za-z][A-Za-z0-9+.-]*:", path
    )


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


def _split_caption_label(paragraph):
    """キャプション段落から ``{#fig:xxx}`` ラベルを取り出す。

    :return: ``(ラベル, ラベルを取り除いた段落)``。ラベルが無ければ ``("", 段落)``。
    """
    label_match = _ATTR_TAIL_RE.search(paragraph[-1])
    if not label_match:
        return "", paragraph
    trimmed = list(paragraph)
    trimmed[-1] = trimmed[-1][: label_match.start()].rstrip()
    return label_match.group(1), trimmed


def _figure_open_tag(label):
    """``docsfw-figure`` の開始タグを組み立てる。"""
    if label:
        return '<figure class="docsfw-figure" id="{}" markdown="1">'.format(label)
    return '<figure class="docsfw-figure" markdown="1">'


def _figcaption_lines(paragraph):
    """キャプション段落を ``figcaption`` の行へ変換する。

    ``markdown="span"`` は内側へ ``<p>`` を作らないため、pandoc 発行版の
    ``figcaption`` と同じ構造になります。複数行のキャプションは ``nl2br`` に
    より ``<br>`` になり、これも pandoc 発行版と一致します。
    """
    lines = list(paragraph)
    lines[0] = '<figcaption class="docsfw-caption" markdown="span">' + lines[0]
    lines[-1] = lines[-1] + "</figcaption>"
    return lines


def convert_captions(text):
    """``Table:`` / ``CodeBlock:`` キャプションを mkdocs 向けの記法へ変換する。

    docsfw は Pandoc のキャプション記法として扱いますが、mkdocs では次の 2 通り
    で表現します。

    - PlantUML / Mermaid フェンスの直後に置かれた ``CodeBlock:`` は、フェンスと
      ともに ``md_in_html`` の ``figure`` へ包みます。pandoc 発行版が図に
      ``<figure>`` と枠を与えるのと同じ見た目になります。
    - それ以外は ``.docsfw-caption`` クラスを付けた段落として表現します。

    ``{#fig:xxx}`` などのラベルは id として残します。

    attr_list はブロック要素の属性を、段落の直後の属性だけの行から読み取ります。
    """
    lines = text.split("\n")
    out = []
    fence = None
    index = 0
    # 直前に閉じた図フェンスの ``(out 上の開始位置, 終了位置, 言語)``。
    diagram_block = None
    fence_start = None
    fence_lang = None

    while index < len(lines):
        line = lines[index]
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
                diagram_match = _DIAGRAM_FENCE_RE.match(line)
                fence_start = len(out) if diagram_match else None
                fence_lang = diagram_match.group(1) if diagram_match else None
                diagram_block = None
            elif fence == marker:
                fence = None
                if fence_start is not None:
                    diagram_block = (fence_start, len(out) + 1, fence_lang)
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

            label, paragraph = _split_caption_label(paragraph)

            if caption_match.group(1) == "CodeBlock" and _is_after_diagram(out, diagram_block):
                block_start, block_end, _lang = diagram_block
                figure = [_figure_open_tag(label), ""]
                figure.extend(out[block_start:block_end])
                figure.append("")
                figure.extend(_figcaption_lines(paragraph))
                figure.extend(["", "</figure>"])
                # md_in_html は生の HTML ブロックの前後に空行を必要とする。
                if block_start > 0 and out[block_start - 1].strip():
                    figure.insert(0, "")
                out[block_start:] = figure
                if index < len(lines) and lines[index].strip():
                    out.append("")
                diagram_block = None
                continue

            attrs = [".docsfw-caption"]
            if label:
                attrs.insert(0, "#" + label)
            # attr_list はブロック要素に対して、属性だけの行を要求する。
            paragraph.append("{{: {} }}".format(" ".join(attrs)))
            out.extend(paragraph)
            diagram_block = None
            continue

        if line.strip():
            diagram_block = None
        out.append(line)
        index += 1

    return "\n".join(out)


def _is_after_diagram(out, diagram_block):
    """キャプションの直前が図フェンスだけであるかを判定する。"""
    if diagram_block is None:
        return False
    _start, end, _lang = diagram_block
    tail = out[end:]
    return bool(tail) and not any(entry.strip() for entry in tail)


def convert_implicit_figures(text):
    """画像 1 個だけの段落を ``figure`` へ変換する。

    Pandoc の ``implicit_figures`` に相当します。Python-Markdown には同等の
    機能が無いため、``md_in_html`` の ``figure`` としてステージング時に組み
    立てます。代替テキストが空の画像は、pandoc 発行版と同じく変換しません。

    画像を Markdown 記法のまま ``figure`` の内側へ置くのは、mkdocs の相対パス
    解決を効かせるためです。生の ``<img>`` を出力すると、``use_directory_urls``
    により ``index.md`` 以外のページで画像のパスが解決できなくなります。
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

        image_match = _IMAGE_ONLY_RE.match(line)
        at_paragraph_start = not out or not out[-1].strip()
        at_paragraph_end = index + 1 >= len(lines) or not lines[index + 1].strip()
        alt = image_match.group(1).strip() if image_match else ""
        if image_match and alt and at_paragraph_start and at_paragraph_end:
            label, attrs = _split_image_attrs(image_match.group(3))
            image = "![{}]({}){}".format(image_match.group(1), image_match.group(2), attrs)
            out.append(_figure_open_tag(label))
            out.append("")
            out.append(image)
            out.append("")
            out.extend(_figcaption_lines([alt]))
            out.append("")
            out.append("</figure>")
            index += 1
            continue

        out.append(line)
        index += 1

    return "\n".join(out)


def _split_image_attrs(attrs):
    """画像の属性から ``{#fig:xxx}`` ラベルを取り出す。

    :return: ``(ラベル, 画像へ残す属性文字列)``。
    """
    if not attrs:
        return "", ""
    tokens = attrs[1:-1].split()
    labels = [token[1:] for token in tokens if token.startswith("#")]
    rest = [token for token in tokens if not token.startswith("#")]
    label = labels[0] if labels else ""
    return label, ("{" + " ".join(rest) + "}") if rest else ""


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


def convert_collapsible_list_fences(text):
    """手動 fenced div を Markdown を解析する HTML コンテナーへ変換する。"""
    out = []
    stack = []
    fence = None
    for line in text.split("\n"):
        match = _FENCE_RE.match(line)
        if match:
            run = match.group(1)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence) and not line.strip()[len(run):].strip():
                fence = None
            out.append(line)
            continue
        if fence is not None:
            out.append(line)
            continue
        if _COLLAPSIBLE_OPEN_RE.match(line):
            params = parse_toc_params(line[line.index("{") + 1:line.rindex("}")])
            stack.append(len(line) - len(line.lstrip(":")))
            out.extend([collapsible_open_tag(params["open-level"]), ""])
        elif stack and _COLLAPSIBLE_CLOSE_RE.match(line) and len(line.strip()) >= stack[-1]:
            stack.pop()
            out.extend(["", "</div>", ""])
        else:
            out.append(line)
    # Pandoc と同じく文書末尾で閉じて、後続 HTML への漏れを防ぐ。
    for _ in stack:
        out.extend(["", "</div>"])
    return "\n".join(out)


def remove_page_breaks(text):
    """``\\newpage`` と ``\\pagebreak`` の行を取り除く。"""
    if "\\newpage" not in text and "\\pagebreak" not in text:
        return text
    return "\n".join(
        line for line in text.split("\n") if not _PAGEBREAK_RE.match(line)
    )


def _front_matter_line(key, value):
    """フロント マターの 1 行を、値を引用符で囲んで組み立てる。"""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return '{}: "{}"'.format(key, escaped)


def build_front_matter(document, lang, details):
    """ナビゲーション用の ``title`` と Git リンクを補ったフロント マターを組み立てる。

    mkdocs はナビゲーションとページ タイトルに ``title`` を使用します。
    docsfw の ``short-title`` は索引とナビゲーションだけに効くため、完全には一致しません。
    索引ページでは、フォルダーの表示名に使えるように最初の H1 も補完対象にします。

    ``git-url`` と ``git-provider`` は、テーマの ``partials/header.html`` が
    ``page.meta`` から読んで「ソースを開く」リンクにします。

    ``author`` と ``date`` は同じくヘッダーの発行者と発行日時になります。
    静的発行の ``set-meta.lua`` が文書側のメタデータを上書きしないことにそろえ、
    ソースのフロント マターに同じキーがある場合は補いません。
    """
    added = []

    title = resolve_short_title(document.fields, lang, details)
    if not title and posixpath.basename(document.staged_rel).lower() == "index.md":
        title = first_heading(document.body)
    if title and not document.fields.get("title"):
        added.append(_front_matter_line("title", title))

    if document.git_url:
        added.append(_front_matter_line("git-url", document.git_url))
        added.append(_front_matter_line("git-provider", document.git_provider))

    if document.publish_author and not document.fields.get("author"):
        added.append(_front_matter_line("author", document.publish_author))
    if document.publish_date and not document.fields.get("date"):
        added.append(_front_matter_line("date", document.publish_date))

    if not added:
        return document.front_matter

    if not document.front_matter:
        return "---\n{}\n---".format("\n".join(added))

    lines = document.front_matter.split("\n")
    return "\n".join(lines[:-1] + added + [lines[-1]])


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


# ルート .nav.yml の並び。insert-toc.sh と同じく、ファイルとフォルダーを
# ソース名 (*.md / フォルダー名) の大小文字無視アルファベット順で混在させる。
ROOT_NAV_SORT_YAML = """sort:
  by: filename
  direction: asc
  type: alphabetical
  ignore_case: true
  sections: mixed"""


def generate_nav_files(out_dir, main_mdroot, subfolders, staged_dirs):
    """``publocal.yaml`` の ``order:`` を mkdocs-awesome-nav の ``.nav.yml`` へ変換する。

    ルートには索引ページのタイトルをフォルダー表示名として使う設定を常に生成します。
    あわせて、本文 ``\\toc`` と同じ並び (ファイルとフォルダーの混在、大小文字を
    無視したアルファベット順) を ``sort:`` として出します。子ディレクトリは継承します。
    索引タイトルがないディレクトリでは、元の名前を表示名に指定します。
    ``publocal.yaml`` に ``order:`` があるディレクトリでは、並び順も生成します。

    :return: 生成した ``.nav.yml`` の数。
    """
    mapper = PathMapper(main_mdroot, subfolders)
    generated = 0

    for staged_dir in sorted(set(staged_dirs) | {""}):
        real_dir = mapper.virtual_to_real(staged_dir)
        publocal = os.path.join(real_dir, "publocal.yaml")
        order = parse_publocal_order(publocal) if os.path.isfile(publocal) else []
        lines = []
        if not staged_dir:
            lines.append("use_index_title: true")
            lines.append(ROOT_NAV_SORT_YAML)
        else:
            index_path = os.path.join(out_dir, staged_dir, "index.md")
            index_title = None
            if os.path.isfile(index_path):
                front_matter, _ = split_front_matter(read_text(index_path))
                index_title = parse_front_matter_fields(front_matter).get("title")
            if not index_title:
                lines.append("title: " + json.dumps(posixpath.basename(staged_dir), ensure_ascii=False))
            else:
                lines.append("use_index_title: true")
        if order:
            lines.append("nav:")
            for name in order:
                if name.lower() in ("readme.md", "skill.md"):
                    name = "index.md"
                lines.append("  - {}".format(name))
            lines.append("  - ...")

        target = os.path.join(out_dir, staged_dir, ".nav.yml") if staged_dir else os.path.join(out_dir, ".nav.yml")
        if write_if_changed(target, "\n".join(lines) + "\n"):
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
# 索引 (mkdocs serve 中の 1 ファイル単位の再ステージングでキャッシュとして使い回す)
# ----------------------------------------------------------------------------

class StageIndex:
    """``build_stage_index`` の結果をまとめたコンテナ。

    ``mapper``/``index``/``real_to_staged`` はワークスペース全体の走査を経て
    構築されるため、``on_serve`` フック等はこれをプロセス内にキャッシュし、
    1 ファイルだけの再ステージング (``stage_single``) に使い回す。

    ``git_resolver`` もリポジトリ単位の情報をキャッシュしているため、同じ寿命で
    使い回す。単一ページ リンク、発行者、発行日時のいずれも無効な場合は ``None``。
    どの情報を出すかは ``git_link_enabled``/``auto_set_author``/``auto_set_date`` が
    個別に決める。
    """

    def __init__(self, workspace, config_path, main_mdroot, subfolders,
                 mapper, kept, assets, index, real_to_staged, by_real_path,
                 lang, details, variant, git_resolver=None,
                 git_link_enabled=True, auto_set_author=True, auto_set_date=True):
        self.workspace = workspace
        self.config_path = config_path
        self.main_mdroot = main_mdroot
        self.subfolders = subfolders
        self.mapper = mapper
        self.kept = kept
        self.assets = assets
        self.index = index
        self.real_to_staged = real_to_staged
        self.by_real_path = by_real_path
        self.lang = lang
        self.details = details
        self.variant = variant
        self.git_resolver = git_resolver
        self.git_link_enabled = git_link_enabled
        self.auto_set_author = auto_set_author
        self.auto_set_date = auto_set_date


def build_stage_index(workspace, config_path, lang="ja", details=True,
                      variant=DEFAULT_LIVEDOCS_VARIANT):
    """ワークスペース全体を走査し、索引 (mapper/index/real_to_staged) を構築する。"""
    config = parse_config(config_path)
    md_root_name = config.get("mdRoot") or "docs"
    main_mdroot = os.path.normpath(os.path.join(workspace, md_root_name))
    subfolders = parse_merge_subfolder_docs(config.get("mergeSubfolderDocs"), workspace)
    mapper = PathMapper(main_mdroot, subfolders)
    git_resolver = create_git_resolver(config, config_path)
    git_link_enabled = is_git_link_enabled(config)
    auto_set_author = is_auto_set_author_enabled(config)
    auto_set_date = is_auto_set_date_enabled(config)

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
        document.body = filter_lang_details(body, lang, details)
        document.title = (
            resolve_short_title(fields, lang, details)
            or first_heading(document.body)
            or posixpath.splitext(document.source_name)[0]
        )
        resolve_document_git_link(document, workspace, git_resolver, git_link_enabled)
        resolve_document_publish_info(
            document, git_resolver, auto_set_author, auto_set_date
        )
        kept.append(document)

    resolve_staged_names(kept)

    index = DocIndex()
    real_to_staged = {}
    by_real_path = {}
    for document in kept:
        index.add(document.staged_rel, document.source_name, document.title)
        key = _norm_key(document.real_path)
        real_to_staged[key] = document.staged_rel
        by_real_path[key] = document
    for real_path, virtual_rel in assets:
        real_to_staged[_norm_key(real_path)] = virtual_rel

    return StageIndex(
        workspace=workspace,
        config_path=config_path,
        main_mdroot=main_mdroot,
        subfolders=subfolders,
        mapper=mapper,
        kept=kept,
        assets=assets,
        index=index,
        real_to_staged=real_to_staged,
        by_real_path=by_real_path,
        lang=lang,
        details=details,
        variant=variant,
        git_resolver=git_resolver,
        git_link_enabled=git_link_enabled,
        auto_set_author=auto_set_author,
        auto_set_date=auto_set_date,
    )


def _render_document(document, container):
    """1 ドキュメント分の変換パイプラインを実行し、書き出す内容を返す。"""
    body = rewrite_links(document.body, document, container.mapper, container.real_to_staged)
    body = rewrite_doxygen_livedocs_links(body)
    body = expand_toc_commands(body, container.index, document.staged_rel)
    body = convert_collapsible_list_fences(body)
    body = convert_deprecated_alerts(body)
    body = convert_captions(body)
    body = convert_implicit_figures(body)
    body = remove_page_breaks(body)

    front_matter = build_front_matter(document, container.lang, container.details)
    content = (front_matter + "\n" + body) if front_matter else body
    if not content.endswith("\n"):
        content += "\n"
    return content


def write_documents(container, out_dir):
    """索引済みの全ドキュメントとアセットを変換・書き出す。

    :return: ``(更新数, 書き出したステージング相対パスの集合)``。
    """
    keep_relative = set()
    updated = 0

    for document in container.kept:
        content = _render_document(document, container)
        if write_if_changed(os.path.join(out_dir, document.staged_rel), content):
            updated += 1
        keep_relative.add(document.staged_rel)

    for real_path, virtual_rel in container.assets:
        if copy_asset_if_changed(real_path, os.path.join(out_dir, virtual_rel)):
            updated += 1
        keep_relative.add(virtual_rel)

    return updated, keep_relative


@dataclass(frozen=True)
class StageSingleResult:
    """単一ファイル ステージングの結果。"""

    found: bool
    updated: bool


@dataclass(frozen=True)
class StageResult:
    """構築済み索引を使った全体ステージングの結果。"""

    document_count: int
    updated: int
    removed: int
    nav_count: int

    @property
    def changed(self):
        """ステージング先に変更があったかどうかを返す。"""
        return self.updated > 0 or self.removed > 0 or self.nav_count > 0


def stage_single(container, out_dir, real_path):
    """1 ファイルだけを軽量に再ステージングする。

    ``container`` (``build_stage_index`` の戻り値) にキャッシュされた索引
    (``mapper``/``index``/``real_to_staged``) をそのまま使い回し、対象ファイル
    自身の front matter 解析から変換・書き出しまでだけをやり直す。
    ワークスペース全体の再走査 (``collect_sources``) は行わない。

    索引そのもの (``\\toc`` の一覧やリンク解決表、README/SKILL の index.md
    昇格判定) は更新しないため、対象ファイル自身のタイトル変更や、対象
    ファイルへリンクしている他ページの表示は最新化されない。呼び出し元は、
    新規ファイルの追加やファイル一覧の変化を検知した場合、あるいはこの
    ズレを解消したい場合に ``build_stage_index`` + ``write_documents`` による
    フル ステージングへフォールバックすること。

    :return: 対象の有無と、ステージング先を更新したかどうか。
    """
    document = container.by_real_path.get(_norm_key(real_path))
    if document is None:
        return StageSingleResult(found=False, updated=False)

    try:
        raw = read_text(real_path)
    except OSError as error:
        print("Warning: cannot read {}: {}".format(real_path, error))
        return StageSingleResult(found=True, updated=False)

    front_matter, body = split_front_matter(raw)
    fields = parse_front_matter_fields(front_matter)
    if is_skipped(fields):
        # 新たに pub_markdown.skip: true になった場合は書き出さない。
        # 既存の staged ファイルは、次回のフル ステージングの remove_stale が掃除する。
        return StageSingleResult(found=True, updated=False)

    document.front_matter = front_matter
    document.fields = fields
    document.body = filter_lang_details(body, container.lang, container.details)
    document.title = (
        resolve_short_title(fields, container.lang, container.details)
        or first_heading(document.body)
        or posixpath.splitext(document.source_name)[0]
    )
    resolve_document_git_link(
        document, container.workspace, container.git_resolver, container.git_link_enabled
    )
    resolve_document_publish_info(
        document, container.git_resolver,
        container.auto_set_author, container.auto_set_date,
    )

    content = _render_document(document, container)
    updated = write_if_changed(os.path.join(out_dir, document.staged_rel), content)
    if posixpath.basename(document.staged_rel) == "index.md":
        nav_updated = generate_nav_files(
            out_dir, container.main_mdroot, container.subfolders,
            [posixpath.dirname(document.staged_rel)],
        )
        updated = updated or nav_updated > 0
    return StageSingleResult(found=True, updated=updated)


# ----------------------------------------------------------------------------
# メイン
# ----------------------------------------------------------------------------

def stage_index(container, out_dir, quiet=False):
    """構築済み索引から全ドキュメントをステージングする。

    :return: ステージング先の更新、削除、ナビゲーション生成を含む結果。
    """
    updated, keep_relative = write_documents(container, out_dir)

    staged_dirs = {""}
    for rel in keep_relative:
        directory = posixpath.dirname(rel)
        while directory:
            staged_dirs.add(directory)
            directory = posixpath.dirname(directory)
    staged_dirs = sorted(staged_dirs)
    nav_count = generate_nav_files(out_dir, container.main_mdroot, container.subfolders, staged_dirs)
    for staged_dir in staged_dirs:
        candidate = posixpath.join(staged_dir, ".nav.yml") if staged_dir else ".nav.yml"
        if os.path.isfile(os.path.join(out_dir, candidate)):
            keep_relative.add(candidate)

    removed = remove_stale(out_dir, keep_relative)

    if not quiet:
        print("staged: variant {}, {} documents, {} assets, {} updated, {} removed, {} nav files".format(
            container.variant, len(container.kept), len(container.assets), updated, removed, nav_count))

    return StageResult(
        document_count=len(container.kept),
        updated=updated,
        removed=removed,
        nav_count=nav_count,
    )


def stage(workspace, out_dir, config_path, quiet=False, lang="ja", details=True,
          variant=DEFAULT_LIVEDOCS_VARIANT):
    """収集から書き出しまでを実行する (フル ステージング)。

    :return: ``(ドキュメント数, 更新数, 生成した .nav.yml 数)``。
    """
    container = build_stage_index(
        workspace, config_path, lang=lang, details=details, variant=variant
    )
    result = stage_index(container, out_dir, quiet=quiet)
    return result.document_count, result.updated, result.nav_count


def main(argv=None):
    parser = argparse.ArgumentParser(description="mkdocs プレビュー用に Markdown をステージングする")
    parser.add_argument("--workspaceFolder", dest="workspace", required=True)
    parser.add_argument("--out", dest="out", default=None,
                        help="ステージング先。既定は <workspaceFolder>/pages/livedocs/src")
    parser.add_argument("--configFile", dest="config", default=None,
                        help="既定は <workspaceFolder>/.vscode/pub_markdown.config.yaml")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--variant",
        default=DEFAULT_LIVEDOCS_VARIANT,
        help="ja / ja-details / en / en-details (default: ja-details)",
    )
    args = parser.parse_args(argv)

    workspace = os.path.abspath(args.workspace)
    config_path = args.config or os.path.join(workspace, ".vscode", "pub_markdown.config.yaml")
    out_dir = args.out or os.path.join(workspace, "pages", "livedocs", "src")
    os.makedirs(out_dir, exist_ok=True)

    try:
        lang, details, variant = parse_livedocs_variant(args.variant)
        stage(
            workspace,
            os.path.abspath(out_dir),
            config_path,
            quiet=args.quiet,
            lang=lang,
            details=details,
            variant=variant,
        )
    except ValueError as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
