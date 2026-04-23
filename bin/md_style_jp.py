#!/usr/bin/env python3
"""
md_style_jp - 日本語 Markdown スタイリングコマンド

Microsoft 日本語スタイルガイドに基づく全半角・スペース挿入ルールの実装。
日本語技術文書の表記を統一し、可読性を向上させる。

主なルール:
1. 全角英数字・括弧類を半角に変換
2. 半角カタカナを全角に変換
3. 全角文字と半角英数字の間に半角スペースを挿入
4. 句読点・括弧周辺のスペースを適切に処理
5. 単位記号周辺のスペースを適切に処理
6. ソフト改行と見做せない行末の不要な trailing spaces を除去
   (次行が空行または EOF の場合は除去、次行が非空行の場合は保持)

Usage:
    python md_style_jp.py [input_file] [-o output_file]
    cat input.md | python md_style_jp.py > output.md
"""

import json
import os
import re
import unicodedata
from enum import Enum, auto
from typing import Callable, List, Tuple, Union


# ---------------------------------------------------------------------------
# URL 保護
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r'https?://\S+')
_URL_TRAILING_PUNCT = frozenset('。、！？：；」』）】〕〉》〙〗')

# ---------------------------------------------------------------------------
# 辞書ベーススペース制御
# ---------------------------------------------------------------------------

_no_space_words: List[str] = []   # スペース挿入を抑制する単語リスト
_replace_pairs: List[Tuple[str, str]] = []    # 汎用文字列置換ペアリスト（長音記号付与・省略など）
_add_space_pairs: List[Tuple[str, str]] = []  # スペースを挿入する変換ペアリスト
_dict_loaded: bool = False


