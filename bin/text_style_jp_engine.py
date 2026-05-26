#!/usr/bin/env python3
"""Japanese text styling engine shared by multiple frontends."""

import difflib
import json
import os
import re
import unicodedata
from enum import Enum, auto
from itertools import product
from typing import Callable, List, Match, Optional, Pattern, Sequence, Tuple, Union


_URL_RE = re.compile(r"https?://\S+")
_URL_TRAILING_PUNCT = frozenset("。、！？：；」』）】〕〉》〙〗")
_FULL_KATAKANA_RE = re.compile(r"^[\u30A0-\u30FF]+$")

_no_space_words: List[str] = []
_replace_pairs: List[Tuple[str, str]] = []
_add_space_pairs: List[Tuple[str, str]] = []
_dict_loaded = False
_replace_sources: dict = {}    # from_word → 辞書ファイルパス
_add_space_sources: dict = {}  # from_word → 辞書ファイルパス

_sudachi_state: Optional[bool] = None
_sudachi_tok = None
_KATAKANA_RUN_RE = re.compile(r"[ァ-ヺー]+")
_KATAKANA_RUN_WITH_SPACES_RE = re.compile(r"[ァ-ヺー]+(?: [ァ-ヺー]+)+")
_no_space_set: set = set()


class CharType(Enum):
    """Character category."""

    HALFWIDTH_ALNUM = auto()
    FULLWIDTH_ALNUM = auto()
    HIRAGANA = auto()
    KATAKANA_FULL = auto()
    KATAKANA_HALF = auto()
    KANJI = auto()
    PUNCTUATION_JP = auto()
    PUNCTUATION_EN = auto()
    BRACKET_OPEN = auto()
    BRACKET_CLOSE = auto()
    SPACE = auto()
    UNIT_NO_SPACE = auto()
    OTHER = auto()


class ValidationResult:
    """Validation result container."""

    def __init__(
        self,
        is_valid: bool,
        original: str,
        corrected: str,
        differences: List[Tuple[int, str, str]],
    ) -> None:
        self.is_valid = is_valid
        self.original = original
        self.corrected = corrected
        self.differences = differences


StylePostProcess = Optional[Callable[[str], str]]


class Finding:
    """dry-run モードで検出された個別の変更。"""

    def __init__(
        self,
        line: int,
        column: int,
        original: str,
        corrected: str,
        rule: str,
        source: str = "",
        message: str = "",
    ) -> None:
        self.line = line          # 1-based 行番号
        self.column = column      # 1-based 列番号
        self.original = original  # 変更前テキスト断片
        self.corrected = corrected  # 変更後テキスト断片
        self.rule = rule          # ルール ID
        self.source = source      # 辞書ファイルパス (辞書ルールのみ)
        self.message = message    # ルールの説明


class DiagnosticCollector:
    """dry-run モードで Finding を収集する。"""

    def __init__(self) -> None:
        self.findings: List[Finding] = []
        self._line: int = 0

    def set_line(self, line: int) -> None:
        self._line = line

    def add(
        self,
        column: int,
        original: str,
        corrected: str,
        rule: str,
        source: str = "",
        message: str = "",
    ) -> None:
        self.findings.append(
            Finding(self._line, column, original, corrected, rule, source, message)
        )


def _record_step_changes(
    before: str,
    after: str,
    rule: str,
    collector: "DiagnosticCollector",
    source: str = "",
    message: str = "",
) -> None:
    """before→after の差分を Finding として collector に追加する。"""
    if before == after:
        return
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        original_fragment = before[i1:i2]
        corrected_fragment = after[j1:j2]
        # NUL 文字を含む断片はプレースホルダー由来のため除外する
        if "\x00" in original_fragment or "\x00" in corrected_fragment:
            continue
        collector.add(i1 + 1, original_fragment, corrected_fragment, rule, source, message)


