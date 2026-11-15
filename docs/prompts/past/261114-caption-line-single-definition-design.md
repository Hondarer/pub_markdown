<!--
生成元: agree-before-implement スキル
文書種別: 最終仕様 (design)
最終更新エージェント: codex (Sol、移動先リンクの更新)
上流文書: `261114-caption-line-single-definition-discussion.md` (検討用 Markdown)。削除されている場合があります。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。上流文書が存在する場合は、上流文書の再開手順に従って進行位置を確認し、判断の経緯を上流文書の Q&A で確認します。存在しない場合は、この文書を単体の最終仕様として扱います。最終更新エージェントのセッション情報が参照可能であれば再開時のコンテキストとして利用し、別エージェントからの引き継ぎや担当変更によりセッションが見つからない場合も異常とせず、文書の記載から継続してください。
-->

# 図とコード ブロックのキャプション行互換処理の廃止 最終仕様

## 概要

Markdown におけるキャプション行 (`Table:` / `Figure:` / `CodeBlock:`) の適用対象をブロック種別ごとに単一定義化し、移行互換として残していた「図フェンス直後の `CodeBlock:` 受け付け」および「通常コード ブロック直後の `Figure:` 採用」を廃止する。

| 対象ブロック | 正しいキャプション行 | ラベル接頭辞 | 対象外キャプション行の扱い |
| --- | --- | --- | --- |
| 表 | `Table:` | `tbl:` | 通常の段落として出力 (警告なし) |
| 図 (`plantuml` / `mermaid` フェンス) | `Figure:` | `fig:` | `CodeBlock:` は警告を出力して通常の段落として出力 |
| 画像 1 個だけの段落 | `Figure:` | `fig:` | `CodeBlock:` は通常の段落として出力 (警告なし) |
| 通常のコード ブロック (図言語以外) | `CodeBlock:` | `lst:` | `Figure:` は警告を出力して通常の段落として出力 |

> [!NOTE]
> `Figure:` 導入直後の段階的移行期間に設けていた互換処理を終了し、文書作成者とフィルター双方の仕様を単純化する。

## 動作仕様

### 対象外組み合わせの振る舞い

1. **図フェンス (`diagram-languages.txt` に含まれる言語) の直後に `CodeBlock:` 行を置いた場合**:
    - キャプションおよびラベルとして採用せず、標準エラー出力へ警告を出力したうえで、`CodeBlock:` 行をそのまま通常の段落として出力する。
    - PlantUML フェンスにソース内 `caption` や `@startuml` タイトルがある場合は、外部キャプションが指定されなかったものとして従来どおりソース内タイトルを使用する。
2. **通常のコード ブロック (図言語以外) の直後に `Figure:` 行を置いた場合**:
    - キャプションおよびラベルとして採用せず、標準エラー出力へ警告を出力したうえで、`Figure:` 行をそのまま通常の段落として出力する。
3. **画像 1 個だけの段落の直後に `CodeBlock:` 行を置いた場合**:
    - 現行どおり警告を出さず、通常の段落として出力する。
4. **上記以外のブロックの直後に `Figure:` / `CodeBlock:` 行を置いた場合**:
    - 現行どおり警告を出さず、通常の段落として出力する。

### ラベル接頭辞不一致の警告仕様

正しいブロックとの組み合わせにおいて、末尾ラベルの接頭辞がキャプション種別と一致しない場合の仕様は次のとおりとする。

- `Figure:` 行 (図フェンスまたは画像) に `{#fig:...}` 以外 (`{#lst:...}` 等) が指定された場合: 標準エラー出力へ警告を出力したうえで、キャプションとラベルを採用する。
- `CodeBlock:` 行 (通常コード ブロック) に `{#lst:...}` 以外 (`{#fig:...}` 等) が指定された場合: 標準エラー出力へ警告を出力したうえで、キャプションとラベルを採用する。
- 互換処理の廃止に伴い、図フェンス直後の `CodeBlock:` における `{#fig:...}` を許容していた例外分岐は削除する。

## 実装設計

### Pandoc フィルター (codeblock-caption-line.lua)

1. **`apply_to_codeblock` の変更**:
    - `is_diagram = is_diagram_codeblock(code_block)` を判定する。
    - `kind == "Figure" and not is_diagram` の場合: 警告 (`"図以外のコード ブロックに対して 'Figure:' が使われています。通常コード ブロックには 'CodeBlock:' を使用してください。"`) を出力し、キャプション・属性・ラベルを設定せず `false` を返す (呼び出し側で通常の段落として出力される)。
    - `kind == "CodeBlock" and is_diagram` の場合: 警告 (`"図のコード ブロックに対して 'CodeBlock:' が使われています。図には 'Figure:' を使用してください。"`) を出力し、キャプション・属性・ラベルを設定せず `false` を返す (通常の段落として出力される)。
    - 上記により、対象外組み合わせでは `code_block.attributes["caption"]` および `SOURCE_MARK` を設定しない。なお、もし廃止済みのフェンス属性 `caption="..."` が併記されていた場合は、後段の `CodeBlock` パスで従来どおり警告して破棄する。
2. **`check_label_prefix` の簡素化**:
    - 第 3 引数 `allow_fig_on_codeblock` を削除し、`kind == "Figure"` なら `lprefix ~= "fig"`、`kind == "CodeBlock"` なら `lprefix ~= "lst"` を無条件に警告する。

### MkDocs 前処理 (stage_livedocs.py)

