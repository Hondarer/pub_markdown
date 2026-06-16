#!/usr/bin/env python3
"""Frontends for Markdown and source comments."""

import os
import re
from typing import Callable, List, Optional, Sequence, Tuple

from text_style_jp_engine import (
    DiagnosticCollector,
    _needs_space_between,
    _record_step_changes,
    replace_nbsp_with_space,
    style_text,
)


_BACKTICK_PATTERN = re.compile(r"(?<!`)(`+)(?!`)[^\n]*?(?<!`)\1(?!`)")
_ADMONITION_MARKER_PATTERN = re.compile(r"\[![A-Za-z][A-Za-z0-9_-]*\]")
_TASK_LIST_MARKER_PATTERN = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[(?: |x|X)\](?=\s|$)")
_EMPTY_TASK_LIST_MARKER_RE = re.compile(r"^(\s*(?:[-*+]|\d+[.)])\s+)\[(?:\s*)\](?=\s|$)")
_DOXYGEN_COMMAND_PLACEHOLDER_PATTERN = re.compile(
    r"[@\\][A-Za-z_]+(?:\[[^\]\n]*\]|\s+\[[^\]\n]*\])?(?:\s+<[^>\n]+>|\s+\[[^\]\n]*\]|\s+\"[^\n\"]*\")*\s+\{[^{}\n]*\}"
)
_DOXYGEN_MATH_PATTERN = re.compile(r"@f(?:\[[^\n]*?@f\]|\$.*?@f\$)")
_INLINE_CODE_NO_SPACE_FOLLOWERS = frozenset("/・、。，．,.!?！？)]}）］｝」』】〕〉》*_~〜～")
_INLINE_CODE_NO_SPACE_PREFIX_RE = re.compile(r"(?:==|!=|<=|>=|=|:)")
_INLINE_CODE_SPACED_SUFFIX_RE = re.compile(r"(?:`{2,}.+?`{2,}|`[^`\n]+`)( +)(?:==|!=|<=|>=|=|:)")
_INLINE_CODE_WITH_SPACE_BEFORE_SLASH_RE = re.compile(r"(`{2,}.+?`{2,}|`[^`\n]+`)\s+/(`{2,}.+?`{2,}|`[^`\n]+`)")
_INLINE_CODE_WITH_SPACE_AFTER_SLASH_RE = re.compile(r"(`{2,}.+?`{2,}|`[^`\n]+`)/\s+(`{2,}.+?`{2,}|`[^`\n]+`)")
_INLINE_CODE_WITH_SPACE_BEFORE_MIDDLEDOT_RE = re.compile(r"(`{2,}.+?`{2,}|`[^`\n]+`)\s+・")
_INLINE_CODE_WITH_SPACE_AFTER_MIDDLEDOT_RE = re.compile(r"・\s+(`{2,}.+?`{2,}|`[^`\n]+`)")
_WAVE_DASH_SPACE_BEFORE_ONLY_RE = re.compile(r"(`{2,}.+?`{2,}|`[^`\n]+`) +([〜～])(`)")
_WAVE_DASH_SPACE_AFTER_ONLY_RE = re.compile(r"(`{2,}.+?`{2,}|`[^`\n]+`)([〜～]) +(`)")
_INLINE_CODE_IMMEDIATELY_AFTER_COLON_RE = re.compile(r":(?=`+)")
_SUPPLEMENTAL_LABEL_IMMEDIATELY_AFTER_COLON_RE = re.compile(r"^(\s*(?:>\s*)?補足):(?=\S)")
_DOXYGEN_INLINE_COMMAND_PATTERN = re.compile(r"[@\\][A-Za-z_]+(?:\{[^}]*\})?")
_DOXYGEN_REF_TRAILING_JP_PUNCT_PATTERN = re.compile(
    r"[@\\]ref\s+[A-Za-z_][A-Za-z0-9_:~.-]*\s+[、。，．]"
)
_DOXYGEN_REF_MISSING_SPACE_BEFORE_JP_PUNCT_RE = re.compile(
    r"((?:[@\\]ref\s+)[A-Za-z_][A-Za-z0-9_:~.-]*)([、。，．])"
)
_LIST_ITEM_RE = re.compile(r"^\s*([-*+]|\d+[.)]) ")
_UNORDERED_LIST_MARKER_RE = re.compile(r"^(\s*)[*+](?= )")
_TABLE_ROW_RE = re.compile(r"^\s*\|")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|(\s*:?-+:?\s*\|)+\s*$")
_GRID_TABLE_BORDER_RE = re.compile(r"^\s*\+(?:[-=:]+\+)+\s*$")
_GRID_TABLE_ROW_RE = re.compile(r"^\s*\|")
_BLOCKQUOTE_RE = re.compile(r"^\s*>")
_HEADING_RE = re.compile(r"^#{1,6} ")
_HEADING_NUMBER_RE = re.compile(r"^(#{1,6})\s+(\d+(?:\.\d+)*\.?|\(\d+(?:\.\d+)*\))\s+(.+)$")
_COMMENT_TAG_START_RE = re.compile(r"^\s*<!--([A-Za-z0-9_-]+):(?:-->)?\s*$")
_HEADING_COUNTER_PREFIX_RE = re.compile(
    r"^(?:回|回目|章|節|項|個|件|人|日|年|月|時|分|秒|本|台|行|列|ページ|頁|つ|か所|ヶ所|箇所)"
)
_HEADING_LITERAL_NUMBER_PREFIX_RE = re.compile(r"^(?:階層)")
_HEADING_DATE_TOKEN_RE = re.compile(r"^(?:\d{6}|\d{8})$")
_HEADING_INLINE_CODE_RE = re.compile(r"`+([^`\n]+)`+")
_EMPHASIS_PATTERN = re.compile(
    r"(?<!\*)\*\*(?=\S)[^*\n]+?(?<=\S)\*\*(?!\*)"
    r"|(?<!\*)\*(?=\S)[^*\n]+?(?<=\S)\*(?!\*)"
    r"|(?<![A-Za-z0-9_])__(?=\S)[^_\n]+?(?<=\S)__(?![A-Za-z0-9_])"
    r"|(?<![A-Za-z0-9_])_(?=\S)[^_\n]+?(?<=\S)_(?![A-Za-z0-9_])"
)
_CODE_OPERATOR_EXPRESSION_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?:[A-Za-z_][A-Za-z0-9_]*|NULL|nullptr|\d+)"
    r"\s*(?:!=|==|<=|>=)"
    r"\s*(?:[A-Za-z_][A-Za-z0-9_]*|NULL|nullptr|\d+)"
    r"(?![A-Za-z0-9_])"
)
_CODE_LOGICAL_MACRO_EXPRESSION_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"!?[A-Z_][A-Z0-9_]*"
    r"(?:\s*(?:&&|\|\|)\s*!?[A-Z_][A-Z0-9_]*)+"
    r"(?![A-Za-z0-9_])"
)
_CODE_NEGATED_IDENTIFIER_PATTERN = re.compile(r"![A-Z_][A-Z0-9_]*")
_COMMENT_CODE_NEGATION_SPACE_RE = re.compile(r"!\s+([A-Z_][A-Z0-9_]*)")
_CODE_CALL_PREFIX_PATTERN = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*[ \t]*(?=\()")
_CODE_BRACKET_QUANTIFIER_PATTERN = re.compile(r"[^\s\[\]`]+[ \t]*\[[^\]\n`]+\][*+?]?")
_CODE_BIG_O_PATTERN = re.compile(r"\bO\([A-Za-z0-9_+\-*/^ .²³]+\)")
_CODE_BRACE_BLOCK_PATTERN = re.compile(r"\{[A-Za-z0-9_(),;\"' .!=<>*/+\-]*\}")
_CODE_INLINE_COMMENT_TAIL_PATTERN = re.compile(r"[ \t]+//[^\n]*")
_CODE_DOT_NUMERIC_SUFFIX_PATTERN = re.compile(r"(?<=\s)\.\d+\b")
_ASCII_PARENTHETICAL_PATTERN = re.compile(r"\b[A-Za-z0-9_.+-]+(?: [A-Za-z0-9_.+-]+)* \([A-Za-z0-9][A-Za-z0-9 _./+-]*\)")
_COMMENT_ALIGNMENT_SPACES_PATTERN = re.compile(r"(?<=\S) {2,}(?=\S)")
_CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")
_LEADING_WHITESPACE_RE = re.compile(r"^[ \t]*")

_FENCE_LANG_TO_SOURCE_MODE = {
    "c": "c", "h": "c",
    "cpp": "cpp", "c++": "cpp", "cc": "cpp", "cxx": "cpp",
    "hpp": "cpp", "hh": "cpp", "hxx": "cpp",
    "cs": "csharp", "csharp": "csharp",
    "py": "python", "python": "python", "python3": "python",
    "sh": "shell", "bash": "shell", "shell": "shell", "zsh": "shell",
    "make": "make", "makefile": "make", "mk": "make",
}

_MARKDOWN_PROTECTED_PATTERNS = [
    _BACKTICK_PATTERN,
    _ADMONITION_MARKER_PATTERN,
    _TASK_LIST_MARKER_PATTERN,
    _DOXYGEN_COMMAND_PLACEHOLDER_PATTERN,
    _DOXYGEN_MATH_PATTERN,
]
_INLINE_PROTECTED_PATTERNS = [_BACKTICK_PATTERN, _DOXYGEN_MATH_PATTERN]
_COMMENT_CODE_PROTECTED_PATTERNS = [
    _BACKTICK_PATTERN,
    _DOXYGEN_MATH_PATTERN,
    _CODE_BRACE_BLOCK_PATTERN,
    _CODE_OPERATOR_EXPRESSION_PATTERN,
    _CODE_LOGICAL_MACRO_EXPRESSION_PATTERN,
    _CODE_NEGATED_IDENTIFIER_PATTERN,
    _ASCII_PARENTHETICAL_PATTERN,
    _CODE_CALL_PREFIX_PATTERN,
    _CODE_BRACKET_QUANTIFIER_PATTERN,
    _CODE_BIG_O_PATTERN,
    _CODE_INLINE_COMMENT_TAIL_PATTERN,
    _CODE_DOT_NUMERIC_SUFFIX_PATTERN,
    _DOXYGEN_REF_TRAILING_JP_PUNCT_PATTERN,
    _COMMENT_ALIGNMENT_SPACES_PATTERN,
]
_XML_TAG_RE = re.compile(r"(<[^>]+>)")

_DOXYGEN_CODE_STARTS = ("@code", "\\code", "@verbatim", "\\verbatim", "@dot", "\\dot")
_DOXYGEN_CODE_ENDS = ("@endcode", "\\endcode", "@endverbatim", "\\endverbatim", "@enddot", "\\enddot")
_DOXYGEN_LITERAL_LINE_PREFIXES = (
    "@image",
    "\\image",
    "@msc",
    "\\msc",
    "@startuml",
    "\\startuml",
    "@enduml",
    "\\enduml",
    "@htmlonly",
    "\\htmlonly",
    "@endhtmlonly",
    "\\endhtmlonly",
)

_ONE_ARG_DESCRIPTION_COMMANDS = frozenset(
    {
        "param",
        "tparam",
        "retval",
        "def",
        "file",
        "section",
        "subsection",
        "subsubsection",
        "page",
        "defgroup",
        "enum",
        "struct",
        "class",
        "union",
        "typedef",
        "fn",
        "var",
    }
)
_REFERENCE_COMMANDS = frozenset(
    {
        "ingroup",
        "copydoc",
        "copybrief",
        "copydetails",
        "anchor",
        "addtogroup",
        "weakgroup",
    }
)
_ONE_ARG_DESCRIPTION_COMMAND_RE = re.compile(
    r"^([@\\]([A-Za-z_]+)(?:\[[^\]]+\])?)(\s+)(\S+)(.*)$"
)
_REFERENCE_COMMAND_RE = re.compile(r"^([@\\]([A-Za-z_]+)(?:\[[^\]]+\])?)(\s*)(.*)$")
_GENERIC_COMMAND_RE = re.compile(r"^([@\\][A-Za-z_]+(?:\[[^\]]+\])?)(\s*)(.*)$")


def detect_mode_from_path(path: str) -> str:
    basename = os.path.basename(path)
    lower_name = basename.lower()
    _, ext = os.path.splitext(lower_name)

    if lower_name in {"makefile", "gnumakefile"}:
        return "make"
    if ext in {".md", ".markdown"}:
        return "markdown"
    if ext in {".c", ".h"}:
        return "c"
    if ext in {".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}:
        return "cpp"
    if ext == ".cs":
        return "csharp"
    if ext == ".py":
        return "python"
    if ext in {".sh", ".bash"}:
        return "shell"
    if ext in {".mk", ".make"}:
        return "make"
    return "text"


def _restore_inline_code_spacing(text: str, original: Optional[str] = None) -> str:
    output: List[str] = []
    last = 0
    original_matches = list(_BACKTICK_PATTERN.finditer(original)) if original is not None else []

    for index, match in enumerate(_BACKTICK_PATTERN.finditer(text)):
        output.append(text[last:match.end()])
        last = match.end()

        if last >= len(text):
            continue

        if index < len(original_matches):
            original_end = original_matches[index].end()
            original_suffix = original[original_end:]
            if (
                re.match(r"\s+(?:==|!=|<=|>=|=|:)", original_suffix)
                and _INLINE_CODE_NO_SPACE_PREFIX_RE.match(text[last:])
            ):
                whitespace = re.match(r"\s+", original_suffix)
                if whitespace is not None:
                    output.append(whitespace.group(0))
                continue

        next_char = text[last]
        if (
            next_char.isspace()
            or next_char in _INLINE_CODE_NO_SPACE_FOLLOWERS
            or _INLINE_CODE_NO_SPACE_PREFIX_RE.match(text[last:])
        ):
            continue

        output.append(" ")

    output.append(text[last:])
    return "".join(output)


def _filter_preserved_inline_code_suffix_findings(
    original: str,
    final: str,
    collector: "DiagnosticCollector",
    start_index: int,
) -> None:
    preserved_columns = []
    for match in _INLINE_CODE_SPACED_SUFFIX_RE.finditer(original):
        if match.group(0) in final:
            preserved_columns.append((match.start(1) + 1, match.end(1) + 1))

    if not preserved_columns:
        return

    kept = collector.findings[:start_index]
    for finding in collector.findings[start_index:]:
        if (
            finding.rule == "space-before-punctuation"
            and finding.original == " "
            and any(start <= finding.column < end for start, end in preserved_columns)
        ):
            continue
        kept.append(finding)

    collector.findings = kept


def _normalize_inline_code_middledot_spacing(text: str) -> str:
    text = _INLINE_CODE_WITH_SPACE_BEFORE_MIDDLEDOT_RE.sub(r"\1・", text)
    text = _INLINE_CODE_WITH_SPACE_AFTER_MIDDLEDOT_RE.sub(r"・\1", text)
    return text


def _normalize_wave_dash_spacing_between_inline_codes(text: str) -> str:
    text = _WAVE_DASH_SPACE_BEFORE_ONLY_RE.sub(r"\1 \2 \3", text)
    text = _WAVE_DASH_SPACE_AFTER_ONLY_RE.sub(r"\1 \2 \3", text)
    return text


def _normalize_inline_code_after_colon_spacing(text: str) -> str:
    output: List[str] = []
    last = 0
    for match in _BACKTICK_PATTERN.finditer(text):
        segment = _INLINE_CODE_IMMEDIATELY_AFTER_COLON_RE.sub(": ", text[last:match.start()])
        if segment.endswith(":"):
            segment += " "
        output.append(segment)
        output.append(match.group(0))
        last = match.end()
    output.append(_INLINE_CODE_IMMEDIATELY_AFTER_COLON_RE.sub(": ", text[last:]))
    return "".join(output)


def _normalize_supplemental_label_after_colon_spacing(text: str) -> str:
    return _SUPPLEMENTAL_LABEL_IMMEDIATELY_AFTER_COLON_RE.sub(r"\1: ", text)


def _strip_markup_delimiters(span: str) -> str:
    if not span:
        return span
    if span.startswith("`"):
        match = re.match(r"(`+)", span)
        if match is None:
            return span
        delim = match.group(1)
        if span.endswith(delim):
            return span[len(delim):-len(delim)]
        return span
    for delim in ("**", "__", "*", "_"):
        if span.startswith(delim) and span.endswith(delim):
            return span[len(delim):-len(delim)]
    return span


def _is_emphasis_span(span: str) -> bool:
    return _EMPHASIS_PATTERN.fullmatch(span) is not None


def _normalize_markup_span_spacing(text: str) -> str:
    pattern = re.compile(rf"{_BACKTICK_PATTERN.pattern}|{_EMPHASIS_PATTERN.pattern}")
    output: List[str] = []
    last = 0

    for match in pattern.finditer(text):
        start, end = match.span()
        output.append(text[last:start])
        span = match.group(0)
        content = _strip_markup_delimiters(span).strip()
        if _is_emphasis_span(span) and content:
            first_char = "A"
            last_char = "A"
        else:
            first_char = content[0] if content else ""
            last_char = content[-1] if content else ""

        if output and output[-1]:
            prev_char = output[-1][-1]
            if first_char and not prev_char.isspace() and _needs_space_between(prev_char, first_char):
                output.append(" ")

        output.append(span)

        next_char = text[end] if end < len(text) else ""
        if last_char and next_char and not next_char.isspace() and _needs_space_between(last_char, next_char):
            output.append(" ")

        last = end

    output.append(text[last:])
    return "".join(output)


def _normalize_inline_code_slash_spacing(text: str) -> str:
    text = _INLINE_CODE_WITH_SPACE_BEFORE_SLASH_RE.sub(r"\1 / \2", text)
    text = _INLINE_CODE_WITH_SPACE_AFTER_SLASH_RE.sub(r"\1 / \2", text)
    return text


def _style_text_with_inline_code_spacing(
    text: str,
    protected_patterns: Sequence[re.Pattern],
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    start_index = len(collector.findings) if collector is not None else 0
    styled = style_text(
        text,
        protected_patterns=protected_patterns,
        collector=collector,
    )
    final = _restore_inline_code_spacing(styled, original=text)
    normalized = _normalize_inline_code_slash_spacing(final)
    if collector is not None:
        if normalized != final:
            _record_step_changes(
                final,
                normalized,
                "inline-code-slash",
                collector,
                message="インライン コード間のスラッシュ前後スペースを補正",
            )
    final = normalized
    normalized = _normalize_inline_code_middledot_spacing(final)
    if collector is not None:
        if normalized != final:
            _record_step_changes(
                final,
                normalized,
                "inline-code-middledot",
                collector,
                message="インライン コード間の中黒前後スペースを削除",
            )
    final = normalized
    normalized = _normalize_wave_dash_spacing_between_inline_codes(final)
    if collector is not None:
        if normalized != final:
            _record_step_changes(
                final,
                normalized,
                "inline-code-wave-dash",
                collector,
                message="インライン コード間の波ダッシュ前後スペースを補正",
            )
    final = normalized
    normalized = _normalize_inline_code_after_colon_spacing(final)
    if collector is not None:
        if normalized != final:
            _record_step_changes(
                final,
                normalized,
                "markup-colon-spacing",
                collector,
                message="コロン後のインライン コード前スペースを補正",
            )
    final = normalized
    normalized = _normalize_supplemental_label_after_colon_spacing(final)
    if collector is not None:
        if normalized != final:
            _record_step_changes(
                final,
                normalized,
                "supplemental-label-colon-spacing",
                collector,
                message="補足ラベルのコロン後スペースを補正",
            )
        final = normalized
        if final == text:
            collector.findings = collector.findings[:start_index]
            return final
        _filter_preserved_inline_code_suffix_findings(text, final, collector, start_index)
    return normalized


def _find_owner_delta(stack: List[Tuple[int, int, int, int]], width: int) -> int:
    """orig_content_indent <= width を満たす最深スタック エントリの delta を返す。

    スタック エントリの構造: (orig_indent, orig_content_indent, delta, target_content_indent)
    """
    for entry in reversed(stack):
        if entry[1] <= width:  # orig_content_indent <= width
            return entry[2]    # delta
    return 0


def _find_owner_continuation_indent(
    stack: List[Tuple[int, int, int, int]], width: int
) -> Optional[Tuple[int, int]]:
    """継続テキスト行の所有リスト項目を返す。

    Markdown 文書では、ネストしたリスト項目の継続行がマーカー後の
    本文開始位置より 1 スペース浅く書かれていることがある。
    その行をリスト項目配下として扱うため、orig_indent < width を満たす
    最深エントリを所有項目とする。
    """
    for entry in reversed(stack):
        if entry[0] < width:
            return entry[2], entry[3]
    return None


def _normalize_list_indent(
    result_lines: List[str],
    code_block_flags: List[bool],
    collector: Optional["DiagnosticCollector"] = None,
) -> Tuple[List[str], List[bool]]:
    """リスト マーカーのネスト字下げを depth × 4 スペースに正規化する。

    マーカー行・継続テキスト行・配下のフェンス付きコード ブロックを
    同一 delta で平行移動させることで相対字下げを保持する。

    スタック エントリ: (orig_indent, orig_content_indent, delta, target_content_indent)
      - orig_indent       : マーカー行の先頭空白幅 (expandtabs(4) 換算)
      - orig_content_indent: マーカー後のコンテンツ開始位置 (orig_indent + マーカー長)
      - delta             : 新インデント − 旧インデント
      - target_content_indent: 正規化後のコンテンツ開始位置
    """
    # スタック エントリ: (orig_indent, orig_content_indent, delta, target_content_indent)
    stack: List[Tuple[int, int, int, int]] = []
    output: List[str] = []

    for i, line in enumerate(result_lines):
        # 空行はスタックに影響を与えずそのまま出力する
        if not line.strip():
            output.append(line)
            continue

        lead_match = _LEADING_WHITESPACE_RE.match(line)
        lead_str = lead_match.group(0) if lead_match else ""
        width = len(lead_str.expandtabs(4))
        content_after_lead = line[len(lead_str):]

        new_line = line

        if not code_block_flags[i]:
            marker_match = _LIST_ITEM_RE.match(line)
            if marker_match:
                # マーカー行: 同 / 浅インデントのエントリを閉じてから深さを決定する
                while stack and width <= stack[-1][0]:
                    stack.pop()
                depth = len(stack)
                target = depth * 4
                delta = target - width
                # トップレベル (depth == 0) の字下げは変更しない。
                # 深さ × 4 の正規化はネスト項目 (depth >= 1) にのみ適用する。
                if depth == 0:
                    delta = 0
                    new_line = line
                else:
                    new_line = " " * target + content_after_lead
                # マーカー長: 先頭空白を除いた "- " / "1. " 部分の文字数
                marker_len = marker_match.end() - len(lead_str)
                marker_indent = width
                if depth != 0:
                    marker_indent = target
                stack.append((width, width + marker_len, delta, marker_indent + marker_len))
            else:
                # 非マーカー行: width == 0 のトップレベル行はリストを閉じる
                if width == 0:
                    stack.clear()
                else:
                    owner = _find_owner_continuation_indent(stack, width)
                    if owner is not None:
                        d, target_content_indent = owner
                        target_width = max(0, width + d, target_content_indent)
                        if target_width != width:
                            new_line = " " * target_width + content_after_lead
        else:
            # コード ブロック内 (フェンス行・内容行・閉じ行)
            # width > 0 のときのみ所有項目の delta で平行移動する
            if width > 0:
                d = _find_owner_delta(stack, width)
                if d != 0:
                    new_line = " " * max(0, width + d) + content_after_lead

        if collector is not None and new_line != line:
            collector.set_line(i + 1)
            _record_step_changes(
                line,
                new_line,
                "list-indent",
                collector,
                message="リストのネスト字下げを 4 スペースに正規化",
            )

        output.append(new_line)

    return output, list(code_block_flags)


def _insert_blank_around_fences(
    result_lines: List[str],
    code_block_flags: List[bool],
) -> Tuple[List[str], List[bool]]:
    new_lines: List[str] = []
    new_flags: List[bool] = []
    n = len(result_lines)

    def is_opening_fence(index: int, line: str) -> bool:
        if not _CODE_FENCE_RE.match(line.lstrip()):
            return False
        if line.lstrip().startswith(">"):
            return False
        return index == 0 or not code_block_flags[index - 1]

    def is_closing_fence(index: int, line: str) -> bool:
        if line.lstrip().startswith(">"):
            return False
        if not re.match(r"^\s*(`{3,}|~{3,})\s*$", line):
            return False
        return index + 1 >= n or not code_block_flags[index + 1]

    for i, line in enumerate(result_lines):
        if is_opening_fence(i, line) and new_lines and new_lines[-1].strip():
            new_lines.append("")
            new_flags.append(False)

        new_lines.append(line)
        new_flags.append(code_block_flags[i])

        if is_closing_fence(i, line) and i + 1 < n and result_lines[i + 1].strip():
            new_lines.append("")
            new_flags.append(False)

    return new_lines, new_flags


def _insert_blank_before_top_level_lists(
    result_lines: List[str],
    code_block_flags: List[bool],
) -> Tuple[List[str], List[bool]]:
    new_lines: List[str] = []
    new_flags: List[bool] = []

    for i, line in enumerate(result_lines):
        if (
            i > 0
            and not code_block_flags[i]
            and _LIST_ITEM_RE.match(line)
            and not line.startswith((" ", "\t"))
            and new_lines
            and new_lines[-1].strip()
            and not new_flags[-1]
            and not new_lines[-1].startswith((" ", "\t"))
        ):
            prev_stripped = new_lines[-1].strip()
            if (
                not _LIST_ITEM_RE.match(prev_stripped)
                and not _TABLE_ROW_RE.match(prev_stripped)
                and not _BLOCKQUOTE_RE.match(prev_stripped)
                and not _CODE_FENCE_RE.match(prev_stripped)
            ):
                new_lines.append("")
                new_flags.append(False)

        new_lines.append(line)
        new_flags.append(code_block_flags[i])

    return new_lines, new_flags


def _insert_blank_after_standalone_emphasis_lines(
    result_lines: List[str],
    code_block_flags: List[bool],
) -> Tuple[List[str], List[bool]]:
    new_lines: List[str] = []
    new_flags: List[bool] = []
    n = len(result_lines)

    for i, line in enumerate(result_lines):
        new_lines.append(line)
        new_flags.append(code_block_flags[i])

        if code_block_flags[i]:
            continue

        stripped = line.strip()
        if not stripped or _EMPHASIS_PATTERN.fullmatch(stripped) is None:
            continue

        if i + 1 < n and result_lines[i + 1].strip():
            new_lines.append("")
            new_flags.append(False)

    return new_lines, new_flags


def _remove_unnecessary_trailing_spaces(
    result_lines: List[str],
    code_block_flags: List[bool],
) -> List[str]:
    def leading_indent_width(line: str) -> int:
        match = _LEADING_WHITESPACE_RE.match(line)
        if match is None:
            return 0
        return len(match.group(0).expandtabs(4))

    def is_list_continuation_line(line: str, next_line: str) -> bool:
        match = _LIST_ITEM_RE.match(line)
        if match is None:
            return False

        next_stripped = next_line.strip()
        if not next_stripped:
            return False
        if (
            _LIST_ITEM_RE.match(next_stripped)
            or _TABLE_ROW_RE.match(next_stripped)
            or _BLOCKQUOTE_RE.match(next_stripped)
            or _HEADING_RE.match(next_stripped)
            or _CODE_FENCE_RE.match(next_stripped)
        ):
            return False

        content_indent = len(line[:match.end()].expandtabs(4))
        return leading_indent_width(next_line) == content_indent

    n = len(result_lines)
    output = []
    for i, line in enumerate(result_lines):
        if code_block_flags[i]:
            output.append(line)
            continue

        stripped_line = line.rstrip()
        if not stripped_line:
            output.append(stripped_line)
            continue

        has_explicit_line_break = len(line) - len(stripped_line) >= 2
        next_line = result_lines[i + 1] if i + 1 < n else ""
        next_stripped = (result_lines[i + 1] if i + 1 < n else "").strip()
        is_list_continuation = is_list_continuation_line(stripped_line, next_line)
        curr_is_block = (
            _TABLE_ROW_RE.match(stripped_line)
            or _BLOCKQUOTE_RE.match(stripped_line)
            or (_LIST_ITEM_RE.match(stripped_line) and not is_list_continuation)
        )
        next_is_block = (
            _LIST_ITEM_RE.match(next_stripped)
            or _TABLE_ROW_RE.match(next_stripped)
            or _BLOCKQUOTE_RE.match(next_stripped)
            or _HEADING_RE.match(next_stripped)
            or _CODE_FENCE_RE.match(next_stripped)
        )

        if next_stripped and (
            has_explicit_line_break
            or is_list_continuation
            or (not curr_is_block and not next_is_block)
        ):
            output.append(stripped_line + "  ")
        else:
            output.append(stripped_line)

    return output


def _normalize_task_list_marker(line: str) -> str:
    return _EMPTY_TASK_LIST_MARKER_RE.sub(r"\1[ ]", line)


def _normalize_unordered_list_marker(line: str) -> str:
    return _UNORDERED_LIST_MARKER_RE.sub(r"\1-", line)


def _remove_markdown_heading_number(line: str) -> str:
    match = _HEADING_NUMBER_RE.match(line)
    if not match:
        return line
    token = match.group(2)
    rest = match.group(3)
    if _should_preserve_markdown_heading_number(token, rest):
        return line
    return match.group(1) + " " + rest


def _has_plain_heading_number_token(token: str) -> bool:
    return not token.endswith((".", ")"))


def _preserve_counter_heading_number(token: str, rest: str) -> bool:
    return _has_plain_heading_number_token(token) and _HEADING_COUNTER_PREFIX_RE.match(rest) is not None


def _preserve_literal_number_heading(token: str, rest: str) -> bool:
    return _has_plain_heading_number_token(token) and _HEADING_LITERAL_NUMBER_PREFIX_RE.match(rest) is not None


def _is_valid_heading_date_token(token: str) -> bool:
    if _HEADING_DATE_TOKEN_RE.match(token) is None:
        return False

    if len(token) == 6:
        year = 2000 + int(token[0:2])
        month = int(token[2:4])
        day = int(token[4:6])
    else:
        year = int(token[0:4])
        month = int(token[4:6])
        day = int(token[6:8])

    if month < 1 or month > 12:
        return False

    days_per_month = (
        31,
        29 if _is_leap_year(year) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    )
    return day >= 1 and day <= days_per_month[month - 1]


def _is_leap_year(year: int) -> bool:
    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    return year % 4 == 0


def _preserve_date_heading_number(token: str, rest: str) -> bool:
    return _has_plain_heading_number_token(token) and _is_valid_heading_date_token(token)


_HEADING_NUMBER_PRESERVE_RULES: Sequence[Callable[[str, str], bool]] = (
    _preserve_counter_heading_number,
    _preserve_literal_number_heading,
    _preserve_date_heading_number,
)


def _should_preserve_markdown_heading_number(token: str, rest: str) -> bool:
    return any(rule(token, rest) for rule in _HEADING_NUMBER_PRESERVE_RULES)


def _remove_heading_inline_code(line: str) -> str:
    if not _HEADING_RE.match(line):
        return line
    return _HEADING_INLINE_CODE_RE.sub(r"\1", line)


def _ensure_heading_marker_space(line: str) -> str:
    match = re.match(r"^(#{1,6})([^\s#].*)$", line)
    if match is None:
        return line
    return match.group(1) + " " + match.group(2)


def _match_comment_tag_start(line: str) -> Optional[re.Match[str]]:
    return _COMMENT_TAG_START_RE.match(line)


def _is_comment_tag_end(line: str, tag: str) -> bool:
    escaped_tag = re.escape(tag)
    return re.match(rf"^\s*(?:<!--:{escaped_tag}-->|:{escaped_tag}-->)\s*$", line) is not None


def _starts_html_comment_block(line: str) -> bool:
    return line.lstrip().startswith("<!--")


def normalize_blank_lines(text: str) -> str:
    if text == "":
        return ""

    output: List[str] = []
    blank_count = 0

    for line in text.split("\n"):
        if line.strip():
            blank_count = 0
            output.append(line)
            continue

        blank_count += 1
        if blank_count == 1:
            output.append("")

    return "\n".join(output).rstrip("\n") + "\n"


def _find_box_drawing_chars(text: str, collector: "DiagnosticCollector") -> None:
    """罫線文字 (Box Drawing, U+2500-U+257F) を検出して collector に警告として追加する。
    インライン コード スパン (バックティック) 内は対象外。ブロッククォートは対象。
    """
    for line_idx, line in enumerate(text.split("\n"), start=1):
        protected: set = set()
        for match in _BACKTICK_PATTERN.finditer(line):
            protected.update(range(match.start(), match.end()))
        collector.set_line(line_idx)
        for col_idx, ch in enumerate(line, start=1):
            if (col_idx - 1) in protected:
                continue
            if 0x2500 <= ord(ch) <= 0x257F:
                collector.add(col_idx, ch, ch, "box-drawing")


def _detect_fence_source_mode(info: str) -> Optional[str]:
    """フェンス情報文字列 (言語タグ部分) から対応するソースモードを返す。

    Pandoc 属性形式 ({.c .numberLines}) と素のトークン (c title="x") の両方に対応する。
    対応言語がない場合は None を返す。
    """
    info = info.strip()
    if not info:
        return None
    if info.startswith("{"):
        m = re.search(r"\.([A-Za-z0-9_+#.-]+)", info)
        lang = m.group(1) if m else ""
    else:
        m = re.match(r"[A-Za-z0-9_+#.-]+", info)
        lang = m.group(0) if m else ""
    return _FENCE_LANG_TO_SOURCE_MODE.get(lang.lower())


def style_markdown(
    text: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    text = replace_nbsp_with_space(text, collector=collector)
    if collector is not None:
        _find_box_drawing_chars(text, collector)
    lines = text.split("\n")
    result_lines: List[str] = []
    code_block_flags: List[bool] = []
    in_code_block = False
    fence_char = "`"
    fence_len = 0
    fence_nest = 0
    in_frontmatter = len(lines) > 0 and lines[0].strip() == "---"
    comment_tag: Optional[str] = None
    in_html_comment_block = False
    in_grid_table = False
    code_block_mode: Optional[str] = None
    code_body_start: int = 0

    for idx, line in enumerate(lines):
        if collector is not None:
            collector.set_line(idx + 1)
        stripped = line.strip()

        if in_frontmatter:
            result_lines.append(_style_text_with_inline_code_spacing(line, [_BACKTICK_PATTERN], collector=collector))
            code_block_flags.append(True)
            if idx > 0 and (stripped == "---" or stripped == "..."):
                in_frontmatter = False
            continue

        if comment_tag is not None:
            result_lines.append(line)
            code_block_flags.append(True)
            if _is_comment_tag_end(line, comment_tag):
                comment_tag = None
            continue

        if in_html_comment_block:
            result_lines.append(line)
            code_block_flags.append(True)
            if "-->" in line:
                in_html_comment_block = False
            continue

        if in_code_block:
            close_pat = r"^(" + re.escape(fence_char) + r"{" + str(fence_len) + r",})\s*$"
            open_pat = r"^(" + re.escape(fence_char) + r"{" + str(fence_len) + r",})\S"
            if re.match(close_pat, stripped):
                if fence_nest == 0:
                    in_code_block = False
                    fence_len = 0
                    if code_block_mode is not None and len(result_lines) > code_body_start:
                        body_text = "\n".join(result_lines[code_body_start:])
                        pre_count = len(collector.findings) if collector is not None else 0
                        styled_body = style_source_comments(body_text, code_block_mode, collector=collector)
                        if collector is not None:
                            for f in collector.findings[pre_count:]:
                                f.line += code_body_start
                        result_lines[code_body_start:] = styled_body.split("\n")
                    code_block_mode = None
                else:
                    fence_nest -= 1
                result_lines.append(line)
                code_block_flags.append(True)
                continue
            if re.match(open_pat, stripped):
                fence_nest += 1
            result_lines.append(line)
            code_block_flags.append(True)
            continue

        comment_tag_match = _match_comment_tag_start(line)
        if comment_tag_match is not None:
            comment_tag = comment_tag_match.group(1)
            result_lines.append(line)
            code_block_flags.append(True)
            continue

        if _starts_html_comment_block(line):
            result_lines.append(line)
            code_block_flags.append(True)
            if "-->" not in line:
                in_html_comment_block = True
            continue

        match = re.match(r"^(`{3,}|~{3,})", stripped)
        if match:
            in_code_block = True
            fence_char = match.group(1)[0]
            fence_len = len(match.group(1))
            fence_nest = 0
            result_lines.append(line)
            code_block_flags.append(True)
            code_block_mode = _detect_fence_source_mode(stripped[match.end():])
            code_body_start = len(result_lines)
            continue

        if in_grid_table:
            if _GRID_TABLE_BORDER_RE.match(line) or _GRID_TABLE_ROW_RE.match(line):
                result_lines.append(line)
                code_block_flags.append(True)
                continue
            in_grid_table = False

        if _GRID_TABLE_BORDER_RE.match(line):
            in_grid_table = True
            result_lines.append(line)
            code_block_flags.append(True)
            continue

        if _TABLE_SEPARATOR_RE.match(line):
            result_lines.append(line)
        else:
            before = line
            line = _normalize_unordered_list_marker(line)
            if collector is not None:
                _record_step_changes(before, line, "unordered-list-marker", collector, message="unordered list マーカーを正規化")
            before = line
            line = _normalize_task_list_marker(line)
            if collector is not None:
                _record_step_changes(before, line, "task-list-marker", collector, message="task list マーカーを正規化")
            before = line
            line = _remove_markdown_heading_number(line)
            if collector is not None:
                _record_step_changes(before, line, "heading-number", collector, message="見出し番号を除去")
            before = line
            line = _remove_heading_inline_code(line)
            if collector is not None:
                _record_step_changes(before, line, "heading-inline-code", collector, message="見出しのインライン コードを除去")
            line = _style_text_with_inline_code_spacing(line, _MARKDOWN_PROTECTED_PATTERNS, collector=collector)
            before = line
            normalized = _normalize_markup_span_spacing(line)
            normalized = _ensure_heading_marker_space(normalized)
            if collector is not None:
                _record_step_changes(before, normalized, "markup-span-spacing", collector, message="強調/インライン コード前後のスペースを補正")
            result_lines.append(normalized)
        code_block_flags.append(False)

    result_lines, code_block_flags = _normalize_list_indent(result_lines, code_block_flags, collector)
    result_lines, code_block_flags = _insert_blank_around_fences(result_lines, code_block_flags)
    result_lines, code_block_flags = _insert_blank_before_top_level_lists(result_lines, code_block_flags)
    result_lines, code_block_flags = _insert_blank_after_standalone_emphasis_lines(result_lines, code_block_flags)
    result_lines = _remove_unnecessary_trailing_spaces(result_lines, code_block_flags)
    return "\n".join(result_lines)


def style_source_comments(
    text: str,
    language: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    text = replace_nbsp_with_space(text, collector=collector)
    if language in {"c", "cpp", "csharp"}:
        return _style_c_like_comments(text, language, collector=collector)
    if language in {"python", "shell", "make"}:
        return _style_hash_comments(text, language, collector=collector)
    raise ValueError(f"unsupported source comment mode: {language}")


def style_by_mode(
    text: str,
    mode: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    if mode == "markdown":
        return normalize_blank_lines(style_markdown(text, collector=collector))
    if mode in {"c", "cpp", "csharp", "python", "shell", "make"}:
        return style_source_comments(text, mode, collector=collector)
    if mode == "text":
        text = replace_nbsp_with_space(text, collector=collector)
        return normalize_blank_lines(text)
    raise ValueError(f"unsupported mode: {mode}")


def _split_line_ending(line: str) -> Tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    if line.endswith("\r"):
        return line[:-1], "\r"
    return line, ""


def _style_general_comment_text(
    text: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    if not text.strip():
        return text
    before = text
    text = _COMMENT_CODE_NEGATION_SPACE_RE.sub(r"!\1", text)
    if collector is not None:
        _record_step_changes(before, text, "comment-code-negation", collector, message="コメント内の C 条件否定のスペースを削除")
    return _style_text_with_inline_code_spacing(text, _COMMENT_CODE_PROTECTED_PATTERNS, collector=collector)


def _style_doxygen_description(
    text: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    if not text.strip():
        return text
    start_index = len(collector.findings) if collector is not None else 0
    before = text
    text = _COMMENT_CODE_NEGATION_SPACE_RE.sub(r"!\1", text)
    if collector is not None:
        _record_step_changes(before, text, "comment-code-negation", collector, message="コメント内の C 条件否定のスペースを削除")
    styled = _style_text_with_inline_code_spacing(
        text,
        _COMMENT_CODE_PROTECTED_PATTERNS + [_DOXYGEN_INLINE_COMMAND_PATTERN],
        collector=collector,
    )
    normalized = _normalize_doxygen_ref_punctuation_spacing(styled, collector=collector)
    if collector is not None and normalized == before:
        collector.findings = collector.findings[:start_index]
    return normalized


def _normalize_doxygen_ref_punctuation_spacing(
    text: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    normalized = _DOXYGEN_REF_MISSING_SPACE_BEFORE_JP_PUNCT_RE.sub(r"\1 \2", text)
    if collector is not None and normalized != text:
        _record_step_changes(
            text,
            normalized,
            "doxygen-ref-punctuation-spacing",
            collector,
            message="@ref 参照名と日本語句読点の間にスペースを挿入",
        )
    return normalized


def _is_doxygen_table_line(content: str) -> bool:
    stripped = content.strip()
    return stripped.startswith("|") or stripped.startswith("Table:")


def _style_doxygen_line(
    content: str,
    in_code_block: bool,
    collector: Optional["DiagnosticCollector"] = None,
) -> Tuple[str, bool]:
    stripped = content.strip()
    if not stripped:
        return content, in_code_block
    if any(stripped.startswith(token) for token in _DOXYGEN_CODE_ENDS):
        return content, False
    if in_code_block:
        return content, True
    if any(stripped.startswith(token) for token in _DOXYGEN_CODE_STARTS):
        return content, True
    if stripped.startswith(_DOXYGEN_LITERAL_LINE_PREFIXES):
        return content, in_code_block
    if _is_doxygen_table_line(content):
        return content, in_code_block

    match = _ONE_ARG_DESCRIPTION_COMMAND_RE.match(content)
    if match and match.group(2) in _ONE_ARG_DESCRIPTION_COMMANDS:
        desc = _style_doxygen_description(match.group(5), collector=collector)
        return match.group(1) + match.group(3) + match.group(4) + desc, in_code_block

    match = _REFERENCE_COMMAND_RE.match(content)
    if match and match.group(2) in _REFERENCE_COMMANDS:
        return content, in_code_block

    match = _GENERIC_COMMAND_RE.match(content)
    if match:
        start_index = len(collector.findings) if collector is not None else 0
        desc = _style_doxygen_description(match.group(3), collector=collector)
        normalized = _normalize_doxygen_ref_punctuation_spacing(
            match.group(1) + match.group(2) + desc,
            collector=collector,
        )
        if collector is not None and normalized == content:
            collector.findings = collector.findings[:start_index]
        return normalized, in_code_block

    return _style_doxygen_description(content, collector=collector), in_code_block


def _style_block_comment(
    comment: str,
    line_styler: Callable[[str, bool], Tuple[str, bool]],
    collector: Optional["DiagnosticCollector"] = None,
    start_line: int = 0,
) -> str:
    lines = comment.splitlines(keepends=True)
    if not lines:
        return comment

    if len(lines) == 1:
        if collector is not None:
            collector.set_line(start_line)
        body, ending = _split_line_ending(lines[0])
        match = re.match(r"^(\s*/\*+!?<?\s*)(.*?)(\s*\*/\s*)$", body)
        if not match:
            return comment
        styled, _ = line_styler(match.group(2), False)
        return match.group(1) + styled + match.group(3) + ending

    output: List[str] = []
    in_code_block = False

    for idx, line in enumerate(lines):
        if collector is not None:
            collector.set_line(start_line + idx)
        body, ending = _split_line_ending(line)

        if idx == 0:
            match = re.match(r"^(\s*/\*+!?<?\s*)(.*)$", body)
            if match:
                prefix = match.group(1)
                content = match.group(2)
                styled, in_code_block = line_styler(content, in_code_block)
                output.append(prefix + styled + ending)
                continue
        elif idx == len(lines) - 1:
            match = re.match(r"^(.*?)(\s*\*/\s*)$", body)
            if match:
                prefix, content = _split_star_prefix(match.group(1))
                styled, in_code_block = line_styler(content, in_code_block)
                output.append(prefix + styled + match.group(2) + ending)
                continue

        prefix, content = _split_star_prefix(body)
        styled, in_code_block = line_styler(content, in_code_block)
        output.append(prefix + styled + ending)

    return "".join(output)


def _split_star_prefix(line: str) -> Tuple[str, str]:
    match = re.match(r"^(\s*\*\s*)(.*)$", line)
    if match:
        return match.group(1), match.group(2)
    match = re.match(r"^(\s+)(.*)$", line)
    if match:
        return match.group(1), match.group(2)
    return "", line


def _style_doxygen_block_comment(
    comment: str,
    collector: Optional["DiagnosticCollector"] = None,
    start_line: int = 0,
) -> str:
    def _styler(content: str, state: bool) -> Tuple[str, bool]:
        return _style_doxygen_line(content, state, collector)

    return _style_block_comment(comment, _styler, collector=collector, start_line=start_line)


def _style_general_block_comment(
    comment: str,
    collector: Optional["DiagnosticCollector"] = None,
    start_line: int = 0,
) -> str:
    def _styler(content: str, state: bool) -> Tuple[str, bool]:
        return _style_general_comment_text(content, collector), state

    return _style_block_comment(comment, _styler, collector=collector, start_line=start_line)


def _style_general_line_comment(
    comment: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    match = re.match(r"^(//[!/<>]*\s*)(.*)$", comment)
    if not match:
        return comment
    return match.group(1) + _style_general_comment_text(match.group(2), collector=collector)


def _style_xml_doc_text(
    content: str,
    in_code_block: bool,
    collector: Optional["DiagnosticCollector"] = None,
) -> Tuple[str, bool]:
    parts = _XML_TAG_RE.split(content)
    output: List[str] = []
    inline_code_depth = 0
    code_block = in_code_block

    for part in parts:
        if part == "":
            continue
        if part.startswith("<") and part.endswith(">"):
            output.append(part)
            tag = part.strip()[1:-1].strip()
            lower = tag.lower()

            if lower.startswith("/code"):
                code_block = False
            elif lower.startswith("/c"):
                inline_code_depth = max(0, inline_code_depth - 1)
            elif lower.endswith("/"):
                pass
            elif lower.startswith("code"):
                code_block = True
            elif lower.startswith("c"):
                inline_code_depth += 1
            continue

        if code_block or inline_code_depth > 0:
            output.append(part)
        else:
            output.append(_style_text_with_inline_code_spacing(part, [_BACKTICK_PATTERN], collector=collector))

    return "".join(output), code_block


def _style_xml_doc_block(
    comment_block: str,
    collector: Optional["DiagnosticCollector"] = None,
    start_line: int = 0,
) -> str:
    lines = comment_block.splitlines(keepends=True)
    output: List[str] = []
    in_code_block = False

    for idx, line in enumerate(lines):
        if collector is not None:
            collector.set_line(start_line + idx)
        body, ending = _split_line_ending(line)
        match = re.match(r"^(\s*///\s?)(.*)$", body)
        if not match:
            output.append(line)
            continue
        prefix = match.group(1)
        content = match.group(2)
        styled, in_code_block = _style_xml_doc_text(content, in_code_block, collector=collector)
        output.append(prefix + styled + ending)

    return "".join(output)


def _style_doxygen_line_block(
    comment_block: str,
    collector: Optional["DiagnosticCollector"] = None,
    start_line: int = 0,
) -> str:
    lines = comment_block.splitlines(keepends=True)
    output: List[str] = []
    in_code_block = False

    for idx, line in enumerate(lines):
        if collector is not None:
            collector.set_line(start_line + idx)
        body, ending = _split_line_ending(line)
        match = re.match(r"^(\s*//[!/<>]*\s?)(.*)$", body)
        if not match:
            output.append(line)
            continue
        prefix = match.group(1)
        content = match.group(2)
        styled, in_code_block = _style_doxygen_line(content, in_code_block, collector=collector)
        output.append(prefix + styled + ending)

    return "".join(output)


def _line_start_index(text: str, index: int) -> int:
    return text.rfind("\n", 0, index) + 1


def _line_end_index(text: str, index: int) -> int:
    end = text.find("\n", index)
    return len(text) if end == -1 else end


def _only_whitespace_since_line_start(text: str, index: int) -> bool:
    line_start = _line_start_index(text, index)
    return text[line_start:index].strip() == ""


def _consume_c_like_string(text: str, start: int, language: str) -> int:
    n = len(text)
    if language == "csharp":
        if text.startswith('"""', start):
            end = text.find('"""', start + 3)
            return n if end == -1 else end + 3
        if text.startswith('@\"', start):
            i = start + 2
            while i < n:
                if text[i] == '"' and (i + 1 >= n or text[i + 1] != '"'):
                    return i + 1
                if text[i] == '"' and i + 1 < n and text[i + 1] == '"':
                    i += 2
                    continue
                i += 1
            return n
        if text.startswith('$@"', start) or text.startswith('@$"', start):
            i = start + 3
            while i < n:
                if text[i] == '"' and (i + 1 >= n or text[i + 1] != '"'):
                    return i + 1
                if text[i] == '"' and i + 1 < n and text[i + 1] == '"':
                    i += 2
                    continue
                i += 1
            return n

    quote = text[start]
    i = start + 1
    while i < n:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        i += 1
    return n


def _consume_to_line_end(text: str, start: int) -> int:
    end = text.find("\n", start)
    return len(text) if end == -1 else end


def _consume_line_comment_block(text: str, start: int, prefix: str) -> int:
    pos = _line_start_index(text, start)
    cursor = pos
    n = len(text)

    while cursor < n:
        line_end = _consume_to_line_end(text, cursor)
        line = text[cursor:line_end]
        stripped = line.lstrip()
        if not stripped.startswith(prefix):
            break
        if line[: len(line) - len(stripped)].strip():
            break
        cursor = line_end
        if cursor < n and text[cursor] == "\n":
            cursor += 1
            continue
        break

    return cursor


def _style_c_like_comments(
    text: str,
    language: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    result: List[str] = []
    last = 0
    i = 0
    n = len(text)

    while i < n:
        if language == "csharp" and (
            text.startswith('$@"', i) or text.startswith('@$"', i) or text.startswith('@"', i) or text.startswith('"""', i)
        ):
            i = _consume_c_like_string(text, i, language)
            continue

        char = text[i]
        if char in {'"', "'"}:
            i = _consume_c_like_string(text, i, language)
            continue

        if text.startswith("///", i) and _only_whitespace_since_line_start(text, i):
            result.append(text[last:i])
            end = _consume_line_comment_block(text, i, "///")
            line_num = text[:i].count("\n") + 1
            result.append(_style_xml_doc_block(text[i:end], collector=collector, start_line=line_num))
            i = end
            last = i
            continue

        if text.startswith("//!", i) and _only_whitespace_since_line_start(text, i):
            result.append(text[last:i])
            end = _consume_line_comment_block(text, i, "//!")
            line_num = text[:i].count("\n") + 1
            result.append(_style_doxygen_line_block(text[i:end], collector=collector, start_line=line_num))
            i = end
            last = i
            continue

        if text.startswith("//", i):
            result.append(text[last:i])
            end = _consume_to_line_end(text, i)
            if collector is not None:
                collector.set_line(text[:i].count("\n") + 1)
            result.append(_style_general_line_comment(text[i:end], collector=collector))
            i = end
            last = i
            continue

        if text.startswith("/*", i):
            result.append(text[last:i])
            end = text.find("*/", i + 2)
            if end == -1:
                end = n
            else:
                end += 2
            comment = text[i:end]
            line_num = text[:i].count("\n") + 1
            if comment.startswith("/**") or comment.startswith("/*!") or comment.startswith("/**<"):
                result.append(_style_doxygen_block_comment(comment, collector=collector, start_line=line_num))
            else:
                result.append(_style_general_block_comment(comment, collector=collector, start_line=line_num))
            i = end
            last = i
            continue

        i += 1

    result.append(text[last:])
    return "".join(result)


def _find_hash_comment_start(line: str, language: str) -> Optional[int]:
    in_single = False
    in_double = False
    in_backtick = False
    escaped = False

    for idx, char in enumerate(line):
        if escaped:
            escaped = False
            continue

        if char == "\\" and not in_single:
            escaped = True
            continue

        if char == "'" and not in_double and not in_backtick:
            in_single = not in_single
            continue
        if char == '"' and not in_single and not in_backtick:
            in_double = not in_double
            continue
        if language in {"shell", "make"} and char == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
            continue

        if char == "#" and not in_single and not in_double and not in_backtick:
            if language == "python":
                return idx
            if idx == 0 or line[idx - 1].isspace():
                return idx

    return None


def _style_hash_comment_content(
    prefix: str,
    content: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    return prefix + _style_general_comment_text(content, collector=collector)


def _style_hash_comments(
    text: str,
    language: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    output: List[str] = []
    lines = text.splitlines(keepends=True)

    for lineno, line in enumerate(lines):
        body, ending = _split_line_ending(line)
        if lineno == 0 and body.startswith("#!"):
            output.append(line)
            continue

        comment_start = _find_hash_comment_start(body, language)
        if comment_start is None:
            output.append(line)
            continue

        if collector is not None:
            collector.set_line(lineno + 1)

        prefix_end = comment_start + 1
        while prefix_end < len(body) and body[prefix_end] == " ":
            prefix_end += 1

        output.append(
            body[:comment_start]
            + _style_hash_comment_content(body[comment_start:prefix_end], body[prefix_end:], collector=collector)
            + ending
        )

    return "".join(output)