def _strip_jsonc(text: str) -> str:
    """Strip JSONC comments and trailing commas while preserving strings."""

    chars = []
    in_string = False
    escape = False
    line_comment = False
    block_comment = False
    i = 0

    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""

        if line_comment:
            if char == "\n":
                line_comment = False
                chars.append(char)
            i += 1
            continue

        if block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                i += 2
                continue
            if char == "\n":
                chars.append(char)
            i += 1
            continue

        if in_string:
            chars.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == "\"":
                in_string = False
            i += 1
            continue

        if char == "\"":
            in_string = True
            chars.append(char)
            i += 1
            continue

        if char == "/" and next_char == "/":
            line_comment = True
            i += 2
            continue

        if char == "/" and next_char == "*":
            block_comment = True
            i += 2
            continue

        chars.append(char)
        i += 1

    without_comments = "".join(chars)
    chars = []
    in_string = False
    escape = False
    i = 0

    while i < len(without_comments):
        char = without_comments[i]

        if in_string:
            chars.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == "\"":
                in_string = False
            i += 1
            continue

        if char == "\"":
            in_string = True
            chars.append(char)
            i += 1
            continue

        if char == ",":
            j = i + 1
            while j < len(without_comments) and without_comments[j].isspace():
                j += 1
            if j < len(without_comments) and without_comments[j] in "}]":
                i += 1
                continue

        chars.append(char)
        i += 1

    return "".join(chars)


def _loads_jsonc(text: str):
    return json.loads(_strip_jsonc(text))


def _is_full_katakana_text(text: str) -> bool:
    return bool(text) and _FULL_KATAKANA_RE.fullmatch(text) is not None


def _is_full_katakana_char(char: str) -> bool:
    return len(char) == 1 and _FULL_KATAKANA_RE.fullmatch(char) is not None


def _has_non_katakana_boundaries(text: str, start: int, length: int) -> bool:
    prev_char = text[start - 1] if start > 0 else ""
    next_char = text[start + length] if start + length < len(text) else ""
    return not _is_full_katakana_char(prev_char) and not _is_full_katakana_char(next_char)


def _expand_add_space_pairs(
    add_space_pairs: List[Tuple[str, str]],
    replace_pairs: List[Tuple[str, str]],
) -> List[Tuple[str, str]]:
    replace_reverse_map = {}
    for from_word, to_word in replace_pairs:
        if not (_is_full_katakana_text(from_word) and _is_full_katakana_text(to_word)):
            continue
        replace_reverse_map.setdefault(to_word, [])
        if from_word not in replace_reverse_map[to_word]:
            replace_reverse_map[to_word].append(from_word)

    expanded_pairs = []
    seen_pairs = set()
    for from_word, to_word in add_space_pairs:
        if (from_word, to_word) not in seen_pairs:
            expanded_pairs.append((from_word, to_word))
            seen_pairs.add((from_word, to_word))

        parts = to_word.split(" ")
        if len(parts) < 2:
            continue

        part_variants = []
        for part in parts:
            variants = [part]
            if _is_full_katakana_text(part):
                for alias in replace_reverse_map.get(part, []):
                    if alias not in variants:
                        variants.append(alias)
            part_variants.append(variants)

        for variant_parts in product(*part_variants):
            alias_from = "".join(variant_parts)
            if (alias_from, to_word) in seen_pairs:
                continue
            expanded_pairs.append((alias_from, to_word))
            seen_pairs.add((alias_from, to_word))

    return expanded_pairs


