<!--
生成元: agree-before-implement スキル
文書種別: 残課題一覧 (backlog)
最終更新日時: 2026-11-26 01:53:59 JST
最終更新エージェント: claude code (opus サブエージェント、主セッション session_01KJc53UFydnbt2gLXTJC1ZC)
稼働 OS: Linux (WSL)
上流文書: `261124-table-caption-before-table-overview.md` (全体管理文書)、`261124-table-caption-before-table-design.md` (最終仕様)、`261124-table-caption-before-table-discussion.md` (検討用 Markdown)、`261124-table-caption-before-table-lightadr.md` (簡易 ADR)。いずれも削除されている場合があります。
下流文書: この残課題一覧を対策する継続作業が開始された場合は、その全体管理文書・検討用 Markdown・最終仕様・残課題一覧のパスを追記します。
継続作業 `261125-docsfw-table-caption-backlog` (BL-001 〜 BL-006): `261125-docsfw-table-caption-backlog-overview.md` (全体管理文書)、`261125-docsfw-table-caption-backlog-discussion.md` (検討用 Markdown)、`261125-docsfw-table-caption-backlog-lightadr.md` (簡易 ADR)、`261125-docsfw-table-caption-backlog-backlog.md` (残課題一覧)、`261125-docsfw-table-caption-backlog-design.md` (最終仕様)。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。「整理状態」が「随時追記中」であれば、案件の作業中です。このファイルの残課題を対策する場合は、新しい全体管理文書と検討用 Markdown から開始し、このファイルの記載を削除せずに状態と経緯を更新してください。
-->

# 表のキャプションの前置き 残課題一覧

## 案件の識別

案件名: `261124-table-caption-before-table`  
作成日: `2026-11-24`  
整理状態: 整理済み

この文書は、今回の作業で判明したものの対策しなかった残課題を記録したものです。各項目はチケット管理システムへの起票にそのまま利用できる詳細度で記載しています。

## 残課題一覧

| 課題 ID | 題名 | 区分 | 優先度 / 影響度 | 状態 |
| --- | --- | --- | --- | --- |
| BL-001 | text_style_jp.py の自己テスト「カスタム マッチャー」の失敗 | 作業中摘出 | 低 | 対応済み |
| BL-002 | ブロック引用の中の Table: 段落の判定 | 作業中摘出 | 低 | 対応済み |
| BL-003 | Doxygen コメントで字下げが表と異なる Table: 段落の検出 | 作業中摘出 | 低 | 対応済み |
| BL-004 | test_livedocs_path_spaces の venv 判定のテストの失敗 | 作業中摘出 | 低 | 対応済み |
| BL-005 | space-inside-brackets が URL の直後の閉じ括弧の前の空白を指摘する | 作業中摘出 | 低 | 対応済み |
| BL-006 | --dry-run の指摘の桁が実際の変更位置と一致しない場合がある | 作業中摘出 | 低 | 対応済み |

## BL-001 text_style_jp.py の自己テスト「カスタム マッチャー」の失敗

### 概要と問題点

- **現状の事象**: `python3 framework/docsfw/bin/text_style_jp.py --test` のうち、Markdown の入力 `カスタムマッチャ` の 1 件が失敗します。期待値は `カスタム マッチャー` ですが、結果は入力のままです。
- **本来あるべき姿**: 自己テストがすべて成功するか、辞書の方針に合わせて期待値が更新されていること。

### 経緯と見送り理由