def _load_dictionaries() -> None:
    """辞書ファイルを読み込む（初回呼び出し時のみ実行）

    読み込み順: home → docsfw → カレントディレクトリ
    同じ from キーが複数の辞書に存在する場合、後から読み込まれた to が優先される。
    no_space は重複を除いて全エントリを使用する。
    """
    global _no_space_words, _replace_pairs, _add_space_pairs, _dict_loaded
    if _dict_loaded:
        return
    _dict_loaded = True

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_paths = [
        os.path.join(os.path.expanduser("~"), ".md_style_jp"),
        os.path.join(script_dir, "..", ".md_style_jp"),
        os.path.join(os.getcwd(), ".md_style_jp"),
    ]

    # 二重処理防止: 絶対パスで重複除去（docsfw がカレントディレクトリと一致する場合など）
    seen = set()  # type: set
    search_paths = []
    for p in candidate_paths:
        abs_p = os.path.abspath(p)
        if abs_p not in seen:
            seen.add(abs_p)
            search_paths.append(abs_p)

    # add_space / replace は from をキーとした OrderedDict で管理し、後から読んだ to で上書き
    no_space_set = []        # type: List[str]
    add_space_map = {}       # type: dict
    replace_map = {}         # type: dict

    for dict_dir in search_paths:
        if not os.path.isdir(dict_dir):
            continue
        for fname in sorted(os.listdir(dict_dir)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(dict_dir, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    data = json.load(f)
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
                pass  # 読み込みエラーは無視（辞書なし扱い）

    _no_space_words[:] = no_space_set
    _add_space_pairs[:] = list(add_space_map.items())
    _replace_pairs[:] = list(replace_map.items())


class CharType(Enum):
    """文字種別"""
    HALFWIDTH_ALNUM = auto()      # 半角英数字
    FULLWIDTH_ALNUM = auto()      # 全角英数字
    HIRAGANA = auto()             # ひらがな
    KATAKANA_FULL = auto()        # 全角カタカナ
    KATAKANA_HALF = auto()        # 半角カタカナ
    KANJI = auto()                # 漢字
    PUNCTUATION_JP = auto()       # 日本語句読点
    PUNCTUATION_EN = auto()       # 英語句読点
    BRACKET_OPEN = auto()         # 開き括弧
    BRACKET_CLOSE = auto()        # 閉じ括弧
    SPACE = auto()                # スペース
    UNIT_NO_SPACE = auto()        # スペース不要の単位 (°, %)
    OTHER = auto()                # その他


class StyleRule:
    """スタイルルール"""
    def __init__(self, name, description, pattern, replacement):
        # type: (str, str, re.Pattern, Union[str, Callable[[re.Match], str]]) -> None
        self.name = name
        self.description = description
        self.pattern = pattern
        self.replacement = replacement


def get_char_type(char: str) -> CharType:
    """文字の種別を判定する"""
    if len(char) != 1:
        return CharType.OTHER

    code = ord(char)

    # スペース
    if char in " \t　":
        return CharType.SPACE

    # 半角英数字
    if ("A" <= char <= "Z") or ("a" <= char <= "z") or ("0" <= char <= "9"):
        return CharType.HALFWIDTH_ALNUM

    # 全角英数字
    if ("Ａ" <= char <= "Ｚ") or ("ａ" <= char <= "ｚ") or ("０" <= char <= "９"):
        return CharType.FULLWIDTH_ALNUM

    # ひらがな
    if 0x3040 <= code <= 0x309F:
        return CharType.HIRAGANA

    # 全角カタカナ
    if 0x30A0 <= code <= 0x30FF:
        return CharType.KATAKANA_FULL

    # 半角カタカナ
    if 0xFF65 <= code <= 0xFF9F:
        return CharType.KATAKANA_HALF

    # 漢字 (CJK統合漢字)
    if (0x4E00 <= code <= 0x9FFF) or (0x3400 <= code <= 0x4DBF):
        return CharType.KANJI

    # 日本語句読点
    if char in "、。，．":
        return CharType.PUNCTUATION_JP

    # 英語句読点
    if char in ",.!?:;":
        return CharType.PUNCTUATION_EN

    # スペース不要の単位
    if char in "°%％":
        return CharType.UNIT_NO_SPACE

    # 開き括弧
    if char in "([{（［｛「『【〔〈《":
        return CharType.BRACKET_OPEN

    # 閉じ括弧
    if char in ")]}）］｝」』】〕〉》":
        return CharType.BRACKET_CLOSE

    return CharType.OTHER


def is_fullwidth(char: str) -> bool:
    """全角文字かどうかを判定する"""
    char_type = get_char_type(char)
    return char_type in {
        CharType.FULLWIDTH_ALNUM,
        CharType.HIRAGANA,
        CharType.KATAKANA_FULL,
        CharType.KANJI,
    }


def is_halfwidth_alnum(char: str) -> bool:
    """半角英数字かどうかを判定する"""
    return get_char_type(char) == CharType.HALFWIDTH_ALNUM


# 全角から半角への変換テーブル（英数字・括弧類）
FULLWIDTH_TO_HALFWIDTH = str.maketrans(
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９（）［］｛｝",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789()[]{}",
)

# 半角カタカナから全角カタカナへの変換テーブル
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

# 濁点・半濁点の結合
DAKUTEN_COMBINATIONS = {
    ("ｶ", "ﾞ"): "ガ", ("ｷ", "ﾞ"): "ギ", ("ｸ", "ﾞ"): "グ", ("ｹ", "ﾞ"): "ゲ", ("ｺ", "ﾞ"): "ゴ",
    ("ｻ", "ﾞ"): "ザ", ("ｼ", "ﾞ"): "ジ", ("ｽ", "ﾞ"): "ズ", ("ｾ", "ﾞ"): "ゼ", ("ｿ", "ﾞ"): "ゾ",
    ("ﾀ", "ﾞ"): "ダ", ("ﾁ", "ﾞ"): "ヂ", ("ﾂ", "ﾞ"): "ヅ", ("ﾃ", "ﾞ"): "デ", ("ﾄ", "ﾞ"): "ド",
    ("ﾊ", "ﾞ"): "バ", ("ﾋ", "ﾞ"): "ビ", ("ﾌ", "ﾞ"): "ブ", ("ﾍ", "ﾞ"): "ベ", ("ﾎ", "ﾞ"): "ボ",
    ("ﾊ", "ﾟ"): "パ", ("ﾋ", "ﾟ"): "ピ", ("ﾌ", "ﾟ"): "プ", ("ﾍ", "ﾟ"): "ペ", ("ﾎ", "ﾟ"): "ポ",
    ("ｳ", "ﾞ"): "ヴ",
}


def convert_fullwidth_alnum_to_halfwidth(text: str) -> str:
    """全角英数字・括弧類 (（）［］｛｝) を半角に変換する"""
    return text.translate(FULLWIDTH_TO_HALFWIDTH)


def convert_halfwidth_katakana_to_fullwidth(text: str) -> str:
    """半角カタカナを全角に変換する"""
    result = []
    i = 0
    while i < len(text):
        char = text[i]
        # 次の文字が濁点・半濁点の場合
        if i + 1 < len(text) and text[i + 1] in "ﾞﾟ":
            combined = DAKUTEN_COMBINATIONS.get((char, text[i + 1]))
            if combined:
                result.append(combined)
                i += 2
                continue
        # 単独の半角カタカナ
        if char in HALFWIDTH_KATAKANA_TO_FULLWIDTH:
            result.append(HALFWIDTH_KATAKANA_TO_FULLWIDTH[char])
        else:
            result.append(char)
        i += 1
    return "".join(result)


_HALFWIDTH_BRACKETS_OPEN = set("([{")
_HALFWIDTH_BRACKETS_CLOSE = set(")]}")
_FULLWIDTH_NO_SPACE = set("・。、，．！？…‥")


def insert_space_between_fullwidth_and_halfwidth(text: str) -> str:
    """全角文字と半角英数字・括弧の間に半角スペースを挿入する"""
    result = []
    prev_char = ""

    for char in text:
        if prev_char and char != " ":
            prev_is_fullwidth = is_fullwidth(prev_char)
            curr_is_fullwidth = is_fullwidth(char)
            curr_needs_space_left = is_halfwidth_alnum(char) or char in _HALFWIDTH_BRACKETS_OPEN
            prev_needs_space_right = is_halfwidth_alnum(prev_char) or prev_char in _HALFWIDTH_BRACKETS_CLOSE

            # 全角 → 半角英数字/開き括弧、または 半角英数字/閉じ括弧 → 全角 の場合にスペースを挿入
            # ただし句読点・中点が隣接する場合はスペース不要
            if ((prev_is_fullwidth and curr_needs_space_left) or \
               (prev_needs_space_right and curr_is_fullwidth)) and \
               prev_char not in _FULLWIDTH_NO_SPACE and char not in _FULLWIDTH_NO_SPACE:
                # すでにスペースがある場合は挿入しない
                if not result or result[-1] != " ":
                    result.append(" ")

        result.append(char)
        prev_char = char

    return "".join(result)


def remove_space_before_punctuation(text: str) -> str:
    """句読点・記号の前の不要なスペースを削除する"""
    # 句読点の前のスペースを削除
    text = re.sub(r" +([、。，．,:;!！?？])", r"\1", text)
    # ドットは直後に英字が続く場合（.NET, .so 等）はスペースを保持する
    text = re.sub(r" +\.(?![A-Za-z])", ".", text)
    return text


def remove_space_inside_brackets(text: str) -> str:
    """括弧内側の不要なスペースを削除する"""
    # 開き括弧の後のスペースを削除
    text = re.sub(r"([\(\[{（［｛「『【〔〈《]) +", r"\1", text)
    # 閉じ括弧の前のスペースを削除
    text = re.sub(r" +([\)\]}）］｝」』】〕〉》])", r"\1", text)
    return text


def remove_space_before_unit_no_space(text: str) -> str:
    """スペース不要の単位 (°, %) の前のスペースを削除する"""
    text = re.sub(r"(\d) +([°%％])", r"\1\2", text)
    return text


def remove_space_before_mm_unit(text: str) -> str:
    """mm 単位の前のスペースを削除する (写真・映写関連)"""
    text = re.sub(r"(\d) +(mm)\b", r"\1\2", text)
    return text


def add_space_after_punctuation_before_alnum(text: str) -> str:
    """句読点・記号の後に半角英数字が続く場合、スペースを挿入する"""
    text = re.sub(r"([?？!！])([A-Za-z0-9])", r"\1 \2", text)
    return text


def add_space_after_number_before_bracket(text: str) -> str:
    """数字/数字 の後に括弧が続く場合、スペースを挿入する"""
    text = re.sub(r"(\d/\d+)(\()", r"\1 \2", text)
    return text


def normalize_spaces(text: str) -> str:
    """連続するスペースを1つに正規化する"""
    # 全角スペースを半角に変換
    text = text.replace("　", " ")
    # 連続するスペースを1つに（行頭インデント・行末スペース・テーブルパディングは保護）
    text = re.sub(r"(?<=[^\s|]) {2,}(?=[^\s|])", " ", text)
    return text


def apply_ms_style(text: str) -> str:
    """
    Microsoft 日本語スタイルガイドに基づいてテキストを整形する

    処理順序:
    1. 全角英数字・括弧類を半角に変換
    2. 半角カタカナを全角に変換
    3. スペースの正規化
    4. 全角文字と半角英数字の間にスペースを挿入
    5. 句読点周辺のスペースを調整
    6. 括弧内側のスペースを削除
    7. 単位記号周辺のスペースを調整
    """
    # 1. 全角英数字・括弧類を半角に変換
    text = convert_fullwidth_alnum_to_halfwidth(text)

    # 2. 半角カタカナを全角に変換
    text = convert_halfwidth_katakana_to_fullwidth(text)

    # 3. スペースの正規化
    text = normalize_spaces(text)

    # 4. 全角文字と半角英数字の間にスペースを挿入
    text = insert_space_between_fullwidth_and_halfwidth(text)

    # 5. 句読点前のスペースを削除
    text = remove_space_before_punctuation(text)

    # 6. 括弧内側のスペースを削除
    text = remove_space_inside_brackets(text)

    # 7. 単位記号前のスペースを削除
    text = remove_space_before_unit_no_space(text)
    text = remove_space_before_mm_unit(text)

    # 8. 句読点後に英数字が続く場合はスペースを挿入
    text = add_space_after_punctuation_before_alnum(text)

    # 9. 数字/数字 + 括弧の間にスペースを挿入
    text = add_space_after_number_before_bracket(text)

    # 10. 最終的なスペースの正規化
    text = normalize_spaces(text)

    return text


class ValidationResult:
    """検証結果"""
    def __init__(self, is_valid, original, corrected, differences):
        # type: (bool, str, str, List[Tuple[int, str, str]]) -> None
        self.is_valid = is_valid
        self.original = original
        self.corrected = corrected
        self.differences = differences


def validate_text(text: str) -> ValidationResult:
    """テキストがスタイルガイドに準拠しているか検証する"""
    corrected = apply_ms_style(text)
    is_valid = text == corrected

    # 差分を検出
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
        differences=differences
    )


def _remove_unnecessary_trailing_spaces(
    result_lines: List[str], code_block_flags: List[bool]
) -> List[str]:
    """ソフト改行と見做せない行末の不要な trailing spaces を除去する。

    - 行末に trailing spaces がある かつ 次行が空行 or EOF → trailing spaces を除去
    - 行末に trailing spaces がある かつ 次行が非空行 → 保持（ソフト改行として有効）
    - コードブロック内の行は対象外
    """
    n = len(result_lines)
    output = []
    for i, line in enumerate(result_lines):
        if code_block_flags[i] or not line.endswith((' ', '\t')):
            output.append(line)
            continue
        next_stripped = (result_lines[i + 1] if i + 1 < n else "").strip()
        if next_stripped:
            output.append(line)            # 次行が非空 → ソフト改行として保持
        else:
            output.append(line.rstrip())   # 次行が空 or EOF → trailing spaces 除去
    return output


def style_markdown(text: str) -> str:
    """
    Markdown テキストをスタイリングする

    コードブロック内は処理をスキップし、本文のみを整形する。
    """
    lines = text.split("\n")
    result_lines = []
    code_block_flags = []
    in_code_block = False
    fence_char = "`"
    fence_len = 0
    fence_nest = 0

    for line in lines:
        stripped = line.strip()
        if not in_code_block:
            # コードブロックの開始を検出（バッククォートまたはチルダ3つ以上）
            m = re.match(r"^(`{3,}|~{3,})", stripped)
            if m:
                in_code_block = True
                fence_char = m.group(1)[0]
                fence_len = len(m.group(1))
                fence_nest = 0
                result_lines.append(line)
                code_block_flags.append(True)
                continue
        else:
            close_pat = r"^(" + re.escape(fence_char) + r"{" + str(fence_len) + r",})\s*$"
            open_pat  = r"^(" + re.escape(fence_char) + r"{" + str(fence_len) + r",})\S"
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

        # インラインコードを保護しながら処理
        result_lines.append(_style_line_preserve_inline_code(line))
        code_block_flags.append(False)

    result_lines = _remove_unnecessary_trailing_spaces(result_lines, code_block_flags)
    return "\n".join(result_lines)


def _replace_skip_existing(text: str, from_word: str, to_word: str) -> str:
    """from_word を to_word に正規化する。既に to_word の位置はそのまま通す。"""
    if from_word == to_word:
        return text
    result = []
    i = 0
    flen = len(from_word)
    tlen = len(to_word)
    while i < len(text):
        if flen >= tlen:
            if text[i:i + flen] == from_word:
                result.append(to_word)
                i += flen
                continue
            if text[i:i + tlen] == to_word:
                # すでに標準形がある位置はそのまま通過
                result.append(to_word)
                i += tlen
                continue
        else:
            if text[i:i + tlen] == to_word:
                # すでに標準形がある位置はそのまま通過
                result.append(to_word)
                i += tlen
                continue
            if text[i:i + flen] == from_word:
                result.append(to_word)
                i += flen
                continue
        result.append(text[i])
        i += 1
    return "".join(result)


def _style_line_preserve_inline_code(line: str) -> str:
    """インラインコードを保護しながら行をスタイリングする"""
    _load_dictionaries()

    # a. インラインコードを抽出して保護（長いバッククォートのシーケンスを先にマッチ）
    pattern = r"``+.+?``+|`[^`]+`"
    code_spans = re.findall(pattern, line)
    code_placeholders = [f"\x00CODE{i}\x00" for i in range(len(code_spans))]

    protected_line = line
    for code, ph in zip(code_spans, code_placeholders):
        protected_line = protected_line.replace(code, ph, 1)

    # b. URL をプレースホルダーに（インラインコード保護後に実行するので、バッククォート内は除外済み）
    url_spans = []  # type: List[str]

    def _url_replacer(m):
        # type: (re.Match) -> str
        url = m.group(0)
        while url and url[-1] in _URL_TRAILING_PUNCT:
            url = url[:-1]
        if len(url) <= len("https://"):
            return m.group(0)
        url_spans.append(url)
        ph = f"\x00URL{len(url_spans) - 1}\x00"
        return ph + m.group(0)[len(url):]

    protected_line = _URL_RE.sub(_url_replacer, protected_line)
    url_placeholders = [f"\x00URL{i}\x00" for i in range(len(url_spans))]

    # c. no_space 単語をプレースホルダーに（長い順で部分一致誤置換を防止）
    sorted_nosp = sorted(_no_space_words, key=len, reverse=True)
    nosp_placeholders = [f"\x00NOSP{i}\x00" for i in range(len(sorted_nosp))]
    for word, ph in zip(sorted_nosp, nosp_placeholders):
        protected_line = protected_line.replace(word, ph)

    # d. スタイリングを適用
    styled_line = apply_ms_style(protected_line)

    # e. no_space プレースホルダーを元の単語に復元
    for word, ph in zip(sorted_nosp, nosp_placeholders):
        styled_line = styled_line.replace(ph, word)

    # f. 辞書置換を適用（URL・インラインコードはまだプレースホルダーなので保護される）
    # f1. add_space: スペース挿入
    for from_word, to_word in _add_space_pairs:
        styled_line = styled_line.replace(from_word, to_word)
    # f2. replace: 汎用文字列置換（長音記号付与・省略など）。標準形がある位置は維持
    for from_word, to_word in _replace_pairs:
        styled_line = _replace_skip_existing(styled_line, from_word, to_word)

    # g. URL を復元
    for url, ph in zip(url_spans, url_placeholders):
        styled_line = styled_line.replace(ph, url, 1)

    # h. インラインコードを復元
    for code, ph in zip(code_spans, code_placeholders):
        styled_line = styled_line.replace(ph, code, 1)

    return styled_line


def run_tests() -> bool:
    """テストを実行する"""
    test_cases = [
        # 全角英数字の変換
        ("ＮＯＴＥ", "NOTE"),
        ("１２３ＡＢＣ", "123ABC"),

        # 半角カタカナの変換
        ("ｶﾀｶﾅ", "カタカナ"),
        ("ｶﾞｷﾞｸﾞ", "ガギグ"),

        # 全角・半角間のスペース
        ("第3章", "第 3 章"),
        ("Windows10を起動", "Windows10 を起動"),
        ("ABCあいう", "ABC あいう"),

        # 句読点前のスペース削除
        ("ボタンをクリックして 、閉じます 。", "ボタンをクリックして、閉じます。"),

        # 括弧内のスペース削除
        ("列 A ( タイトル )", "列 A (タイトル)"),
        ("[ 新規 ] をクリック", "[新規] をクリック"),
        ("「 test 」と入力", "「test」と入力"),

        # 単位記号
        ("45 °", "45°"),
        ("50 %", "50%"),
        ("10 mm", "10mm"),

        # 疑問符後のスペース
        ("保存しますか?Excelを使用", "保存しますか? Excel を使用"),

        # 数字/数字 + 括弧
        ("10/13(ページ)", "10/13 (ページ)"),

    ]

    # style_markdown() を使うテスト（URL 保護など Markdown 固有の処理を含む）
    markdown_test_cases = [
        # URL 内のスペース挿入防止
        ("詳しくは https://example.com/日本語abc を参照", "詳しくは https://example.com/日本語abc を参照"),
        ("https://example.com/abc日本語終端", "https://example.com/abc日本語終端"),
        ("[テキスト](https://example.com/日本語パス)", "[テキスト](https://example.com/日本語パス)"),
        ("参照先 https://example.com/doc。次の章", "参照先 https://example.com/doc。次の章"),

        # replace: 長音付与・長音削除
        ("サーバ", "サーバー"),
        ("サーバー", "サーバー"),
        ("カテゴリー", "カテゴリ"),
        ("カテゴリ", "カテゴリ"),
        ("カテゴリー一覧", "カテゴリ一覧"),

        # replace の保護
        ("`カテゴリー` を使う", "`カテゴリー` を使う"),
        ("https://example.com/カテゴリー", "https://example.com/カテゴリー"),

        # testfw 固有タグの no_space 例外
        ("Pre-Assert手順", "Pre-Assert手順"),
        ("Pre-Assert確認", "Pre-Assert確認"),
        ("Pre-Assert確認_正常系", "Pre-Assert確認_正常系"),
        ("Pre-Assert確認_異常系", "Pre-Assert確認_異常系"),
        ("[Pre-Assert手順]", "[Pre-Assert手順]"),
        ("[Pre-Assert確認]", "[Pre-Assert確認]"),
        ("[Pre-Assert確認_正常系]", "[Pre-Assert確認_正常系]"),
        ("[Pre-Assert確認_異常系]", "[Pre-Assert確認_異常系]"),
    ]

    print("日本語 Markdown スタイリング 変換テスト")
    print("=" * 60)

    all_passed = True
    for original, expected in test_cases:
        result = apply_ms_style(original)
        passed = result == expected
        status = "✓" if passed else "✗"

        print(f"\n{status} 入力: {original!r}")
        print(f"  期待: {expected!r}")
        print(f"  結果: {result!r}")

        if not passed:
            all_passed = False

    for original, expected in markdown_test_cases:
        result = style_markdown(original)
        passed = result == expected
        status = "✓" if passed else "✗"

        print(f"\n{status} 入力: {original!r}")
        print(f"  期待: {expected!r}")
        print(f"  結果: {result!r}")

        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("すべてのテストに合格しました")
    else:
        print("一部のテストに失敗しました")

    return all_passed


def main():
    """CLI エントリーポイント"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="md_style_jp",
        description="日本語 Markdown スタイリングコマンド (Microsoft 日本語スタイルガイド準拠)",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="入力ファイル (省略時は標準入力)",
    )
    parser.add_argument(
        "-o", "--output",
        help="出力ファイル (省略時は標準出力)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="テストを実行",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="変更が必要かチェックのみ (変更が必要な場合は終了コード 1)",
    )
    parser.add_argument(
        "-i", "--in-place",
        action="store_true",
        help="入力ファイルを直接上書きする",
    )

    args = parser.parse_args()

    # テストモード
    if args.test:
        sys.exit(0 if run_tests() else 1)

    # --in-place は入力ファイルが必要
    if args.in_place and not args.input:
        parser.error("--in-place を使用する場合は入力ファイルを指定してください")

    # 入力を読み込み
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    # スタイリングを適用
    styled = style_markdown(text)

    # チェックモード
    if args.check:
        if text != styled:
            print(f"スタイリングが必要です: {args.input or '(stdin)'}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # 出力
    if args.in_place:
        if text != styled:
            with open(args.input, "w", encoding="utf-8") as f:
                f.write(styled)
            print("Modified: {}".format(args.input))
        else:
            print("No changes: {}".format(args.input))
    elif args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(styled)
    else:
        sys.stdout.write(styled)


if __name__ == "__main__":
    main()