def load_dictionaries() -> None:
    """Load dictionary files only once."""

    global _dict_loaded
    if _dict_loaded:
        return
    _dict_loaded = True

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_paths = [
        os.path.join(os.path.expanduser("~"), ".text_style_jp"),
        os.path.join(script_dir, "..", ".text_style_jp"),
        os.path.join(os.getcwd(), ".text_style_jp"),
    ]

    seen_paths = set()
    search_paths = []
    for path in candidate_paths:
        abs_path = os.path.abspath(path)
        if abs_path not in seen_paths:
            seen_paths.add(abs_path)
            search_paths.append(abs_path)

    # word -> "no_space" or "add_space" の最終分類。ファイル名昇順で後ファイルが勝つ。
    # 同一ファイル内では add_space が no_space に勝つ。
    word_kind = {}
    add_space_to = {}    # add_space として確定した語の変換先
    no_space_order = []  # no_space として初めて登場した語の挿入順
    replace_map = {}
    replace_source: dict = {}     # from_word → ファイルパス (出典追跡用)
    add_space_source: dict = {}   # from_word → ファイルパス (出典追跡用)

    file_entries = []  # (fname, dir_index, abs_path)
    for di, dict_dir in enumerate(search_paths):
        if not os.path.isdir(dict_dir):
            continue
        for fname in os.listdir(dict_dir):
            if not fname.endswith(".json"):
                continue
            file_entries.append((fname, di, os.path.join(dict_dir, fname)))
    file_entries.sort(key=lambda e: (e[0], e[1]))

    for _fname, _di, fpath in file_entries:
        try:
            with open(fpath, encoding="utf-8") as handle:
                data = _loads_jsonc(handle.read())
        except Exception:
            continue

        file_ns = set()
        file_as = {}
        for word in data.get("no_space", []):
            if isinstance(word, str):
                file_ns.add(word)
        for pair in data.get("add_space", []):
            if isinstance(pair, dict) and "from" in pair and "to" in pair:
                file_as[pair["from"]] = pair["to"]
                add_space_source[pair["from"]] = fpath
        for pair in data.get("replace", []):
            if isinstance(pair, dict) and "from" in pair and "to" in pair:
                replace_map[pair["from"]] = pair["to"]
                replace_source[pair["from"]] = fpath

        for word in file_ns:
            if word not in file_as:
                word_kind[word] = "no_space"
                add_space_to.pop(word, None)
                if word not in no_space_order:
                    no_space_order.append(word)
        for word, to in file_as.items():
            word_kind[word] = "add_space"
            add_space_to[word] = to

    final_no_space = [w for w in no_space_order if word_kind.get(w) == "no_space"]
    final_add_space = [(w, t) for w, t in add_space_to.items() if word_kind.get(w) == "add_space"]

    _no_space_words[:] = final_no_space
    _no_space_set.clear()
    _no_space_set.update(final_no_space)
    _replace_pairs[:] = list(replace_map.items())
    _replace_sources.clear()
    _replace_sources.update(replace_source)

    expanded = _expand_add_space_pairs(final_add_space, _replace_pairs)
    final_expanded = [(f, t) for f, t in expanded if f not in _no_space_set]
    _add_space_pairs[:] = final_expanded
    _add_space_sources.clear()
    # エイリアス展開されたペアは元の add_space エントリの出典を継承する
    for from_word, _to_word in final_expanded:
        if from_word in add_space_source:
            _add_space_sources[from_word] = add_space_source[from_word]
        else:
            # エイリアス: 同じ to_word を持つ元エントリの出典を探す
            for orig_from, orig_src in add_space_source.items():
                if add_space_to.get(orig_from) == _to_word:
                    _add_space_sources[from_word] = orig_src
                    break


def get_char_type(char: str) -> CharType:
    if len(char) != 1:
        return CharType.OTHER

    code = ord(char)

    if char in " \t　":
        return CharType.SPACE
    if ("A" <= char <= "Z") or ("a" <= char <= "z") or ("0" <= char <= "9"):
        return CharType.HALFWIDTH_ALNUM
    if ("Ａ" <= char <= "Ｚ") or ("ａ" <= char <= "ｚ") or ("０" <= char <= "９"):
        return CharType.FULLWIDTH_ALNUM
    if 0x3040 <= code <= 0x309F:
        return CharType.HIRAGANA
    if 0x30A0 <= code <= 0x30FF:
        return CharType.KATAKANA_FULL
    if 0xFF65 <= code <= 0xFF9F:
        return CharType.KATAKANA_HALF
    if (0x4E00 <= code <= 0x9FFF) or (0x3400 <= code <= 0x4DBF):
        return CharType.KANJI
    if char in "、。，．":
        return CharType.PUNCTUATION_JP
    if char in ",.!?:;":
        return CharType.PUNCTUATION_EN
    if char in "°%％":
        return CharType.UNIT_NO_SPACE
    if char in "([{（［｛「『【〔〈《":
        return CharType.BRACKET_OPEN
    if char in ")]}）］｝」』】〕〉》":
        return CharType.BRACKET_CLOSE
    return CharType.OTHER


def is_fullwidth(char: str) -> bool:
    return get_char_type(char) in {
        CharType.FULLWIDTH_ALNUM,
        CharType.HIRAGANA,
        CharType.KATAKANA_FULL,
        CharType.KANJI,
    }


def is_halfwidth_alnum(char: str) -> bool:
    return get_char_type(char) == CharType.HALFWIDTH_ALNUM


FULLWIDTH_TO_HALFWIDTH = str.maketrans(
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
    "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    "０１２３４５６７８９（）［］｛｝",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789()[]{}",
)


