<!--
生成元: agree-before-implement スキル
文書種別: 検討用 Markdown (discussion)
最終更新エージェント: agy / セッション ID: 215c7a4f-c55d-4c1c-a095-71dd0f86f212
下流文書: `261114-caption-line-single-definition-design.md` (最終仕様)、`261114-caption-line-single-definition-backlog.md` (残課題一覧)。未作成の場合や、削除されている場合があります。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。ユーザーが編集した最新版を読み直し、作業 WBS の `← **CURRENT**` の項目から再開します。最終更新エージェントのセッション情報が参照可能であれば再開時のコンテキストとして利用し、別エージェントからの引き継ぎや担当変更によりセッションが見つからない場合も異常とせず、文書の記載から継続してください。`← **CURRENT**` の項目は処理が中止された項目である場合があり、どこまで進んでいたかは文書だけでは分かりません。対象成果物の内容を確認して実施済みの範囲を特定してから、作業を再開してください。`← **CURRENT**` がなく、作業 WBS がすべて完了 (✅) であれば、この案件の合意フローは完了しています。
-->

# 図とコード ブロックのキャプション行互換処理の廃止 検討

ファイル名: `framework/docsfw/docs/prompts/current/261114-caption-line-single-definition-discussion.md`

## 検討の識別

検討 ID: caption-line-single-definition

版: 2

状態: 合意済み

## 作業 WBS と進捗管理

この検討用 Markdown が管理する作業 WBS です。検討用 Markdown のための情報収集と質問の実施、残懸念がないことの確認 (第 1 ゲート: 最終仕様作成への着手)、最終決定事項 (最終仕様) を記載した `261114-caption-line-single-definition-design.md` の作成、最終仕様の承認の受付 (第 2 ゲート)、承認された最終仕様に従った作業の実施、および作業完了後の成果物の承認の受付 (第 3 ゲート) に至る詳細な手順を記載します。

凡例: ⏸️ 未着手、🔄 実施中、🚫 ブロック中、⚠️ 要注意、✅ 完了。現在取り組んでいる項目の末尾に `← **CURRENT**` を付けます。

