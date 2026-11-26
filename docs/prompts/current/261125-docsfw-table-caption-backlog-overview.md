<!--
生成元: agree-before-implement スキル
文書種別: 全体管理文書 (overview)
最終更新日時: 2026-11-26 23:34:09 JST
最終更新エージェント: agy (gemini-4-hydrogen-medium、主セッション session_01KJc53RTnwmpzd7VMLf1qR9)
稼働 OS: Linux (WSL)
上流文書: `261124-table-caption-before-table-backlog.md` (残課題一覧。BL-001 〜 BL-006 を対策する継続作業)
下流文書: `261125-docsfw-table-caption-backlog-discussion.md` (検討用 Markdown)、`261125-docsfw-table-caption-backlog-lightadr.md` (簡易 ADR)、`261125-docsfw-table-caption-backlog-design.md` (最終仕様)、`261125-docsfw-table-caption-backlog-backlog.md` (残課題一覧)。未作成の場合や、削除されている場合があります。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。この文書と、ユーザーが編集した最新の検討用 Markdown を読み直し、作業 WBS の `← **CURRENT**` の項目から再開します。最終更新エージェントのセッション情報や稼働 OS・最終更新日時が参照可能であれば再開時のコンテキストや環境差分の把握に利用し、別エージェントや別環境・別 OS からの引き継ぎ、担当変更によりセッションが見つからない場合も異常とせず、文書の記載から継続してください。`← **CURRENT**` の項目は処理が中止された項目である場合があり、どこまで進んでいたかは文書だけでは分かりません。対象成果物の内容を確認して実施済みの範囲を特定してから、作業を再開してください。`← **CURRENT**` がなく、作業 WBS がすべて完了 (✅) であれば、この案件の合意フローは完了しています。
-->

# 表のキャプションの前置きの残課題の対策 全体管理

この文書は、案件の識別、作業 WBS、対象範囲、確認状況、経緯を管理します。質問と回答の本文は検討用 Markdown に、決定事項は簡易 ADR に記載し、この文書には重複して記載しません。

## 案件の識別

検討 ID: 261125-docsfw-table-caption-backlog

検討用 Markdown の版: 3

状態: 完了 (第 3 ゲートの承認を受領)

## 作業 WBS と進捗管理

凡例: ⏸️ 未着手、🔄 実施中、🚫 ブロック中、⚠️ 要注意、✅ 完了。現在取り組んでいる項目の末尾に `← **CURRENT**` を付けます。

