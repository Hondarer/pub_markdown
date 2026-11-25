"""表のキャプション (Table: 段落) の位置を判定し、表の直前へ移す。

docsfw の表のキャプションは、空行を挟んで表の直前に置く Table: 段落で指定する。
Pandoc の table_captions 拡張は表の前後どちらの Table: も受け付けるが、表が連続
すると後置きを優先するため、docsfw は前置きだけを受け付ける。

このモジュールは Markdown と、C/C++ の Doxygen コメント (``/** ... */`` の
`` * `` 行) を対象に、次の 2 つの規則で Table: 段落を直前の表の前へ移す。

- 既定の規則: 直前のブロックが同じ字下げの表で、直後のブロックが表でない
  Table: 段落を移す。直後が表の Table: 段落は、表に挟まれていても前置きとして
  正しいため変更しない。
- 移行の規則 (``migrate=True``): 表の直後の Table: 段落を、直後に表が続くか
  どうかにかかわらず、すべて直前の表のキャプションとして移す。後置きだけで
  書かれた文書を前置きへ移行するときにだけ使う。前置きで書かれた文書に適用
  すると、表に挟まれた Table: を前の表へ付け替えてしまう。

フェンス付きコード ブロック、HTML コメント、Doxygen の ``@code`` などの中は
対象外とする。Doxygen コメントの行頭の構造コマンド (``@par``、``@parblock``、
``@endparblock`` など) の行は、段落の区切りとして扱い、移動の対象に含めない。
"""

import re
from typing import List, Sequence, Tuple

_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_DOXY_FENCE_START_RE = re.compile(r"^\s*[@\\](code|verbatim|startuml|dot|msc)\b")
_DOXY_FENCE_END_RE = re.compile(r"^\s*[@\\](endcode|endverbatim|enduml|enddot|endmsc)\b")
_TABLE_SEPARATOR_RE = re.compile(
    r"^(?=[^\n]*\|)[ \t]*\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$"
)
_GRID_BORDER_RE = re.compile(r"^[ \t]*\+(?:[-=:]+\+)+[ \t]*$")
_CAPTION_RE = re.compile(r"^[ \t]*Table:")
_DOXY_LINE_RE = re.compile(r"^([ \t]*\*)(?!/)(.*)$")
# 行頭の Doxygen コマンド (@par、@parblock、@endparblock、@param など) は段落を区切る。
# 文中に置くインライン コマンドだけは、段落の一部として扱う。
_DOXY_COMMAND_RE = re.compile(r"^\s*[@\\]([A-Za-z]+|\{|\})")
_DOXY_INLINE_COMMANDS = frozenset(("a", "b", "c", "e", "em", "p", "ref", "link", "endlink", "anchor"))

# 行の種別。TEXT はブロックの行、BLANK は空行、BARRIER は判定の対象外の行。
_BLANK, _TEXT, _BARRIER = "blank", "text", "barrier"

SUPPORTED_MODES = ("markdown", "c", "cpp")


def _indent_width(text: str) -> int:
    match = re.match(r"^[ \t]*", text)
    return len(match.group(0).expandtabs(4)) if match else 0


def _is_closing_fence(content: str, fence: str) -> bool:
    match = _FENCE_RE.match(content)
    if not match:
        return False
    marker = match.group(1)
    return marker[0] == fence[0] and len(marker) >= len(fence) and not content.strip()[len(marker):].strip()


def _classify_markdown(lines: Sequence[str]) -> List[Tuple[str, str]]:
    result: List[Tuple[str, str]] = []
    fence = None
    in_html_comment = False
    for line in lines:
        if fence is not None:
            result.append((_BARRIER, line))
            if _is_closing_fence(line, fence):
                fence = None
            continue
        if in_html_comment:
            result.append((_BARRIER, line))
            if "-->" in line:
                in_html_comment = False
            continue
        match = _FENCE_RE.match(line)
        if match:
            fence = match.group(1)
            result.append((_BARRIER, line))
            continue
        if line.lstrip().startswith("<!--") and "-->" not in line:
            in_html_comment = True
            result.append((_BARRIER, line))
            continue
        result.append((_TEXT if line.strip() else _BLANK, line))
    return result