- **摘出契機**: 表のキャプションの前置きの実装中に `--test` を実行して発見しました。変更前の HEAD (`framework/docsfw` v20261118.0.0) を作業用ディレクトリに取り出して実行しても、同じ 1 件が失敗します。
- **今回の見送り理由**: 今回の変更とは無関係の既存の問題で、辞書 (`replace` / `add_space` と SudachiPy によるカタカナ分割) の判断を含むため、範囲外としました。
- **継続作業での経緯と対処**: 継続作業 `261125-docsfw-table-caption-backlog` (全体管理文書 `261125-docsfw-table-caption-backlog-overview.md`) で検討中 (2026-11-25 開始)。原因は辞書の設定の干渉ではなく、SudachiPy (sudachidict-core 20261015) が `カスタムマッチャ` を未知語の 1 語として分割しないため、分割後の `replace` に届かないこと。`no_space` の `マッチャ` はエンジンが保護から外すため効果がありません。2026-11-25 に方針を合意 (簡易 ADR の LADR-002): `90_local-katakana.json` の `add_space` に `カスタム マッチャー` を追加し、自己テストの期待値は変えない。`no_space` の効果のない `マッチャ` は削除する。SudachiPy を無効にしても同じ結果になり、Sudachi 辞書の版に依存しないことを複製で確認済み。 2026-11-25 に最終仕様 `261125-docsfw-table-caption-backlog-design.md` を作成。2026-11-26 に `90_local-katakana.json` の `add_space` へ `カスタム マッチャー` を追加し、`no_space` の `マッチャ` を削除。`text_style_jp.py --test` が全件成功することを確認 (Windows 側の確認は別途)。

### 影響範囲とリスク

- **影響対象**: `text_style_jp.py --test` の結果。
- **放置した場合のリスク**: 自己テストが常に失敗するため、新たな退行が埋もれます。

### 推奨される対応策

- **恒久対応案**: `マッチャ` を長音付きの `マッチャー` へ置き換える辞書の項目と、カタカナ分割の結果を確認し、辞書と期待値のどちらを直すかを決めます。
- **参考情報**: `framework/docsfw/bin/text_style_jp.py` の `run_tests()`、`framework/docsfw/bin_internal/text_style_jp_engine.py`。

## BL-002 ブロック引用の中の Table: 段落の判定

### 概要と問題点

- **現状の事象**: `bin_internal/table_caption_position.py` は、行頭が `>` のブロック引用の中の `Table:` 段落をキャプションとして判定しません。そのため、前処理 (`table-caption-preprocess.py`) は並べ替えもエスケープも行わず、Pandoc の `table_captions` の解釈 (表が連続すると後置きを優先) がそのまま適用されます。`text_style_jp.py` の `table-caption-position` も検出しません。MkDocs の `convert_captions()` も、行頭の `>` を含む `Table:` 行を扱いません。
- **本来あるべき姿**: ブロック引用の中でも、表の直前の `Table:` 段落が直後の表のキャプションになり、Pandoc 発行と MkDocs 発行の結果が一致すること。

### 経緯と見送り理由

- **摘出契機**: 前処理の実装中に、分類の対象を確認して判明しました。
- **今回の見送り理由**: リポジトリ内にブロック引用の中の表キャプションの使用例がなく、移行の対象もないため、範囲外としました。
- **継続作業での経緯と対処**: 継続作業 `261125-docsfw-table-caption-backlog` (全体管理文書 `261125-docsfw-table-caption-backlog-overview.md`) で検討中 (2026-11-25 開始)。ブロック引用の中で、1 つ目の表にキャプションがなく 2 つ目の表の前に `Table:` を書くと、Pandoc は 1 つ目の表へ付けることを再現。MkDocs は誤った付け替えはなく、キャプションのクラスが付かない表示の差だけ。2026-11-25 に方針を合意 (簡易 ADR の LADR-005): ブロック引用の中でも、引用の深さが同じ `Table:` 段落と表の組を引用の外と同じ規則で扱い、Pandoc の前処理、`text_style_jp.py`、MkDocs の `convert_captions()` のすべてを対応させる。 2026-11-25 に最終仕様 `261125-docsfw-table-caption-backlog-design.md` を作成。2026-11-26 に `table_caption_position.py` (引用の深さを加えた分類と区間)、`table-caption-preprocess.py` (`prepare_for_pandoc()` 経由)、`stage_livedocs.py` の `convert_captions()` を対応させ、4 つのテスト ファイルへテストを追加。Pandoc 前処理、`text_style_jp` の `table-caption-position`、MkDocs の変換のすべてで局所テストが成功。正本文書への反映は最終仕様の WBS 4.7 で行う。