HALFWIDTH_KATAKANA_TO_FULLWIDTH = {
    "ｦ": "ヲ", "ｧ": "ァ", "ｨ": "ィ", "ｩ": "ゥ", "ｪ": "ェ",
    "ｫ": "ォ", "ｬ": "ャ", "ｭ": "ュ", "ｮ": "ョ", "ｯ": "ッ",
    "ｰ": "ー", "ｱ": "ア", "ｲ": "イ", "ｳ": "ウ", "ｴ": "エ",
    "ｵ": "オ", "ｶ": "カ", "ｷ": "キ", "ｸ": "ク", "ｹ": "ケ",
    "ｺ": "コ", "ｻ": "サ", "ｼ": "シ", "ｽ": "ス", "ｾ": "セ",
    "ｿ": "ソ", "ﾀ": "タ", "ﾁ": "チ", "ﾂ": "ツ", "ﾃ": "テ",
    "ﾄ": "ト", "ﾅ": "ナ", "ﾆ": "ニ", "ﾇ": "ヌ", "ﾈ": "ネ",
    "ﾉ": "ノ", "ﾊ": "ハ", "ﾋ": "ヒ", "ﾌ": "フ", "ﾍ": "ヘ",
    "ﾎ": "ホ", "ﾏ": "マ", "ﾐ": "ミ", "ﾑ": "ム", "ﾒ": "メ",
    "ﾓ": "モ", "ﾔ": "ヤ", "ﾕ": "ユ", "ﾖ": "ヨ", "ﾗ": "ラ",
    "ﾘ": "リ", "ﾙ": "ル", "ﾚ": "レ", "ﾛ": "ロ", "ﾜ": "ワ",
    "ﾝ": "ン", "ﾞ": "゛", "ﾟ": "゜",
}


DAKUTEN_COMBINATIONS = {
    ("ｶ", "ﾞ"): "ガ", ("ｷ", "ﾞ"): "ギ", ("ｸ", "ﾞ"): "グ", ("ｹ", "ﾞ"): "ゲ", ("ｺ", "ﾞ"): "ゴ",
    ("ｻ", "ﾞ"): "ザ", ("ｼ", "ﾞ"): "ジ", ("ｽ", "ﾞ"): "ズ", ("ｾ", "ﾞ"): "ゼ", ("ｿ", "ﾞ"): "ゾ",
    ("ﾀ", "ﾞ"): "ダ", ("ﾁ", "ﾞ"): "ヂ", ("ﾂ", "ﾞ"): "ヅ", ("ﾃ", "ﾞ"): "デ", ("ﾄ", "ﾞ"): "ド",
    ("ﾊ", "ﾞ"): "バ", ("ﾋ", "ﾞ"): "ビ", ("ﾌ", "ﾞ"): "ブ", ("ﾍ", "ﾞ"): "ベ", ("ﾎ", "ﾞ"): "ボ",
    ("ﾊ", "ﾟ"): "パ", ("ﾋ", "ﾟ"): "ピ", ("ﾌ", "ﾟ"): "プ", ("ﾍ", "ﾟ"): "ペ", ("ﾎ", "ﾟ"): "ポ",
    ("ｳ", "ﾞ"): "ヴ",
}


_HALFWIDTH_BRACKETS_OPEN = set("([{")
_HALFWIDTH_BRACKETS_CLOSE = set(")]}")
_FULLWIDTH_NO_SPACE = set("・。、，．！？…‥")


def convert_fullwidth_alnum_to_halfwidth(text: str) -> str:
    return text.translate(FULLWIDTH_TO_HALFWIDTH)


def convert_halfwidth_katakana_to_fullwidth(text: str) -> str:
    result = []
    i = 0
    while i < len(text):
        char = text[i]
        if i + 1 < len(text) and text[i + 1] in "ﾞﾟ":
            combined = DAKUTEN_COMBINATIONS.get((char, text[i + 1]))
            if combined:
                result.append(combined)
                i += 2
                continue
        if char in HALFWIDTH_KATAKANA_TO_FULLWIDTH:
            result.append(HALFWIDTH_KATAKANA_TO_FULLWIDTH[char])
        else:
            result.append(char)
        i += 1
    return "".join(result)


