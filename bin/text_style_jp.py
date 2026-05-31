#!/usr/bin/env python3
"""Japanese text styling CLI for Markdown and source comments."""

import contextlib
import io
import os
import sys
import tempfile
from typing import List, Optional, Sequence, Tuple

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from text_style_jp_engine import (
    DiagnosticCollector,
    Finding,
    _loads_jsonc,
    _record_step_changes,
    apply_ms_style,
    style_prose,
    style_text,
    validate_text,
)
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
        ("フォント :", "フォント:"),
        ("送信者 1 : 受信者 1", "送信者 1 : 受信者 1"),
        ("path, ...", "path, ..."),
        ("文末 .", "文末."),
        ("列 A ( タイトル )", "列 A (タイトル)"),
        ("[ 新規 ] をクリック", "[新規] をクリック"),
        ("「 test 」と入力", "「test」と入力"),
        ("45 °", "45°"),
        ("50 %", "50%"),
        ("10 mm", "10mm"),
        ("ビルド ・ テスト", "ビルド・テスト"),
        ("保存しますか?Excelを使用", "保存しますか? Excel を使用"),
        ("10/13(ページ)", "10/13 (ページ)"),
        ("hoge()", "hoge()"),
        ("hoge(fuga)", "hoge(fuga)"),
        ("hoge(説明)", "hoge (説明)"),
        ("hoge(key:value)", "hoge (key:value)"),
        ("hoge(説明:値)", "hoge (説明:値)"),
        ("hoge (説明)", "hoge (説明)"),
        ("GNU Make(スキルガイド)", "GNU Make (スキルガイド)"),
        ("Markdown(GFM)仕様", "Markdown (GFM) 仕様"),
    ]

    markdown_test_cases: List[Tuple[str, str]] = [
        ("詳しくは https://example.com/日本語abc を参照", "詳しくは https://example.com/日本語abc を参照"),
        ("https://example.com/abc日本語終端", "https://example.com/abc日本語終端"),
        ("[テキスト](https://example.com/日本語パス)", "[テキスト](https://example.com/日本語パス)"),
        ("参照先 https://example.com/doc。次の章", "参照先 https://example.com/doc。次の章"),
        ("ビルド・テスト", "ビルド・テスト"),
        ("ブル", "ブルー"),
        ("(ブル)", "(ブルー)"),
        ("ブル。", "ブルー。"),
        ("サーバ", "サーバー"),
        ("サーバー", "サーバー"),
        ("カテゴリー", "カテゴリ"),
        ("カテゴリ", "カテゴリ"),
        ("カテゴリー一覧", "カテゴリ一覧"),
        ("メモリーを確保", "メモリを確保"),
        ("プロパティーを取得", "プロパティを取得"),
        ("ライブラリーの依存", "ライブラリの依存"),
        ("サブ モジュール", "サブモジュール"),
        ("ワークス ペース", "ワークスペース"),
        ("サブ ディレクトリ", "サブディレクトリ"),
        ("クロス プラットフォーム", "クロスプラットフォーム"),
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
        ("データフロ", "データフロー"),
        ("ファイルディスクリプタ", "ファイル記述子"),
        ("ファイルディスクリプター", "ファイル記述子"),
        ("フィルタ", "フィルター"),
        ("フィルタリング", "フィルタリング"),
        ("モニタ", "モニター"),
        ("モニタリング", "モニタリング"),
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
        (
            "1. `.c` のコンパイル完了時に `.d` 依存ファイルが生成される  \n   (GCC: `-MMD -MP -MF`、MSVC: `/showIncludes` + フィルタ、GROUP_COMPILE: `/sourceDependencies`)",
            "1. `.c` のコンパイル完了時に `.d` 依存ファイルが生成される  \n   (GCC: `-MMD -MP -MF`、MSVC: `/showIncludes` + フィルター、GROUP_COMPILE: `/sourceDependencies`)",
        ),
        ("**LTO (`-flto`, Release ビルド)**:", "**LTO (`-flto`, Release ビルド)**:"),
        ("`cmd`, `arg`", "`cmd`, `arg`"),
        ("単語, 単語", "単語, 単語"),
        ("先頭の ./ は中間一致を防くために明示したほうがベターです。", "先頭の ./ は中間一致を防くために明示したほうがベターです。"),
        ("全角コロン：サンプル", "全角コロン:サンプル"),
        ("## @brief { brief description }", "## @brief { brief description }"),
        (
            "## @param[<dir>] <parameter-name> { parameter description }",
            "## @param[<dir>] <parameter-name> { parameter description }",
        ),
        ("## @f[ ~ @f], @f$ ~ @f$", "## @f[ ~ @f], @f$ ~ @f$"),
        (
            "## @exception <exception-object> { exception description }",
            "## @exception <exception-object> { exception description }",
        ),
        ("## @tparam <template-parameter-name> { description }", "## @tparam <template-parameter-name> { description }"),
        ("## @par [(paragraph title)] { paragraph }", "## @par [(paragraph title)] { paragraph }"),
        ("- item\n  detail", "- item  \n  detail"),
        ("- item  \n  detail", "- item  \n  detail"),
        ("- item\n  - child", "- item\n  - child"),
        ("説明文\n- item", "説明文\n\n- item"),
        ("説明文:\n- item", "説明文:\n\n- item"),
        ("説明文\n\n- item", "説明文\n\n- item"),
        ("### 非侵襲的\n- テスト対象の C コードを一切変更する必要がない", "### 非侵襲的\n\n- テスト対象の C コードを一切変更する必要がない"),
        ("1. item\n   detail", "1. item  \n   detail"),
        ("1. item  \n   detail", "1. item  \n   detail"),
        ("1. item\n   1. child", "1. item\n   1. child"),
        ("- [] task", "- [ ] task"),
        ("- [ ] task", "- [ ] task"),
        ("- [x] task", "- [x] task"),
        ("1. [] task", "1. [ ] task"),
        ("1. [ ] task", "1. [ ] task"),
        ("1. [X] task", "1. [X] task"),
        ("`init`・`clone`・`commit`・`log`", "`init`・`clone`・`commit`・`log`"),
        ("`init` ・`clone` ・`commit` ・`log`", "`init`・`clone`・`commit`・`log`"),
        (
            "1:1 (ユニキャスト) 通信では送信者 1 : 受信者 1 の構成となります。",
            "1:1 (ユニキャスト) 通信では送信者 1 : 受信者 1 の構成となります。",
        ),
        (
            "世代管理は `path`, `path.1`, `path.2`, ... の形式です。",
            "世代管理は `path`, `path.1`, `path.2`, ... の形式です。",
        ),
        (
            "- [GNU Make(スキルガイド)](../04-build-system/gnu-make.md)",
            "- [GNU Make (スキル ガイド)](../04-build-system/gnu-make.md)",
        ),
        (
            "- [GNU Make(スキル ガイド)](../04-build-system/gnu-make.md)",
            "- [GNU Make (スキル ガイド)](../04-build-system/gnu-make.md)",
        ),
        (
            "- [GitHub Flavored Markdown(GFM)仕様]",
            "- [GitHub Flavored Markdown (GFM) 仕様]",
        ),
        (
            "- [第 2 章 Git の基本](https://git-scm.com/book/ja/v2/Git-の基本-Git-リポジトリの取得) - `init`・`clone`・`commit`・`log`",
            "- [第 2 章 Git の基本](https://git-scm.com/book/ja/v2/Git-の基本-Git-リポジトリの取得) - `init`・`clone`・`commit`・`log`",
        ),
        ("> 引用\n> 続き", "> 引用\n> 続き"),
        ("> 引用  \n> 続き", "> 引用  \n> 続き"),
        ("> [!NOTE]\n> 補足情報です。", "> [!NOTE]\n> 補足情報です。"),
        (
            "> [!TIP]\n> 通常はプロジェクトルートで `make with-cov` を行います。",
            "> [!TIP]\n> 通常はプロジェクト ルートで `make with-cov` を行います。",
        ),
        (
            "> [!IMPORTANT]\n> 本フレームワークでは `cov-build` が必要な場合に、`make` 内部で自動的に `cov-build` を経由します。\n> `make` コマンドそのものには `cov-build` は不要です。",
            "> [!IMPORTANT]\n> 本フレームワークでは `cov-build` が必要な場合に、`make` 内部で自動的に `cov-build` を経由します。\n> `make` コマンドそのものには `cov-build` は不要です。",
        ),
        ("> [!WARNING]\n> 注意が必要です。", "> [!WARNING]\n> 注意が必要です。"),
        ("> [!CAUTION]\n> 危険な操作です。", "> [!CAUTION]\n> 危険な操作です。"),
        ("> [!TODO]\n> 未対応タイプです。", "> [!TODO]\n> 未対応タイプです。"),
        ("```\ncode  \n```\n本文", "```\ncode  \n```\n\n本文"),
        ("**変更前:**\n```python\ncode\n```", "**変更前:**\n\n```python\ncode\n```"),
        ("**変更前 (makefile):**\n```makefile\ncode\n```", "**変更前 (makefile):**\n\n```makefile\ncode\n```"),
        ("**変更前:**\n\n```python\ncode\n```", "**変更前:**\n\n```python\ncode\n```"),
        ("**変更前**:\n```makefile\ncode\n```", "**変更前**:\n\n```makefile\ncode\n```"),
        ("1. **変更前:**\n```python\ncode\n```", "1. **変更前:**\n\n```python\ncode\n```"),
        ("  **変更前:**\n```python\ncode\n```", "  **変更前:**\n\n```python\ncode\n```"),
        ("`(タイトル)`", "`(タイトル)`"),
        ("` ```text `", "` ```text `"),
        ("`<com_util/base/shared_lib_lifecycle.h>` :", "`<com_util/base/shared_lib_lifecycle.h>` :"),
        (" *  - `<com_util/base/shared_lib_lifecycle.h>` :", " * - `<com_util/base/shared_lib_lifecycle.h>` :"),
        ("`1`=あり", "`1`=あり"),
        ("`0`=なし", "`0`=なし"),
        ("`FLAG`==1", "`FLAG`==1"),
        ("`value`!=0", "`value`!=0"),
        ("`x`<=10", "`x`<=10"),
        ("`y`>=1", "`y`>=1"),
        ("`1` =あり", "`1` =あり"),
        ("`ref`/`out`", "`ref`/`out`"),
        ("`ref` / `out`", "`ref` / `out`"),
        ("`ref` /`out`", "`ref` / `out`"),
        ("`ref`/ `out`", "`ref` / `out`"),
        ("`sscanf` / `vsscanf`: `0`", "`sscanf` / `vsscanf`: `0`"),
        ("`void`: `Return()`", "`void`: `Return()`"),
        ("`void` : `Return()`", "`void` : `Return()`"),
        (
            "Linux Kernel は**Sphinx**をドキュメンテーションの中核として採用し、reStructuredText 形式で`make htmldocs` または`make pdfdocs` によって生成する。",
            "Linux Kernel は **Sphinx** をドキュメンテーションの中核として採用し、reStructuredText 形式で `make htmldocs` または `make pdfdocs` によって生成する。",
        ),
        ("`makechild.mk`(親階層から継承)", "`makechild.mk` (親階層から継承)"),
        ("`foo`(bar)", "`foo` (bar)"),
        ("`foo`()", "`foo` ()"),
        ("`foo` (already)", "`foo` (already)"),
        ("foo()", "foo()"),
        ("`foo()`", "`foo()`"),
        (
            "利用側に `onLoad()` / `onUnload()` の実装を要求します。",
            "利用側に `onLoad()` / `onUnload()` の実装を要求します。",
        ),
        ("- item1\n- item2", "- item1\n- item2"),
        ("* item1\n* item2", "* item1\n* item2"),
        ("1. item1\n2. item2", "1. item1\n2. item2"),
        ("- item\n\n本文", "- item\n\n本文"),
        ("| A | B |\n| C | D |", "| A | B |\n| C | D |"),
        ("| :--: | :-- | --: |", "| :--: | :-- | --: |"),
        ("| 第3章 |", "| 第 3 章 |"),
        ("|---|---|\n| C | D |", "|---|---|\n| C | D |"),
        ("1. first\n   continuation\n2. second", "1. first  \n   continuation\n2. second"),
        ("- item\n  detail\n- next", "- item  \n  detail\n- next"),
        ("paragraph\n# heading", "paragraph\n# heading"),
        ("## 1. 段落の説明", "## 段落の説明"),
        ("## 1 段落の説明", "## 段落の説明"),
        ("## 1.2 段落の説明", "## 段落の説明"),
        ("## 1.2. 段落の説明", "## 段落の説明"),
        ("## (1) 段落の説明", "## 段落の説明"),
        ("### 2回以上の制限", "### 2 回以上の制限"),
        ("### 2 回以上の制限", "### 2 回以上の制限"),
        ("#### 1 階層下まで指定", "#### 1 階層下まで指定"),
        ("#### 2 階層下まで指定", "#### 2 階層下まで指定"),
        ("# 1. タイトル", "# タイトル"),
        ("# (1) タイトル", "# タイトル"),
        ("###### 1.2.3. タイトル", "###### タイトル"),
        ("###### (1.2.3) タイトル", "###### タイトル"),
        ("1. 段落の説明", "1. 段落の説明"),
        ("```\n## 1. コード\n```", "```\n## 1. コード\n```"),
        ("---\nname: foo\n---\n## 1. タイトル", "---\nname: foo\n---\n## タイトル"),
        ("   cont1\n   cont2", "   cont1  \n   cont2"),
        ("変更に", "変更に"),
        ("更に詳しく", "さらに詳しく"),
        ("また更に", "またさらに"),
        ("変更に加えて更に", "変更に加えてさらに"),
        ("ライフサイクル", "ライフサイクル"),
        ("ライフ サイクル", "ライフサイクル"),
        ("# AIフレンドリー", "# AI フレンドリー"),
        ("- AIフレンドリー", "- AI フレンドリー"),
        ("AI フレンド リー", "AI フレンドリー"),
        ("**強調**（補足）", "**強調** (補足)"),
        ("**強調**(補足)", "**強調** (補足)"),
        ("**固定エージェント**（物理マシン・固定 VM）を対象に", "**固定エージェント** (物理マシン・固定 VM) を対象に"),
        ("LD_PRELOAD に追加するライブラリの絶対パス **(Linux のみ)**", "LD_PRELOAD に追加するライブラリの絶対パス **(Linux のみ)**"),
        ("**リンク補完の配置先：**\n`/INCLUDE` pragma は `mock_com_util.h` ヘッダーに記述します。", "**リンク補完の配置先:**\n\n`/INCLUDE` pragma は `mock_com_util.h` ヘッダーに記述します。"),
        ("○(RECEIVER → SENDER)", "○ (RECEIVER → SENDER)"),
        ("○(双方向)", "○ (双方向)"),
        ("✅(複数 path からの重複排除)", "✅ (複数 path からの重複排除)"),
        ("O(1)", "O(1)"),
        ("O(log n)", "O(log n)"),
        ("O(V+E)", "O(V+E)"),
        ("リオーダーバッファ", "リオーダー バッファー"),
        ("リオーダーバッファー", "リオーダー バッファー"),
        ("リオーダバッファ", "リオーダー バッファー"),
        ("リオーダバッファー", "リオーダー バッファー"),
        ("リオーダーバッファタイムアウト", "リオーダー バッファー タイムアウト"),
        ("リオーダーバッファータイムアウト", "リオーダー バッファー タイムアウト"),
        ("リオーダバッファタイムアウト", "リオーダー バッファー タイムアウト"),
        ("リオーダバッファータイムアウト", "リオーダー バッファー タイムアウト"),
        ("シグナルハンドラ", "シグナル ハンドラー"),
        ("シグナル ハンドラ", "シグナル ハンドラー"),
        ("フィルタファイル", "フィルター ファイル"),
        ("フィルタ ファイル", "フィルター ファイル"),
        ("フィルターファイル", "フィルター ファイル"),
        ("フィルタルール", "フィルター ルール"),
        ("フィルタ ルール", "フィルター ルール"),
        ("フィルタールール", "フィルター ルール"),
        ("フィルタ・セッション", "フィルター・セッション"),
        ("フィル タ・セッション", "フィルター・セッション"),
        ("接続元アドレス フィルタ", "接続元アドレス フィルター"),
        ("接続元アドレス フィル タ", "接続元アドレス フィルター"),
        ("セキュリティー", "セキュリティ"),
        ("セキュリティー設定", "セキュリティ設定"),
        ("文書のセキュリティー チェック", "文書のセキュリティ チェック"),
        ("送信元ポート フィル タ", "送信元ポート フィルター"),
        ("Lua フィル タ", "Lua フィルター"),
        ('# makefile の変数代入 "= と :=" の違い', '# makefile の変数代入 "= と :=" の違い'),
        ("## +=（追記）の挙動", "## += (追記) の挙動"),
        ("## ?=（条件付き代入）", "## ?= (条件付き代入)"),
        ("##?=(条件付き代入)", "## ?= (条件付き代入)"),
        ("- **トランスポート**: UDP/IPv4（unicast / multicast / broadcast / unicast_bidir）または TCP/IPv4（tcp / tcp_bidir）", "- **トランスポート**: UDP/IPv4 (unicast / multicast / broadcast / unicast_bidir) または TCP/IPv4 (tcp / tcp_bidir)"),
        ("**bold**(ascii)", "**bold**(ascii)"),
        ("ジョブ（スクリプト記述）サンプル", "ジョブ (スクリプト記述) サンプル"),
        ("フリースタイル ジョブ（スクリプト記述）サンプル", "フリースタイル ジョブ (スクリプト記述) サンプル"),
        # YAML frontmatter
        ("---\nname: foo\n---\n本文", "---\nname: foo\n---\n本文"),
        ("---\ndescription: |\n  line1\n  line2\n---", "---\ndescription: |\n  line1\n  line2\n---"),
        ("---\ntitle: 第3章\n---\n# heading", "---\ntitle: 第 3 章\n---\n# heading"),
        ("---\nname: foo\n---\n行1\n行2", "---\nname: foo\n---\n行 1  \n行 2"),
        (
            "<!--ja:-->\n# トップレベルの index\n<!--:ja-->\n<!--en:\n# index of top level\n:en-->",
            "<!--ja:-->\n# トップレベルの index\n<!--:ja-->\n<!--en:\n# index of top level\n:en-->",
        ),
        (
            "<!--\n## C4\n\n```{.mermaid caption=\"C4 のサンプル\"}\nC4Context\n    title C4 Context のサンプル\n    Person(user, \"利用者\")\n    System(pub, \"pub_markdown\", \"Markdown を発行する\")\n    Rel(user, pub, \"Markdown を発行\")\n```\n\n-->",
            "<!--\n## C4\n\n```{.mermaid caption=\"C4 のサンプル\"}\nC4Context\n    title C4 Context のサンプル\n    Person(user, \"利用者\")\n    System(pub, \"pub_markdown\", \"Markdown を発行する\")\n    Rel(user, pub, \"Markdown を発行\")\n```\n\n-->",
        ),
        # 見出し行のインラインコード除去
        ("## `com_util_tracer_create`", "## com_util_tracer_create"),
        ("### `#ifdef` / `#ifndef`", "### #ifdef / #ifndef"),
        ("# VS Code と `c_cpp_properties.json` の手順", "# VS Code と c_cpp_properties.json の手順"),
        ("#### `.vscode/.env.linux` / `.vscode/.env.windows`", "#### .vscode/.env.linux / .vscode/.env.windows"),
        ("## ``double`` backtick", "## double backtick"),
        ("通常文の `inline code` はそのまま", "通常文の `inline code` はそのまま"),
        ("```\n## `コードブロック内` はそのまま\n```", "```\n## `コードブロック内` はそのまま\n```"),
        ("例:\n```makefile\nLIBS += mock_calcbase mock_libc\n```", "例:\n\n```makefile\nLIBS += mock_calcbase mock_libc\n```"),
        (
            "例:\n```makefile\nLIBS += mock_calcbase mock_libc\n```\n補足",
            "例:\n\n```makefile\nLIBS += mock_calcbase mock_libc\n```\n\n補足",
        ),
        ("```makefile\nLIBS += mock_calcbase mock_libc\n```\n補足", "```makefile\nLIBS += mock_calcbase mock_libc\n```\n\n補足"),
        ("例:\n\n```makefile\nLIBS += mock_calcbase mock_libc\n```", "例:\n\n```makefile\nLIBS += mock_calcbase mock_libc\n```"),
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
            "c",
            "/** `<com_util/base/shared_lib_lifecycle.h>` : */\n",
            "/** `<com_util/base/shared_lib_lifecycle.h>` : */\n",
        ),
        (
            "c",
            "/** @retval          0以外 第3章の失敗。 */\n",
            "/** @retval          0以外 第 3 章の失敗。 */\n",
        ),
        (
            "c",
            "/** @retval          CALC_SUCCESS以外 第3章の失敗。 */\n",
            "/** @retval          CALC_SUCCESS以外 第 3 章の失敗。 */\n",
        ),
        (
            "c",
            "/** @param[in]      value 第3章の入力。 */\n",
            "/** @param[in]      value 第 3 章の入力。 */\n",
        ),
        (
            "c",
            "/** @section        section1 第3章。 */\n",
            "/** @section        section1 第 3 章。 */\n",
        ),
        (
            "c",
            "/** @defgroup       GROUP1 第3章。 */\n",
            "/** @defgroup       GROUP1 第 3 章。 */\n",
        ),
        (
            "c",
            "/** @copydoc processData(const char*, int) */\n",
            "/** @copydoc processData(const char*, int) */\n",
        ),
        (
            "c",
            "/** ファイル ディスクリプタを確認する。 */\n",
            "/** ファイル記述子を確認する。 */\n",
        ),
        (
            "c",
            "/** ファイル ディスクリプターを確認する。 */\n",
            "/** ファイル記述子を確認する。 */\n",
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

    mode_style_test_cases: List[Tuple[str, str, str]] = [
        ("markdown", "行1\n\n\n行2", "行 1\n\n行 2\n"),
        ("markdown", "```\nline1\n\n\nline2\n```", "```\nline1\n\nline2\n```\n"),
        ("python", "value = 1\n\n\n# 第3章", "value = 1\n\n# 第 3 章\n"),
        ("text", "line1\n \t \n\nline2", "line1\n\nline2\n"),
        ("text", "line1", "line1\n"),
        ("text", "", "\n"),
    ]

    mode_test_cases: List[Tuple[str, str]] = [
        ("README.md", "markdown"),
        ("sample.c", "c"),
        ("sample.hpp", "cpp"),
        ("sample.cs", "csharp"),
        ("sample.py", "python"),
        ("sample.sh", "shell"),
        ("Makefile", "make"),
        ("sample.txt", "text"),
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

    jsonc_text = r'''
    {
      // 行コメントを許容する
      "no_space": [
        "JSONC辞書テスト", // 末尾コメントを許容する
      ],
      "replace": [
        {
          "from": "https://example.com/a//b",
          "to": "/* string literal */",
        },
      ],
    }
    '''
    try:
        data = _loads_jsonc(jsonc_text)
        passed = (
            data["no_space"] == ["JSONC辞書テスト"]
            and data["replace"][0]["from"] == "https://example.com/a//b"
            and data["replace"][0]["to"] == "/* string literal */"
        )
    except Exception:
        passed = False
    status = "✓" if passed else "✗"
    print(f"\n{status} dictionary JSONC parse")
    if not passed:
        all_passed = False

    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            dict_dir = os.path.join(tmp_dir, ".text_style_jp")
            os.mkdir(dict_dir)
            dict_path = os.path.join(dict_dir, "99_jsonc-test.json")
            with open(dict_path, "w", encoding="utf-8") as handle:
                handle.write(jsonc_text)
            try:
                os.chdir(tmp_dir)
                result = style_markdown("JSONC辞書テスト")
            finally:
                os.chdir(original_cwd)
        passed = result == "JSONC辞書テスト"
    except Exception:
        passed = False
        result = ""
    finally:
        os.chdir(original_cwd)
    status = "✓" if passed else "✗"
    print("\n{} dictionary JSONC load 入力: {!r}".format(status, "JSONC辞書テスト"))
    print("  期待: {!r}".format("JSONC辞書テスト"))
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

    for mode, original, expected in mode_style_test_cases:
        result = style_by_mode(original, mode)
        passed = result == expected
        status = "✓" if passed else "✗"
        print(f"\n{status} mode style {mode} 入力: {original!r}")
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

    # --- dry-run / DiagnosticCollector テスト ---

    # _record_step_changes: 変更なし → Finding なし
    c = DiagnosticCollector()
    c.set_line(1)
    _record_step_changes("abc", "abc", "test-rule", c)
    passed = len(c.findings) == 0
    status = "✓" if passed else "✗"
    print(f"\n{status} _record_step_changes 変更なし")
    if not passed:
        all_passed = False

    # _record_step_changes: 変更あり → Finding が 1 件以上、line/rule が正しい
    c = DiagnosticCollector()
    c.set_line(2)
    _record_step_changes("第3章", "第 3 章", "test-rule", c)
    passed = (
        len(c.findings) >= 1
        and all(f.line == 2 for f in c.findings)
        and all(f.rule == "test-rule" for f in c.findings)
    )
    status = "✓" if passed else "✗"
    fragments = [(f.original, f.corrected) for f in c.findings]
    print(f"\n{status} _record_step_changes 変更あり: {fragments}")
    if not passed:
        all_passed = False

    # _record_step_changes: NUL を含む断片は除外される
    c = DiagnosticCollector()
    c.set_line(1)
    _record_step_changes("abc\x00def", "abc\x00xyz\x00", "test-rule", c)
    # NUL を含む断片が Finding に含まれないことを確認
    passed = all("\x00" not in f.original and "\x00" not in f.corrected for f in c.findings)
    status = "✓" if passed else "✗"
    print(f"\n{status} _record_step_changes NUL プレースホルダー除外: {[(f.original, f.corrected) for f in c.findings]}")
    if not passed:
        all_passed = False

    # style_prose: ルール属性テスト (fullwidth-alnum)
    c = DiagnosticCollector()
    c.set_line(5)
    result = style_prose("ＡＢＣＤ", collector=c)
    passed = (
        result == "ABCD"
        and len(c.findings) >= 1
        and any(f.rule == "fullwidth-alnum" for f in c.findings)
        and all(f.line == 5 for f in c.findings)
    )
    status = "✓" if passed else "✗"
    rules_found = [f.rule for f in c.findings]
    print(f"\n{status} style_prose fullwidth-alnum: rules={rules_found}")
    if not passed:
        all_passed = False

    # style_prose: ルール属性テスト (fullwidth-halfwidth-space)
    c = DiagnosticCollector()
    c.set_line(1)
    result = style_prose("第3章", collector=c)
    passed = (
        result == "第 3 章"
        and any(f.rule == "fullwidth-halfwidth-space" for f in c.findings)
    )
    status = "✓" if passed else "✗"
    rules_found = [f.rule for f in c.findings]
    print(f"\n{status} style_prose fullwidth-halfwidth-space: rules={rules_found}")
    if not passed:
        all_passed = False

    # style_markdown: 行番号テスト
    c = DiagnosticCollector()
    result = style_markdown("line1\n第3章\nline3", collector=c)
    passed = (
        any(f.line == 2 and f.rule == "fullwidth-halfwidth-space" for f in c.findings)
    )
    status = "✓" if passed else "✗"
    line2_findings = [(f.line, f.rule) for f in c.findings if f.rule == "fullwidth-halfwidth-space"]
    print(f"\n{status} style_markdown 行番号追跡: {line2_findings}")
    if not passed:
        all_passed = False

    # style_markdown: heading-number ルール
    c = DiagnosticCollector()
    c.set_line(1)
    result = style_markdown("## 1. タイトル", collector=c)
    passed = (
        result == "## タイトル"
        and any(f.rule == "heading-number" for f in c.findings)
    )
    status = "✓" if passed else "✗"
    print(f"\n{status} style_markdown heading-number: {[(f.rule, f.original, f.corrected) for f in c.findings if f.rule == 'heading-number']}")
    if not passed:
        all_passed = False

    # _format_findings_stylish: 出力フォーマットテスト
    c = DiagnosticCollector()
    c.set_line(3)
    c.add(5, "第3章", "第 3 章", "fullwidth-halfwidth-space", "", "全角/半角境界スペース")
    output = _format_findings_stylish("test.md", c.findings)
    passed = (
        "test.md" in output
        and "3:5" in output
        and '"第3章"' in output
        and '"第 3 章"' in output
        and "fullwidth-halfwidth-space" in output
        and "1 problem found" in output
    )
    status = "✓" if passed else "✗"
    print(f"\n{status} _format_findings_stylish 出力フォーマット")
    if not passed:
        all_passed = False
        print(f"  出力:\n{output}")

    # _format_findings_stylish: 辞書出典あり
    c = DiagnosticCollector()
    c.set_line(1)
    c.add(1, "サーバ", "サーバー", "dict-replace", "/path/to/10_microsoft.json", "辞書 replace")
    output = _format_findings_stylish("test.md", c.findings)
    passed = "10_microsoft.json" in output
    status = "✓" if passed else "✗"
    print(f"\n{status} _format_findings_stylish 辞書出典表示")
    if not passed:
        all_passed = False

    # CLI in-place: 着手時メッセージを先に出力する
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_path = os.path.join(tmp_dir, "sample.md")
            with open(input_path, "w", encoding="utf-8") as handle:
                handle.write("ファイルディスクリプタ")
            stdout_buffer = io.StringIO()
            try:
                os.chdir(tmp_dir)
                with contextlib.redirect_stdout(stdout_buffer):
                    exit_code = main([input_path, "--mode", "markdown", "--in-place"])
            finally:
                os.chdir(original_cwd)
            with open(input_path, "r", encoding="utf-8") as handle:
                updated = handle.read()
        output = stdout_buffer.getvalue()
        passed = (
            exit_code == 0
            and f"Processing: {input_path}" in output
            and f"Modified: {input_path}" in output
            and output.index(f"Processing: {input_path}") < output.index(f"Modified: {input_path}")
            and updated == "ファイル記述子\n"
        )
    except Exception:
        passed = False
        output = ""
        updated = ""
    finally:
        os.chdir(original_cwd)
    status = "✓" if passed else "✗"
    print(f"\n{status} CLI in-place progress output")
    if not passed:
        all_passed = False
        print(f"  出力: {output!r}")
        print(f"  更新後: {updated!r}")

    print("\n" + "=" * 60)
    print("すべてのテストに合格しました" if all_passed else "一部のテストに失敗しました")
    return all_passed


def _format_findings_stylish(filepath: str, findings: List[Finding]) -> str:
    """textlint 風のフォーマットで Finding 一覧を文字列に変換する。"""
    lines = [filepath]
    for f in sorted(findings, key=lambda f: (f.line, f.column)):
        source_info = f" ({os.path.basename(f.source)})" if f.source else ""
        lines.append(f'  {f.line}:{f.column}\t"{f.original}" → "{f.corrected}"\t{f.rule}{source_info}')
    lines.append("")
    count = len(findings)
    lines.append(f"  {count} problem{'s' if count != 1 else ''} found")
    return "\n".join(lines) + "\n"


def _build_parser(prog: str, description: str, allow_mode_option: bool):
    import argparse

    parser = argparse.ArgumentParser(prog=prog, description=description)
    parser.add_argument("input", nargs="?", help="入力ファイル (省略時は標準入力)")
    parser.add_argument("-o", "--output", help="出力ファイル (省略時は標準出力)")
    parser.add_argument("--test", action="store_true", help="テストを実行")
    parser.add_argument("--check", action="store_true", help="変更が必要かチェックのみ (変更が必要な場合は終了コード 1)")
    parser.add_argument("--dry-run", action="store_true", help="変更を適用せず、検出された変更をルール名付きで表示する")
    parser.add_argument("-i", "--in-place", action="store_true", help="入力ファイルを直接上書きする")
    if allow_mode_option:
        parser.add_argument(
            "--mode",
            default="auto",
            choices=["auto", "markdown", "c", "cpp", "csharp", "python", "shell", "make", "text"],
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

    if args.in_place:
        print(f"Processing: {args.input}", flush=True)

    if args.input:
        with open(args.input, "r", encoding="utf-8") as handle:
            text = handle.read()
    else:
        text = sys.stdin.read()

    requested_mode = getattr(args, "mode", "auto")
    mode = _resolve_mode(args.input, requested_mode, default_mode)

    if args.dry_run:
        collector = DiagnosticCollector()
        style_by_mode(text, mode, collector=collector)
        if collector.findings:
            sys.stdout.write(_format_findings_stylish(args.input or "(stdin)", collector.findings))
            return 1
        return 0

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