1. **`convert_captions` の変更**:
    - 図フェンス直後の分岐条件を `caption_kind == "Figure" and _is_after_diagram(out, diagram_block)` に限定し、`CodeBlock:` は図として `<figure>` 化しない。
    - `caption_kind == "CodeBlock" and _is_after_diagram(out, diagram_block)` の場合: 標準エラー出力へ警告 (`"[stage_livedocs] 警告: 図のコード ブロックに対して 'CodeBlock:' が使われています。図には 'Figure:' を使用してください。\n"`) を出力し、通常の `.docsfw-caption` 相当の段落として出力するか、あるいは通常の段落として出力する。
      > [!IMPORTANT]
      > Pandoc フィルター側では対象外の `CodeBlock:` / `Figure:` 行を通常の段落として出力する。`stage_livedocs.py` でも、対象外と判定された図フェンス直後の `CodeBlock:` および通常コード ブロック直後の `Figure:` はキャプションとして採用せず、通常の段落として出力する (`.docsfw-caption` 等のキャプション用クラスや `{: #... }` 属性化を行わず、元の段落行をそのまま `out` に残す)。
    - PlantUML フェンスにソース内 `caption` があり直後に `CodeBlock:` が置かれた場合、`CodeBlock:` は図のキャプションとして採用されないため、`internal_caption` による `<figure>` ラップが優先されるように状態を維持する。具体的には、`caption_kind == "CodeBlock" and _is_after_diagram(...)` で警告を出して通常段落へフォールバックする前に、`internal_caption` があれば `_wrap_diagram_with_caption(out, diagram_block, internal_caption)` を実行する。
2. **`_check_caption_label_prefix` の簡素化**:
    - 引数 `after_diagram` を削除し、`caption_kind == "CodeBlock"` では常に `lprefix ~= "lst"` で警告する。なお、対象外組み合わせ (図フェンス直後の `CodeBlock:`、通常コード ブロック直後の `Figure:`) はキャプションとして解釈しないため、対象外組み合わせ時には `_check_caption_label_prefix` を呼ばない。

### 過去検討記録の残存箇所の更新

リポジトリ内の `docs/prompts/` 配下 (本件関連文書 `261114-figure-caption-line-*` および `261114-caption-line-single-definition-*` を除く) に残っている図フェンス直後の `CodeBlock:` 行 (2 箇所) を `Figure:` へ書き換える。

- [cplat-account-session-discussion.md](../../../../../app/cplat/docs/prompts/current/cplat-account-session-discussion.md#L295)
- [261109-porter-path-priority-timestamp-auth-design.md](../../../../../app/porter/docs/prompts/past/261109-porter-path-priority-timestamp-auth-design.md#L134)

### テストの更新

1. `framework/docsfw/bin_test/test_figure_caption_line.py`:
    - `test_diagram_fence_keeps_codeblock_compatibility_without_warning` を、図フェンス直後の `CodeBlock:` が警告を出力し通常の段落 (`<p>CodeBlock: ...</p>`) として出力されること (図キャプションにならないこと) を検証するテストへ更新する。
    - `test_normal_codeblock_with_figure_warns_and_applies_caption` を、通常コード ブロック直後の `Figure:` が警告を出力し通常の段落 (`<p>Figure: ...</p>`) として出力されること (コード キャプションにならないこと) を検証するテストへ更新する。
2. `framework/docsfw/bin_test/test_plantuml_caption_priority.py`:
    - `test_codeblock_line_overrides_source_caption` を `Figure:` 行を使用するテスト (`test_figure_line_overrides_source_caption`) へ更新する。
3. `framework/docsfw/livedocs/bin_test/test_stage_livedocs.py`:
    - 既存のテストのうち、標準的な図キャプションのテストとして `CodeBlock:` を使用している箇所を `Figure:` へ更新する。
    - 図フェンス直後の `CodeBlock:` および通常コード ブロック直後の `Figure:` が警告を出力し、`<figure>` 化や `.docsfw-caption` 化されず通常の段落として残ることを検証するテストを追加する。

## 永続的知見の反映計画

作業実施フェーズで、以下の正本ドキュメントおよびコード コメントを更新する。

1. [codeblock-caption.md](../../codeblock-caption.md):
    - 「互換性と警告」節から、図フェンスへの `CodeBlock:` 非推奨互換記述および通常コード ブロックへの `Figure:` 採用記述を削除する。
    - 対象ブロックとキャプション行の対応が 1 対 1 の単一定義であること、および対象外の組み合わせ (`plantuml` / `mermaid` 直後の `CodeBlock:`、通常コード ブロック直後の `Figure:`) は警告を出力して通常の段落として出力することを明記する。
2. [codeblock-caption-line.lua](../../../bin_internal/pandoc-filters/codeblock-caption-line.lua) および [stage_livedocs.py](../../../livedocs/bin/stage_livedocs.py):
    - ファイル先頭コメントおよび `convert_captions` の docstring から互換受け付けに関する記述を削除し、単一定義の仕様を記述する。

## 受入条件と検証計画

以下のすべてを満たすことをもって完了とする。

1. **単体テストの更新・追加と全件合格**:
    - `framework/docsfw/bin_test/test_figure_caption_line.py`、`test_plantuml_caption_priority.py`、および `framework/docsfw/livedocs/bin_test/test_stage_livedocs.py` がすべてパスすること。
2. **リポジトリ全体の残存確認**:
    - `261114-figure-caption-line-*` および本案件の検討文書を除き、全リポジトリで図フェンス直後の `CodeBlock:` 行が 0 件であることを検索で確認すること。
3. **機械的検証**:
    - 変更したすべての Markdown ファイルに対して `text_style_jp.py --dry-run` がエラー 0 件で通ること。
4. **過去残課題一覧の更新**:
    - [261114-figure-caption-line-backlog.md](261114-figure-caption-line-backlog.md) の `BL-001` の状態を「対応済み」へ更新し、本案件での対処経緯と対処内容を追記すること。
