---
name: check-all-markdown-style
description: |
  リポジトリ内の管理対象 Markdown に対して
  framework/docsfw/bin/text_style_jp.py を --in-place で一括実行するときに使うスキルです。
  自動生成物と外部 OSS 由来 Markdown を除外し、開始前の Git クリーン確認、
  長時間実行の監視、変更差分の日本語構文確認、ユーザー報告までを扱います。
when_to_use: |
  - リポジトリ内の Markdown 全体に text_style_jp.py を適用したいとき
  - 自動生成物と外部 OSS 由来 Markdown を除外して Markdown スタイルを一括更新したいとき
  - Markdown スタイル適用後の差分に日本語構文の破綻がないか確認したいとき
---

# 全 Markdown スタイル チェック

## 前提

- Git のステージング、コミット、アンステージは行わない。
- `--dry-run` は不要。対象に `--in-place` を直接実行する。
- 変更の妥当性評価はユーザーが行うが、エージェントは差分を読み、日本語構文の破綻や明らかな不自然変換を報告する。
- 実行は長時間になるため、`yield_time_ms` を長めに取り、完了まで監視する。

## 開始前チェック

作業開始時に、ルートと全サブモジュールの Git 状態がクリーンであることを確認する。  
出力が 1 行でもある場合は、`text_style_jp.py` を実行せず、ユーザーへ状態を報告して継続可否を仰ぐ。

```bash
git status --porcelain=v1 --ignore-submodules=none
git submodule foreach --recursive 'git status --porcelain=v1'
```

## 対象範囲

対象は各 Git ルートの tracked Markdown (`*.md`) のみとする。  
未追跡ファイル、生成物ディレクトリ、`node_modules`、`pages` などは対象にしない。

除外する外部 OSS / 配布物:

- `framework/docsfw/bin/modules/LibDeflate/**`
- `framework/docsfw/styles/widdershins/**`
- `framework/testfw/gtest/**`

## 実行手順

1. 対象ファイル一覧を NUL 区切りで作成する。空白や日本語を含むパスに対応するため、改行区切りにしない。

    ```bash
    bash -lc 'set -euo pipefail
    list=/tmp/text_style_jp_markdown_targets.zlist
    : > "$list"
    add_root() {
      local prefix="$1"
      local gitdir="$2"
      git -C "$gitdir" ls-files -z "*.md" | while IFS= read -r -d "" f; do
        case "$prefix$f" in
          framework/docsfw/bin/modules/LibDeflate/*) continue ;;
          framework/docsfw/styles/widdershins/*) continue ;;
          framework/testfw/gtest/*) continue ;;
        esac
        printf "%s\0" "$prefix$f" >> "$list"
      done
    }
    add_root "" "."
    add_root "app/com_util/" "app/com_util"
    add_root "app/porter/" "app/porter"
    add_root "framework/docsfw/" "framework/docsfw"
    add_root "framework/doxyfw/" "framework/doxyfw"
    add_root "framework/makefw/" "framework/makefw"
    add_root "framework/testfw/" "framework/testfw"
    tr -cd "\000" < "$list" | wc -c'
    ```

2. 対象件数をユーザーへ短く報告する。

3. `--in-place` を 1 ファイルずつ実行し、ログを `/tmp/text_style_jp_inplace.log` に保存する。

    ```bash
    bash -lc 'set -euo pipefail
    list=/tmp/text_style_jp_markdown_targets.zlist
    log=/tmp/text_style_jp_inplace.log
    : > "$log"
    total=$(tr -cd "\000" < "$list" | wc -c)
    i=0
    while IFS= read -r -d "" f; do
      i=$((i + 1))
      printf "[%s/%s] in-place %s\n" "$i" "$total" "$f"
      python framework/docsfw/bin/text_style_jp.py "$f" --mode markdown --in-place >> "$log" 2>&1
    done < "$list"
    printf "in_place_done=%s\nlog=%s\n" "$total" "$log"'
    ```

4. 実行後、変更されたファイルを確認する。

    ```bash
    rg -n "^Modified:" /tmp/text_style_jp_inplace.log
    git status --short --ignore-submodules=none
    git submodule foreach --recursive 'git status --short'
    ```

## 差分確認

変更された Markdown の diff を読み、次の観点で日本語構文の破綻がないか確認する。

- 日本語の文末や見出しが不自然になっていないか。
- `#pragma weak` のように、Markdown 見出し中でも `#` が C 言語表記として必要な箇所が壊れていないか。
- インライン コード、リンク、URL、ファイル パス、コマンド名の意味が変わっていないか。
- 本文段落で 1 文の途中に表示幅調整目的の改行が追加されていないか。
- リストの入れ子、表、コード フェンス、引用、リンク定義など Markdown 構造上の改行が崩れていないか。
- 全角 `？` / `！` から半角 `?` / `!` への変換が文脈上許容できるか。
- 用語置換やスペース挿入により、日本語として読みにくい文になっていないか。

明らかな破綻がある場合は、ユーザーへ報告してから最小限の修正を行う。  
判断が割れる場合は、修正せずに「確認が必要な差分」として報告する。

## 報告

完了時は次を簡潔に報告する。

- 対象ファイル数
- 除外した代表パス
- `--in-place` の完了有無
- 変更されたファイル
- 日本語構文チェックで問題なし、または確認が必要な箇所
- ログ ファイルのパス