### 影響範囲とリスク

- **影響対象**: ブロック引用 (admonition を含む) の中に、キャプション付きの表を連続して書いた文書。
- **放置した場合のリスク**: キャプションが前の表に付く、または MkDocs でキャプションとして表示されない可能性があります。

### 推奨される対応策

- **恒久対応案**: `table_caption_position.py` の分類で、行頭の `>` の深さを取り除いた内容で判定し、同じ深さのブロック引用の中だけで並べ替えます。`stage_livedocs.py` も同じ規則で扱います。
- **参考情報**: `framework/docsfw/bin_internal/table_caption_position.py`、`framework/docsfw/livedocs/bin/stage_livedocs.py` の `convert_captions()`。

## BL-003 Doxygen コメントで字下げが表と異なる Table: 段落の検出

### 概要と問題点

- **現状の事象**: `table_caption_position.py` は、`Table:` 段落と表の字下げの幅が一致する場合だけを対象にします。Doxygen コメントでは、`@param` の説明に合わせて表を深く字下げし、`Table:` 行を浅い字下げで書く例があります (移行前の `app/porter/prod/include/porter/porter_spec.h` の送信オプション フラグの表)。Doxygen は出力時に字下げをそろえるため、発行結果では表と `Table:` が隣り合いますが、`text_style_jp.py` の `table-caption-position` はこの形を検出しません。
- **本来あるべき姿**: Doxygen コメントでも、表の後ろに書いた `Table:` を検出できること。

### 経緯と見送り理由

- **摘出契機**: 既存の記述の一括移行で、該当の 1 か所だけが変換されずに残ったことで判明しました。この 1 か所は手作業で表の直前へ移しました。
- **今回の見送り理由**: 該当がリポジトリ内で 1 か所だけで、Doxygen の字下げの解釈を判定に取り入れる設計が別途必要なため、範囲外としました。
- **継続作業での経緯と対処**: 継続作業 `261125-docsfw-table-caption-backlog` (全体管理文書 `261125-docsfw-table-caption-backlog-overview.md`) で検討中 (2026-11-25 開始)。表が `Table:` より深い Doxygen コメントが検出されないことを再現。Doxygen の XML では表と `Table:` が隣り合う。2026-11-25 に方針を合意 (簡易 ADR の LADR-006): C/C++ のモードに限り、表の字下げが `Table:` 段落より深い場合も組として扱う。Markdown のモードは変えない。 2026-11-25 に最終仕様 `261125-docsfw-table-caption-backlog-design.md` を作成。2026-11-26 に `table_caption_position.py` へ `_caption_fits_table()` を追加し、C/C++ のモードで表が `Table:` 段落以上に深い場合も組として扱うようにした。`test_table_caption_position.py` と `test_text_style_jp_table_caption.py` へテストを追加し、局所テストが成功。正本文書への反映は最終仕様の WBS 4.7 で行う。

### 影響範囲とリスク

- **影響対象**: C/C++ ヘッダーの Doxygen コメントで、表を `@param` などの説明の字下げで書いた箇所。
- **放置した場合のリスク**: 表の後ろに書いた `Table:` が残っても `text_style_jp.py` で検出されず、Pandoc 発行で通常の段落として表示されます (前処理の警告は出ます)。

### 推奨される対応策

- **恒久対応案**: Doxygen モードでは、表のブロックと `Table:` 段落の字下げの差を許容する、または Doxygen の段落の規則に合わせて字下げを正規化してから判定します。
- **参考情報**: `framework/docsfw/bin_internal/table_caption_position.py` の `_classify_doxygen()` と `_same_indent()`、`app/porter/prod/include/porter/porter_spec.h`。

## BL-004 test_livedocs_path_spaces の venv 判定のテストの失敗

### 概要と問題点

