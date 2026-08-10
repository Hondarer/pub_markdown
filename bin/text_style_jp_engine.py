#!/usr/bin/env python3
"""Japanese text styling engine shared by multiple frontends."""

import contextlib
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
_NBSP = "\u00A0"

_no_space_words: List[str] = []
_replace_pairs: List[Tuple[str, str]] = []
_add_space_pairs: List[Tuple[str, str]] = []
_dict_loaded = False
_replace_sources: dict = {}    # from_word → 辞書ファイル パス
_add_space_sources: dict = {}  # from_word → 辞書ファイル パス

_sudachi_state: Optional[bool] = None
_sudachi_tok = None
_KATAKANA_RUN_RE = re.compile(r"[ァ-ヺー]+")
_KATAKANA_RUN_WITH_SPACES_RE = re.compile(r"[ァ-ヺー]+(?: [ァ-ヺー]+)+")
_no_space_set: set = set()
_replace_from_set: set = set()


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
        self.source = source      # 辞書ファイル パス (辞書ルールのみ)
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


def replace_nbsp_with_space(
    text: str,
    collector: Optional["DiagnosticCollector"] = None,
) -> str:
    """Replace NBSP (U+00A0) with ASCII spaces across the entire input."""
    if _NBSP not in text:
        return text

    if collector is not None:
        for line_no, line in enumerate(text.split("\n"), start=1):
            if _NBSP not in line:
                continue
            collector.set_line(line_no)
            for column, char in enumerate(line, start=1):
                if char == _NBSP:
                    collector.add(
                        column,
                        _NBSP,
                        " ",
                        "nbsp-space",
                        message="NBSP を半角スペースに変換",
                    )

    return text.replace(_NBSP, " ")


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


def _expand_segment_aliases(
    segment: str,
    replace_reverse_map: dict,
) -> List[str]:
    variants = [segment]
    seen = {segment}

    for to_word in sorted(replace_reverse_map, key=len, reverse=True):
        if to_word not in segment:
            continue
        current_variants = list(variants)
        for variant in current_variants:
            if to_word not in variant:
                continue
            for alias in replace_reverse_map[to_word]:
                alias_variant = variant.replace(to_word, alias)
                if alias_variant in seen:
                    continue
                variants.append(alias_variant)
                seen.add(alias_variant)

    return variants


def _expand_add_space_words(
    add_space_words: List[str],
    replace_pairs: List[Tuple[str, str]],
) -> List[Tuple[str, str]]:
    replace_reverse_map = {}
    for from_word, to_word in replace_pairs:
        replace_reverse_map.setdefault(to_word, [])
        if from_word not in replace_reverse_map[to_word]:
            replace_reverse_map[to_word].append(from_word)

    expanded_pairs = []
    seen_pairs = set()
    for to_word in add_space_words:
        compact_to = to_word.replace(" ", "")
        if (compact_to, to_word) not in seen_pairs:
            expanded_pairs.append((compact_to, to_word))
            seen_pairs.add((compact_to, to_word))
        parts = to_word.split(" ")
        if len(parts) < 2:
            segment_variants = [_expand_segment_aliases(to_word, replace_reverse_map)]
        else:
            segment_variants = [
                _expand_segment_aliases(part, replace_reverse_map)
                for part in parts
            ]

        for variant_parts in product(*segment_variants):
            alias_key = "".join(variant_parts)
            if (alias_key, to_word) in seen_pairs:
                continue
            expanded_pairs.append((alias_key, to_word))
            seen_pairs.add((alias_key, to_word))

    return expanded_pairs