def _classify_doxygen(lines: Sequence[str]) -> List[Tuple[str, str]]:
    result: List[Tuple[str, str]] = []
    in_comment = False
    fence = None
    doxy_fence = False
    for line in lines:
        if not in_comment:
            if "/**" in line or "/*!" in line:
                rest = line.split("/**", 1)[-1].split("/*!", 1)[-1]
                if "*/" not in rest:
                    in_comment = True
            result.append((_BARRIER, line))
            continue
        if "*/" in line:
            in_comment = False
            fence = None
            doxy_fence = False
            result.append((_BARRIER, line))
            continue
        match = _DOXY_LINE_RE.match(line)
        if not match:
            result.append((_BARRIER, line))
            continue
        content = match.group(2)
        if content.startswith(" "):
            content = content[1:]
        if fence is not None or doxy_fence:
            result.append((_BARRIER, content))
            if fence is not None and _is_closing_fence(content, fence):
                fence = None
            if doxy_fence and _DOXY_FENCE_END_RE.match(content):
                doxy_fence = False
            continue
        fence_match = _FENCE_RE.match(content)
        if fence_match:
            fence = fence_match.group(1)
            result.append((_BARRIER, content))
            continue
        if _DOXY_FENCE_START_RE.match(content):
            doxy_fence = True
            result.append((_BARRIER, content))
            continue
        command = _DOXY_COMMAND_RE.match(content)
        if command and command.group(1) not in _DOXY_INLINE_COMMANDS:
            result.append((_BARRIER, content))
            continue
        result.append((_TEXT if content.strip() else _BLANK, content))
    return result


def _segments(kinds: Sequence[Tuple[str, str]]) -> List[Tuple[str, int, int]]:
    """同じ種別の連続した行を (種別, 開始, 終了) の区間にまとめる。"""
    names = {_TEXT: "block", _BLANK: "gap", _BARRIER: "barrier"}
    segments: List[Tuple[str, int, int]] = []
    index = 0
    while index < len(kinds):
        kind = kinds[index][0]
        end = index
        while end < len(kinds) and kinds[end][0] == kind:
            end += 1
        segments.append((names[kind], index, end))
        index = end
    return segments


def _is_table(kinds: Sequence[Tuple[str, str]], segment: Tuple[str, int, int]) -> bool:
    return any(
        _TABLE_SEPARATOR_RE.match(kinds[i][1]) or _GRID_BORDER_RE.match(kinds[i][1])
        for i in range(segment[1], segment[2])
    )


def _is_caption(kinds: Sequence[Tuple[str, str]], segment: Tuple[str, int, int]) -> bool:
    return bool(_CAPTION_RE.match(kinds[segment[1]][1]))


def _same_indent(kinds: Sequence[Tuple[str, str]], left: Tuple[str, int, int], right: Tuple[str, int, int]) -> bool:
    return _indent_width(kinds[left[1]][1]) == _indent_width(kinds[right[1]][1])


def relocate_table_captions(text: str, mode: str, migrate: bool = False) -> Tuple[str, List[Tuple[int, int, int]]]:
    """Table: 段落を直前の表の前へ移す。

    :param text: 改行を ``\\n`` に正規化したテキスト。
    :param mode: ``markdown``、``c``、``cpp`` のいずれか。それ以外は変更しない。
    :param migrate: True なら移行の規則、False なら既定の規則で移す。
    :return: ``(移動後のテキスト, 移動の一覧)``。移動の一覧の各要素は
        ``(キャプションの開始行, 表の開始行, キャプションの終了行)`` で、行番号は
        入力テキストの 1 始まり。
    """
    if mode not in SUPPORTED_MODES:
        return text, []
    lines = text.split("\n")
    kinds = _classify_markdown(lines) if mode == "markdown" else _classify_doxygen(lines)
    segments = _segments(kinds)
    order = list(range(len(segments)))
    moves: List[Tuple[int, int, int]] = []
    k = 0
    while k + 2 < len(order):
        table, gap, caption = segments[order[k]], segments[order[k + 1]], segments[order[k + 2]]
        if (
            table[0] == "block" and gap[0] == "gap" and caption[0] == "block"
            and _is_table(kinds, table) and _is_caption(kinds, caption) and not _is_table(kinds, caption)
            and _same_indent(kinds, table, caption)
        ):
            followed_by_table = False
            if k + 4 < len(order):
                next_gap, following = segments[order[k + 3]], segments[order[k + 4]]
                followed_by_table = (
                    next_gap[0] == "gap" and following[0] == "block"
                    and _is_table(kinds, following) and _same_indent(kinds, caption, following)
                )
            if migrate or not followed_by_table:
                order[k], order[k + 2] = order[k + 2], order[k]
                moves.append((caption[1] + 1, table[1] + 1, caption[2]))
                k += 3
                continue
        k += 1
    if not moves:
        return text, []
    out: List[str] = []
    for index in order:
        _name, start, end = segments[index]
        out.extend(lines[start:end])
    return "\n".join(out), moves