作業 4 の各項目は、[Q-001](261125-docsfw-table-caption-backlog-discussion.md#q-001-対策する残課題の範囲) で対策の対象に選ばれた課題だけを実施します。

- ✅ 1. 検討用 Markdown のための情報収集と質問の実施
    - ✅ 1.1. 前提条件と要求事項の調査 (対策元 `261124-table-caption-before-table-backlog.md` の BL-001 〜 BL-006 を「検討中」へ更新、`text_style_jp.py --test` と Sudachi の分割結果、`resolve_python_components.py` の判定、Doxygen 1.17.0 と Pandoc 3.11 での URL の閉じ括弧、ブロック引用と Doxygen の字下げの再現、dry-run の桁の再現)
    - ✅ 1.2. 課題・論点の抽出と確認項目 ([Q-001](261125-docsfw-table-caption-backlog-discussion.md#q-001-対策する残課題の範囲) 〜 [Q-010](261125-docsfw-table-caption-backlog-discussion.md#q-010-検証の範囲-windows-側の検証の要否)) の作成
    - ✅ 1.3. Q&A ターンごとのユーザー回答の受付と記録 (JST 日時、Git ユーザー名または発言者)
    - ✅ 1.4. 回答に基づく前提・制約の検証、簡易 ADR (`261125-docsfw-table-caption-backlog-lightadr.md`) への決定事項の反映、WBS の見直し (対策元 `261124-table-caption-before-table-backlog.md` へ合意方針や見送り決定を随時反映)
    - ✅ 1.5. 追加の確認項目 ([Q-011](261125-docsfw-table-caption-backlog-discussion.md#q-011-桁の写像の変更範囲を踏まえた-q-006-の再確認)、[Q-012](261125-docsfw-table-caption-backlog-discussion.md#q-012-コメントの桁の基準を-cc-以外のモードにも適用するか)) の作成とユーザー回答の受付 (BL-006 の変更範囲の説明の訂正と、C/C++ 以外のコメントのモードの扱い。2026-11-25 21:03:13 JST に回答)
    - ✅ 1.6. 追加の回答の検証と、BL-006 の決定の簡易 ADR への反映 (LADR-008。対策元 backlog の BL-006 へ反映)
- ✅ 2. 前提合意と残懸念の解消 (第 1 ゲート: 最終仕様作成への着手)
    - ✅ 2.1. 全論点に対する未解決事項および質問の解消確認
    - ✅ 2.2. 方針・前提条件の合意確定 (検討用 Markdown 版 3、LADR-001 〜 LADR-008)
- ✅ 3. 最終決定事項 (最終仕様) の作成と承認の受付
    - ✅ 3.1. `261125-docsfw-table-caption-backlog-design.md` の作成 (対策元 backlog の確定方針・状態を随時反映)
    - ✅ 3.2. 最終仕様における受入条件と整合性の確認 (LADR-001 〜 LADR-008 との一致、Q-012 の Context の桁の誤記の訂正を反映)
    - ✅ 3.3. 対話セッションにおける最終仕様の承認の受付 (第 2 ゲート: 作業着手の合意。2026-11-25 21:48 頃の対話でのユーザーの指示により承認)
- ✅ 4. 承認された最終仕様に従った作業の実施
    - ✅ 4.1. BL-001: `framework/docsfw/.text_style_jp/90_local-katakana.json` の `add_space` への `カスタム マッチャー` の追加と、`no_space` の `マッチャ` の削除
    - ✅ 4.2. BL-002: `framework/docsfw/bin_internal/table_caption_position.py`、`framework/docsfw/bin_internal/table-caption-preprocess.py`、`framework/docsfw/livedocs/bin/stage_livedocs.py` の `convert_captions()` の引用の深さの扱い、テスト (`bin_test/test_table_caption_position.py`、`bin_test/test_table_caption_line.py`、`livedocs/bin_test/test_stage_livedocs.py`)
    - ✅ 4.3. BL-003: `framework/docsfw/bin_internal/table_caption_position.py` の `_same_indent()` と `relocate_table_captions()` の Doxygen モードの字下げの判定、テスト (`bin_test/test_table_caption_position.py`)
    - ✅ 4.4. BL-004: `framework/docsfw/bin_test/test_livedocs_path_spaces.py` の前提確認 (採用範囲を満たさない Python ではスキップ)
    - ✅ 4.5. BL-005: `app/cplat/prod/include/cplat/net/socket.h` の 268 行と 270 行のコメントの空白の削除
    - ✅ 4.6. BL-006: `framework/docsfw/bin_internal/text_style_jp_engine.py` と `framework/docsfw/bin_internal/text_style_jp_frontends.py` の桁の写像 (すべてのコメント解析モードを含む)、`framework/docsfw/bin/text_style_jp.py` の自己テスト、`framework/docsfw/docs/text_style_jp.md` の桁の定義
    - ✅ 4.7. 正本文書およびコード コメントへの永続的知見の反映 (`framework/docsfw/docs/table-caption.md`、`framework/docsfw/docs/text_style_jp.md`、各 docstring とテストのコメント。`python-components.md` は変更なし)
    - ✅ 4.8. 局所テストおよび機械的検証 (一時ディレクトリの livedocs の venv で `text_style_jp.py --test`、`framework/docsfw/bin_test`、`framework/docsfw/livedocs/bin_test`、Doxygen での URL、整形結果の不変の比較、変更した Markdown への `text_style_jp.py --dry-run`)
    - ✅ 4.9. Windows 側の Claude Code セッションでの検証 (主エージェントがパッチを仲介。Sudachi 辞書の版と Doxygen 1.18.0 での URL の確認を含む) (依頼 5 で、docsfw d0fd02c と cplat f760bff8 での `text_style_jp.py --test`、docsfw と livedocs の `bin_test`、Doxygen 1.17.0 での URL がすべて成功。依頼 6 で Doxygen 1.18.0 (8e760943) の `ulink url` 6 件にも閉じ括弧なし)
    - ✅ 4.10. 受入条件への適合確認 (全作業の完了確認) (最終仕様の「受入条件のまとめ」の 5 項目に適合。変更したファイルは「変更対象のファイル」の範囲内で、`table-caption-preprocess.py` は変更不要)
    - ✅ 4.11. 簡易 ADR (`261125-docsfw-table-caption-backlog-lightadr.md`) の最終確認 (各決定が実装後の状態と一致することを確認。LADR-005 に、引用の外の段落の終わり方が Pandoc と一致する事実を追記)
    - ✅ 4.12. 残課題一覧 (`261125-docsfw-table-caption-backlog-backlog.md`) の再構築と整理、および対策元 `261124-table-caption-before-table-backlog.md` の最終状態・転記先の確定 (この案件の残課題は BL-001、BL-002 の 2 件で整理済み。対策元の BL-001 〜 BL-006 はすべて対応済みで、転記なし)
- ✅ 5. 成果物の承認の受付 (第 3 ゲート)
    - ✅ 5.1. 成果物・検証結果・残課題の提示
    - ✅ 5.2. 対話セッションにおける成果物の承認の受付 (2026-11-26 23:34 JST の対話で、ユーザーが「第3ゲート待ちの全案件を承認します。」と発言し承認)

## 対象と参照資料

対象成果物: docsfw の `text_style_jp.py` とその辞書・エンジン、表のキャプションの判定 (`table_caption_position.py`、`stage_livedocs.py`)、livedocs の依存の判定のテスト、`app/cplat` のコメント 2 か所。範囲は [Q-001](261125-docsfw-table-caption-backlog-discussion.md#q-001-対策する残課題の範囲) で確定します。

今回の対象範囲: 対策元 `261124-table-caption-before-table-backlog.md` の BL-001 〜 BL-006 のうち、Q-001 で選ばれた課題。

依頼の源泉: ユーザーの指示 (2026-11-25 対話) 「消化可能なバックログを消化していきたい、各 prompt/current で対応可能な backlog を agree-before-implement スキルで推進します。サブエージェントには Sonnet を使用してください。また、Windows 側に Claude Code が待機しているので、疎通を取って連携して進めてください。」

書き込み可能な検討文書: この文書、`261125-docsfw-table-caption-backlog-discussion.md`、`261125-docsfw-table-caption-backlog-lightadr.md`、`261125-docsfw-table-caption-backlog-backlog.md`、対策元 `261124-table-caption-before-table-backlog.md` (状態・経緯・メタ情報のみ)

参照資料と版:

- `framework/docsfw` (HEAD 9d37dce0 時点)
- 対策元 `261124-table-caption-before-table-backlog.md` (BL-001 〜 BL-006、すべて未着手から検討中へ)
- CI の Linux コンテナーの定義: `/home/user/oracle-linux-container` の `src/Dockerfile` (HEAD f6d9a27 時点。Doxygen 1.17.0、Pandoc 3.11、SudachiPy は未導入で初回実行時に最新版を導入)。Windows の CI は `.github/workflows/ci.yml` の `DOXYGEN_VERSION` (1.18.0)
- CI のログ: run 45552671556 (2026-11-25、成功) の `linux-ol9-bin-test-logs` (sudachipy 0.7.0、sudachidict-core 20261015)
- 手元の環境: Linux (WSL)、Python 3.12.15、pandoc 3.11、Doxygen 1.17.0、sudachidict-core 20261015、SudachiPy 0.7.0、mkdocs 1.6.1、mkdocs-material 9.7.7、pymdown-extensions 13.1、watchdog 7.1.0

## 観点別の確認

| 観点 | 状態 | 根拠・関連 Q |
| --- | --- | --- |
| 目的・利用者 | 確認済み | [Q-001](261125-docsfw-table-caption-backlog-discussion.md#q-001-対策する残課題の範囲)。残課題の消化が目的 (2026-11-25 の対話でのユーザーの指示) |
| 範囲・境界 | 確認済み | BL-001 〜 BL-005 は確認済み ([Q-001](261125-docsfw-table-caption-backlog-discussion.md#q-001-対策する残課題の範囲)、[Q-003](261125-docsfw-table-caption-backlog-discussion.md#q-003-no_space-と-replace-の両方にある語の扱い))。BL-006 の変更範囲とコメントのモードの対象も確認済み ([Q-011](261125-docsfw-table-caption-backlog-discussion.md#q-011-桁の写像の変更範囲を踏まえた-q-006-の再確認)、[Q-012](261125-docsfw-table-caption-backlog-discussion.md#q-012-コメントの桁の基準を-cc-以外のモードにも適用するか))。範囲外の気付き 2 件は残課題一覧 `261125-docsfw-table-caption-backlog-backlog.md` へ記録 |
| 入力・根拠 | 確認済み | 各課題を手元で再現または検証。Doxygen と Pandoc の URL の扱いは [Q-005](261125-docsfw-table-caption-backlog-discussion.md#q-005-url-の直後の閉じ括弧の前の空白の扱い) の Context と Assessment。CI コンテナーの版 (Doxygen 1.17.0、SudachiPy は初回実行時に最新版を導入) は `/home/user/oracle-linux-container` の `src/Dockerfile` と CI の run 45552671556 のログで確認 |
| 整合性・依存関係 | 確認済み | [Q-008](261125-docsfw-table-caption-backlog-discussion.md#q-008-ブロック引用の中の-table-段落の扱い) (Pandoc と MkDocs の対称性) と [Q-009](261125-docsfw-table-caption-backlog-discussion.md#q-009-doxygen-コメントで字下げが異なる-table-段落の扱い) は確認済み。`app/cplat/AGENTS.md` の同期規則は、コメントだけの変更のため対象外。BL-006 は [Q-011](261125-docsfw-table-caption-backlog-discussion.md#q-011-桁の写像の変更範囲を踏まえた-q-006-の再確認) で前提を訂正したうえで合意 |
| 実現性・例外 | 確認済み | [Q-002](261125-docsfw-table-caption-backlog-discussion.md#q-002-自己テストカスタム-マッチャーの失敗の直し方) (Sudachi 辞書の版に依存しないことを確認)、[Q-004](261125-docsfw-table-caption-backlog-discussion.md#q-004-test_livedocs_path_spaces-の失敗の直し方) (`make bin-test` の経路ではスキップしないことを確認) は確認済み。[Q-006](261125-docsfw-table-caption-backlog-discussion.md#q-006-dry-run-の桁の定義) は [Q-011](261125-docsfw-table-caption-backlog-discussion.md#q-011-桁の写像の変更範囲を踏まえた-q-006-の再確認) で再確認し確定 |
| 受入条件・検証 | 確認済み | 検証の範囲は [Q-010](261125-docsfw-table-caption-backlog-discussion.md#q-010-検証の範囲-windows-側の検証の要否)。受入条件と検証手順は最終仕様に記載。手元の livedocs の venv は `make livedocs-venv` (`--ensure`) で固定版を補える (セッションの一時ディレクトリの venv で確認) |

## 質問一覧

| Q-ID | 論点 | 状態 | 依存・関連 | 反映先の決定 |
| --- | --- | --- | --- | --- |
| [Q-001](261125-docsfw-table-caption-backlog-discussion.md#q-001-対策する残課題の範囲) | 対策する残課題の範囲 | 解決済み | なし | LADR-001 |
| [Q-002](261125-docsfw-table-caption-backlog-discussion.md#q-002-自己テストカスタム-マッチャーの失敗の直し方) | 自己テスト「カスタム マッチャー」の失敗の直し方 | 解決済み | Q-001 (BL-001) | LADR-002 |
| [Q-003](261125-docsfw-table-caption-backlog-discussion.md#q-003-no_space-と-replace-の両方にある語の扱い) | no_space と replace の両方にある語の扱い | 解決済み | Q-001、Q-002 | LADR-002 |
| [Q-004](261125-docsfw-table-caption-backlog-discussion.md#q-004-test_livedocs_path_spaces-の失敗の直し方) | test_livedocs_path_spaces の失敗の直し方 | 解決済み | Q-001 (BL-004)、Q-010 | LADR-003 |
| [Q-005](261125-docsfw-table-caption-backlog-discussion.md#q-005-url-の直後の閉じ括弧の前の空白の扱い) | URL の直後の閉じ括弧の前の空白の扱い | 解決済み | Q-001 (BL-005) | LADR-004 |
| [Q-006](261125-docsfw-table-caption-backlog-discussion.md#q-006-dry-run-の桁の定義) | dry-run の桁の定義 | 解決済み | Q-001 (BL-006) | LADR-008 |
| [Q-007](261125-docsfw-table-caption-backlog-discussion.md#q-007-コメントの解析モードでの桁の基準) | コメントの解析モードでの桁の基準 | 解決済み | Q-006 | LADR-008 |
| [Q-008](261125-docsfw-table-caption-backlog-discussion.md#q-008-ブロック引用の中の-table-段落の扱い) | ブロック引用の中の Table: 段落の扱い | 解決済み | Q-001 (BL-002)、Q-009 | LADR-005 |
| [Q-009](261125-docsfw-table-caption-backlog-discussion.md#q-009-doxygen-コメントで字下げが異なる-table-段落の扱い) | Doxygen コメントで字下げが異なる Table: 段落の扱い | 解決済み | Q-001 (BL-003)、Q-008 | LADR-006 |
| [Q-010](261125-docsfw-table-caption-backlog-discussion.md#q-010-検証の範囲-windows-側の検証の要否) | 検証の範囲 (Windows 側の検証の要否) | 解決済み | Q-002、Q-004 | LADR-007 |
| [Q-011](261125-docsfw-table-caption-backlog-discussion.md#q-011-桁の写像の変更範囲を踏まえた-q-006-の再確認) | 桁の写像の変更範囲を踏まえた Q-006 の再確認 | 解決済み | Q-006、Q-007 | LADR-008 |
| [Q-012](261125-docsfw-table-caption-backlog-discussion.md#q-012-コメントの桁の基準を-cc-以外のモードにも適用するか) | コメントの桁の基準を C/C++ 以外のモードにも適用するか | 解決済み | Q-007、Q-011 | LADR-008 |

## 対象成果物と合意版

最終決定事項 (最終仕様) の設計書: `261125-docsfw-table-caption-backlog-design.md`

検討用 Markdown の合意版 (第 1 ゲート): 版 3 (2026-11-25 21:03:13 JST 保存の回答まで)

最終仕様 (design.md) の合意版 (第 2 ゲート): 2026-11-25 21:48 頃の対話でのユーザーの指示により承認 (最終更新 2026-11-25 21:10:08 JST の版)

更新予定の成果物: `framework/docsfw/.text_style_jp/90_local-katakana.json`、`framework/docsfw/bin_internal/table_caption_position.py`、`framework/docsfw/livedocs/bin/stage_livedocs.py`、`framework/docsfw/bin_test/test_livedocs_path_spaces.py`、`app/cplat/prod/include/cplat/net/socket.h`、各テストと正本文書、`framework/docsfw/bin_internal/text_style_jp_engine.py`、`framework/docsfw/bin_internal/text_style_jp_frontends.py`。詳細は最終仕様

受入条件: 最終仕様 `261125-docsfw-table-caption-backlog-design.md` の各課題の受入条件と「受入条件のまとめ」

## 経緯

| 日時 (JST) | 出来事 | 内容・参照先 |
| --- | --- | --- |
| 2026-11-25 20:39 | 案件の開始 | 対策元 `261124-table-caption-before-table-backlog.md` の BL-001 〜 BL-006 を「検討中」へ更新。全体管理文書と検討用 Markdown (版 1、Q-001 〜 Q-010) を作成 (当初の記録の 20:52 は、ファイルの保存時刻 20:39 と合わないため訂正) |
| 2026-11-25 20:43 | ユーザーの回答 | 検討用 Markdown 版 1 の Q-001 〜 Q-010 に回答 (いずれも推奨案。Q-001 は BL-001 〜 BL-006 の全件) |
| 2026-11-25 20:47 | 担当の交代 | 回答の検証から最終仕様の作成までを opus サブエージェントへ交代 (ユーザーの指示) |
| 2026-11-25 21:01 | 回答の検証と追加質問 | Q-001 〜 Q-005、Q-008 〜 Q-010 を解決済みにし、簡易 ADR (LADR-001 〜 LADR-007) を作成。Q-006 の Context の変更範囲の説明が不正確だったため Q-006、Q-007 を未解決とし、[Q-011](261125-docsfw-table-caption-backlog-discussion.md#q-011-桁の写像の変更範囲を踏まえた-q-006-の再確認) と [Q-012](261125-docsfw-table-caption-backlog-discussion.md#q-012-コメントの桁の基準を-cc-以外のモードにも適用するか) を追加 (版 2)。範囲外の気付き 2 件を残課題一覧 `261125-docsfw-table-caption-backlog-backlog.md` へ記録 |
| 2026-11-25 21:03 | ユーザーの回答 | 検討用 Markdown 版 2 の [Q-011](261125-docsfw-table-caption-backlog-discussion.md#q-011-桁の写像の変更範囲を踏まえた-q-006-の再確認) と [Q-012](261125-docsfw-table-caption-backlog-discussion.md#q-012-コメントの桁の基準を-cc-以外のモードにも適用するか) に回答 (いずれも A) |
| 2026-11-25 21:06 | 第 1 ゲートの通過 | Q-006、Q-007、Q-011、Q-012 を解決済みにし、簡易 ADR に LADR-008 を追加 (版 3)。全観点を確認済みとし、最終仕様 `261125-docsfw-table-caption-backlog-design.md` の作成に着手 |
| 2026-11-25 21:10 | 最終仕様の作成 | `261125-docsfw-table-caption-backlog-design.md` を作成し、対策元 backlog の BL-001 〜 BL-006 を「対応中」へ更新。第 2 ゲート (最終仕様の承認) を待つ |
| 2026-11-25 21:48 | 第 2 ゲートの通過 | ユーザーの指示 (2026-11-25 21:48 頃の対話。「全体の進め方を先に指示する。…ユーザーの確認なく継続的に自走すること。…決定した最終仕様が実現できない場合は、ユーザーに問い合わせることなく backlog に送る。各サブモジュール (案件) 完了時に main にプッシュし CI を起動させ、エラーや警告があれば都度対処する。…」および「6. は他の案件同様 main へのコミットを事前許可する。」) により、承認待ちだった最終仕様を承認されたものとして扱う |
| 2026-11-26 01:18 | 作業の実施の開始 | sonnet サブエージェントが WBS 4.1 から着手 |
| 2026-11-26 01:28 | BL-001 〜 BL-005 の実施 | WBS 4.1 〜 4.5 を完了。対策元 backlog の BL-001 〜 BL-005 を「対応済み」へ更新。4.6 (BL-006) 以降は次の担当へ引き継ぐ |
| 2026-11-26 01:29 | 担当の交代 | opus サブエージェントが WBS 4.6 から着手 |
| 2026-11-26 01:44 | BL-006 の実施 | WBS 4.6 を完了。対策元 backlog の BL-006 を「対応済み」へ更新 |
| 2026-11-26 01:47 | 正本文書への反映 | WBS 4.7 を完了 (`table-caption.md`、`text_style_jp.md`)。簡易 ADR の LADR-002 の見出しを、辞書の変更後の `text_style_jp.py --dry-run` の指摘がない表記に変更 (決定の内容は変更なし) |
| 2026-11-26 01:54 | 局所テストと機械的検証 | WBS 4.8 を完了 (結果は「反映と検証の記録」)。Windows 側の検証 (WBS 4.9) を主エージェントへ依頼 |
| 2026-11-26 03:50 | Windows 側の検証の結果の受領 | 依頼 5: `text_style_jp.py --test` 成功 (dry-run の桁 14 件、元の行の対応 6 件が ✓。SudachiPy 0.6.11、SudachiDict-core 20260723)、docsfw の `bin_test` 144 件成功 (スキップ 1 件、Linux 専用)、livedocs の `bin_test` 371 件成功、Doxygen 1.17.0 の `ulink url` 6 件に閉じ括弧なし。手元の Windows の Doxygen が 1.17.0 だったため、1.18.0 での確認を依頼 6 として追加 |
| 2026-11-26 04:08 | 作業の完了 | WBS 4.9 〜 4.12 を完了 (依頼 6 で Doxygen 1.18.0 の URL を確認、受入条件に適合、簡易 ADR の最終確認、残課題一覧の整理)。第 3 ゲートの成果物の提示へ |
| 2026-11-26 23:34 | 第 3 ゲートの通過 | 2026-11-26 23:34 JST の対話で、ユーザーが「第3ゲート待ちの全案件を承認します。」と発言し承認。作業 WBS 5.1、5.2、5 を完了 |

## 反映と検証の記録

作業 4.1 〜 4.5 の対応箇所と検証結果 (2026-11-26、Linux (WSL)。検証用の Python は一時ディレクトリの livedocs の venv で、pymdown-extensions 11.0.2、watchdog 6.0.0):

| 課題 | 対応箇所 | 検証結果 |
| --- | --- | --- |
| BL-001 | `framework/docsfw/.text_style_jp/90_local-katakana.json` (`add_space` へ `カスタム マッチャー` を追加、`no_space` の `マッチャ` を削除) | `text_style_jp.py --test` が全件成功。`カスタムマッチャ`、`カスタムマッチャー`、`カスタム マッチャ` がいずれも `カスタム マッチャー`、`マッチャ` が `マッチャー`、`引数マッチャ` が `引数マッチャー` |
| BL-002 | `bin_internal/table_caption_position.py` (引用の深さを加えた分類と区間、`_same_depth()`、接頭辞を保ったエスケープ)、`livedocs/bin/stage_livedocs.py` (`_split_blockquote_prefix()`、`convert_captions()`、`_is_followed_by_table()`)。`table-caption-preprocess.py` は変更なし。テストは `bin_test/test_table_caption_position.py`、`bin_test/test_table_caption_line.py`、`bin_test/test_text_style_jp_table_caption.py`、`livedocs/bin_test/test_stage_livedocs.py` | 各テスト ファイルが成功 (Pandoc 前処理なしでは前の表にキャプションが付くことを確認し、前処理ありで次の表だけに付くことをテスト)。Python-Markdown (`tables`、`attr_list`、`github-callouts`) で引用とアラートの中のキャプションに `docsfw-table-caption` クラスが付き、次の要素が表であることを確認 |
| BL-003 | `bin_internal/table_caption_position.py` (`_caption_fits_table()`) | `test_table_caption_position.py` と `test_text_style_jp_table_caption.py` が成功 (Markdown のモードの字下げの判定は変更なし) |
| BL-004 | `bin_test/test_livedocs_path_spaces.py` (採用範囲を満たさない Python ではスキップ) | 採用範囲を満たす Python では 2 件とも実行されて成功。`/usr/bin/python3` ではスキップ (理由に pymdown-extensions、watchdog を表示) |
| BL-005 | `app/cplat/prod/include/cplat/net/socket.h` の 2 か所 (`app/cplat` はサブモジュール) | `text_style_jp.py --dry-run` の指摘なし。Doxygen 1.17.0 の XML の 2 つの `ulink url` に閉じ括弧が含まれない |

作業 4.6 〜 4.8 の対応箇所と検証結果 (2026-11-26、Linux (WSL)。Python は同じ一時ディレクトリの venv):

| 項目 | 対応箇所 | 検証結果 |
| --- | --- | --- |
| BL-006 | `bin_internal/text_style_jp_engine.py` (`_PositionMap`、`DiagnosticCollector` の `set_line()`、`set_line_source()`、`resume_line()`、`track()`、`snapshot()`、`focus()`、`unfocus()`、`use_map()`、`isolate_lines()`、`restore_lines()`、`add()`。`_record_step_changes()`、`_replace_skip_existing()`、`_apply_add_space_pairs()`、`style_text()` の写像の更新)、`bin_internal/text_style_jp_frontends.py` (コメントの各書式関数への本文の開始位置と退避前のコメントの受け渡し、`_style_doxygen_line()` と `_style_xml_doc_text()` の部分文字列の写像、Markdown のフェンスの中の行の写像の退避、`_normalize_list_indent()` の `resume_line()`)、`bin/text_style_jp.py` (桁の自己テスト 14 件と、元の行との対応の自己テスト 6 件) | 最終仕様の表の期待値がすべて一致。変更前の実装では、新しい自己テストのうち桁の 11 件 (変更前から一致していた `dict-replace` と `list-indent` の 3 件を除く) と対応の 6 件が失敗することを確認。既存の自己テストは期待値を変えずに成功 |
| 整形の結果の不変 | 変更前の作業ツリー (WBS 4.5 の完了時点) の `bin`、`bin_internal`、`.text_style_jp` を一時ディレクトリへ複製した版と、変更後の版 | `framework/docsfw/docs/*.md`、`app/cplat/prod/include/cplat/**/*.h`、各 app の Markdown・C/C++・C#・Python・シェル・make の 442 件と、それらの和文と英数字の間の空白を除くなどして整形が必要な状態にした 441 件の、`main([..., "-o", ...])` の出力が `diff -r` で一致 |
| 桁と元の行の対応 | 上記の整形が必要な状態の 441 件の `--dry-run` 相当の Finding (32,891 件) | 変更前は 897 件が元の行の位置と対応しない。変更後は 1 件だけで、`dict-no-space-join` が結合した文字列に対する `dict-replace` (前の処理が変えた文字への変更。桁は範囲の先頭を指す) |
| 正本文書 | `docs/table-caption.md` (扱う条件にブロック引用の深さ、扱わない場合、MkDocs 発行の引用の記号)、`docs/text_style_jp.md` (表のキャプションの位置のブロック引用と Doxygen の深い表、dry-run の出力例と桁の定義) | `--dry-run` の指摘なし |
| 局所テスト | `text_style_jp.py --test`、`framework/docsfw/bin_test` (144 件)、`framework/docsfw/livedocs/bin_test` (371 件) | すべて成功 |
| BL-004 | `/usr/bin/python3` での `test_make_livedocs_with_complete_system_environment` | スキップ (理由に pymdown-extensions、watchdog)。最終仕様の `-m unittest -v test_livedocs_path_spaces.…` の形は、`PYTHONSAFEPATH=1` では作業ディレクトリのモジュールを読み込めず ImportError になるため、`-m unittest discover -p 'test_livedocs_path_spaces.py' -k test_make_livedocs_with_complete_system_environment` で実行 |
| BL-005 | `socket.h` の `--dry-run` と Doxygen 1.17.0 の XML | 指摘なし。`ulink url` の 6 件はいずれも閉じ括弧を含まない |
| 案件の文書 | `--dry-run` | 最終仕様 (23 行、55 行) と検討用 Markdown の Q-002 の見出し (74 行) の括弧で囲んだ表記を、ユーザーの指示 (2026-11-26 の対話「文脈が変化しないのであれば置換してしまってよい」) により「カスタム マッチャー」へ置き換え、指摘なし。変換前の入力を示すコード表記の `カスタムマッチャ` は、意味が変わるため変えない |

Windows 側の検証 (WBS 4.9) は未実施です。