def _drop_inverse_replace_pairs(replace_map: dict, replace_source: dict) -> None:
    """逆方向の replace ペア (a→b と b→a) が両立する場合、優先度の低い
    (basename が小さい) 側を除去する。両者を残すと適用順で相殺し、実変換は
    変わらないまま dry-run に無意味な往復変更が出力されるため。"""
    handled = set()
    for a in list(replace_map.keys()):
        b = replace_map.get(a)
        if b is None or b == a:
            continue
        if (a, b) in handled or (b, a) in handled:
            continue
        if replace_map.get(b) == a:
            handled.add((a, b))
            key_a = (os.path.basename(replace_source.get(a, "")), a)
            key_b = (os.path.basename(replace_source.get(b, "")), b)
            drop = a if key_a < key_b else b
            replace_map.pop(drop, None)
            replace_source.pop(drop, None)


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
    add_space_words = {}  # compact_word -> add_space 正規形
    no_space_order = []  # no_space として初めて登場した語の挿入順
    replace_map = {}
    replace_source: dict = {}     # from_word → ファイル パス (出典追跡用)
    add_space_source: dict = {}   # compact_word → ファイル パス (出典追跡用)

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
        for word in data.get("add_space", []):
            if isinstance(word, str):
                compact_word = word.replace(" ", "")
                file_as[compact_word] = word
                add_space_source[compact_word] = fpath
            else:
                raise ValueError(f"add_space entries must be strings: {fpath}")
        for pair in data.get("replace", []):
            if isinstance(pair, dict) and "from" in pair and "to" in pair:
                replace_map[pair["from"]] = pair["to"]
                replace_source[pair["from"]] = fpath

        for word in file_ns:
            if word not in file_as:
                word_kind[word] = "no_space"
                add_space_words.pop(word, None)
                if word not in no_space_order:
                    no_space_order.append(word)
        for word, to_word in file_as.items():
            word_kind[word] = "add_space"
            add_space_words[word] = to_word

    _drop_inverse_replace_pairs(replace_map, replace_source)

    # replace の見出し語は no_space 保護から外す。両方に属する語 (`チャンネル` など) を
    # 退避すると、分割後の replace が語へ届かず表記の統一が効かなくなる。
    # 分割済み表記の連結は _join_katakana_split_by_no_space が
    # _replace_from_set 側で拾うため、保護を外しても復元機能は失われない。
    final_no_space = [
        w for w in no_space_order
        if word_kind.get(w) == "no_space" and w not in replace_map
    ]
    final_add_space = [
        t for w, t in add_space_words.items()
        if word_kind.get(w) == "add_space"
    ]

    _no_space_words[:] = final_no_space
    _no_space_set.clear()
    _no_space_set.update(final_no_space)
    _replace_pairs[:] = list(replace_map.items())
    _replace_from_set.clear()
    _replace_from_set.update(from_word for from_word, _ in _replace_pairs)
    _replace_sources.clear()
    _replace_sources.update(replace_source)

    expanded = _expand_add_space_words(final_add_space, _replace_pairs)
    final_expanded = [(f, t) for f, t in expanded if f not in _no_space_set]
    _add_space_pairs[:] = final_expanded
    _add_space_sources.clear()
    # エイリアス展開されたペアは元の add_space エントリの出典を継承する
    for from_word, _to_word in final_expanded:
        compact_to = _to_word.replace(" ", "")
        if compact_to in add_space_source:
            _add_space_sources[from_word] = add_space_source[compact_to]


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
_FULLWIDTH_NO_SPACE = set("・。、，．！？…‥〜～")
_FULLWIDTH_COLON_NO_SPACE_FOLLOWERS = set("、。，．,;:!！?？)]}）］｝」』】〕〉》*_~")


def convert_fullwidth_alnum_to_halfwidth(text: str) -> str:
    return text.translate(FULLWIDTH_TO_HALFWIDTH)


def convert_fullwidth_colon_to_halfwidth(text: str) -> str:
    result = []
    for index, char in enumerate(text):
        if char != "：":
            result.append(char)
            continue

        result.append(":")
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if (
            next_char
            and not next_char.isspace()
            and next_char not in _FULLWIDTH_COLON_NO_SPACE_FOLLOWERS
        ):
            result.append(" ")

    return "".join(result)


_FULLWIDTH_QUESTION_EXCLAMATION = str.maketrans("？！", "?!")


