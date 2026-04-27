#!/usr/bin/env python3
"""Japanese text styling engine shared by multiple frontends."""

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

_sudachi_state: Optional[bool] = None
_sudachi_tok = None
_KATAKANA_RUN_RE = re.compile(r"[ァ-ヿ]+")


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

    no_space_set = []
    add_space_map = {}
    replace_map = {}

    for dict_dir in search_paths:
        if not os.path.isdir(dict_dir):
            continue
        for fname in sorted(os.listdir(dict_dir)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(dict_dir, fname)
            try:
                with open(fpath, encoding="utf-8") as handle:
                    data = json.load(handle)
                for word in data.get("no_space", []):
                    if isinstance(word, str) and word not in no_space_set:
                        no_space_set.append(word)
                for pair in data.get("add_space", []):
                    if isinstance(pair, dict) and "from" in pair and "to" in pair:
                        add_space_map[pair["from"]] = pair["to"]
                for pair in data.get("replace", []):
                    if isinstance(pair, dict) and "from" in pair and "to" in pair:
                        replace_map[pair["from"]] = pair["to"]
            except Exception:
                pass

    _no_space_words[:] = no_space_set
    _replace_pairs[:] = list(replace_map.items())
    _add_space_pairs[:] = _expand_add_space_pairs(list(add_space_map.items()), _replace_pairs)


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

    return re.sub(r"([A-Za-z0-9_])\(([^)]*)\)", _replace, text)


def normalize_spaces(text: str) -> str:
    text = text.replace("　", " ")
    text = re.sub(r"(?<=[^\s|]) {2,}(?=[^\s|])", " ", text)
    return text


def style_prose(text: str) -> str:
    text = convert_fullwidth_alnum_to_halfwidth(text)
    text = convert_halfwidth_katakana_to_fullwidth(text)
    text = normalize_spaces(text)
    text = insert_space_between_fullwidth_and_halfwidth(text)
    text = remove_space_before_punctuation(text)
    text = remove_space_inside_brackets(text)
    text = remove_space_before_unit_no_space(text)
    text = remove_space_before_mm_unit(text)
    text = add_space_after_punctuation_before_alnum(text)
    text = add_space_after_number_before_bracket(text)
    text = add_space_before_supplemental_bracket(text)
    text = normalize_spaces(text)
    return text


apply_ms_style = style_prose


def _replace_skip_existing(text: str, from_word: str, to_word: str) -> str:
    if from_word == to_word:
        return text

    require_boundary = _is_full_katakana_text(from_word) and _is_full_katakana_text(to_word)
    result = []
    i = 0
    flen = len(from_word)
    tlen = len(to_word)

    while i < len(text):
        if flen >= tlen:
            if text[i:i + flen] == from_word and (
                not require_boundary or _has_non_katakana_boundaries(text, i, flen)
            ):
                result.append(to_word)
                i += flen
                continue
            if text[i:i + tlen] == to_word and (
                not require_boundary or _has_non_katakana_boundaries(text, i, tlen)
            ):
                result.append(to_word)
                i += tlen
                continue
        else:
            if text[i:i + tlen] == to_word and (
                not require_boundary or _has_non_katakana_boundaries(text, i, tlen)
            ):
                result.append(to_word)
                i += tlen
                continue
            if text[i:i + flen] == from_word and (
                not require_boundary or _has_non_katakana_boundaries(text, i, flen)
            ):
                result.append(to_word)
                i += flen
                continue

        result.append(text[i])
        i += 1

    return "".join(result)


def _apply_add_space_pairs(text: str) -> str:
    for from_word, to_word in sorted(_add_space_pairs, key=lambda pair: len(pair[0]), reverse=True):
        text = text.replace(from_word, to_word)
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


def _restore_nosp_with_boundaries(text: str, replacements: List[Tuple[str, str]]) -> str:
    """no_space_words のプレースホルダーを復元し、カタカナ境界にスペースを補う。

    SudachiPy が保護語の隣接部分を分割した後、復元時に境界スペースが失われる
    ケースを補正する。例: \x00NOSP\x00パフォーマンス → トラブルシューティング パフォーマンス
    """
    restored = text
    for placeholder, original in replacements:
        while placeholder in restored:
            idx = restored.index(placeholder)
            end = idx + len(placeholder)
            space_before = (
                idx > 0
                and _is_full_katakana_char(restored[idx - 1])
                and original
                and _is_full_katakana_char(original[0])
            )
            space_after = (
                end < len(restored)
                and original
                and _is_full_katakana_char(original[-1])
                and _is_full_katakana_char(restored[end])
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
) -> str:
    load_dictionaries()

    protected = text
    pattern_replacements: List[Tuple[str, str]] = []
    if protected_patterns:
        protected, pattern_replacements = _protect_patterns(protected, protected_patterns)

    protected, url_replacements = _protect_urls(protected)

    sorted_nosp = sorted(_no_space_words, key=len, reverse=True)
    nosp_replacements = []
    for idx, word in enumerate(sorted_nosp):
        placeholder = f"\x00NOSP{idx}\x00"
        protected = protected.replace(word, placeholder)
        nosp_replacements.append((placeholder, word))

    styled = style_prose(protected)
    styled = _split_katakana_with_sudachi(styled)
    styled = _restore_nosp_with_boundaries(styled, nosp_replacements)

    for placeholder, word in nosp_replacements:
        styled = styled.replace(word, placeholder)
    for from_word, to_word in _replace_pairs:
        styled = _replace_skip_existing(styled, from_word, to_word)
    styled = _restore_nosp_with_boundaries(styled, nosp_replacements)
    styled = _apply_add_space_pairs(styled)

    styled = _restore_replacements(styled, url_replacements)
    styled = _restore_replacements(styled, pattern_replacements)

    if postprocess is not None:
        styled = postprocess(styled)

    return styled


def validate_text(text: str) -> ValidationResult:
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