def _needs_space_between(prev_char: str, curr_char: str) -> bool:
    """Return True if a space should be inserted between prev_char and curr_char.

    Mirrors the boundary detection logic in insert_space_between_fullwidth_and_halfwidth,
    and is used to restore correct spacing at no_space_words placeholder boundaries.
    """
    if not prev_char or prev_char in " \t　" or curr_char == " ":
        return False
    prev_is_fullwidth = is_fullwidth(prev_char)
    curr_is_fullwidth = is_fullwidth(curr_char)
    curr_needs_space_left = is_halfwidth_alnum(curr_char) or curr_char in _HALFWIDTH_BRACKETS_OPEN
    prev_needs_space_right = is_halfwidth_alnum(prev_char) or prev_char in _HALFWIDTH_BRACKETS_CLOSE
    return (
        ((prev_is_fullwidth and curr_needs_space_left) or (prev_needs_space_right and curr_is_fullwidth))
        and prev_char not in _FULLWIDTH_NO_SPACE
        and curr_char not in _FULLWIDTH_NO_SPACE
    )


def insert_space_between_fullwidth_and_halfwidth(text: str) -> str:
    result = []
    prev_char = ""

    for char in text:
        if prev_char and char != " ":
            prev_is_fullwidth = is_fullwidth(prev_char)
            curr_is_fullwidth = is_fullwidth(char)
            curr_needs_space_left = is_halfwidth_alnum(char) or char in _HALFWIDTH_BRACKETS_OPEN
            prev_needs_space_right = is_halfwidth_alnum(prev_char) or prev_char in _HALFWIDTH_BRACKETS_CLOSE

            if (
                ((prev_is_fullwidth and curr_needs_space_left) or (prev_needs_space_right and curr_is_fullwidth))
                and prev_char not in _FULLWIDTH_NO_SPACE
                and char not in _FULLWIDTH_NO_SPACE
            ):
                if not result or result[-1] != " ":
                    result.append(" ")

        result.append(char)
        prev_char = char

    return "".join(result)


def remove_space_before_punctuation(text: str) -> str:
    text = re.sub(r" +([、。，．,:;!！?？])", r"\1", text)
    text = re.sub(r" +\.(?![A-Za-z])", ".", text)
    return text


def remove_space_around_middle_dot_between_katakana(text: str) -> str:
    return re.sub(r"(?<=[ァ-ヿ])\s*・\s*(?=[ァ-ヿ])", "・", text)


def remove_space_inside_brackets(text: str) -> str:
    text = re.sub(r"([\(\[{（［｛「『【〔〈《]) +", r"\1", text)
    text = re.sub(r" +([\)\]}）］｝」』】〕〉》])", r"\1", text)
    return text


def remove_space_before_unit_no_space(text: str) -> str:
    return re.sub(r"(\d) +([°%％])", r"\1\2", text)


def remove_space_before_mm_unit(text: str) -> str:
    return re.sub(r"(\d) +(mm)\b", r"\1\2", text)


def add_space_after_punctuation_before_alnum(text: str) -> str:
    return re.sub(r"([?？!！])([A-Za-z0-9])", r"\1 \2", text)


def add_space_after_number_before_bracket(text: str) -> str:
    return re.sub(r"(\d/\d+)(\()", r"\1 \2", text)


def add_space_before_supplemental_bracket(text: str) -> str:
    def _replace(match: Match[str]) -> str:
        content = match.group(2)
        if re.search(r"[^\x00-\x7F]|:", content):
            return match.group(1) + " (" + content + ")"
        return match.group(0)

    return re.sub(r"([A-Za-z0-9_*])\(([^)]*)\)", _replace, text)


def normalize_spaces(text: str) -> str:
    text = text.replace("　", " ")
    text = re.sub(r"(?<=[^\s|]) {2,}(?=[^\s|])", " ", text)
    return text