- **現状の事象**: `framework/docsfw/bin_test/test_livedocs_path_spaces.py::LivedocsPathSpacesTest::test_make_livedocs_with_complete_system_environment` が失敗します。システムの Python 環境がそろっている場合に livedocs 用の venv を作らないことを確認するテストですが、`INFO: Preparing livedocs venv at /tmp/livedocs space .../venv space` が出力され、venv が作られます。
- **本来あるべき姿**: テストの前提 (システム環境がそろっている) が成り立つ環境ではテストが成功し、成り立たない環境ではスキップされること。

### 経緯と見送り理由

- **摘出契機**: 表のキャプションの前置きの変更後に、docsfw の `bin_test` を実行して発見しました。HEAD を作業用ディレクトリに取り出した複製でも失敗します。
- **今回の見送り理由**: venv の作成の判定は表のキャプションと無関係で、範囲外としました。
- **継続作業での経緯と対処**: 継続作業 `261125-docsfw-table-caption-backlog` (全体管理文書 `261125-docsfw-table-caption-backlog-overview.md`) で検討中 (2026-11-25 開始)。原因は、システム Python の pymdown-extensions 13.1 と watchdog 7.1.0 が採用範囲 (`<12.0.0`、`<7.0.0`) の外で、テストの前提が成り立たないこと。採用範囲を広げた複製ではテストが成功することを確認。2026-11-25 に方針を合意 (簡易 ADR の LADR-003): テストを実行する Python が採用範囲を満たさない場合はテストをスキップする。採用範囲は変えない。`make bin-test` の経路では採用範囲を満たす Python が選ばれるため、スキップは起きない。 2026-11-25 に最終仕様 `261125-docsfw-table-caption-backlog-design.md` を作成。2026-11-26 に `test_make_livedocs_with_complete_system_environment` の先頭で、`resolve_python_components.py` の判定により採用範囲を確認し、満たさない場合 (手元の `/usr/bin/python3` は pymdown-extensions と watchdog が範囲外) は不足するパッケージ名を示してスキップするようにした。採用範囲を満たす Python (`make livedocs-venv` の venv) では 2 件とも実行されて成功することを確認。

### 影響範囲とリスク

- **影響対象**: docsfw の `bin_test` の実行結果。
- **放置した場合のリスク**: テストが常に失敗するため、livedocs の環境準備の退行が埋もれます。

### 推奨される対応策

- **恒久対応案**: システム環境の判定条件 (必要なパッケージの検出) と、この環境で不足しているものを調べ、判定かテストの前提のどちらを直すかを決めます。
- **参考情報**: `framework/docsfw/bin_test/test_livedocs_path_spaces.py`、livedocs の venv 準備の処理。

## BL-005 space-inside-brackets が URL の直後の閉じ括弧の前の空白を指摘する

### 概要と問題点

- **現状の事象**: `text_style_jp.py` の `space-inside-brackets` は、`(see: https://man7.org/linux/man-pages/man7/socket.7.html )` のように、URL と閉じ括弧の間に置いた空白を削除の対象として指摘します。
- **本来あるべき姿**: URL の範囲を区切るための空白を誤検出しないこと、または URL を括弧で囲む書き方をリポジトリで 1 つに定め、規則と記述をそろえること。

### 経緯と見送り理由

- **摘出契機**: 移行前からある `--dry-run` の指摘を個別に判断した際に、`app/cplat/prod/include/cplat/net/socket.h` の 268 行と 270 行で検出しました。空白を削除すると、Doxygen が閉じ括弧まで URL として扱うおそれがあるため、この 2 件は据え置きました。
- **今回の見送り理由**: 規則の実装の変更、または URL の書き方の規範の決定が必要で、表のキャプションの変更の範囲外のためです。
- **継続作業での経緯と対処**: 継続作業 `261125-docsfw-table-caption-backlog` (全体管理文書 `261125-docsfw-table-caption-backlog-overview.md`) で検討中 (2026-11-25 開始)。Doxygen 1.17.0 は空白なしの `(see: URL)` でも閉じ括弧を URL に含めないことを確認。Pandoc 3.11 と MkDocs は裸の URL を自動リンクしない。2026-11-25 に方針を合意 (簡易 ADR の LADR-004): `socket.h` の 2 か所の空白を削除し、規則と正本文書は変えない。 2026-11-25 に最終仕様 `261125-docsfw-table-caption-backlog-design.md` を作成。2026-11-26 に `socket.h` の 2 か所の空白を削除し、`text_style_jp.py --dry-run` の指摘がなくなることと、Doxygen 1.17.0 の XML の `ulink url` に閉じ括弧が含まれないことを確認 (Doxygen 1.18.0 は Windows 側で確認)。