def convert_fullwidth_question_exclamation_to_halfwidth(text: str) -> str:
    return text.translate(_FULLWIDTH_QUESTION_EXCLAMATION)


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
    text = re.sub(r" +([、。，．,;])", r"\1", text)
    # 直後が空白または行末の ? ! は、文末の約物ではなく記号そのものを指している
    # (「- ! で始まる否定パターン」など) ため、前のスペースを保持する。
    text = re.sub(r" +([?？!！])(?![=\s])", r"\1", text)
    # 直後が ASCII の識別子で始まるコロンは、約物ではなくトークンの一部
    # (「行全体が :key--> の形式」の `:key-->` など) を指すため、前のスペースを保持する。
    text = re.sub(r" +:(?![ =]|[A-Za-z0-9_])", ":", text)
    # 直後が空白または行末の . は、文末の約物ではなく記号そのものを指している
    # (「(数字 + . + 空白)」など) ため、前のスペースを保持する。
    text = re.sub(r" +\.(?![A-Za-z./\\\s])", ".", text)
    return text


def remove_space_around_middle_dot_between_katakana(text: str) -> str:
    return re.sub(r"(?<=[ァ-ヿ])\s*・\s*(?=[ァ-ヿ])", "・", text)


def remove_space_inside_brackets(text: str) -> str:
    # バックスラッシュでエスケープされた括弧 (LaTeX の \[ など) は文字そのものを
    # 指すため、直後のスペースを保持する。
    text = re.sub(r"(?<!\\)([\(\[{（［｛「『【〔〈《]) +", r"\1", text)
    text = re.sub(r" +([\)\]}）］｝」』】〕〉》])", r"\1", text)
    return text


def remove_space_before_unit_no_space(text: str) -> str:
    return re.sub(r"(\d) +([°%％])", r"\1\2", text)


def remove_space_before_mm_unit(text: str) -> str:
    return re.sub(r"(\d) +(mm)\b", r"\1\2", text)


# `? !` の直後に続いても半角スペースを挿入しない全角文字 (句読点・閉じ括弧・波ダッシュ・三点リーダー等)
_FULLWIDTH_NO_SPACE_AFTER_BANG = "・。、，．！？…‥〜～）］｝」』】〕〉》"


def add_space_after_punctuation_before_alnum(text: str) -> str:
    # 開き括弧 (も対象に含める。全角の `？（` は半角化後に `?(` となり、
    # 英数字と同じく直前の約物との間にスペースが必要になる。
    # 角括弧は Markdown の画像記法 `![alt](url)` を壊すため対象にしない。
    text = re.sub(r"([?？!！])([A-Za-z0-9(])", r"\1 \2", text)
    # 半角 `? !` の後に日本語 (全角文字) が続く場合もスペースを挿入する。
    # 直後が全角の句読点・閉じ括弧などのときは挿入しない。
    text = re.sub(
        r"([?？!！])(?=[^\x00-\x7F])(?![" + re.escape(_FULLWIDTH_NO_SPACE_AFTER_BANG) + r"])",
        r"\1 ",
        text,
    )
    return text


def add_space_after_number_before_bracket(text: str) -> str:
    return re.sub(r"(\d/\d+)(\()", r"\1 \2", text)