_STYLE_PROSE_STEPS = [
    ("fullwidth-alnum",          convert_fullwidth_alnum_to_halfwidth,                   "全角英数字を半角に変換"),
    ("halfwidth-katakana",       convert_halfwidth_katakana_to_fullwidth,                "半角カタカナを全角に変換"),
    ("normalize-spaces",         normalize_spaces,                                       "スペースを正規化"),
    ("fullwidth-halfwidth-space", insert_space_between_fullwidth_and_halfwidth,          "全角/半角境界にスペースを挿入"),
    ("space-before-punctuation", remove_space_before_punctuation,                        "句読点前のスペースを削除"),
    ("space-around-middledot",   remove_space_around_middle_dot_between_katakana,        "中黒前後のスペースを削除"),
    ("space-inside-brackets",    remove_space_inside_brackets,                           "括弧内のスペースを削除"),
    ("space-before-unit",        remove_space_before_unit_no_space,                      "単位記号前のスペースを削除"),
    ("space-before-mm",          remove_space_before_mm_unit,                            "mm 前のスペースを削除"),
    ("space-after-punctuation",  add_space_after_punctuation_before_alnum,               "句読点後にスペースを挿入"),
    ("space-after-number-bracket", add_space_after_number_before_bracket,               "数字/括弧間にスペースを挿入"),
    ("supplemental-bracket",     add_space_before_supplemental_bracket,                  "補足括弧前にスペースを挿入"),
    ("normalize-spaces",         normalize_spaces,                                       "スペースを正規化"),
]


