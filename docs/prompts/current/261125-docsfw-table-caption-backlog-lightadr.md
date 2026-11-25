<!--
生成元: agree-before-implement スキル
文書種別: 簡易 ADR (lightadr)
最終更新日時: 2026-11-26 04:05:00 JST
最終更新エージェント: claude code (主セッション session_01KJc53UFydnbt2gLXTJC1ZC)
稼働 OS: Linux (WSL)
上流文書: `261125-docsfw-table-caption-backlog-overview.md` (全体管理文書)、`261125-docsfw-table-caption-backlog-discussion.md` (検討用 Markdown)。いずれも削除されている場合があります。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。上流文書の全体管理文書が存在する場合は、その再開手順に従って進行位置を確認します。存在しない場合は、この文書を単体の決定事項の記録として扱います。この文書は正式な ADR ではありません。正式な ADR への転記はユーザーが必要時に行うため、エージェントは依頼なしに転記や正式な ADR の作成・更新を行わないでください。最終更新エージェントのセッション情報や稼働 OS・最終更新日時が参照可能であれば再開時のコンテキストや環境差分の把握に利用し、別エージェントや別環境・別 OS からの引き継ぎ、担当変更によりセッションが見つからない場合も異常とせず、文書の記載から継続してください。
-->

# 表のキャプションの前置きの残課題の対策 簡易 ADR

ファイル名: `261125-docsfw-table-caption-backlog-lightadr.md`

この文書は、検討で得られた事実、ユーザーの選択とコメント、およびそれらに基づく決定事項を、決定 1 件ごとにまとめた簡易 ADR (Architecture Decision Record: 設計判断の記録) です。正式な ADR ではなく、対案の比較や決定の影響の評価は記載していません。  
各決定の「決定」は、方針が変わるたびに書き換え、常に最新の決定だけを示します。変更の推移は「経緯」に時系列で記録します。

## 決定事項一覧