def add_space_before_supplemental_bracket(text: str) -> str:
    def _is_big_o_notation(prefix: str, content: str) -> bool:
        return prefix == "O" and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ^_+/#*.,-]*", content) is not None

    def _is_symbol_prefix(prefix: str) -> bool:
        return len(prefix) == 1 and unicodedata.category(prefix).startswith("S")

    def _is_expression_operator(prefix: str, previous_char: str) -> bool:
        return prefix in "+-*/%&|^" and (
            previous_char == ")"
            or previous_char == "]"
            or previous_char == "}"
            or previous_char == "`"
            or bool(re.fullmatch(r"[A-Za-z0-9_]", previous_char))
        )

    def _replace_symbol(content: str, prefix: str, previous_char: str, original: str) -> str:
        if prefix == "$":
            return original
        if _is_expression_operator(prefix, previous_char):
            return original
        if _is_symbol_prefix(prefix):
            return prefix + " (" + content + ")"
        return original

    def _replace(content: str, prefix: str, original: str) -> str:
        if _is_big_o_notation(prefix, content):
            return original
        if re.search(r"[^\x00-\x7F]|:", content):
            return prefix + " (" + content + ")"
        return original

    def _replace_acronym_suffix(content: str, prefix: str, original: str) -> str:
        if _is_big_o_notation(prefix, content):
            return original
        if re.fullmatch(r"[A-Z0-9][A-Z0-9 ._+/#*-]*", content):
            return prefix + " (" + content + ")"
        return original

    def _replace_ascii_slash_list(content: str, prefix: str, original: str) -> str:
        if _is_big_o_notation(prefix, content):
            return original
        if (
            re.fullmatch(r"[A-Za-z0-9_./-]*[A-Z0-9/][A-Za-z0-9_./-]*", prefix)
            and re.fullmatch(r"[A-Za-z0-9_./-]+(?:\s*/\s*[A-Za-z0-9_./-]+)+", content)
        ):
            return prefix + " (" + content + ")"
        return original

    def _replace_plain(match: Match[str]) -> str:
        return _replace(match.group(2), match.group(1), match.group(0))

    def _replace_emphasis(match: Match[str]) -> str:
        return _replace(match.group(2), match.group(1), match.group(0))

    def _replace_plain_acronym_suffix(match: Match[str]) -> str:
        return _replace_acronym_suffix(match.group(2), match.group(1), match.group(0))

    def _replace_emphasis_acronym_suffix(match: Match[str]) -> str:
        return _replace_acronym_suffix(match.group(2), match.group(1), match.group(0))

    def _replace_plain_ascii_slash_list(match: Match[str]) -> str:
        return _replace_ascii_slash_list(match.group(2), match.group(1), match.group(0))

    text = re.sub(
        r"([^\s()])\(([^)]*)\)",
        lambda match: _replace_symbol(
            match.group(2),
            match.group(1),
            text[match.start(1) - 1] if match.start(1) > 0 else "",
            match.group(0),
        ),
        text,
    )
    text = re.sub(r"([A-Za-z0-9_./-]+)\(([^)]*)\)", _replace_plain_ascii_slash_list, text)
    text = re.sub(r"([A-Za-z0-9_])\(([^)]*)\)", _replace_plain, text)
    text = re.sub(r"([+?:]=)\(([^)]*)\)", _replace_plain, text)
    text = re.sub(r"((?<=[^\s*])\*\*|(?<=[^\s_])__|(?<=[^\s*])\*|(?<=[^\s_])_)\(([^)]*)\)", _replace_emphasis, text)
    text = re.sub(
        r"([A-Za-z0-9_])\(([^)]*)\)(?=(?:\s*[^\x00-\x7F])|$)",
        _replace_plain_acronym_suffix,
        text,
    )
    return re.sub(
        r"((?<=[^\s*])\*\*|(?<=[^\s_])__|(?<=[^\s*])\*|(?<=[^\s_])_)\(([^)]*)\)(?=(?:\s*[^\x00-\x7F])|$)",
        _replace_emphasis_acronym_suffix,
        text,
    )


def normalize_spaces(text: str) -> str:
    text = text.replace("　", " ")
    text = re.sub(r"(?<=[^\s|]) {2,}(?=[^\s|])", " ", text)
    return text