- ✅ 1. 検討用 Markdown のための情報収集と質問の実施
    - ✅ 1.1. 前提条件と要求事項の調査 (`261114-figure-caption-line-backlog.md`、Pandoc フィルター、MkDocs 前処理、正本文書、テスト、リポジトリ内残存箇所)
    - ✅ 1.2. 課題・論点の抽出と明確化のための確認項目 ([Q-001](#q-001-対象外組み合わせの扱いと警告方針)、[Q-002](#q-002-過去検討記録に残る図フェンス直後の-codeblock-行の扱い)、[Q-003](#q-003-ラベル接頭辞不一致の警告仕様の扱い)) の作成
    - ✅ 1.3. Q&A ターンごとのユーザー回答の受付と記録 (JST 日時、Git ユーザー名または発言者)
    - ✅ 1.4. 回答に基づく前提・制約の検証と WBS の見直し
- ✅ 2. 前提合意と残懸念の解消 (第 1 ゲート: 最終仕様作成への着手)
    - ✅ 2.1. 全論点に対する未解決事項および質問の解消確認
    - ✅ 2.2. 方針・前提条件の合意確定 (懸念がないことをもってフェーズ 2 へ着手)
- ✅ 3. 最終決定事項 (最終仕様) の作成と承認の受付
    - ✅ 3.1. `framework/docsfw/docs/prompts/current/261114-caption-line-single-definition-design.md` の作成
    - ✅ 3.2. 最終仕様における受入条件と整合性の確認
    - ✅ 3.3. 対話セッションにおける最終仕様 (design.md) の承認の受付 (第 2 ゲート: 作業着手の合意)
- ✅ 4. 承認された最終仕様に従った作業の実施
    - ✅ 4.1. Pandoc フィルター (`framework/docsfw/bin_internal/pandoc-filters/codeblock-caption-line.lua`) の更新
    - ✅ 4.2. MkDocs 前処理 (`framework/docsfw/livedocs/bin/stage_livedocs.py`) の更新
    - ✅ 4.3. 過去検討記録の残存 `CodeBlock:` 書き換え (Q-002 の決定に応じる)
    - ✅ 4.4. 単体テスト (`framework/docsfw/bin_test/test_figure_caption_line.py`、`framework/docsfw/bin_test/test_plantuml_caption_priority.py`、`framework/docsfw/livedocs/bin_test/test_stage_livedocs.py`) の更新
    - ✅ 4.5. 正本文書 (`framework/docsfw/docs/codeblock-caption.md`) およびコード コメントの更新
    - ✅ 4.6. 局所テストおよび機械的検証 (`text_style_jp.py` 等) の実施
    - ✅ 4.7. 受入条件への適合確認 (全完確認)
    - ✅ 4.8. 過去残課題一覧 (`261114-figure-caption-line-backlog.md`) の経緯・対処更新および本案件の残課題一覧整理 (残渣がなければ削除)
- ✅ 5. 成果物の承認の受付 (第 3 ゲート)
    - ✅ 5.1. 成果物・検証結果・残課題の提示
    - ✅ 5.2. 対話セッションにおける成果物の承認の受付 (「承認」または「完了」の受領によるスキル完了)

## 対象と参照資料

対象成果物:

- [codeblock-caption-line.lua](../../../bin_internal/pandoc-filters/codeblock-caption-line.lua)
- [stage_livedocs.py](../../../livedocs/bin/stage_livedocs.py)
- [codeblock-caption.md](../../codeblock-caption.md)
- [test_figure_caption_line.py](../../../bin_test/test_figure_caption_line.py)、[test_plantuml_caption_priority.py](../../../bin_test/test_plantuml_caption_priority.py)、[test_stage_livedocs.py](../../../livedocs/bin_test/test_stage_livedocs.py)
- 過去検討記録の残存箇所 (Q-002 の結果による)
- 引き継ぎ元の残課題一覧: [261114-figure-caption-line-backlog.md](261114-figure-caption-line-backlog.md) (経緯・対処の更新対象)

今回の対象範囲: `261114-figure-caption-line-backlog.md` の `BL-001` (図とコード ブロックのキャプション行互換処理の廃止および `Table:` / `Figure:` / `CodeBlock:` の単一定義化)

書き込み可能な検討用 Markdown: この文書 (`framework/docsfw/docs/prompts/current/261114-caption-line-single-definition-discussion.md`)

参照資料と版:

- [261114-figure-caption-line-backlog.md](261114-figure-caption-line-backlog.md) (整理状態: 整理済み)
- [261114-figure-caption-line-design.md](261114-figure-caption-line-design.md)
- [codeblock-caption.md](../../codeblock-caption.md)
- [AGENTS.md](../../../AGENTS.md)

## 現行の合意内容

1. 引き継ぎ元課題 [BL-001](261114-figure-caption-line-backlog.md#bl-001-図とコード-ブロックのキャプション行互換処理の廃止) に基づき、`Table:` (表のみ)、`Figure:` (図フェンスおよび画像のみ)、`CodeBlock:` (通常のコード ブロックのみ) の単一定義化を行う。
2. 図フェンス直後の `CodeBlock:` 行および通常コード ブロック直後の `Figure:` 行は、キャプションとして採用せず通常の段落として出力し、標準エラー出力へ警告を出す ([Q-001](#q-001-対象外組み合わせの扱いと警告方針))。
3. `docs/prompts/` 配下の過去検討記録に残る図フェンス直後の `CodeBlock:` 行 (2 箇所: [cplat-account-session-discussion.md](../../../../../app/cplat/docs/prompts/current/cplat-account-session-discussion.md#L295)、[261109-porter-path-priority-timestamp-auth-design.md](../../../../../app/porter/docs/prompts/current/261109-porter-path-priority-timestamp-auth-design.md#L134)) は `Figure:` へ書き換える ([Q-002](#q-002-過去検討記録に残る図フェンス直後の-codeblock-行の扱い))。
4. 図フェンス直後の `CodeBlock:` に関するラベル接頭辞不一致の互換例外は削除し、正しいブロックとの組み合わせでラベル接頭辞が不一致の場合は現行どおり警告を出したうえでキャプションとラベルを採用する ([Q-003](#q-003-ラベル接頭辞不一致の警告仕様の扱い))。

## 観点別の確認

| 観点 | 状態 | 根拠・関連 Q |
| --- | --- | --- |
| 目的・利用者 | 確認済み | 文書作成者・保守者向けに記法の二重化を解消する ([BL-001](261114-figure-caption-line-backlog.md#bl-001-図とコード-ブロックのキャプション行互換処理の廃止)) |
| 範囲・境界 | 確認済み | [Q-002](#q-002-過去検討記録に残る図フェンス直後の-codeblock-行の扱い) |
| 入力・根拠 | 確認済み | [261114-figure-caption-line-backlog.md](261114-figure-caption-line-backlog.md)、[codeblock-caption-line.lua](../../../bin_internal/pandoc-filters/codeblock-caption-line.lua)、[stage_livedocs.py](../../../livedocs/bin/stage_livedocs.py) |
| 整合性・依存関係 | 確認済み | [Q-001](#q-001-対象外組み合わせの扱いと警告方針)、[Q-003](#q-003-ラベル接頭辞不一致の警告仕様の扱い) |
| 実現性・例外 | 確認済み | [Q-001](#q-001-対象外組み合わせの扱いと警告方針)、[Q-003](#q-003-ラベル接頭辞不一致の警告仕様の扱い) |
| 受入条件・検証 | 確認済み | 単体テスト (`bin_test`、`livedocs/bin_test`)、全リポジトリ検索、`text_style_jp.py --dry-run` |

## 質問一覧

| Q-ID | 論点 | 状態 | 依存・関連 |
| --- | --- | --- | --- |
| [Q-001](#q-001-対象外組み合わせの扱いと警告方針) | 対象外組み合わせの扱いと警告方針 | 解決済み | なし |
| [Q-002](#q-002-過去検討記録に残る図フェンス直後の-codeblock-行の扱い) | 過去検討記録に残る図フェンス直後の `CodeBlock:` 行の扱い | 解決済み | [Q-001](#q-001-対象外組み合わせの扱いと警告方針) |
| [Q-003](#q-003-ラベル接頭辞不一致の警告仕様の扱い) | ラベル接頭辞不一致の警告仕様の扱い | 解決済み | [Q-001](#q-001-対象外組み合わせの扱いと警告方針) |

## 明確化のための確認項目

### Q-001 対象外組み合わせの扱いと警告方針

**Status**

解決済み

**Question**

図フェンス (`plantuml` / `mermaid`) の直後に `CodeBlock:` 行を置いた場合、および通常のコード ブロックの直後に `Figure:` 行を置いた場合、どのような振る舞いにしますか。

**Context**

- **経緯と背景**: 現在は移行互換のため、図フェンス直後の `CodeBlock:` 行を警告なしで図キャプションとして採用し、通常コード ブロック直後の `Figure:` 行も標準エラー出力へ警告を出したうえでキャプションとして採用しています。`BL-001` では、これらをキャプションとして解釈せず「通常の段落として扱う (または警告を出して破棄する)」ことが提案されています。
- **根拠資料**: [codeblock-caption-line.lua](../../../bin_internal/pandoc-filters/codeblock-caption-line.lua#L204-L228)、[stage_livedocs.py](../../../livedocs/bin/stage_livedocs.py#L915-L966)、[codeblock-caption.md](../../codeblock-caption.md#L39-L44)
- **既存の他組み合わせとの比較**:
    - 画像 1 個だけの段落の直後に `CodeBlock:` 行を置いた場合、および直前が対象ブロックでない `Figure:` / `CodeBlock:` 行は、キャプションとして扱わず **通常の段落として出力 (警告なし)** としています。
    - 廃止されたフェンス属性 `caption="..."` は、**標準エラー出力へ警告を出して属性を破棄** しています。
- **各案の違い**:
    - **案 A (推奨)**: 対象外の組み合わせ (図フェンス直後の `CodeBlock:`、通常コード ブロック直後の `Figure:`) はキャプションとして採用せず **通常の段落として出力** し、あわせて誤記法に気付けるよう **標準エラー出力へ警告を出力** します。
    - **案 B**: 他の対象外ブロック (画像直後の `CodeBlock:` 等) と完全に統一し、**警告なしで通常の段落として出力** します。
    - **案 C**: 誤ったキャプション行が残らないよう、**標準エラー出力へ警告を出して段落ごと破棄** します (本文から消えます)。

**Answer**

選択方式: 単一選択

- [x] A: (推奨) キャプションとして採用せず通常の段落として出力し、標準エラー出力へ警告を出す。
- [ ] B: キャプションとして採用せず通常の段落として出力し、警告は出さない。
- [ ] C: キャプションとして採用せず、標準エラー出力へ警告を出したうえで段落ごと破棄する。
- [ ] D: その他
- [ ] X: 意図不明 (詳細な質問内容に再生成すること)

その他の回答 / 補足:

回答者: Tetsuo Honda  
回答日時: 2026-11-14 22:14:02 JST

**Recommendation**

推奨: A  
理由: 本文が意図せず消えるリスク (案 C) を避けつつ、本来キャプションとして意図された誤記法がサイレントに通常段落へフォールバックして見落とされるリスク (案 B) を防げるためです。

**Assessment**

単一選択で明確に「A」が選択された。通常段落としての出力と標準エラー出力への警告により、誤記法の見落としと本文消失の双方を回避でき、矛盾はない。

### Q-002 過去検討記録に残る図フェンス直後の CodeBlock: 行の扱い

**Status**

解決済み

**Question**

`docs/prompts/` 配下の過去の検討記録に残っている図フェンス直後の `CodeBlock:` 行 (2 箇所) はどう扱いますか。

**Context**

- **経緯と背景**: `Figure:` 導入時に `docs/prompts/` 以外の既存文書はすべて `Figure:` へ書き換えられました。リポジトリ全体を検索したところ、`docs/prompts/` 配下 (本件の説明・検討記録である `261114-figure-caption-line-*` を除く) に残っている図フェンス直後の `CodeBlock:` 行は以下の **2 箇所のみ** でした。
    1. [cplat-account-session-discussion.md](../../../../../app/cplat/docs/prompts/current/cplat-account-session-discussion.md#L295) (`mermaid` フェンス直後の `CodeBlock:`)
    2. [261109-porter-path-priority-timestamp-auth-design.md](../../../../../app/porter/docs/prompts/current/261109-porter-path-priority-timestamp-auth-design.md#L134) (`mermaid` フェンス直後の `CodeBlock:`)
- **判断の影響**: [Q-001](#q-001-対象外組み合わせの扱いと警告方針) で図フェンス直後の `CodeBlock:` をキャプションとして採用しない方針にした場合、上記 2 箇所をそのまま残すと、これらを発行した際に図のキャプションが付かなくなります (案 A の場合は警告も出ます)。

**Answer**

選択方式: 単一選択

- [x] A: (推奨) 上記 2 箇所を `Figure:` へ書き換えて、過去検討記録の図キャプションと発行時の整合を保つ。
- [ ] B: 過去の検討記録は変更しない方針を優先し、上記 2 箇所は書き換えない。
- [ ] C: その他
- [ ] X: 意図不明 (詳細な質問内容に再生成すること)

その他の回答 / 補足:

回答者: Tetsuo Honda  
回答日時: 2026-11-14 22:14:02 JST

**Recommendation**

推奨: A  
理由: 対象がわずか 2 箇所であり、`Figure:` へ更新しても検討の判断内容自体は変わらず、発行時のキャプション表示および警告ゼロの状態を維持できるためです。

**Assessment**

単一選択で明確に「A」が選択された。対象は 2 ファイルのみであり、書き換えによる矛盾や副作用はない。

**Related**

- [Q-001](#q-001-対象外組み合わせの扱いと警告方針)

### Q-003 ラベル接頭辞不一致の警告仕様の扱い

**Status**

解決済み

**Question**

正しいブロックとの組み合わせにおいてラベル接頭辞だけが不一致な場合 (`Figure:` に `{#lst:...}`、通常コード ブロックの `CodeBlock:` に `{#fig:...}` 等) の仕様はどうしますか。

**Context**

- **経緯と背景**: 現在、`codeblock-caption-line.lua` と `stage_livedocs.py` では、正しい組み合わせであってもラベル接頭辞がキャプション種別と一致しない場合は「標準エラー出力へ警告を出したうえでキャプションとラベルを採用する」仕様となっています。なお、図フェンス直後の互換 `CodeBlock:` における `{#fig:...}` だけは例外として警告を出していませんでした。
- **根拠資料**: [codeblock-caption-line.lua](../../../bin_internal/pandoc-filters/codeblock-caption-line.lua#L187-L201)、[stage_livedocs.py](../../../livedocs/bin/stage_livedocs.py#L795-L808)
- **判断の影響**: 互換処理の廃止に伴い、図フェンス直後の `CodeBlock:` に対する例外分岐 (`allow_fig_on_codeblock` / `after_diagram`) は不要となり削除します。そのうえで、通常のラベル接頭辞不一致時の挙動を現行のまま (警告＋採用) 維持するか、不採用 (警告してキャプションまたはラベルを無視) に変更するかを確認します。

**Answer**

選択方式: 単一選択

- [x] A: (推奨) 互換例外だけを削除し、ラベル接頭辞不一致時は現行どおり「警告を出したうえでキャプションとラベルを採用する」仕様を維持する。
- [ ] B: 互換例外を削除したうえで、ラベル接頭辞が不一致の場合は警告を出してラベル (またはキャプション全体) を採用しない。
- [ ] C: その他
- [ ] X: 意図不明 (詳細な質問内容に再生成すること)

その他の回答 / 補足:

回答者: Tetsuo Honda  
回答日時: 2026-11-14 22:14:02 JST

**Recommendation**

推奨: A  
理由: 本案件の目的は図とコード ブロックのキャプション行の互換処理廃止であり、既存のラベル接頭辞不一致時の警告＋採用仕様まで破壊的に変更する必要がないためです。

**Assessment**

単一選択で明確に「A」が選択された。互換例外の削除と既存の警告＋採用仕様の維持は目的に整合する。

**Related**

- [Q-001](#q-001-対象外組み合わせの扱いと警告方針)

## 対象成果物と合意版

最終決定事項 (最終仕様) の設計書: `framework/docsfw/docs/prompts/current/261114-caption-line-single-definition-design.md`

検討用 Markdown の合意版 (第 1 ゲート): 版 2 (全 Q 解決済み・残懸念なし)

最終仕様 (design.md) の合意版 (第 2 ゲート): 承認済み (2026-11-14 22:16:33 JST)

更新予定の成果物:

- `framework/docsfw/bin_internal/pandoc-filters/codeblock-caption-line.lua`
- `framework/docsfw/livedocs/bin/stage_livedocs.py`
- `framework/docsfw/docs/codeblock-caption.md`
- `framework/docsfw/bin_test/test_figure_caption_line.py`、`framework/docsfw/bin_test/test_plantuml_caption_priority.py`、`framework/docsfw/livedocs/bin_test/test_stage_livedocs.py`
- `app/cplat/docs/prompts/current/cplat-account-session-discussion.md`、`app/porter/docs/prompts/current/261109-porter-path-priority-timestamp-auth-design.md`
- `framework/docsfw/docs/prompts/current/261114-figure-caption-line-backlog.md` (対処結果の記録)

受入条件:

1. `test_figure_caption_line.py`、`test_plantuml_caption_priority.py`、`test_stage_livedocs.py` が全件合格すること。
2. 関連検討文書を除き、全リポジトリで図フェンス直後の `CodeBlock:` 行が 0 件であること。
3. 変更した全 Markdown ファイルで `text_style_jp.py --dry-run` がエラー 0 件で通ること。
4. `261114-figure-caption-line-backlog.md` の `BL-001` を対応済みへ更新すること。

## 反映と検証の記録

- **実装更新**:
    - [codeblock-caption-line.lua](../../../bin_internal/pandoc-filters/codeblock-caption-line.lua): 図フェンス直後の `CodeBlock:` と通常コード ブロック直後の `Figure:` を警告出力＋不採用 (通常段落として出力) に変更し、`check_label_prefix` の互換例外を削除。
    - [stage_livedocs.py](../../../livedocs/bin/stage_livedocs.py): 同様に図フェンス直後の `CodeBlock:` と通常コード ブロック直後の `Figure:` を警告出力＋通常段落出力へ変更し、`_check_caption_label_prefix` の互換例外を削除。
- **過去検討記録の書き換え**:
    - [cplat-account-session-discussion.md](../../../../../app/cplat/docs/prompts/current/cplat-account-session-discussion.md#L295) および [261109-porter-path-priority-timestamp-auth-design.md](../../../../../app/porter/docs/prompts/current/261109-porter-path-priority-timestamp-auth-design.md#L134) の図フェンス直後の `CodeBlock:` を `Figure:` へ更新。
- **正本文書と過去残課題一覧の更新**:
    - [codeblock-caption.md](../../codeblock-caption.md): 互換記述を削除し、対象外の組み合わせと警告仕様へ更新。
    - [261114-figure-caption-line-backlog.md](261114-figure-caption-line-backlog.md): `BL-001` の状態を「対応済み」へ更新し、継続作業の経緯と対処を追記。新たな残課題はなし。
- **検証結果**:
    - `python3 -m unittest framework/docsfw/bin_test/test_figure_caption_line.py framework/docsfw/bin_test/test_plantuml_caption_priority.py framework/docsfw/livedocs/bin_test/test_stage_livedocs.py -v`: 89 件すべて合格 (`OK`)。
    - リポジトリ全体検索 (関連検討文書除く): 図フェンス直後の `CodeBlock:` 残存 0 件。
    - `text_style_jp.py --dry-run`: 変更した Markdown ファイル (`codeblock-caption.md`、`cplat-account-session-discussion.md`、`261109-porter-path-priority-timestamp-auth-design.md`) すべてエラー 0 件。