| 決定 ID | 題名 | 最終更新日 | 源泉 |
| --- | --- | --- | --- |
| [LADR-001](#ladr-001-対策する残課題の範囲) | 対策する残課題の範囲 | 2026-11-25 | [Q-001](261125-docsfw-table-caption-backlog-discussion.md#q-001-対策する残課題の範囲) |
| [LADR-002](#ladr-002-自己テストのカスタム-マッチャーの変換の失敗の直し方と辞書の整理) | 自己テストの「カスタム マッチャー」の変換の失敗の直し方と辞書の整理 | 2026-11-25 | [Q-002](261125-docsfw-table-caption-backlog-discussion.md#q-002-自己テストカスタム-マッチャーの失敗の直し方)、[Q-003](261125-docsfw-table-caption-backlog-discussion.md#q-003-no_space-と-replace-の両方にある語の扱い) |
| [LADR-003](#ladr-003-test_livedocs_path_spaces-の前提の確認) | test_livedocs_path_spaces の前提の確認 | 2026-11-25 | [Q-004](261125-docsfw-table-caption-backlog-discussion.md#q-004-test_livedocs_path_spaces-の失敗の直し方) |
| [LADR-004](#ladr-004-url-の直後の閉じ括弧の前の空白) | URL の直後の閉じ括弧の前の空白 | 2026-11-25 | [Q-005](261125-docsfw-table-caption-backlog-discussion.md#q-005-url-の直後の閉じ括弧の前の空白の扱い) |
| [LADR-005](#ladr-005-ブロック引用の中の-table-段落) | ブロック引用の中の Table: 段落 | 2026-11-25 | [Q-008](261125-docsfw-table-caption-backlog-discussion.md#q-008-ブロック引用の中の-table-段落の扱い) |
| [LADR-006](#ladr-006-doxygen-コメントで表が深い-table-段落の検出) | Doxygen コメントで表が深い Table: 段落の検出 | 2026-11-25 | [Q-009](261125-docsfw-table-caption-backlog-discussion.md#q-009-doxygen-コメントで字下げが異なる-table-段落の扱い) |
| [LADR-007](#ladr-007-検証の範囲) | 検証の範囲 | 2026-11-25 | [Q-010](261125-docsfw-table-caption-backlog-discussion.md#q-010-検証の範囲-windows-側の検証の要否) |
| [LADR-008](#ladr-008-dry-run-の桁の定義) | dry-run の桁の定義 | 2026-11-25 | [Q-006](261125-docsfw-table-caption-backlog-discussion.md#q-006-dry-run-の桁の定義)、[Q-007](261125-docsfw-table-caption-backlog-discussion.md#q-007-コメントの解析モードでの桁の基準)、[Q-011](261125-docsfw-table-caption-backlog-discussion.md#q-011-桁の写像の変更範囲を踏まえた-q-006-の再確認)、[Q-012](261125-docsfw-table-caption-backlog-discussion.md#q-012-コメントの桁の基準を-cc-以外のモードにも適用するか) |

## LADR-001 対策する残課題の範囲

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

対策元の残課題一覧 `261124-table-caption-before-table-backlog.md` には、優先度が低い 6 件 (BL-001 〜 BL-006) が未着手で残っていました。消化できる残課題を進める依頼に基づき、今回の案件で対策する課題を決める必要がありました。

### 得られた事実

- 6 件とも、手元の環境で再現または事実を確認できました (検討用 Markdown の Q-001 の Context)。
- BL-002 は、Pandoc 発行でキャプションが前の表に付く実害があります。BL-003 は、リポジトリ内の該当がすでに手作業で修正済みです。

### 決定

BL-001 〜 BL-006 の 6 件すべてを、この案件で対策します。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:43 | [Q-001](261125-docsfw-table-caption-backlog-discussion.md#q-001-対策する残課題の範囲) | A 〜 F: BL-001 〜 BL-006 をそれぞれ対策する | なし | 新規に決定 |

## LADR-002 自己テストの「カスタム マッチャー」の変換の失敗の直し方と辞書の整理

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

`text_style_jp.py --test` の「`カスタムマッチャ` → `カスタム マッチャー`」が失敗していました。辞書を直すか自己テストを直すか、また、効果のない辞書の項目をどう扱うかを決める必要がありました。

### 得られた事実

- 失敗の原因は、SudachiPy (sudachidict-core 20261015) が `カスタムマッチャ` を未知語の 1 語として返し、分割後の `replace` (`マッチャ` → `マッチャー`) に届かないことです。
- `.text_style_jp/90_local-katakana.json` の `no_space` の `マッチャ` は、`replace` の `from` にもあるため、エンジンが保護から外しており、効果がありません (`text_style_jp_engine.py` の `load_dictionaries()`)。
- 作業用の複製で、`add_space` へ `カスタム マッチャー` を追加し、`no_space` から `マッチャ` を削除すると、`--test` が全件成功しました。SudachiPy を無効にしても、`カスタムマッチャ` と `カスタム マッチャ` はどちらも `カスタム マッチャー` になりました。
- CI の Linux コンテナーは SudachiPy を事前導入せず、初回実行時に最新版を導入します。2026-11-25 の CI (run 45552671556) では sudachipy 0.7.0、sudachidict-core 20261015 でした。

### 決定

- `90_local-katakana.json` の `add_space` に `カスタム マッチャー` を追加します。自己テストの期待値は変えません。
- `90_local-katakana.json` の `no_space` から `マッチャ` を削除します。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:43 | [Q-002](261125-docsfw-table-caption-backlog-discussion.md#q-002-自己テストカスタム-マッチャーの失敗の直し方) | A: `add_space` に `カスタム マッチャー` を追加し、テストの期待値は変えない | なし | 新規に決定 |
| 2026-11-25 20:43 | [Q-003](261125-docsfw-table-caption-backlog-discussion.md#q-003-no_space-と-replace-の両方にある語の扱い) | A: `no_space` の `マッチャ` を削除する | なし | 決定を補足 (辞書の整理を追加) |

## LADR-003 test_livedocs_path_spaces の前提の確認

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

`test_livedocs_path_spaces.py` の `test_make_livedocs_with_complete_system_environment` は、テストを実行する Python が livedocs の依存の採用範囲を満たすことを前提にしています。前提が成り立たない環境で失敗しており、テストと採用範囲のどちらを直すかを決める必要がありました。

### 得られた事実

- 手元のシステム Python は pymdown-extensions 13.1 と watchdog 7.1.0 で、採用範囲 (`<12.0.0`、`<7.0.0`) の外でした。
- `make bin-test` は `resolve_python_components.py --run-script` で採用範囲を満たす Python を選んでテストを起動します。CI (run 45552671556、ol9) では、docsfw の `bin_test` が livedocs の venv の Python で実行され、72 件が成功しています。
- `app/general/bin_internal/run-bin-tests.py` は、想定外のスキップを失敗として扱います。

### 決定

テストの先頭で、`resolve_python_components.py` の判定と同じ方法で、`sys.executable` が `requirements-compatible.txt` の採用範囲を満たすかを確認し、満たさない場合はテストをスキップします。採用範囲は変更しません。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:43 | [Q-004](261125-docsfw-table-caption-backlog-discussion.md#q-004-test_livedocs_path_spaces-の失敗の直し方) | A: 前提が成り立たない環境ではテストをスキップする | なし | 新規に決定 |

## LADR-004 URL の直後の閉じ括弧の前の空白

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

`app/cplat/prod/include/cplat/net/socket.h` の 268 行と 270 行の `(see: URL )` は、閉じ括弧の前の空白が `space-inside-brackets` に指摘されていました。空白は、Doxygen が閉じ括弧を URL に含めることを避けるために入れたものでした。空白と規則のどちらを直すかを決める必要がありました。

### 得られた事実

- Doxygen 1.17.0 は、空白のない `(see: URL)。` でも、2 つの URL のどちらにも閉じ括弧を含めません (生成した XML の `ulink url` で確認)。CI の Linux コンテナーの Doxygen も 1.17.0 です。Windows の CI は Doxygen 1.18.0 を使います。
- Pandoc 3.11 (`markdown+hard_line_breaks`) と MkDocs の設定は、裸の URL を自動リンクしません。
- リポジトリ内で `(see: URL )` の形は、この 2 か所だけです。
- 変更はコメントの空白だけで、`app/cplat` の公開 API を変えません。

### 決定

`socket.h` の 268 行と 270 行の、URL と閉じ括弧の間の空白を削除します。`space-inside-brackets` の規則と、正本文書は変更しません。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:43 | [Q-005](261125-docsfw-table-caption-backlog-discussion.md#q-005-url-の直後の閉じ括弧の前の空白の扱い) | A: `socket.h` の空白を削除し、規則と文書は変えない | なし | 新規に決定 |

## LADR-005 ブロック引用の中の Table: 段落

決定者: Tetsuo Honda  
最終更新日: 2026-11-26

### 背景と課題

表のキャプションの判定 (`table_caption_position.py`) と MkDocs の変換 (`stage_livedocs.py` の `convert_captions()`) は、行頭が `>` のブロック引用の中の `Table:` 段落を扱っていませんでした。Pandoc では前の表にキャプションが付く場合があり、扱いを決める必要がありました。

### 得られた事実

- ブロック引用の中で、1 つ目の表にキャプションがなく、2 つ目の表の前に `Table:` を書くと、Pandoc はキャプションを 1 つ目の表へ付けます。
- MkDocs は、引用の中の `Table:` を通常の段落として表示します。誤った表への付け替えはありません。
- Python-Markdown の `attr_list` は、引用の中の段落の直後の属性行を読み取ります。`github-callouts` の `> [!NOTE]` の中でも同じです。
- 引用の深さで区間を分けるため、引用の外 (深さ 0) の `Table:` 段落の途中に `>` で始まる行があると、そこで段落が終わります。Pandoc もブロック引用で段落を終えるため、Pandoc の解釈と一致します (実装時の確認)。

### 決定

ブロック引用の中でも、引用の深さが同じ `Table:` 段落と表の組を、引用の外と同じ規則で扱います。Pandoc の前処理、`text_style_jp.py` の `table-caption-position`、MkDocs の `convert_captions()` のすべてを対応させ、Pandoc 発行と MkDocs 発行の結果をそろえます。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:43 | [Q-008](261125-docsfw-table-caption-backlog-discussion.md#q-008-ブロック引用の中の-table-段落の扱い) | A: ブロック引用の中でもキャプションとして扱い、Pandoc と MkDocs の両方を対応する | なし | 新規に決定 |

## LADR-006 Doxygen コメントで表が深い Table: 段落の検出

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

`table_caption_position.py` は、表と `Table:` 段落の字下げが一致する場合だけを判定の対象にしていました。Doxygen コメントでは、`@param` の説明に合わせて表を深く字下げし、`Table:` を浅く書く形があり、後置きを検出できませんでした。

### 得られた事実

- 表が深く、後ろに浅い `Table:` を置いた Doxygen コメントは、`text_style_jp.py --dry-run` で検出されません。
- Doxygen 1.17.0 は、表を `@param` の説明の後ろ、または箇条書きの外の段落として出力し、`Table:` の段落を表の直後に続けます。前置きへ移した形でも、`Table:` の段落の直後に表が続きます。

### 決定

C/C++ のモード (`c`、`cpp`) に限り、表の字下げが `Table:` 段落より深い場合も、表と `Table:` 段落を組として扱います。`Table:` 段落のほうが深い場合は、従来どおり対象外とします。Markdown のモードの判定は変えません。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:43 | [Q-009](261125-docsfw-table-caption-backlog-discussion.md#q-009-doxygen-コメントで字下げが異なる-table-段落の扱い) | A: Doxygen のモードで、表が深い場合も後置きとして検出する | なし | 新規に決定 |

## LADR-007 検証の範囲

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

対象の多くは Python と辞書とコメントですが、Sudachi 辞書の版、空白を含むパス、Doxygen の版など、OS によって結果が変わりうる箇所があります。Windows 側でも検証するかを決める必要がありました。

### 得られた事実

- Windows の CI は Doxygen 1.18.0 を使い、Linux の CI コンテナーは Doxygen 1.17.0 を使います。
- SudachiPy は、CI と手元のどちらでも、初回実行時に最新版が導入されます。

### 決定

Linux で局所テストを実行したあと、主エージェントの仲介で Windows 側の Claude Code セッションへ変更を渡し、同じ局所テストを実行します。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:43 | [Q-010](261125-docsfw-table-caption-backlog-discussion.md#q-010-検証の範囲-windows-側の検証の要否) | A: Linux の局所テストのあと、Windows 側でも同じテストを実行する | なし | 新規に決定 |

## LADR-008 dry-run の桁の定義

決定者: Tetsuo Honda  
最終更新日: 2026-11-25

### 背景と課題

`text_style_jp.py --dry-run` が示す `行:桁` の桁が、実際の変更の位置と一致しない場合がありました。桁の定義と、コメントを解析するモードでの基準を決める必要がありました。

### 得られた事実

- 桁は、各整形ステップが処理した時点の文字列での位置です (`text_style_jp_engine.py` の `_record_step_changes()`)。前のステップによる空白の挿入と削除、URL などのプレースホルダーへの退避、Markdown の行の前処理 (見出し番号の削除など) で、元の行の位置とずれます。例: `## 1. 見出しtext` の挿入が `3:7` (元の行では 10 桁目)、URL を含む行の挿入が `5:28` (元の行では 36 桁目) と報告されます。
- コメントを解析するモード (`c`、`cpp`、`csharp`、`python`、`shell`、`make`、Markdown の言語付きフェンスの中) では、桁がコメント本文の先頭を 1 とする位置です。
- 桁の単位は Python の文字 (コード ポイント) で、全角文字とタブも 1 と数えます。
- `--check` は、整形が必要なファイル名だけを出力し、行と桁を出力しません (`bin/text_style_jp.py` の `main()`)。
- 位置の写像の更新が必要な処理は、エンジンとフロントエンドの診断の経路全体にわたります (エンジンで `_record_step_changes()` 7 か所と `collector.add()` 7 か所、フロントエンドで `_record_step_changes()` 14 か所と `set_line()` 11 か所)。整形の結果は変わりません。

### 決定

- `--dry-run` の桁 (`Finding.column`) は、入力ファイルの行の文字位置 (1 始まり、コード ポイント単位、全角文字とタブも 1) とします。
- 挿入の桁は、元の行で挿入位置の直後にある文字の桁とします。削除と置換の桁は、元の行で対象の範囲の先頭の桁とします。
- コメントを解析するすべてのモード (`c`、`cpp`、`csharp`、`python`、`shell`、`make`) と、Markdown の言語付きフェンスの中のコメントでも、ソースの行 (Markdown のフェンスでは Markdown の行) の文字位置とします。
- 位置の写像は `DiagnosticCollector` に集約し、文字列を変えるすべての処理で、変換の前後の文字列を渡して更新します。整形の結果 (`--in-place` の出力) は変えません。
- 桁の定義を `docs/text_style_jp.md` に記載します。

### 経緯

| 日時 (JST) | 源泉 | ユーザーの選択 | ユーザーのコメント | 決定への反映 |
| --- | --- | --- | --- | --- |
| 2026-11-25 20:43 | [Q-006](261125-docsfw-table-caption-backlog-discussion.md#q-006-dry-run-の桁の定義) | A: 桁を元の行の文字位置に一致させ、定義を文書に記載する | なし | 新規に決定 (変更範囲の説明の訂正のため Q-011 で再確認) |
| 2026-11-25 20:43 | [Q-007](261125-docsfw-table-caption-backlog-discussion.md#q-007-コメントの解析モードでの桁の基準) | A: ソースの行の文字位置へ揃える (対象は `c`、`cpp`) | なし | 決定を補足 (コメントのモードの基準) |
| 2026-11-25 21:03 | [Q-011](261125-docsfw-table-caption-backlog-discussion.md#q-011-桁の写像の変更範囲を踏まえた-q-006-の再確認) | A: Q-006 の案 A を維持し、すべての処理で位置の写像を更新する | なし | 決定を確定 (写像を診断の経路全体で更新) |
| 2026-11-25 21:03 | [Q-012](261125-docsfw-table-caption-backlog-discussion.md#q-012-コメントの桁の基準を-cc-以外のモードにも適用するか) | A: コメントを解析するすべてのモードで、ソースの行の文字位置へ揃える | なし | 決定を変更 (対象を `c`、`cpp` からすべてのコメント解析モードへ拡大) |
