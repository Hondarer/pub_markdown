<!--
生成元: agree-before-implement スキル
文書種別: 全体管理文書 (overview)
最終更新日時: 2026-11-25 19:33:00 JST
最終更新エージェント: claude code / セッション ID: session_01KJc53RaT4Cei9nCXSSZqH1
稼働 OS: Linux (WSL)
下流文書: `261124-table-caption-before-table-discussion.md` (検討用 Markdown)、`261124-table-caption-before-table-lightadr.md` (簡易 ADR)、`261124-table-caption-before-table-design.md` (最終仕様)、`261124-table-caption-before-table-backlog.md` (残課題一覧)。未作成の場合や、削除されている場合があります。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。この文書と、ユーザーが編集した最新の検討用 Markdown を読み直し、作業 WBS の `← **CURRENT**` の項目から再開します。最終更新エージェントのセッション情報や稼働 OS・最終更新日時が参照可能であれば再開時のコンテキストや環境差分の把握に利用し、別エージェントや別環境・別 OS からの引き継ぎ、担当変更によりセッションが見つからない場合も異常とせず、文書の記載から継続してください。`← **CURRENT**` の項目は処理が中止された項目である場合があり、どこまで進んでいたかは文書だけでは分かりません。対象成果物の内容を確認して実施済みの範囲を特定してから、作業を再開してください。`← **CURRENT**` がなく、作業 WBS がすべて完了 (✅) であれば、この案件の合意フローは完了しています。
-->

# 表のキャプションの前置き 全体管理

この文書は、案件の識別、作業 WBS、対象範囲、確認状況、経緯を管理します。質問と回答の本文は検討用 Markdown に、決定事項は簡易 ADR に記載し、この文書には重複して記載しません。

## 案件の識別

検討 ID: 261124-table-caption-before-table

検討用 Markdown の版: 4

状態: 成果物の承認待ち

## 作業 WBS と進捗管理

凡例: ⏸️ 未着手、🔄 実施中、🚫 ブロック中、⚠️ 要注意、✅ 完了。現在取り組んでいる項目の末尾に `← **CURRENT**` を付けます。

