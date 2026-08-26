#!/usr/bin/env python3
r"""``\toc`` コマンドをディレクトリ横断の索引リストへ展開する。

docsfw の ``bin/pandoc-filters/insert-toc.lua`` と ``insert-toc.sh`` のうち、
c-modernization-kit で実際に使用されているパラメーターだけを再実装します。

対応するパラメーターを次に示します。

    depth             走査する深さ。0 は基準ディレクトリの直下のみ。-1 は無制限。
    exclude           除外パターン。複数指定できる。
    basedir           基準ディレクトリ。指定しない場合は自身のディレクトリ。
    exclude-basedir   基準ディレクトリ自体を索引に出さない。
    open-level        docsfw では折り畳みの初期展開段数。本実装では無視する。

出力の書式は insert-toc.sh と同じです。

    - 📄 [ファイル名](パス) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;タイトル
    - 📁 [フォルダー名](パス) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;タイトル
    - 📁 フォルダー名
"""

import posixpath
import re

TOC_LINE_RE = re.compile(r"^[ \t]*\\toc(?:[ \t]+(.*?))?[ \t]*$")
_PARAM_RE = re.compile(r'([A-Za-z][A-Za-z0-9_-]*)=(?:"([^"]*)"|\'([^\']*)\'|([^\s]+))')
_FENCE_RE = re.compile(r"^\s*(```+|~~~+)")

_DESCRIPTION_SEPARATOR = "<br/>" + "&nbsp;" * 5

INDEX_CANDIDATES = ("index.md", "readme.md", "skill.md")


def parse_toc_params(params_str):
    """``\\toc`` に続くパラメーター文字列を辞書へ変換する。"""
    params = {
        "depth": 0,
        "exclude": [],
        "basedir": "",
        "exclude-basedir": False,
    }
    if not params_str:
        return params

    for match in _PARAM_RE.finditer(params_str):
        key = match.group(1)
        value = match.group(2)
        if value is None:
            value = match.group(3)
        if value is None:
            value = match.group(4)

        if key == "depth":
            try:
                params["depth"] = int(value)
            except ValueError:
                pass
        elif key == "exclude":
            params["exclude"].append(value)
        elif key == "basedir":
            params["basedir"] = value.strip("/")
        elif key == "exclude-basedir":
            params["exclude-basedir"] = value.lower() == "true"

    return params


def is_excluded(path, patterns):
    """insert-toc.sh の ``is_excluded`` と同じ規則で除外を判定する。

    ``dir/*`` はディレクトリ配下すべてとディレクトリ自身を除外します。
    それ以外はパスに対する部分文字列マッチングです。
    """
    if not patterns:
        return False

    # 先頭に区切りを付けて、ディレクトリ パターンの境界判定を単純にする。
    probe = "/" + path
    for pattern in patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        if pattern.endswith("/*"):
            dir_pattern = pattern[:-2]
            if probe.endswith("/" + dir_pattern) or ("/" + dir_pattern + "/") in probe:
                return True
        elif pattern in probe:
            return True
    return False


class DocIndex:
    """ステージング済みの仮想ツリーを保持し、索引生成に必要な情報を返す。"""

    def __init__(self):
        # 仮想ディレクトリ (posix、ステージング ルートからの相対。ルートは "")
        self._dir_entries = {}
        self._dir_subdirs = {}

    def add(self, staged_rel, source_name, title):
        """1 ファイルを索引へ登録する。

        :param staged_rel: ステージング後の相対パス (``general/index.md`` など)。
        :param source_name: 元のファイル名 (``README.md`` など)。表示に使う。
        :param title: 説明として表示するタイトル。
        """
        vdir = posixpath.dirname(staged_rel)
        entry = {
            "staged_rel": staged_rel,
            "staged_name": posixpath.basename(staged_rel),
            "source_name": source_name,
            "title": title,
        }
        self._dir_entries.setdefault(vdir, []).append(entry)
        self._register_dir_chain(vdir)

    def _register_dir_chain(self, vdir):
        """``vdir`` とその祖先を親ディレクトリの子として登録する。"""
        current = vdir
        while current:
            parent = posixpath.dirname(current)
            self._dir_subdirs.setdefault(parent, set()).add(posixpath.basename(current))
            self._dir_entries.setdefault(current, [])
            current = parent
        self._dir_entries.setdefault("", [])

    def files_in(self, vdir):
        return self._dir_entries.get(vdir, [])

    def subdirs_in(self, vdir):
        return sorted(self._dir_subdirs.get(vdir, ()), key=str.lower)

    def index_entry(self, vdir):
        """``vdir`` のディレクトリ索引となるエントリーを返す。無ければ ``None``。"""
        for entry in self._dir_entries.get(vdir, []):
            if entry["staged_name"].lower() == "index.md":
                return entry
        return None

    def has_visible_file(self, vdir, patterns):
        """``vdir`` 配下に、除外されずに残るファイルがあるかどうかを返す。"""
        stack = [vdir]
        while stack:
            current = stack.pop()
            for entry in self._dir_entries.get(current, []):
                match_path = posixpath.join(current, entry["source_name"]) if current else entry["source_name"]
                if not is_excluded(match_path, patterns):
                    return True
            for name in self._dir_subdirs.get(current, ()):
                child = posixpath.join(current, name) if current else name
                if not is_excluded(child, patterns):
                    stack.append(child)
        return False


