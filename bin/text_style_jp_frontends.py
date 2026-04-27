#!/usr/bin/env python3
"""Frontends for Markdown and source comments."""

import os
import re
from typing import Callable, List, Optional, Sequence, Tuple

from text_style_jp_engine import style_text


_BACKTICK_PATTERN = re.compile(r"``+.+?``+|`[^`]+`")
_DOXYGEN_MATH_PATTERN = re.compile(r"@f\$.*?@f\$")
_DOXYGEN_INLINE_COMMAND_PATTERN = re.compile(r"[@\\][A-Za-z_]+(?:\{[^}]*\})?")
_LIST_ITEM_RE = re.compile(r"^\s*([-*+]|\d+[.)]) ")
_TABLE_ROW_RE = re.compile(r"^\s*\|")
_HEADING_RE = re.compile(r"^#{1,6} ")
_BOLD_HEADING_RE = re.compile(r"^\*\*.+\*\*:?$")
_CODE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")

_INLINE_PROTECTED_PATTERNS = [_BACKTICK_PATTERN, _DOXYGEN_MATH_PATTERN]
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

_PARAM_COMMAND_RE = re.compile(
    r"^([@\\](?:param|tparam|retval)(?:\[[^\]]+\])?)(\s+)(\S+)(.*)$"
)
_IDENTIFIER_COMMAND_RE = re.compile(r"^([@\\](?:def|file))(\s+)(\S+)(.*)$")
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
    raise ValueError(f"unsupported file type for auto mode: {path}")


