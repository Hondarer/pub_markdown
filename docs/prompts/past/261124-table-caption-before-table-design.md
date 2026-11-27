<!--
生成元: agree-before-implement スキル
文書種別: 最終仕様 (design)
最終更新日時: 2026-11-24 08:25:00 JST
最終更新エージェント: claude code / セッション ID: session_01KJc53RaT4Cei9nCXSSZqH1
稼働 OS: Linux (WSL)
上流文書: `261124-table-caption-before-table-overview.md` (全体管理文書)、`261124-table-caption-before-table-discussion.md` (検討用 Markdown)、`261124-table-caption-before-table-lightadr.md` (簡易 ADR)。いずれも削除されている場合があります。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。上流文書の全体管理文書が存在する場合は、その再開手順に従って進行位置を確認し、決定事項を簡易 ADR で、判断の経緯を検討用 Markdown の Q&A で確認します。存在しない場合は、この文書を単体の最終仕様として扱います。
-->

# 表のキャプションの前置き 最終仕様

## 概要

表のキャプションを指定する `Table:` 段落を、表の直後ではなく表の直前に置く記法へ変更します。  
GitHub などで Markdown をそのまま表示した場合も、表題が表の上に表示され、本文の見出しと同じ位置で読めるようにします。  
発行結果での表示位置 (表の上) は変わりません。

`Figure:` と `CodeBlock:` は対象外とし、ブロックの直後に置く記法のままとします。

> [!NOTE]
> Pandoc の Markdown は `Table:` を表の前後どちらに置いても受け付けますが、表が連続すると後置きの解釈が優先されます。docsfw は前置きだけを受け付ける判定を自前で行い、Pandoc には判定済みの並びで渡します。

## 記法

### 基本形

`Table:` 段落を表の直前に置き、`Table:` 段落と表の間に空行を 1 行以上入れます。

```markdown
Table: 表のキャプション {#tbl:sample}

| 項目 | 値 |
|---|---|
| A | B |
```

- 末尾の `{#tbl:xxx}` は省略できるラベルで、pandoc-crossref による採番と相互参照の対象になります。
- キャプションを段落内で改行すると、HTML、DOCX、MkDocs のいずれでも改行を保持します。ラベルは最後の行の末尾に置きます。
- キャプションの接頭辞は `Table:` だけです。`table:` と、行頭の `:` だけの短縮形はキャプションとして扱いません。

### キャプションとして扱う条件

`Table:` 段落は、次のすべてを満たす場合に、直後の表のキャプションになります。

1. 段落の先頭が `Table:` で始まる。
2. 段落の直後のブロックが表である (間に空行を挟む)。
3. 段落と表の字下げの幅が一致する (箇条書きの項目内では、表と同じ字下げ)。

表が連続する場合も、`Table:` 段落は常に直後の表のキャプションです。

```markdown
Table: 1 つ目の表

| 項目 | 値 |
|---|---|
| t1 | 10 |

Table: 2 つ目の表

| 項目 | 値 |
|---|---|
| u1 | 30 |
```

### キャプションとして扱わない場合

条件を満たさない `Table:` 段落は、Pandoc 発行と MkDocs 発行のどちらでも、通常の段落として出力し、標準エラー出力へ警告を出します。  
表の直後に置いた従来の書き方 (後置き) も、直後に表がなければこの扱いになります。

`Table:` 段落と表の間に空行がない場合、表は段落の一部として解析されるため、キャプションにも表にもなりません。

## Pandoc 発行

### 前処理による並べ替え

Pandoc に Markdown を渡す直前に、前処理 `bin_internal/table-caption-preprocess.py` を通します。  
前処理は、元の行の順序を見て、キャプションとして扱う `Table:` 段落を表の直後へ並べ替えます。  
Pandoc の `table_captions` 拡張 (既定で有効) が、並べ替えた `Table:` 段落を解析の時点で表のキャプションとして取り込みます。

前処理の規則は次のとおりです。

1. キャプションとして扱う条件を満たす `Table:` 段落は、直後の表の後ろへ移す。表が連続する場合も、各 `Table:` 段落は直後の表の後ろへ移るため、Pandoc の解釈と帰属が一致する。
2. 条件を満たさない `Table:` 段落は、先頭の `Table:` を `Table\:` にエスケープし、警告を出す。Pandoc はこの段落をキャプションとして取り込まず、`Table:` で始まる通常の段落として出力する。
3. 表の直前または直後にある、行頭が `table:` または `:` の段落も、コロンをエスケープしてキャプションとして取り込まれないようにする。
4. ラベルの接頭辞が `tbl` 以外の場合は、警告を出したうえでラベルを採用する。
5. フェンス付きコード ブロックと HTML コメントの中は変更しない。