_STYLE_PROSE_STEPS = [
    ("fullwidth-alnum",          convert_fullwidth_alnum_to_halfwidth,                   "全角英数字を半角に変換"),
    ("fullwidth-colon",          convert_fullwidth_colon_to_halfwidth,                   "全角コロンを半角に変換"),
    ("fullwidth-bang",           convert_fullwidth_question_exclamation_to_halfwidth,    "全角の疑問符・感嘆符を半角に変換"),
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
    text_without_spaces = text.replace(" ", "")
    pairs = sorted(
        _add_space_pairs,
        key=lambda pair: len(pair[0].replace(" ", "")),
        reverse=True,
    )
    candidates = []

    def _has_word_boundary(from_word: str, start: int, end: int) -> bool:
        if not from_word:
            return True
        if is_halfwidth_alnum(from_word[0]):
            if start > 0 and is_halfwidth_alnum(text[start - 1]):
                return False
        if is_halfwidth_alnum(from_word[-1]):
            if end < len(text) and is_halfwidth_alnum(text[end]):
                return False
        # カタカナで始まる (終わる) 語は、前後にカタカナが続くとき語の一部であり、
        # そこで区切ると残りが孤立する。「イベント フィルター」を
        # 「イベント フィルタリング」の先頭に当てると「リング」が取り残される。
        if _is_full_katakana_char(from_word[0]):
            if start > 0 and _is_full_katakana_char(text[start - 1]):
                return False
        if _is_full_katakana_char(from_word[-1]):
            if end < len(text) and _is_full_katakana_char(text[end]):
                return False
        return True

    for priority, (from_word, to_word) in enumerate(pairs):
        compact_from = from_word.replace(" ", "")
        if compact_from not in text_without_spaces:
            continue
        pattern = re.compile(" *".join(re.escape(char) for char in compact_from))

        for match in pattern.finditer(text):
            if not _has_word_boundary(compact_from, match.start(), match.end()):
                continue
            candidates.append(
                (priority, match.start(), match.end(), match.group(0), to_word, from_word)
            )

    selected = []
    for candidate in sorted(candidates, key=lambda item: (item[0], item[1])):
        _priority, start, end, _original, _corrected, _from_word = candidate
        overlaps = any(
            start < selected_end and end > selected_start
            for selected_start, selected_end, *_ in selected
        )
        if overlaps:
            continue
        selected.append((start, end, _original, _corrected, _from_word))

    if not selected:
        return text

    result = []
    pos = 0
    for start, end, original, corrected, from_word in sorted(selected):
        result.append(text[pos:start])
        result.append(corrected)
        if collector is not None and original != corrected:
            collector.add(
                start + 1,
                original,
                corrected,
                "dict-add-space",
                _add_space_sources.get(from_word, ""),
                "辞書 add_space",
            )
        pos = end
    result.append(text[pos:])
    return "".join(result)


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
    for placeholder, original in reversed(replacements):
        restored = restored.replace(placeholder, original, 1)
    return restored


_NON_WORD_BOUNDARY_KATAKANA = frozenset("ー・")

_PLAUSIBLE_FRAGMENT_CACHE: dict = {}


def _is_plausible_katakana_fragment(text: str, leading: bool) -> bool:
    """カタカナ列が、それ単独で 1 語として通用するかを判定する。

    no_space 語の保護によってカタカナ連続を区切るとき、区切りの残りが語として
    通用しない断片であれば、その区切り自体が誤りである。
    例: 「クオート」を「ク」+「オート」と区切ると「ク」が残る。

    辞書に載る語はこの判定に到達しない (プレースホルダーへ退避済みのため) ので、
    ここへ来るのは辞書外の文字列である。カタカナ連続の先頭にある 2 文字の辞書外
    カタカナは、独立した語ではなく長い語の先頭部分であることが多いため退ける
    (「パーミッション」の「パー」、「シーシャープ」の「シー」、
    「プリプロセス」の「プリ」)。末尾に残る 2 文字は、直前の辞書語で語頭が
    説明済みであり、独立した短い語であることが多いため認める
    (「テストログ」の「ログ」、「ファイルパス」の「パス」)。
    """
    cached = _PLAUSIBLE_FRAGMENT_CACHE.get((text, leading))
    if cached is not None:
        return cached
    if len(text) < (3 if leading else 2):
        _PLAUSIBLE_FRAGMENT_CACHE[(text, leading)] = False
        return False
    if not _init_sudachi():
        _PLAUSIBLE_FRAGMENT_CACHE[(text, leading)] = True
        return True
    import sudachipy

    morphemes = _sudachi_tok.tokenize(text, sudachipy.SplitMode.A)
    result = len(morphemes) == 1 and _is_valid_katakana_segment(morphemes[0])
    _PLAUSIBLE_FRAGMENT_CACHE[(text, leading)] = result
    return result


def _protect_katakana_run(run: str, mapping: dict, max_len: int, separator: str) -> str:
    """カタカナ連続 1 件を、no_space 語の左から最長一致で区切って退避する。

    無条件の部分一致で退避すると、語の途中で切れて復元時に誤った境界スペースが
    入る (「マップ」の退避が「アンマップ」を「アン マップ」にする)。
    左から最長一致で走査し、no_space 語に該当しない残りが 1 語として通用しない
    場合は、この連続に対する退避そのものを取りやめる。

    区切りが 2 つ以上になったときは、separator を語境界へ挿入する。
    復元時の境界判定は隣接文字を見るため、プレースホルダーどうしが隣り合う場合や
    語が長音で終わる場合に境界を検出できない。
    語彙の分割を行わない文脈 (コード フェンス内) では separator に空文字を渡す。
    """
    segments: List[str] = []
    pending = ""
    pos = 0
    while pos < len(run):
        matched = ""
        for length in range(min(max_len, len(run) - pos), 1, -1):
            candidate = run[pos:pos + length]
            if candidate in mapping:
                matched = candidate
                break
        if not matched:
            pending += run[pos]
            pos += 1
            continue
        if pending:
            if not _is_plausible_katakana_fragment(pending, leading=not segments):
                return run
            segments.append(pending)
            pending = ""
        segments.append(mapping[matched])
        pos += len(matched)
    if pending:
        if segments and not _is_plausible_katakana_fragment(pending, leading=False):
            return run
        segments.append(pending)
    return separator.join(segments)


def _protect_no_space_words(
    text: str, replacements: List[Tuple[str, str]], separator: str = " "
) -> str:
    """no_space 語をプレースホルダーへ退避する。

    カタカナだけで構成される語はカタカナ連続ごとに左から最長一致で退避する。
    それ以外 (英数字や空白を含む語) は従来どおり単純な部分一致で退避する。
    """
    katakana_map = {}
    protected = text
    for placeholder, word in replacements:
        if _KATAKANA_RUN_RE.fullmatch(word):
            katakana_map[word] = placeholder
        else:
            protected = protected.replace(word, placeholder)
    if not katakana_map:
        return protected
    max_len = max(len(word) for word in katakana_map)
    return _KATAKANA_RUN_RE.sub(
        lambda m: _protect_katakana_run(m.group(0), katakana_map, max_len, separator),
        protected,
    )


def _restore_no_space_words(text: str, replacements: List[Tuple[str, str]]) -> str:
    """no_space 語のプレースホルダーを、境界スペースを補わずに復元する。"""
    restored = text
    for placeholder, word in replacements:
        restored = restored.replace(placeholder, word)
    return restored


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
    """カタカナ列 + 半角スペース + カタカナ列 を、連結形が辞書にあれば結合する。

    ユーザーが誤って「ワークス ペース」「サブ ディレクトリ」のようにスペース入りで
    書いた場合に、no_space 登録された単独カタカナ語へ復元する。
    no_space リストに登録された語が tbx 単独語または社内独自語であれば
    自動的に補正されるため、個別の replace 定義が不要になる。

    連結形が replace の見出し語に一致する場合も結合する。「エラーハンド リング」の
    ように語の途中で分断されていると、見出し語「エラーハンドリング」に一致せず
    置換が働かないまま、さらに分割が進むため。
    """
    if not _no_space_set and not _replace_from_set:
        return text

    def _replace(match: re.Match) -> str:
        merged = match.group(0).replace(" ", "")
        if merged in _no_space_set or merged in _replace_from_set:
            return merged
        return match.group(0)

    return _KATAKANA_RUN_WITH_SPACES_RE.sub(_replace, text)


def _is_valid_katakana_segment(morph) -> bool:
    """Sudachi の形態素が、カタカナ複合語の分割単位として妥当かを判定する。

    分割の誤りは「スタイリング → スタイ リング」のように意味のない断片を生む。
    断片を生む分割は棄却して連結形へ戻すほうが安全なため、次を不当とみなす。

    - 1 文字の表層形 (「ク オート」の「ク」)
    - 未知語 (辞書にない断片。「リストア ップ」の「ップ」)
    - 接頭辞・接尾辞 (「サブ アイテム」の「サブ」)
    """
    surface = morph.surface()
    if len(surface) < 2:
        return False
    if morph.is_oov():
        return False
    pos = morph.part_of_speech()
    if pos and pos[0] == "接頭辞":
        return False
    if len(pos) > 1 and "接尾" in pos[1]:
        return False
    return True


def _merge_invalid_katakana_segments(morphemes: Sequence) -> List[str]:
    """不当な分割単位を隣接する単位へ結合し、妥当な区切りだけを残す。

    先頭が不当な場合は直後へ、それ以外は直前へ結合する。
    結合してできた語は再検証しない (分割しない方向は常に安全側のため)。
    """
    surfaces = [morph.surface() for morph in morphemes]
    valid = [_is_valid_katakana_segment(morph) for morph in morphemes]

    merged: List[str] = []
    pending = ""
    for surface, is_valid in zip(surfaces, valid):
        if not is_valid:
            if merged and not pending:
                merged[-1] += surface
            else:
                pending += surface
            continue
        if pending:
            merged.append(pending + surface)
            pending = ""
            continue
        merged.append(surface)
    if pending:
        if merged:
            merged[-1] += pending
        else:
            merged.append(pending)
    return merged


def _split_katakana_with_sudachi(text: str) -> str:
    """SudachiPy モード B でカタカナ連続部分を分割する。"""
    if not _init_sudachi():
        return text
    import sudachipy

    def _replace(m: re.Match) -> str:
        morphemes = _sudachi_tok.tokenize(m.group(0), sudachipy.SplitMode.B)
        return " ".join(_merge_invalid_katakana_segments(morphemes))

    return _KATAKANA_RUN_RE.sub(_replace, text)


_lexical_styling_enabled = True


@contextlib.contextmanager
def lexical_styling_disabled():
    """このブロックの間、語彙の置換と分割を行わない。

    コード フェンスの中では、記号と空白の正規化だけを行い、用語は原文のまま残す。
    対象は replace 辞書、add_space 辞書、SudachiPy によるカタカナ分割。
    """
    global _lexical_styling_enabled
    previous = _lexical_styling_enabled
    _lexical_styling_enabled = False
    try:
        yield
    finally:
        _lexical_styling_enabled = previous


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

    if _lexical_styling_enabled:
        before = protected
        protected = _join_katakana_split_by_no_space(protected)
        if collector is not None:
            _record_step_changes(before, protected, "dict-no-space-join", collector, message="no_space 語のスペースを結合")

        # Sudachi B 分割や no_space 保護で対象文字列が分断される前に、
        # カタカナ replace を先行適用する。「`カテゴリー → カテゴリ`」のような逆方向 ー 削除や
        # 「`スライドショ → スライドショー`」のような順方向 ー 付与は、分割後に走らせると
        # from word の連続性が失われて適用されないため、前段で処理しておく。
        for from_word, to_word in _replace_pairs:
            protected = _replace_skip_existing(
                protected, from_word, to_word,
                collector=collector,
                source=_replace_sources.get(from_word, ""),
            )

    # no_space 語の退避は語彙の置換とは別の役割を持つ。style_prose の全半角境界
    # スペース挿入から語を守るため、フェンス内でも必ず退避する。
    # ただしフェンス内では語境界の分割を行わないため、区切りのスペースは入れない。
    sorted_nosp = sorted(_no_space_words, key=len, reverse=True)
    nosp_replacements = [
        (f"\x00NOSP{idx}\x00", word) for idx, word in enumerate(sorted_nosp)
    ]
    protected = _protect_no_space_words(
        protected, nosp_replacements, separator=" " if _lexical_styling_enabled else ""
    )

    styled = style_prose(protected, collector=collector)

    if _lexical_styling_enabled:
        before = styled
        styled = _split_katakana_with_sudachi(styled)
        if collector is not None:
            _record_step_changes(before, styled, "sudachi-split", collector, message="SudachiPy でカタカナを分割")

        styled = _restore_nosp_with_boundaries(styled, nosp_replacements)

        styled = _protect_no_space_words(styled, nosp_replacements)
        for from_word, to_word in _replace_pairs:
            styled = _replace_skip_existing(
                styled, from_word, to_word,
                collector=collector,
                source=_replace_sources.get(from_word, ""),
            )
        styled = _restore_nosp_with_boundaries(styled, nosp_replacements)
        styled = _apply_add_space_pairs(styled, collector=collector)
    else:
        styled = _restore_no_space_words(styled, nosp_replacements)

    before = styled
    styled = add_space_before_supplemental_bracket(styled)
    if collector is not None:
        _record_step_changes(before, styled, "supplemental-bracket", collector, message="補足括弧前にスペースを挿入")

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