def _insert_blank_before_fence_after_bold(
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
        is_bold_heading = (
            not line.startswith((" ", "\t"))
            and not _LIST_ITEM_RE.match(line)
            and _BOLD_HEADING_RE.match(stripped)
        )
        if not is_bold_heading:
            continue

        if i + 1 < n and _CODE_FENCE_RE.match(result_lines[i + 1].lstrip()):
            new_lines.append("")
            new_flags.append(False)

    return new_lines, new_flags


def _remove_unnecessary_trailing_spaces(
    result_lines: List[str],
    code_block_flags: List[bool],
) -> List[str]:
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

        next_stripped = (result_lines[i + 1] if i + 1 < n else "").strip()
        curr_is_block = _LIST_ITEM_RE.match(stripped_line) or _TABLE_ROW_RE.match(stripped_line)
        next_is_block = (
            _LIST_ITEM_RE.match(next_stripped)
            or _TABLE_ROW_RE.match(next_stripped)
            or _HEADING_RE.match(next_stripped)
            or _CODE_FENCE_RE.match(next_stripped)
        )

        if next_stripped and not curr_is_block and not next_is_block:
            output.append(stripped_line + "  ")
        else:
            output.append(stripped_line)

    return output


def style_markdown(text: str) -> str:
    lines = text.split("\n")
    result_lines: List[str] = []
    code_block_flags: List[bool] = []
    in_code_block = False
    fence_char = "`"
    fence_len = 0
    fence_nest = 0

    for line in lines:
        stripped = line.strip()
        if not in_code_block:
            match = re.match(r"^(`{3,}|~{3,})", stripped)
            if match:
                in_code_block = True
                fence_char = match.group(1)[0]
                fence_len = len(match.group(1))
                fence_nest = 0
                result_lines.append(line)
                code_block_flags.append(True)
                continue
        else:
            close_pat = r"^(" + re.escape(fence_char) + r"{" + str(fence_len) + r",})\s*$"
            open_pat = r"^(" + re.escape(fence_char) + r"{" + str(fence_len) + r",})\S"
            if re.match(close_pat, stripped):
                if fence_nest == 0:
                    in_code_block = False
                    fence_len = 0
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

        result_lines.append(style_text(line, protected_patterns=[_BACKTICK_PATTERN]))
        code_block_flags.append(False)

    result_lines, code_block_flags = _insert_blank_before_fence_after_bold(result_lines, code_block_flags)
    result_lines = _remove_unnecessary_trailing_spaces(result_lines, code_block_flags)
    return "\n".join(result_lines)


def style_source_comments(text: str, language: str) -> str:
    if language in {"c", "cpp", "csharp"}:
        return _style_c_like_comments(text, language)
    if language in {"python", "shell", "make"}:
        return _style_hash_comments(text, language)
    raise ValueError(f"unsupported source comment mode: {language}")


def style_by_mode(text: str, mode: str) -> str:
    if mode == "markdown":
        return style_markdown(text)
    if mode in {"c", "cpp", "csharp", "python", "shell", "make"}:
        return style_source_comments(text, mode)
    raise ValueError(f"unsupported mode: {mode}")


def _split_line_ending(line: str) -> Tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    if line.endswith("\r"):
        return line[:-1], "\r"
    return line, ""


def _style_general_comment_text(text: str) -> str:
    if not text.strip():
        return text
    return style_text(text, protected_patterns=_INLINE_PROTECTED_PATTERNS)


def _style_doxygen_description(text: str) -> str:
    if not text.strip():
        return text
    return style_text(
        text,
        protected_patterns=[_BACKTICK_PATTERN, _DOXYGEN_MATH_PATTERN, _DOXYGEN_INLINE_COMMAND_PATTERN],
    )


def _is_doxygen_table_line(content: str) -> bool:
    stripped = content.strip()
    return stripped.startswith("|") or stripped.startswith("Table:")


def _style_doxygen_line(content: str, in_code_block: bool) -> Tuple[str, bool]:
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

    match = _PARAM_COMMAND_RE.match(content)
    if match:
        desc = _style_doxygen_description(match.group(4))
        return match.group(1) + match.group(2) + match.group(3) + desc, in_code_block

    match = _IDENTIFIER_COMMAND_RE.match(content)
    if match:
        desc = _style_doxygen_description(match.group(4))
        return match.group(1) + match.group(2) + match.group(3) + desc, in_code_block

    match = _GENERIC_COMMAND_RE.match(content)
    if match:
        desc = _style_doxygen_description(match.group(3))
        return match.group(1) + match.group(2) + desc, in_code_block

    return _style_doxygen_description(content), in_code_block


def _style_block_comment(
    comment: str,
    line_styler: Callable[[str, bool], Tuple[str, bool]],
) -> str:
    lines = comment.splitlines(keepends=True)
    if not lines:
        return comment

    if len(lines) == 1:
        body, ending = _split_line_ending(lines[0])
        match = re.match(r"^(\s*/\*+!?<?\s*)(.*?)(\s*\*/\s*)$", body)
        if not match:
            return comment
        styled, _ = line_styler(match.group(2), False)
        return match.group(1) + styled + match.group(3) + ending

    output: List[str] = []
    in_code_block = False

    for idx, line in enumerate(lines):
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


def _style_doxygen_block_comment(comment: str) -> str:
    return _style_block_comment(comment, _style_doxygen_line)


def _style_general_block_comment(comment: str) -> str:
    return _style_block_comment(comment, lambda content, state: (_style_general_comment_text(content), state))


def _style_general_line_comment(comment: str) -> str:
    match = re.match(r"^(//[!/<>]*\s*)(.*)$", comment)
    if not match:
        return comment
    return match.group(1) + _style_general_comment_text(match.group(2))


def _style_xml_doc_text(content: str, in_code_block: bool) -> Tuple[str, bool]:
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
            output.append(style_text(part, protected_patterns=[_BACKTICK_PATTERN]))

    return "".join(output), code_block


def _style_xml_doc_block(comment_block: str) -> str:
    lines = comment_block.splitlines(keepends=True)
    output: List[str] = []
    in_code_block = False

    for line in lines:
        body, ending = _split_line_ending(line)
        match = re.match(r"^(\s*///\s?)(.*)$", body)
        if not match:
            output.append(line)
            continue
        prefix = match.group(1)
        content = match.group(2)
        styled, in_code_block = _style_xml_doc_text(content, in_code_block)
        output.append(prefix + styled + ending)

    return "".join(output)


def _style_doxygen_line_block(comment_block: str) -> str:
    lines = comment_block.splitlines(keepends=True)
    output: List[str] = []
    in_code_block = False

    for line in lines:
        body, ending = _split_line_ending(line)
        match = re.match(r"^(\s*//[!/<>]*\s?)(.*)$", body)
        if not match:
            output.append(line)
            continue
        prefix = match.group(1)
        content = match.group(2)
        styled, in_code_block = _style_doxygen_line(content, in_code_block)
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


def _style_c_like_comments(text: str, language: str) -> str:
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
            result.append(_style_xml_doc_block(text[i:end]))
            i = end
            last = i
            continue

        if text.startswith("//!", i) and _only_whitespace_since_line_start(text, i):
            result.append(text[last:i])
            end = _consume_line_comment_block(text, i, "//!")
            result.append(_style_doxygen_line_block(text[i:end]))
            i = end
            last = i
            continue

        if text.startswith("//", i):
            result.append(text[last:i])
            end = _consume_to_line_end(text, i)
            result.append(_style_general_line_comment(text[i:end]))
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
            if comment.startswith("/**") or comment.startswith("/*!") or comment.startswith("/**<"):
                result.append(_style_doxygen_block_comment(comment))
            else:
                result.append(_style_general_block_comment(comment))
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


def _style_hash_comment_content(prefix: str, content: str) -> str:
    return prefix + _style_general_comment_text(content)


def _style_hash_comments(text: str, language: str) -> str:
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

        prefix_end = comment_start + 1
        while prefix_end < len(body) and body[prefix_end] == " ":
            prefix_end += 1

        output.append(
            body[:comment_start]
            + _style_hash_comment_content(body[comment_start:prefix_end], body[prefix_end:])
            + ending
        )

    return "".join(output)