判定は `text_style_jp.py` と同じ共通モジュール `bin_internal/table_caption_position.py` で行います。  
前処理は `pub_markdown_core.sh` のすべての Pandoc 呼び出し (HTML と DOCX) に適用します。  
前処理で例外が発生した場合は、入力をそのまま出力します。

> [!NOTE]
> Lua フィルターで `Table:` 段落を畳み込む方式では、`Table:` 段落が解析の時点で通常の段落になります。Pandoc は箇条書きの項目に段落が 1 つでもあると、リスト全体を段落ごとの表示にするため、項目の中の表の前に `Table:` を置くだけで表示が変わります。前処理で並べ替えると、Pandoc の解析結果は従来と同じになります。

### 表示

`table-caption-style.lua` (キャプションを `div.docsfw-caption.docsfw-table-caption` として表の前へ出す処理) と DOCX の出力は変更しません。  
DOCX では、Pandoc が表のキャプションを表の前に出力します。  
`codeblock-caption-line.lua` は `Table:` を扱いません。

## MkDocs 発行

`livedocs/bin/stage_livedocs.py` の `convert_captions()` を変更します。

- `Table:` 段落の後の空行に続くブロックが表 (区切り行を含むブロック) で、字下げの幅が一致する場合は、キャプションの段落をその位置のまま出力し、`.docsfw-caption .docsfw-table-caption` クラスとラベルの id を付けます。キャプションを表の前へ移す処理は不要になるため削除します。
- 条件を満たさない `Table:` 段落は、警告を出し、クラスを付けない通常の段落として、その位置に残します。
- 字下げの扱い (箇条書きの項目内の 4 スペース、8 スペース) と、複数行のキャプションの字下げの除去は現状と同じです。

## text_style_jp.py

### 日常の確認 (既定の動作)

`bin/text_style_jp.py` と `bin_internal/text_style_jp_frontends.py` に、キャプションの位置の規則 (規則名 `table-caption-position`) を追加します。

- 対象: `Table:` 段落のうち、直前のブロックが同じ字下げの表で、直後のブロックが表でないもの。
- `--dry-run` と `--check`: 該当箇所を報告します。
- `--in-place`: 該当する `Table:` 段落を、直前の表の前へ同じ字下げのまま移します。
- 直後が表の `Table:` 段落は、表に挟まれていても前置きとして正しいと判定し、変更しません。
- Markdown と、C/C++ の Doxygen コメント内の Markdown の両方に適用します。フェンス付きコード ブロックの中は対象外です。
- Doxygen コメントで行頭に置いた構造コマンド (`@par`、`@parblock`、`@endparblock`、`@param` など) の行は、ブロックの区切りとして扱い、移動の対象に含めません。

### 移行用オプション

旧記法 (後置き) で書かれた文書を移行するオプション `--migrate-table-caption` を追加します。

- 表の直後の `Table:` 段落を、直後に表が続くかどうかにかかわらず、すべて直前の表のキャプションとして表の前へ移します。
- このオプションを指定した場合は、キャプションの移動だけを行い、その他の整形規則は適用しません。
- `--dry-run`、`--check`、`--in-place` と組み合わせて使います。
- 後置きだけで書かれた文書に適用するものとし、前置きと後置きが混在する文書は適用の対象外です。オプションの説明に、この適用条件を記載します。

> [!IMPORTANT]
> 移行用オプションを前置きで書かれた文書に適用すると、表に挟まれた `Table:` を前の表へ付け替えてしまいます。日常の整形では指定しません。

## 既存の記述の移行

### 範囲

リポジトリ全体の、行頭が `Table:` の段落を移行します。

- 対象: Markdown (過去の検討記録 `docs/prompts/past/` を含む) と、C/C++ の Doxygen コメント
- 対象のリポジトリ: 親リポジトリと、すべてのサブモジュール (`framework/docsfw`、`framework/doxyfw`、`framework/makefw`、`framework/testfw`、`app/cplat`、`app/porter`、`app/cjson`、`app/lua`、`app/openssl`、`app/sqlite`、`app/zlib`)
- 対象外: フェンス付きコード ブロックの中、`node_modules/`、`.venv/` などの外部由来の配布物と自動生成物