- ✅ 1. 検討用 Markdown のための情報収集と質問の実施
    - ✅ 1.1. 前提条件と要求事項の調査 (Pandoc の `table_captions` 拡張、`table-caption-style.lua`、`stage_livedocs.py` の `convert_captions()`、`text_style_jp.py`、Doxygen コメント内の `Table:`、既存の `Table:` の件数)
    - ✅ 1.2. 課題・論点の抽出と確認項目 ([Q-001](261124-table-caption-before-table-discussion.md#q-001-前置きのキャプションを表へ結び付ける方式) 〜 [Q-007](261124-table-caption-before-table-discussion.md#q-007-後置きの-table-の機械的な検出)) の作成
    - ✅ 1.3. Q&A ターンごとのユーザー回答の受付と記録 (版 1: Q-001 〜 Q-007、版 2: Q-008、Q-009)
    - ✅ 1.4. 回答に基づく前提・制約の検証、簡易 ADR への決定事項の反映 (LADR-002 〜 LADR-009)、WBS の見直し
- ✅ 2. 前提合意と残懸念の解消 (第 1 ゲート: 最終仕様作成への着手)
    - ✅ 2.1. 全論点に対する未解決事項および質問の解消確認
    - ✅ 2.2. 方針・前提条件の合意確定
- ✅ 3. 最終決定事項 (最終仕様) の作成と承認の受付
    - ✅ 3.1. `261124-table-caption-before-table-design.md` の作成
    - ✅ 3.2. 最終仕様における受入条件と整合性の確認
    - ✅ 3.3. 対話セッションにおける最終仕様の承認の受付 (第 2 ゲート)
- ⚠️ 4. 承認された最終仕様に従った作業の実施
    - ✅ 4.1. Pandoc 側の実装 (前処理 `bin_internal/table-caption-preprocess.py` の追加、`bin_internal/pub_markdown_core.sh` の Pandoc 呼び出しへの前処理の適用と `-table_captions` の取り消し、`codeblock-caption-line.lua` からの `Table:` の処理の削除)
    - ✅ 4.2. MkDocs 側の実装 (`livedocs/bin/stage_livedocs.py` の `convert_captions()`)
    - ✅ 4.3. `text_style_jp.py` による後置きの検出と修正 (`bin/text_style_jp.py`、`bin_internal/text_style_jp_frontends.py`)
    - ✅ 4.4. 移行専用の変換スクリプト (作業用の一時ディレクトリ) の作成と、案件の終了時の `text_style_jp.py --migrate-table-caption` への統合
    - ✅ 4.5. テストの追加・更新 (`livedocs/bin_test/test_stage_livedocs.py`、`bin_test/` の Pandoc 発行テスト、`text_style_jp.py` と変換処理のテスト)
    - ✅ 4.6. 正本文書の更新 (`docs/table-caption.md`、`docs/codeblock-caption.md`、`docs/sample/table-caption.md`、`docs/sample/list-table.md`、`docs/sample/README.md`、`app/general/docs/doxygen-comment-guideline.md`、`bin/text_style_jp.py` の自己テスト用の例)
    - ✅ 4.7. 既存の `Table:` の移行 (過去の検討記録を含むリポジトリ全体の Markdown と Doxygen コメント。framework の各サブモジュール、`app/general`、`app/cplat`、`app/porter` などの app)
    - ✅ 4.8. 局所テスト、発行結果の比較、`text_style_jp.py` による確認
    - ⚠️ 4.9. 受入条件への適合確認 (受入条件 7 は、移行で書き換えた Markdown に移行前からある `text_style_jp.py --dry-run` の指摘 154 件が残るため未達。移行による増加は 0 件。扱いを第 3 ゲートで確認)
    - ✅ 4.10. 簡易 ADR の最終確認
    - ✅ 4.11. 残課題一覧の再構築と整理
    - ✅ 4.12. 親リポジトリとサブモジュールの pull で取り込んだ変更の `Table:` の再確認 (追加の依頼)
- 🔄 5. 成果物の承認の受付 (第 3 ゲート)
    - 🔄 5.1. 成果物・検証結果・残課題の提示 ← **CURRENT**
    - ⏸️ 5.2. 対話セッションにおける成果物の承認の受付

## 対象と参照資料

対象成果物: docsfw の表キャプション処理 (Pandoc 発行と MkDocs 発行)、表キャプションの正本文書、既存文書と Doxygen コメントの `Table:` 行

今回の対象範囲: `Table:` 行を表の直前に置く記法への変更と、それに伴う処理・文書・既存記述の移行。`Figure:` と `CodeBlock:` は後置きのまま変更しません (2026-11-24 の対話でのユーザーの指示に基づく)。

書き込み可能な検討文書: この文書、`261124-table-caption-before-table-discussion.md`、`261124-table-caption-before-table-lightadr.md`、`261124-table-caption-before-table-backlog.md`

参照資料と版:

- `framework/docsfw` v20261118.0.0 (コミット 2a0f1df3): `docs/table-caption.md`、`docs/codeblock-caption.md`、`bin_internal/pandoc-filters/table-caption-style.lua`、`livedocs/bin/stage_livedocs.py`
- pandoc 3.11 (手元の環境)
- `app/general/docs/doxygen-comment-guideline.md`

## 観点別の確認

| 観点 | 状態 | 根拠・関連 Q |
| --- | --- | --- |
| 目的・利用者 | 確認済み | GitHub などでそのまま表示したときの見やすさと、表題を本文の見出しと同じ位置に置くことが目的 (2026-11-24 の対話でのユーザーの発言) |
| 範囲・境界 | 確認済み | [Q-005](261124-table-caption-before-table-discussion.md#q-005-既存の-table-の移行範囲)、[Q-008](261124-table-caption-before-table-discussion.md#q-008-変換処理の置き場所) |
| 入力・根拠 | 確認済み | 参照資料と版を記載。Pandoc の挙動は手元の pandoc 3.11 で確認済み |
| 整合性・依存関係 | 確認済み | [Q-002](261124-table-caption-before-table-discussion.md#q-002-後置きの-table-の扱い)、[Q-003](261124-table-caption-before-table-discussion.md#q-003-短縮形--の扱い)。Q-006 と Q-007 の重なりは [Q-008](261124-table-caption-before-table-discussion.md#q-008-変換処理の置き場所) で解消 |
| 実現性・例外 | 確認済み | [Q-001](261124-table-caption-before-table-discussion.md#q-001-前置きのキャプションを表へ結び付ける方式)、[Q-004](261124-table-caption-before-table-discussion.md#q-004-キャプションと表の間の空行)、[Q-009](261124-table-caption-before-table-discussion.md#q-009-表に挟まれた-table-段落の解釈) |
| 受入条件・検証 | 確認済み | [Q-007](261124-table-caption-before-table-discussion.md#q-007-後置きの-table-の機械的な検出)。受入条件は最終仕様の「受入条件」に記載 |

## 質問一覧

| Q-ID | 論点 | 状態 | 依存・関連 | 反映先の決定 |
| --- | --- | --- | --- | --- |
| [Q-001](261124-table-caption-before-table-discussion.md#q-001-前置きのキャプションを表へ結び付ける方式) | 前置きのキャプションを表へ結び付ける方式 | 解決済み | なし | LADR-002 |
| [Q-002](261124-table-caption-before-table-discussion.md#q-002-後置きの-table-の扱い) | 後置きの `Table:` の扱い | 解決済み | Q-001 | LADR-003 |
| [Q-003](261124-table-caption-before-table-discussion.md#q-003-短縮形--の扱い) | 短縮形 `:` の扱い | 解決済み | Q-001 | LADR-004 |
| [Q-004](261124-table-caption-before-table-discussion.md#q-004-キャプションと表の間の空行) | キャプションと表の間の空行 | 解決済み | Q-001 | LADR-005 |
| [Q-005](261124-table-caption-before-table-discussion.md#q-005-既存の-table-の移行範囲) | 既存の `Table:` の移行範囲 | 解決済み | Q-002 | LADR-006 |
| [Q-006](261124-table-caption-before-table-discussion.md#q-006-一括移行の手段) | 一括移行の手段 | 解決済み | Q-005、Q-008 | LADR-008 |
| [Q-007](261124-table-caption-before-table-discussion.md#q-007-後置きの-table-の機械的な検出) | 後置きの `Table:` の機械的な検出 | 解決済み | Q-002 | LADR-007 |
| [Q-008](261124-table-caption-before-table-discussion.md#q-008-変換処理の置き場所) | 変換処理の置き場所 | 解決済み | Q-006、Q-007、Q-009 | LADR-008 |
| [Q-009](261124-table-caption-before-table-discussion.md#q-009-表に挟まれた-table-段落の解釈) | 表に挟まれた `Table:` 段落の解釈 | 解決済み | Q-002、Q-005、Q-007、Q-008 | LADR-009 |
| [Q-010](261124-table-caption-before-table-discussion.md#q-010-箇条書きの表示が変わる問題の対処) | 箇条書きの表示が変わる問題の対処 | 解決済み | Q-001、Q-002、Q-003 | LADR-002 |

## 対象成果物と合意版

最終決定事項 (最終仕様) の設計書: `261124-table-caption-before-table-design.md`

検討用 Markdown の合意版 (第 1 ゲート): 版 3 (2026-11-24 07:16、Q-001 〜 Q-009 解決済み)

最終仕様の合意版 (第 2 ゲート): 2026-11-24 07:16 版を承認 (2026-11-24 の対話で「進めて下さい」)

更新予定の成果物: 最終仕様の「Pandoc 発行」「MkDocs 発行」「text_style_jp.py」「既存の記述の移行」「テスト」「正本文書とコメントへの反映」の各章に記載したファイル

受入条件: 最終仕様の「受入条件」の 8 項目

## 経緯

| 日時 (JST) | 出来事 | 内容・参照先 |
| --- | --- | --- |
| 2026-11-24 06:50 | 方針の事前確認 | 対話で `Table:` の前置きの妥当性を確認し、ユーザーが方針を妥当と判断 ([LADR-001](261124-table-caption-before-table-lightadr.md#ladr-001-table-行を表の直前に置く)) |
| 2026-11-24 06:58 | 案件の開始 | 全体管理文書、検討用 Markdown (版 1、Q-001 〜 Q-007)、簡易 ADR を作成 |
| 2026-11-24 07:07 | 版 1 の回答 | Q-001 〜 Q-007 にユーザーが回答。Q-006 を未解決とし、LADR-002 〜 LADR-007 を記録 ([簡易 ADR](261124-table-caption-before-table-lightadr.md)) |
| 2026-11-24 07:10 | 版 2 の質問追加 | Q-006 と Q-007 の回答の重なり、および表に挟まれた `Table:` の解釈を Q-008、Q-009 として追加。WBS の 4. を見直し |
| 2026-11-24 07:13 | 版 2 の回答 | Q-008、Q-009 にユーザーが回答。Q-006 を解決済みとし、LADR-008、LADR-009 を記録 |
| 2026-11-24 07:16 | 第 1 ゲートの通過 | 全 Q の解決と観点別の確認を終え、最終仕様 (`261124-table-caption-before-table-design.md`) を作成 |
| 2026-11-24 07:47 | 第 2 ゲートの通過 | 対話で最終仕様が承認された。難易度の低い作業は Sonnet に委譲する指示を受けた |
| 2026-11-24 08:10 | 作業の中断 | 発行結果の比較で、`table_captions` の無効化による箇条書きの表示の差分を検出。Q-010 を追加して作業 4.8 を中断 |
| 2026-11-24 08:19 | 方針の変更と作業の再開 | Q-010 で A が選ばれ、Pandoc 発行を前処理での並べ替えへ変更。最終仕様の「Pandoc 発行」の章を改訂し ([LADR-002](261124-table-caption-before-table-lightadr.md#ladr-002-pandoc-での前置きキャプションの結び付け))、作業 4.1 から再開 |
| 2026-11-24 09:12 | 作業の完了 | 作業 4 を終え、残課題一覧 (`261124-table-caption-before-table-backlog.md`) を整理。第 3 ゲートの承認を依頼 |
| 2026-11-25 19:00 | 追加の依頼 | 第 3 ゲートの承認の前に、親リポジトリとサブモジュールの変更を pull して最新化し、変更があったファイルの `Table:` を再確認する依頼を受けた。作業 4.12 として実施 |
| 2026-11-25 19:33 | 追加の依頼の完了 | pull と再確認を終え、Doxygen の構造コマンドの判定を修正。第 3 ゲートの承認を再度依頼 |

## 反映と検証の記録

### 対応箇所

| 対象 | 変更内容 |
| --- | --- |
| `framework/docsfw/bin_internal/table_caption_position.py` (新規) | 判定の共通モジュール。`relocate_table_captions()` (既定と移行の規則) と `prepare_for_pandoc()` (Pandoc 向けの並べ替えとエスケープ) |
| `framework/docsfw/bin_internal/table-caption-preprocess.py` (新規) | Pandoc に渡す前の前処理 (標準入力から標準出力) |
| `framework/docsfw/bin_internal/pub_markdown_core.sh` | Pandoc 呼び出し 6 か所に前処理を追加 |
| `framework/docsfw/bin_internal/pandoc-filters/codeblock-caption-line.lua` | 変更なし (途中で加えた `Table:` の処理は Q-010 の決定で取り消し) |
| `framework/docsfw/livedocs/bin/stage_livedocs.py` | `convert_captions()` を前置きの判定へ変更。表の前へ移す処理を削除。図の直後の `Table:` の前に図を包む処理を追加 |
| `framework/docsfw/bin/text_style_jp.py`、`bin_internal/text_style_jp_frontends.py`、`bin_internal/text_style_jp_engine.py` | `table-caption-position` 規則、`--migrate-table-caption`、並べ替えの差分を `unattributed-change` から外す `covered_lines`、自己テストの例の前置き化 |
| `framework/testfw/bin_internal/results_markdown.py` とテスト | テスト結果の Markdown の表キャプションを表の前に出力 |
| テスト | `bin_test/test_table_caption_line.py`、`bin_test/test_table_caption_position.py`、`bin_test/test_text_style_jp_table_caption.py` (新規)、`livedocs/bin_test/test_stage_livedocs.py`、`bin_test/test_heading_content_indent.py`、`bin_test/test_docx_heading_indent.py` |
| 正本文書 | `docs/table-caption.md`、`docs/codeblock-caption.md`、`docs/text_style_jp.md`、`docs/livedocs-design.md`、`docs/sample/` の 3 ファイル、`framework/testfw/docs/about-test-phase.md`、`app/general/docs/doxygen-comment-guideline.md`、`table-caption-style.lua` のコメント、`app/doxygen-sample/prod/include/table.h` のコメント |
| 既存の記述の移行 | 移行専用スクリプトで 345 ファイル 1851 件を表の前へ移動。手作業で `app/porter/prod/include/porter/porter_spec.h` (字下げの不一致) と `app/general/docs/prompts/past/261113-source-comment-bl029-progress.md` (HTML コメントのマーカー) を修正 |
| 既存の不具合の修正 | `framework/docsfw/docs/text_style_jp.md` のコード フェンスの閉じ方の誤り (10 個の表がコード ブロックになっていた) |
| pull 後の再移行 (作業 4.12) | 上流の変更と重なる 34 ファイルは、移行前の内容へ戻してから fast-forward で pull し、移行を取り込み後の内容へ適用し直した (`porter_spec.h` は 3 方向マージ)。pull で変更された Markdown と C/C++ の 307 ファイルを再確認し、新たに書かれた後置きを含めて 37 ファイル 271 件を表の前へ移動 |
| Doxygen の構造コマンドの判定 (作業 4.12) | `table_caption_position.py` が `@par`、`@parblock`、`@endparblock` などの行をブロックの一部として扱い、キャプションとこれらの行を入れ替えていた不具合を修正し、テストを追加。`app/porter` の `porter-bench.cc`、`porter-config-check.c`、`porter-test.c` を正しい結果へ置き換え、`@par` の直下の表は doxygen-comment-guideline の規則どおり `@parblock` ～ `@endparblock` で囲んだ |
| コード例の移行 (作業 4.12) | Markdown のコード フェンス内の例 (`framework/doxyfw/docs/cheatsheet.md`、`commands.md`、`framework/makefw/docs/subfolder-compilation.md`、`app/general` の検討記録 1 件) の後置きのキャプションを表の前へ移動 |
| 上流の文書の不具合の修正 (作業 4.12) | `app/porter/docs/architecture.md` で、取り込んだコミットが表の途中に節を挿入し、表の後半とキャプションが表から外れていた。節を表の説明の後ろへ移し、キャプションを表の前へ移動 |

### 検証結果

- 移行の一致: 統合後の `--migrate-table-caption` (共通モジュール) を移行前の複製に適用した結果が、移行専用スクリプトの結果と全 346 ファイルで一致 (1851 件、差異 0)。
- 移行後の検出: 全対象ファイルで既定の規則の移動対象 0 件、前処理の警告 0 件。
- Pandoc 発行の比較: 移行前 (HEAD のフィルター、移行前の文書) と移行後 (前処理と新しいフィルター、移行後の文書) の HTML を Markdown 321 ファイルで比較。差分は `framework/docsfw/docs/sample/README.md` の短縮形 `:` の例だけ (Q-003 の決定どおり)。
- MkDocs 発行の比較: HEAD と変更後の `convert_captions()` を 321 ファイルで比較 (連続する空行を正規化)。差分は同じ `sample/README.md` だけ。比較の途中で、PlantUML の図の直後の `Table:` で図のキャプションが失われる不具合を検出して修正し、テストを追加。
- Doxygen: `app/doxygen-sample` で `make doxy` を実行し、doxybook2 の出力で `Table:` が表の前に出ること、前処理と Pandoc で 4 つの表すべてにキャプションが付くことを確認。
- テスト: docsfw `bin_test` 114 件成功 (ブラウザーのテストと下記の 1 件を除く)、livedocs `bin_test` 362 件成功、testfw `bin_test` 125 件成功。
- `text_style_jp.py --test`: `カスタムマッチャ` の 1 件が失敗。変更前の HEAD でも同じく失敗する既存の問題 (残課題 BL-001)。
- `bin_test/test_livedocs_path_spaces.py::test_make_livedocs_with_complete_system_environment`: venv の作成の判定で失敗。表キャプションとは無関係で、HEAD の複製でも失敗。

- `text_style_jp.py --dry-run`: 移行で書き換えた Markdown と C/C++ ファイルのすべてで、移行前の複製と比べて指摘の増加は 0 件。移行前からある指摘が Markdown に合計 154 件残る。この案件で作成・更新した正本文書と検討文書は指摘 0 件。

- pull 後の再確認 (作業 4.12): リポジトリ全体の Markdown と C/C++ の 357 ファイルで、既定の規則の移動対象 0 件、前処理の警告 0 件。作業 4.12 で書き換えた 39 ファイルの `--dry-run` の指摘 (キャプションの規則を除く) は HEAD 版と同じ 9 件で、増加 0 件。キャプションのテスト 44 件、docsfw `bin_test` 115 件が成功。`app/porter` の `make doxy` で、`@parblock` で囲んだ 6 か所のキャプションと表が同じ見出しの中に、キャプション、表の順で出力されることを確認。

### 未完了項目

- 受入条件 7 (変更した Markdown が `--dry-run` で指摘なし) は、移行前からある指摘 154 件のため未達。扱いをユーザーに確認する。
