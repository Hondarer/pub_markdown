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

Usage:
    python md_style_jp.py [input_file] [-o output_file]
    cat input.md | python md_style_jp.py > output.md
"""

import re
import unicodedata
from enum import Enum, auto
from typing import Callable, List, Tuple, Union


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
            if (prev_is_fullwidth and curr_needs_space_left) or \
               (prev_needs_space_right and curr_is_fullwidth):
                # 既にスペースがある場合は挿入しない
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


def style_markdown(text: str) -> str:
    """
    Markdown テキストをスタイリングする

    コードブロック内は処理をスキップし、本文のみを整形する。
    """
    lines = text.split("\n")
    result_lines = []
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
                continue
            if re.match(open_pat, stripped):
                fence_nest += 1
            result_lines.append(line)
            continue

        # インラインコードを保護しながら処理
        result_lines.append(_style_line_preserve_inline_code(line))

    return "\n".join(result_lines)


def _style_line_preserve_inline_code(line: str) -> str:
    """インラインコードを保護しながら行をスタイリングする"""
    # インラインコードを抽出して保護（長いバッククォートのシーケンスを先にマッチ）
    pattern = r"``+.+?``+|`[^`]+`"
    code_spans = re.findall(pattern, line)
    placeholders = [f"\x00CODE{i}\x00" for i in range(len(code_spans))]

    # インラインコードをプレースホルダーに置換
    protected_line = line
    for code, placeholder in zip(code_spans, placeholders):
        protected_line = protected_line.replace(code, placeholder, 1)

    # スタイリングを適用
    styled_line = apply_ms_style(protected_line)

    # プレースホルダーを元のインラインコードに戻す
    for code, placeholder in zip(code_spans, placeholders):
        styled_line = styled_line.replace(placeholder, code, 1)

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
