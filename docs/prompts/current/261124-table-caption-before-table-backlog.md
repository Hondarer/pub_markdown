<!--
生成元: agree-before-implement スキル
文書種別: 残課題一覧 (backlog)
最終更新日時: 2026-11-24 09:12:23 JST
最終更新エージェント: claude code / セッション ID: session_01KJc53RaT4Cei9nCXSSZqH1
稼働 OS: Linux (WSL)
上流文書: `261124-table-caption-before-table-overview.md` (全体管理文書)、`261124-table-caption-before-table-design.md` (最終仕様)、`261124-table-caption-before-table-discussion.md` (検討用 Markdown)、`261124-table-caption-before-table-lightadr.md` (簡易 ADR)。いずれも削除されている場合があります。
下流文書: この残課題一覧を対策する継続作業が開始された場合は、その全体管理文書・検討用 Markdown・最終仕様・残課題一覧のパスを追記します。
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
| BL-001 | text_style_jp.py の自己テスト「カスタムマッチャ」の失敗 | 作業中摘出 | 低 | 未着手 |
| BL-002 | ブロック引用の中の Table: 段落の判定 | 作業中摘出 | 低 | 未着手 |
| BL-003 | Doxygen コメントで字下げが表と異なる Table: 段落の検出 | 作業中摘出 | 低 | 未着手 |
| BL-004 | test_livedocs_path_spaces の venv 判定のテストの失敗 | 作業中摘出 | 低 | 未着手 |

## BL-001 text_style_jp.py の自己テスト「カスタムマッチャ」の失敗

### 概要と問題点

- **現状の事象**: `python3 framework/docsfw/bin/text_style_jp.py --test` のうち、Markdown の入力 `カスタムマッチャ` の 1 件が失敗します。期待値は `カスタム マッチャー` ですが、結果は入力のままです。
- **本来あるべき姿**: 自己テストがすべて成功するか、辞書の方針に合わせて期待値が更新されていること。

### 経緯と見送り理由

- **摘出契機**: 表のキャプションの前置きの実装中に `--test` を実行して発見しました。変更前の HEAD (`framework/docsfw` v20261118.0.0) を作業用ディレクトリに取り出して実行しても、同じ 1 件が失敗します。
- **今回の見送り理由**: 今回の変更とは無関係の既存の問題で、辞書 (`replace` / `add_space` と SudachiPy によるカタカナ分割) の判断を含むため、範囲外としました。

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

### 影響範囲とリスク

- **影響対象**: docsfw の `bin_test` の実行結果。
- **放置した場合のリスク**: テストが常に失敗するため、livedocs の環境準備の退行が埋もれます。

### 推奨される対応策

- **恒久対応案**: システム環境の判定条件 (必要なパッケージの検出) と、この環境で不足しているものを調べ、判定かテストの前提のどちらを直すかを決めます。
- **参考情報**: `framework/docsfw/bin_test/test_livedocs_path_spaces.py`、livedocs の venv 準備の処理。