def _entry_line(indent, icon, label, link, title):
    """索引の 1 行を組み立てる。"""
    prefix = "  " * indent
    if link is None:
        return "{}- {} {}".format(prefix, icon, label)
    line = "{}- {} [{}]({})".format(prefix, icon, label, link)
    if title:
        line += " {}{}".format(_DESCRIPTION_SEPARATOR, title)
    return line


def _render_dir(index, vdir, base_dir, level, params, from_dir, lines):
    """``vdir`` の直下を索引へ書き出す。``level`` はインデント段数。"""
    max_depth = params["depth"]
    patterns = params["exclude"]

    children = []
    for name in index.subdirs_in(vdir):
        children.append((name, True))
    for entry in index.files_in(vdir):
        children.append((entry["source_name"], False, entry))

    children.sort(key=lambda item: item[0].lower())

    for child in children:
        name = child[0]
        is_dir = child[1]
        child_path = posixpath.join(vdir, name) if vdir else name
        relative_to_base = posixpath.relpath(child_path, base_dir) if base_dir else child_path

        if max_depth >= 0 and relative_to_base.count("/") > max_depth:
            continue
        if is_excluded(child_path, patterns):
            continue

        if is_dir:
            if not index.has_visible_file(child_path, patterns):
                continue
            dir_index = index.index_entry(child_path)
            if dir_index is None:
                lines.append(_entry_line(level, "📁", name, None, None))
            else:
                link = posixpath.relpath(dir_index["staged_rel"], from_dir) if from_dir else dir_index["staged_rel"]
                lines.append(_entry_line(level, "📁", name, link, dir_index["title"]))
            _render_dir(index, child_path, base_dir, level + 1, params, from_dir, lines)
        else:
            entry = child[2]
            # ディレクトリ索引はフォルダー行に集約されるため、ファイルとしては出さない。
            if entry["staged_name"].lower() == "index.md":
                continue
            link = posixpath.relpath(entry["staged_rel"], from_dir) if from_dir else entry["staged_rel"]
            lines.append(_entry_line(level, "📄", name, link, entry["title"]))


def render_toc(index, source_staged_rel, params):
    """1 個の ``\\toc`` を Markdown の索引リストへ展開する。

    :param index: :class:`DocIndex`。
    :param source_staged_rel: ``\\toc`` を含むファイルのステージング後の相対パス。
    :param params: :func:`parse_toc_params` の戻り値。
    :return: 索引の Markdown 文字列。対象が無い場合は空文字列。
    """
    from_dir = posixpath.dirname(source_staged_rel)
    base_dir = posixpath.join(from_dir, params["basedir"]) if params["basedir"] else from_dir
    base_dir = posixpath.normpath(base_dir) if base_dir else ""
    if base_dir == ".":
        base_dir = ""

    lines = []
    if params["exclude-basedir"]:
        _render_dir(index, base_dir, base_dir, 0, params, from_dir, lines)
    else:
        base_index = index.index_entry(base_dir)
        base_name = posixpath.basename(base_dir) if base_dir else "."
        if base_index is None:
            lines.append(_entry_line(0, "📁", base_name, None, None))
        else:
            link = posixpath.relpath(base_index["staged_rel"], from_dir) if from_dir else base_index["staged_rel"]
            lines.append(_entry_line(0, "📁", base_name, link, base_index["title"]))
        _render_dir(index, base_dir, base_dir, 1, params, from_dir, lines)

    return "\n".join(lines)


def expand_toc_commands(text, index, source_staged_rel):
    r"""``text`` 中の ``\toc`` 行をすべて索引へ置き換える。

    コード フェンスの内側にある ``\toc`` は処理しません。
    """
    if "\\toc" not in text:
        return text

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

        if fence is not None:
            out.append(line)
            continue

        toc_match = TOC_LINE_RE.match(line)
        if toc_match:
            params = parse_toc_params(toc_match.group(1))
            rendered = render_toc(index, source_staged_rel, params)
            if rendered:
                out.append(rendered)
            continue

        out.append(line)

    return "\n".join(out)