### 影響範囲とリスク

- **影響対象**: C/C++ のコメントと Markdown で、括弧の中の末尾に URL を書いた箇所。
- **放置した場合のリスク**: 該当ファイルの `--dry-run` の指摘が常に残り、`--in-place` を適用すると URL の自動リンクが壊れる可能性があります。

### 推奨される対応策

- **恒久対応案**: `space-inside-brackets` で、直前の語が URL の場合を例外にします。あわせて、Doxygen と Pandoc の両方で、`(see: <URL>)` の形で閉じ括弧が URL に含まれないかを確認し、書き方を規範に定めます。
- **参考情報**: `framework/docsfw/bin_internal/text_style_jp_engine.py`、`app/cplat/prod/include/cplat/net/socket.h`、AGENTS.md の `see: <URL>` の規則。

## BL-006 --dry-run の指摘の桁が実際の変更位置と一致しない場合がある

### 概要と問題点

- **現状の事象**: 移行前からある指摘を判断したサブ エージェントから、`text_style_jp.py --dry-run` が示す `行:桁` の桁が、`--in-place` の実際の差分の位置と合わない場合があると報告されました。桁は空白の挿入位置を示しており、指摘の対象の語の位置とは異なる場合があります。文字単位でない可能性も指摘されています。
- **本来あるべき姿**: 桁の意味 (文字単位か、挿入位置か) が文書に定義され、表示がその定義と一致すること。

### 経緯と見送り理由

- **摘出契機**: 移行前からある指摘の個別判断の作業中に報告されました。
- **今回の見送り理由**: 桁の算出は表のキャプションの変更と無関係で、再現の条件の調査が必要なためです。
- **継続作業での経緯と対処**: 継続作業 `261125-docsfw-table-caption-backlog` (全体管理文書 `261125-docsfw-table-caption-backlog-overview.md`) で検討中 (2026-11-25 開始)。桁が各整形ステップが処理した時点の文字列での位置であること、C/C++ のコメントのモードではコメント本文の位置であることを再現。2026-11-25 に方針を合意 (簡易 ADR の LADR-008): 桁を入力ファイルの行の文字位置 (1 始まり、コード ポイント単位) とし、コメントを解析するすべてのモードでもソースの行の位置にする。位置の写像を `DiagnosticCollector` に集約し、文字列を変えるすべての処理で更新する。整形の結果は変えない。 2026-11-25 に最終仕様 `261125-docsfw-table-caption-backlog-design.md` を作成し、対応中 (第 2 ゲートの承認待ち)。2026-11-26 に `text_style_jp_engine.py` の `_PositionMap` と `DiagnosticCollector` で桁を元の行の位置へ写像し、`text_style_jp_frontends.py` のすべてのコメント解析モードで本文の開始位置を渡すよう実装。`text_style_jp.py --test` に桁の自己テストを追加し、`docs/text_style_jp.md` に桁の定義を記載。整形の結果 (`-o` の出力) が変更前と一致することを確認。

### 影響範囲とリスク

- **影響対象**: `--dry-run` と `--check` の出力を読む利用者とエージェント。
- **放置した場合のリスク**: 指摘の箇所の特定に時間がかかり、判断を誤る可能性があります。

### 推奨される対応策

- **恒久対応案**: 全角文字と半角文字を含む行で、報告される桁と差分の位置を比べて再現条件を特定し、桁の単位を文字単位に統一するか、文書に定義を記載します。
- **参考情報**: `framework/docsfw/bin_internal/text_style_jp_engine.py` の `DiagnosticCollector`、`framework/docsfw/docs/text_style_jp.md`。