_PANDOC_ALT_CAPTION_RE = re.compile(r"^([ \t]*)(table|)(:)")
_LABEL_TAIL_RE = re.compile(r"\{#([^\s{}]+)\}\s*$")


def prepare_for_pandoc(text: str) -> Tuple[str, List[str]]:
    """Pandoc の table_captions 拡張に渡せるよう、前置きの Table: を表の後ろへ並べ替える。

    Pandoc の table_captions は Table: 段落を表の前後どちらでも取り込み、表が連続
    すると後置きを優先する。前置きの Table: を Lua フィルターで畳み込む方式では、
    解析の時点で Table: が通常の段落になり、箇条書きの項目内では Pandoc がリスト
    全体を段落ごとの表示にしてしまう。元の行の順序が分かるこの段階で後置きへ並べ
    替えれば、Pandoc の解析結果は表の後ろに書いた場合と同じになる。

    - キャプションとして扱う Table: 段落 (空行を挟んで直後に同じ字下げの表が続く
      もの) は、表の後ろへ移す。
    - それ以外の Table: 段落は ``Table\\:`` にエスケープし、警告を返す。
    - 表の直前または直後にある行頭 ``table:`` / ``:`` の段落もエスケープする。

    :param text: 改行を ``\\n`` に正規化した Markdown。
    :return: ``(Pandoc に渡すテキスト, 警告メッセージの一覧)``
    """
    lines = text.split("\n")
    kinds = _classify_markdown(lines)
    segments = _segments(kinds)
    warnings: List[str] = []
    escaped = list(lines)

    def is_block(index: int) -> bool:
        return 0 <= index < len(segments) and segments[index][0] == "block"

    def is_gap(index: int) -> bool:
        return 0 <= index < len(segments) and segments[index][0] == "gap"

    def adjacent_table(index: int, step: int) -> bool:
        return is_gap(index + step) and is_block(index + 2 * step) and _is_table(kinds, segments[index + 2 * step])

    order = list(range(len(segments)))
    k = 0
    while k < len(order):
        index = order[k]
        segment = segments[index]
        if segment[0] != "block":
            k += 1
            continue
        first = segment[1]
        if _is_table(kinds, segment):
            # Table: 行の直後に空行なしで表を書くと、Pandoc は全体を 1 つの段落にする。
            if _is_caption(kinds, segment):
                escaped[first] = lines[first].replace("Table:", "Table\\:", 1)
                warnings.append(
                    f"{first + 1} 行目: 'Table:' 行の直後に表がありません。"
                    "表のキャプションは、空行を挟んで表の直前に記述してください。"
                )
            k += 1
            continue
        if _is_caption(kinds, segment):
            following = index + 2
            if (
                adjacent_table(index, 1)
                and _same_indent(kinds, segment, segments[following])
                and k + 2 < len(order) and order[k + 2] == following
            ):
                label = _LABEL_TAIL_RE.search(lines[segment[2] - 1])
                if label and label.group(1).split(":", 1)[0] != "tbl" and ":" in label.group(1):
                    warnings.append(
                        f"{first + 1} 行目: 'Table:' 行に表以外のラベル接頭辞 '{{#{label.group(1)}}}' が指定されています。"
                    )
                order[k], order[k + 2] = order[k + 2], order[k]
                k += 3
                continue
            escaped[first] = lines[first].replace("Table:", "Table\\:", 1)
            warnings.append(
                f"{first + 1} 行目: 'Table:' 行の直後に表がありません。"
                "表のキャプションは、空行を挟んで表の直前に記述してください。"
            )
        else:
            match = _PANDOC_ALT_CAPTION_RE.match(lines[first])
            if match and (adjacent_table(index, 1) or adjacent_table(index, -1)):
                escaped[first] = lines[first][: match.start(3)] + "\\:" + lines[first][match.end(3):]
        k += 1

    out: List[str] = []
    for index in order:
        _name, start, end = segments[index]
        out.extend(escaped[start:end])
    return "\n".join(out), warnings