### 手順

1. 移行専用の変換スクリプトを作業用の一時ディレクトリに作成します。リポジトリには置きません。
2. 移行前の対象ファイルの複製を一時ディレクトリに保存します。
3. 変換スクリプトで、対象ファイルを一括で変換します。
4. 変換後に、日常の確認 (`text_style_jp.py --check` の `table-caption-position`) で後置きの検出が 0 件であることを確認します。
5. 案件の終了時に、変換スクリプトの機能を `text_style_jp.py --migrate-table-caption` として統合します。
6. 統合後の `--migrate-table-caption` を手順 2 の複製に適用し、手順 3 の結果と一致することを確認します。

移行は変換処理で自動化します。作業を委譲する場合は、低コストのモデルを使います。

## テスト

Table: 追加・更新するテスト

| 対象 | 配置 | 確認する内容 |
| --- | --- | --- |
| Pandoc の前処理とフィルター | `bin_test/test_table_caption_line.py` (新規) | 前置きの結び付け、表が連続する場合、後置きの警告と段落化、空行なしの扱い、ラベルと pandoc-crossref の採番、複数行のキャプション、箇条書きの項目内、`:` と `table:` を扱わないこと、DOCX のキャプション |
| MkDocs 前処理 | `livedocs/bin_test/test_stage_livedocs.py` | 表のキャプションに関する既存のテストを前置きに書き換え、表が連続する場合、後置きの警告、字下げの不一致を追加 |
| text_style_jp.py | `bin_test/test_text_style_jp_table_caption.py` (新規) | 既定の動作での検出と修正 (表に挟まれた前置きを変更しないことを含む)、`--migrate-table-caption` の変換、Doxygen コメント、フェンス内の除外 |

## 正本文書とコメントへの反映

| 反映先 | 反映する内容 |
| --- | --- |
| `framework/docsfw/docs/table-caption.md` | 前置きの記法、キャプションとして扱う条件と扱わない場合、Pandoc と MkDocs の処理の流れ |
| `framework/docsfw/docs/codeblock-caption.md` | 表のキャプションは表の前に置き、図とコード ブロックはブロックの後ろに置くことの説明 |
| `framework/docsfw/docs/text_style_jp.md` | `table-caption-position` 規則と `--migrate-table-caption` の説明と適用条件 |
| `framework/docsfw/docs/sample/table-caption.md`、`sample/list-table.md`、`sample/README.md` | 前置きの例への書き換え、`sample/README.md` の短縮形 `:` の例と説明の削除 |
| `framework/testfw/docs/about-test-phase.md` | 表題の付け方の記述 (「表の直後に」) の更新 |
| `app/general/docs/doxygen-comment-guideline.md` | Doxygen コメント内の `Table:` の位置と空行の規則 |
| `bin/text_style_jp.py` の自己テストの例 | 前置きの例への書き換え |
| `table-caption-preprocess.py`、`table_caption_position.py`、`table-caption-style.lua`、`stage_livedocs.py` の先頭コメントと docstring | 前置きの判定と、前処理で並べ替えてから Pandoc に渡す理由 |

上の表のほか、`Table:` の位置を説明している文書 (AGENTS.md、SKILL.md を含む) を、「表の直後」「Table: 行」などの語で検索して同じく更新します。

## 受入条件

1. Pandoc 発行 (HTML と DOCX) と MkDocs 発行のいずれでも、前置きの `Table:` が直後の表のキャプションとして表の上に表示されること。表が連続する場合も、それぞれの表に正しいキャプションが付くこと。
2. 後置きの `Table:` が、両方の発行で通常の段落として出力され、警告が出ること。
3. ラベル付きのキャプションが pandoc-crossref で採番され、相互参照が機能すること。
4. 追加・更新したテストと、docsfw の既存のテストが成功すること。
5. 移行後、全リポジトリの対象ファイルで `text_style_jp.py --check` の `table-caption-position` の検出が 0 件であること。
6. 統合後の `--migrate-table-caption` の変換結果が、移行専用スクリプトの結果と一致すること。
7. 変更した Markdown が `text_style_jp.py --dry-run` で指摘なしであること。
8. 代表的な文書 (`framework/docsfw/docs/sample/table-caption.md`、`sample/list-table.md`、`sample/repeatedly-test.md`、`app/doxygen-sample` の Doxygen 出力) の発行結果で、キャプションの内容と位置が移行前と同じであること。