def style_prose(
    text: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    for rule_id, func, message in _STYLE_PROSE_STEPS:
        before = text
        text = func(text)
        if collector is not None:
            _record_step_changes(before, text, rule_id, collector, message=message)
    return text


apply_ms_style = style_prose


def _has_kanji_prev_char(text: str, i: int) -> bool:
    return i > 0 and get_char_type(text[i - 1]) == CharType.KANJI


def _replace_skip_existing(
    text: str,
    from_word: str,
    to_word: str,
    collector: Optional["DiagnosticCollector"] = None,
    source: str = "",
) -> str:
    if from_word == to_word:
        return text

    require_boundary = _is_full_katakana_text(from_word) and _is_full_katakana_text(to_word)
    from_starts_with_kanji = bool(from_word) and get_char_type(from_word[0]) == CharType.KANJI
    result = []
    i = 0
    flen = len(from_word)
    tlen = len(to_word)
    # result 側での現在位置 (列番号計算に使う)
    result_pos = 0

    while i < len(text):
        if flen >= tlen:
            if text[i:i + flen] == from_word and (
                not require_boundary or _has_non_katakana_boundaries(text, i, flen)
            ) and not (from_starts_with_kanji and _has_kanji_prev_char(text, i)):
                if collector is not None and "\x00" not in from_word:
                    collector.add(result_pos + 1, from_word, to_word, "dict-replace", source, "辞書 replace")
                result.append(to_word)
                result_pos += len(to_word)
                i += flen
                continue
            if text[i:i + tlen] == to_word and (
                not require_boundary or _has_non_katakana_boundaries(text, i, tlen)
            ):
                result.append(to_word)
                result_pos += tlen
                i += tlen
                continue
        else:
            if text[i:i + tlen] == to_word and (
                not require_boundary or _has_non_katakana_boundaries(text, i, tlen)
            ):
                result.append(to_word)
                result_pos += tlen
                i += tlen
                continue
            if text[i:i + flen] == from_word and (
                not require_boundary or _has_non_katakana_boundaries(text, i, flen)
            ) and not (from_starts_with_kanji and _has_kanji_prev_char(text, i)):
                if collector is not None and "\x00" not in from_word:
                    collector.add(result_pos + 1, from_word, to_word, "dict-replace", source, "辞書 replace")
                result.append(to_word)
                result_pos += len(to_word)
                i += flen
                continue

        result.append(text[i])
        result_pos += 1
        i += 1

    return "".join(result)


def _apply_add_space_pairs(
    text: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    for from_word, to_word in sorted(_add_space_pairs, key=lambda pair: len(pair[0]), reverse=True):
        if from_word not in text:
            continue
        before = text
        text = text.replace(from_word, to_word)
        if collector is not None and before != text:
            _record_step_changes(
                before, text, "dict-add-space", collector,
                source=_add_space_sources.get(from_word, ""),
                message="辞書 add_space",
            )
    return text


def _protect_patterns(
    text: str,
    protected_patterns: Sequence[Union[str, Pattern[str]]],
) -> Tuple[str, List[Tuple[str, str]]]:
    replacements: List[Tuple[str, str]] = []
    protected = text

    for pattern in protected_patterns:
        regex = re.compile(pattern) if isinstance(pattern, str) else pattern
        new_text_parts = []
        last = 0
        for match in regex.finditer(protected):
            new_text_parts.append(protected[last:match.start()])
            placeholder = f"\x00PROT{len(replacements)}\x00"
            original = match.group(0)
            replacements.append((placeholder, original))
            new_text_parts.append(placeholder)
            last = match.end()
        new_text_parts.append(protected[last:])
        protected = "".join(new_text_parts)

    return protected, replacements


def _protect_urls(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    replacements: List[Tuple[str, str]] = []

    def _replacer(match: Match[str]) -> str:
        url = match.group(0)
        while url and url[-1] in _URL_TRAILING_PUNCT:
            url = url[:-1]
        if len(url) <= len("https://"):
            return match.group(0)
        placeholder = f"\x00URL{len(replacements)}\x00"
        replacements.append((placeholder, url))
        return placeholder + match.group(0)[len(url):]

    protected = _URL_RE.sub(_replacer, text)
    return protected, replacements


def _restore_replacements(text: str, replacements: Sequence[Tuple[str, str]]) -> str:
    restored = text
    for placeholder, original in replacements:
        restored = restored.replace(placeholder, original, 1)
    return restored


_NON_WORD_BOUNDARY_KATAKANA = frozenset("ー・")


def _restore_nosp_with_boundaries(text: str, replacements: List[Tuple[str, str]]) -> str:
    """no_space_words のプレースホルダーを復元し、境界にスペースを補う。

    SudachiPy が保護語の隣接部分を分割した後、復元時に境界スペースが失われる
    ケースを補正する。例: \x00NOSP\x00パフォーマンス → トラブルシューティング パフォーマンス

    また、no_space_words 保護によってプレースホルダー境界で全角↔半角ブラケットの
    スペース挿入が阻害されるケースも補正する。
    例: ジョブ\x00→\x00(スクリプト...) → ジョブ (スクリプト...)

    長音記号 (ー) と中黒 (・) は Unicode カタカナ範囲に含まれるが、単独で語境界を
    構成しないため、境界判定では除外する (例: 「カテゴリ」+「ー」を「カテゴリ ー」に
    分離しない、「ビルド」+「・」を「ビルド ・」に分離しない)。
    """
    restored = text
    for placeholder, original in replacements:
        while placeholder in restored:
            idx = restored.index(placeholder)
            end = idx + len(placeholder)
            space_before = (
                idx > 0
                and (
                    (
                        _is_full_katakana_char(restored[idx - 1])
                        and restored[idx - 1] not in _NON_WORD_BOUNDARY_KATAKANA
                        and original
                        and _is_full_katakana_char(original[0])
                        and original[0] not in _NON_WORD_BOUNDARY_KATAKANA
                    )
                    or (
                        bool(original)
                        and _needs_space_between(restored[idx - 1], original[0])
                    )
                )
            )
            space_after = (
                end < len(restored)
                and original
                and (
                    (
                        _is_full_katakana_char(original[-1])
                        and original[-1] not in _NON_WORD_BOUNDARY_KATAKANA
                        and _is_full_katakana_char(restored[end])
                        and restored[end] not in _NON_WORD_BOUNDARY_KATAKANA
                    )
                    or _needs_space_between(original[-1], restored[end])
                )
            )
            restored = (
                restored[:idx]
                + (" " if space_before else "")
                + original
                + (" " if space_after else "")
                + restored[end:]
            )
    return restored


def _init_sudachi() -> bool:
    """SudachiPy を初期化する。未インストールなら自動インストールを試みる。"""
    global _sudachi_state, _sudachi_tok
    if _sudachi_state is not None:
        return _sudachi_state
    try:
        import sudachipy
        import sudachipy.dictionary
        _sudachi_tok = sudachipy.dictionary.Dictionary().create()
        _sudachi_state = True
        return True
    except ImportError:
        pass
    import importlib
    import subprocess
    import sys
    try:
        print(
            "SudachiPy が見つかりません。インストールしています (初回のみ)...",
            file=sys.stderr,
        )
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--user", "sudachipy", "sudachidict-core"]
        )
        importlib.invalidate_caches()
        import sudachipy
        import sudachipy.dictionary
        _sudachi_tok = sudachipy.dictionary.Dictionary().create()
        _sudachi_state = True
        return True
    except Exception:
        _sudachi_state = False
        return False


def _join_katakana_split_by_no_space(text: str) -> str:
    """カタカナ列 + 半角スペース + カタカナ列 を、連結形が no_space に登録されていれば結合する。

    ユーザーが誤って「ワークス ペース」「サブ ディレクトリ」のようにスペース入りで
    書いた場合に、no_space 登録された単独カタカナ語へ復元する。
    no_space リストに登録された語が tbx 単独語または社内独自語であれば
    自動的に補正されるため、個別の replace 定義が不要になる。
    """
    if not _no_space_set:
        return text

    def _replace(match: re.Match) -> str:
        merged = match.group(0).replace(" ", "")
        if merged in _no_space_set:
            return merged
        return match.group(0)

    return _KATAKANA_RUN_WITH_SPACES_RE.sub(_replace, text)


def _split_katakana_with_sudachi(text: str) -> str:
    """SudachiPy モード B でカタカナ連続部分を分割する。"""
    if not _init_sudachi():
        return text
    import sudachipy

    def _replace(m: re.Match) -> str:
        morphemes = _sudachi_tok.tokenize(m.group(0), sudachipy.SplitMode.B)
        surfaces = [morph.surface() for morph in morphemes]
        return " ".join(surfaces)

    return _KATAKANA_RUN_RE.sub(_replace, text)


def style_text(
    text: str,
    protected_patterns: Optional[Sequence[Union[str, Pattern[str]]]] = None,
    postprocess: StylePostProcess = None,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    load_dictionaries()

    protected = text
    pattern_replacements: List[Tuple[str, str]] = []
    if protected_patterns:
        protected, pattern_replacements = _protect_patterns(protected, protected_patterns)

    protected, url_replacements = _protect_urls(protected)

    before = protected
    protected = _join_katakana_split_by_no_space(protected)
    if collector is not None:
        _record_step_changes(before, protected, "dict-no-space-join", collector, message="no_space 語のスペースを結合")

    # Sudachi B 分割や no_space 保護で対象文字列が分断される前に、
    # カタカナ replace を先行適用する。「カテゴリー → カテゴリ」のような逆方向 ー 削除や
    # 「スライドショ → スライドショー」のような順方向 ー 付与は、分割後に走らせると
    # from word の連続性が失われて適用されないため、前段で処理しておく。
    for from_word, to_word in _replace_pairs:
        protected = _replace_skip_existing(
            protected, from_word, to_word,
            collector=collector,
            source=_replace_sources.get(from_word, ""),
        )

    sorted_nosp = sorted(_no_space_words, key=len, reverse=True)
    nosp_replacements = []
    for idx, word in enumerate(sorted_nosp):
        placeholder = f"\x00NOSP{idx}\x00"
        protected = protected.replace(word, placeholder)
        nosp_replacements.append((placeholder, word))

    styled = style_prose(protected, collector=collector)

    before = styled
    styled = _split_katakana_with_sudachi(styled)
    if collector is not None:
        _record_step_changes(before, styled, "sudachi-split", collector, message="SudachiPy でカタカナを分割")

    styled = _restore_nosp_with_boundaries(styled, nosp_replacements)

    for placeholder, word in nosp_replacements:
        styled = styled.replace(word, placeholder)
    for from_word, to_word in _replace_pairs:
        styled = _replace_skip_existing(
            styled, from_word, to_word,
            collector=collector,
            source=_replace_sources.get(from_word, ""),
        )
    styled = _restore_nosp_with_boundaries(styled, nosp_replacements)
    styled = _apply_add_space_pairs(styled, collector=collector)

    styled = _restore_replacements(styled, url_replacements)
    styled = _restore_replacements(styled, pattern_replacements)

    if postprocess is not None:
        styled = postprocess(styled)

    return styled


def validate_text(text: str) -> ValidationResult:
    # Deprecated: DiagnosticCollector を style_text() に渡す方式を推奨する。
    corrected = style_prose(text)
    is_valid = text == corrected

    differences = []
    if not is_valid:
        for i, (orig_char, corr_char) in enumerate(
            zip(text.ljust(len(corrected)), corrected.ljust(len(text)))
        ):
            if orig_char != corr_char:
                differences.append((i, orig_char, corr_char))

    return ValidationResult(
        is_valid=is_valid,
        original=text,
        corrected=corrected,
        differences=differences,
    )


def contains_cjk(text: str) -> bool:
    """Return whether the text contains Japanese/CJK text."""

    for char in text:
        if unicodedata.east_asian_width(char) in {"W", "F"}:
            return True
    return False
