#!/usr/bin/env python3
"""Japanese text styling CLI for Markdown and source comments."""

from typing import List, Optional, Sequence, Tuple

from text_style_jp_engine import apply_ms_style, style_prose, validate_text
from text_style_jp_frontends import (
    detect_mode_from_path,
    style_by_mode,
    style_markdown,
    style_source_comments,
)


def run_tests() -> bool:
    engine_test_cases: List[Tuple[str, str]] = [
        ("ＮＯＴＥ", "NOTE"),
        ("１２３ＡＢＣ", "123ABC"),
        ("ｶﾀｶﾅ", "カタカナ"),
        ("ｶﾞｷﾞｸﾞ", "ガギグ"),
        ("第3章", "第 3 章"),
        ("Windows10を起動", "Windows10 を起動"),
        ("ABCあいう", "ABC あいう"),
        ("ボタンをクリックして 、閉じます 。", "ボタンをクリックして、閉じます。"),
        ("列 A ( タイトル )", "列 A (タイトル)"),
        ("[ 新規 ] をクリック", "[新規] をクリック"),
        ("「 test 」と入力", "「test」と入力"),
        ("45 °", "45°"),
        ("50 %", "50%"),
        ("10 mm", "10mm"),
        ("保存しますか?Excelを使用", "保存しますか? Excel を使用"),
        ("10/13(ページ)", "10/13 (ページ)"),
        ("hoge()", "hoge()"),
        ("hoge(fuga)", "hoge(fuga)"),
        ("hoge(説明)", "hoge (説明)"),
        ("hoge(key:value)", "hoge (key:value)"),
        ("hoge(説明:値)", "hoge (説明:値)"),
        ("hoge (説明)", "hoge (説明)"),
    ]

    markdown_test_cases: List[Tuple[str, str]] = [
        ("詳しくは https://example.com/日本語abc を参照", "詳しくは https://example.com/日本語abc を参照"),
        ("https://example.com/abc日本語終端", "https://example.com/abc日本語終端"),
        ("[テキスト](https://example.com/日本語パス)", "[テキスト](https://example.com/日本語パス)"),
        ("参照先 https://example.com/doc。次の章", "参照先 https://example.com/doc。次の章"),
        ("ブル", "ブルー"),
        ("(ブル)", "(ブルー)"),
        ("ブル。", "ブルー。"),
        ("サーバ", "サーバー"),
        ("サーバー", "サーバー"),
        ("カテゴリー", "カテゴリ"),
        ("カテゴリ", "カテゴリ"),
        ("カテゴリー一覧", "カテゴリ一覧"),
        ("`カテゴリー` を使う", "`カテゴリー` を使う"),
        ("https://example.com/カテゴリー", "https://example.com/カテゴリー"),
        ("トラブル", "トラブル"),
        ("ケーブル", "ケーブル"),
        ("テーブル", "テーブル"),
        ("トラブルシューティング", "トラブルシューティング"),
        ("トラブルシューティングツール", "トラブルシューティング ツール"),
        ("トラブルシューティングパフォーマンスカウンタ", "トラブルシューティング パフォーマンス カウンター"),
        ("トラブルシューティングパフォーマンスカウンター", "トラブルシューティング パフォーマンス カウンター"),
        ("トラブルシューター", "トラブル シューター"),
        ("インライン", "インライン"),
        ("インラインコード", "インライン コード"),
        ("メールサーバ", "メール サーバー"),
        ("メールサーバー", "メール サーバー"),
        ("ファイルサーバ", "ファイル サーバー"),
        ("リソースプロバイダ", "リソース プロバイダー"),
        ("ソースコードコメント", "ソース コード コメント"),
        ("スライドショ", "スライド ショー"),
        ("メールフロ", "メール フロー"),
        ("データフロ", "データ フロー"),
        ("Pre-Assert手順", "Pre-Assert手順"),
        ("Pre-Assert確認", "Pre-Assert確認"),
        ("Pre-Assert確認_正常系", "Pre-Assert確認_正常系"),
        ("Pre-Assert確認_異常系", "Pre-Assert確認_異常系"),
        ("[Pre-Assert手順]", "[Pre-Assert手順]"),
        ("[Pre-Assert確認]", "[Pre-Assert確認]"),
        ("[Pre-Assert確認_正常系]", "[Pre-Assert確認_正常系]"),
        ("[Pre-Assert確認_異常系]", "[Pre-Assert確認_異常系]"),
        ("行1\n行2", "行 1  \n行 2"),
        ("行1   \n行2", "行 1  \n行 2"),
        ("行1\t \n行2", "行 1  \n行 2"),
        ("行1  \n", "行 1\n"),
        ("行1  \n\n行2", "行 1\n\n行 2"),
        ("```\ncode  \n```\n本文", "```\ncode  \n```\n本文"),
        ("**変更前:**\n```python\ncode\n```", "**変更前:**\n\n```python\ncode\n```"),
        ("**変更前 (makefile):**\n```makefile\ncode\n```", "**変更前 (makefile):**\n\n```makefile\ncode\n```"),
        ("**変更前:**\n\n```python\ncode\n```", "**変更前:**\n\n```python\ncode\n```"),
        ("**変更前**:\n```makefile\ncode\n```", "**変更前**:\n\n```makefile\ncode\n```"),
        ("1. **変更前:**\n```python\ncode\n```", "1. **変更前:**\n```python\ncode\n```"),
        ("  **変更前:**\n```python\ncode\n```", "  **変更前:**\n```python\ncode\n```"),
        ("`(タイトル)`", "`(タイトル)`"),
        ("`makechild.mk`(親階層から継承)", "`makechild.mk`(親階層から継承)"),
        ("`foo`(bar)", "`foo`(bar)"),
        ("`foo`()", "`foo`()"),
        ("`foo` (already)", "`foo` (already)"),
        ("- item1\n- item2", "- item1\n- item2"),
        ("* item1\n* item2", "* item1\n* item2"),
        ("1. item1\n2. item2", "1. item1\n2. item2"),
        ("- item\n\n本文", "- item\n\n本文"),
        ("| A | B |\n| C | D |", "| A | B |\n| C | D |"),
        ("|---|---|\n| C | D |", "|---|---|\n| C | D |"),
        ("1. first\n   continuation\n2. second", "1. first\n   continuation\n2. second"),
        ("- item\n  detail\n- next", "- item\n  detail\n- next"),
        ("paragraph\n# heading", "paragraph\n# heading"),
        ("   cont1\n   cont2", "   cont1  \n   cont2"),
    ]

    source_test_cases: List[Tuple[str, str, str]] = [
        (
            "c",
            "/** @brief 第3章の説明。 */\nint main(void);\n",
            "/** @brief 第 3 章の説明。 */\nint main(void);\n",
        ),
        (
            "c",
            "/**\n *  @param[in]      a 第3章の入力。\n *  @code{.c}\n *  printf(\"第3章\\n\");\n *  @endcode\n */\n",
            "/**\n *  @param[in]      a 第 3 章の入力。\n *  @code{.c}\n *  printf(\"第3章\\n\");\n *  @endcode\n */\n",
        ),
        (
            "c",
            "int value = 0; // 第3章の値\n",
            "int value = 0; // 第 3 章の値\n",
        ),
        (
            "c",
            "/** `(タイトル)` */\n",
            "/** `(タイトル)` */\n",
        ),
        (
            "csharp",
            "    /// <summary>\n    /// 第3章の説明と <see cref=\"CalcResult\"/> の参照。\n    /// </summary>\n",
            "    /// <summary>\n    /// 第 3 章の説明と <see cref=\"CalcResult\"/> の参照。\n    /// </summary>\n",
        ),
        (
            "csharp",
            "    /// <code>\n    /// Console.WriteLine(\"第3章\");\n    /// </code>\n",
            "    /// <code>\n    /// Console.WriteLine(\"第3章\");\n    /// </code>\n",
        ),
        (
            "python",
            "value = 1  # 第3章の説明\n",
            "value = 1  # 第 3 章の説明\n",
        ),
        (
            "shell",
            "echo test # 第3章の説明\n",
            "echo test # 第 3 章の説明\n",
        ),
        (
            "make",
            "\t@echo test # 第3章の説明\n",
            "\t@echo test # 第 3 章の説明\n",
        ),
        (
            "python",
            "#!/usr/bin/env python3\n# 第3章の説明\n",
            "#!/usr/bin/env python3\n# 第 3 章の説明\n",
        ),
    ]

    mode_test_cases: List[Tuple[str, str]] = [
        ("README.md", "markdown"),
        ("sample.c", "c"),
        ("sample.hpp", "cpp"),
        ("sample.cs", "csharp"),
        ("sample.py", "python"),
        ("sample.sh", "shell"),
        ("Makefile", "make"),
    ]

    print("日本語テキスト スタイリング 変換テスト")
    print("=" * 60)

    all_passed = True

    for original, expected in engine_test_cases:
        result = style_prose(original)
        passed = result == expected
        status = "✓" if passed else "✗"
        print(f"\n{status} engine 入力: {original!r}")
        print(f"  期待: {expected!r}")
        print(f"  結果: {result!r}")
        if not passed:
            all_passed = False

    for original, expected in markdown_test_cases:
        result = style_markdown(original)
        passed = result == expected
        status = "✓" if passed else "✗"
        print(f"\n{status} markdown 入力: {original!r}")
        print(f"  期待: {expected!r}")
        print(f"  結果: {result!r}")
        if not passed:
            all_passed = False

    for language, original, expected in source_test_cases:
        result = style_source_comments(original, language)
        passed = result == expected
        status = "✓" if passed else "✗"
        print(f"\n{status} {language} 入力: {original!r}")
        print(f"  期待: {expected!r}")
        print(f"  結果: {result!r}")
        if not passed:
            all_passed = False

    for path, expected in mode_test_cases:
        result = detect_mode_from_path(path)
        passed = result == expected
        status = "✓" if passed else "✗"
        print(f"\n{status} mode 入力: {path!r}")
        print(f"  期待: {expected!r}")
        print(f"  結果: {result!r}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    print("すべてのテストに合格しました" if all_passed else "一部のテストに失敗しました")
    return all_passed


def _build_parser(prog: str, description: str, allow_mode_option: bool):
    import argparse

    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument("input", nargs="?", help="入力ファイル (省略時は標準入力)")
    parser.add_argument("-o", "--output", help="出力ファイル (省略時は標準出力)")
    parser.add_argument("--test", action="store_true", help="テストを実行")
    parser.add_argument("--check", action="store_true", help="変更が必要かチェックのみ (変更が必要な場合は終了コード 1)")
    parser.add_argument("-i", "--in-place", action="store_true", help="入力ファイルを直接上書きする")
    if allow_mode_option:
        parser.add_argument(
            "--mode",
            default="auto",
            choices=["auto", "markdown", "c", "cpp", "csharp", "python", "shell", "make"],
            help="入力の構文モード。auto の場合はファイル名から推定する",
        )
    return parser


def _resolve_mode(input_path: Optional[str], requested_mode: str, default_mode: str) -> str:
    if requested_mode != "auto":
        return requested_mode
    if default_mode != "auto":
        return default_mode
    if not input_path:
        raise ValueError("--mode auto を標準入力に対して使用する場合は mode を明示してください")
    return detect_mode_from_path(input_path)


def main(
    argv: Optional[Sequence[str]] = None,
    default_mode: str = "auto",
    prog: str = "text_style_jp",
    description: str = "日本語テキスト スタイリングコマンド",
    allow_mode_option: bool = True,
) -> int:
    import sys

    parser = _build_parser(prog, description, allow_mode_option)
    args = parser.parse_args(argv)

    if args.test:
        return 0 if run_tests() else 1

    if args.in_place and not args.input:
        parser.error("--in-place を使用する場合は入力ファイルを指定してください")

    if args.input:
        with open(args.input, "r", encoding="utf-8") as handle:
            text = handle.read()
    else:
        text = sys.stdin.read()

    requested_mode = getattr(args, "mode", "auto")
    mode = _resolve_mode(args.input, requested_mode, default_mode)
    styled = style_by_mode(text, mode)

    if args.check:
        if text != styled:
            print(f"スタイリングが必要です: {args.input or '(stdin)'}", file=sys.stderr)
            return 1
        return 0

    if args.in_place:
        if text != styled:
            with open(args.input, "w", encoding="utf-8") as handle:
                handle.write(styled)
            print(f"Modified: {args.input}")
        else:
            print(f"No changes: {args.input}")
        return 0

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(styled)
        return 0

    sys.stdout.write(styled)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
