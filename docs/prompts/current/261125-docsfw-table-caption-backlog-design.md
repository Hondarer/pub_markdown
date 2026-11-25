<!--
生成元: agree-before-implement スキル
文書種別: 最終仕様 (design)
最終更新日時: 2026-11-26 02:05:00 JST
最終更新エージェント: claude code (主セッション session_01KJc53UFydnbt2gLXTJC1ZC)
稼働 OS: Linux (WSL)
上流文書: `261125-docsfw-table-caption-backlog-overview.md` (全体管理文書)、`261125-docsfw-table-caption-backlog-discussion.md` (検討用 Markdown)、`261125-docsfw-table-caption-backlog-lightadr.md` (簡易 ADR)。対策元は `261124-table-caption-before-table-backlog.md` (残課題一覧の BL-001 〜 BL-006)。いずれも削除されている場合があります。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。上流文書の全体管理文書が存在する場合は、その再開手順に従って進行位置を確認し、決定事項を簡易 ADR で、判断の経緯を検討用 Markdown の Q&A で確認します。存在しない場合は、この文書を単体の最終仕様として扱います。最終更新エージェントのセッション情報や稼働 OS・最終更新日時が参照可能であれば再開時のコンテキストや環境差分の把握に利用し、別エージェントや別環境・別 OS からの引き継ぎ、担当変更によりセッションが見つからない場合も異常とせず、文書の記載から継続してください。
-->

# 表のキャプションの前置きの残課題の対策 最終仕様

ファイル名: `261125-docsfw-table-caption-backlog-design.md`

## 概要

docsfw の表のキャプションの前置きの導入時に残った 6 件の課題を対策します。

Table: 対策する課題と変更の要点

| 課題 | 内容 | 変更の要点 |
| --- | --- | --- |
| BL-001 | `text_style_jp.py --test` の「カスタム マッチャー」の失敗 | 辞書の `add_space` に 1 語を追加し、効果のない `no_space` の 1 語を削除 |
| BL-002 | ブロック引用の中の `Table:` 段落 | 引用の深さを取り除いて判定し、Pandoc の前処理、`text_style_jp`、MkDocs の変換をそろえる |
| BL-003 | Doxygen コメントで表が `Table:` より深い場合の検出 | C/C++ のモードで、表が深い場合も組として扱う |
| BL-004 | `test_livedocs_path_spaces` の前提の不成立 | 採用範囲を満たさない Python ではテストをスキップ |
| BL-005 | URL の直後の閉じ括弧の前の空白 | `socket.h` の 2 か所の空白を削除 |
| BL-006 | `--dry-run` の桁のずれ | 桁を入力ファイルの行の文字位置へ写像する |

整形の結果 (`--in-place` の出力) が変わるのは、BL-001 (辞書) と BL-002 と BL-003 (表のキャプションの移動の対象の拡大) だけです。BL-006 は `--dry-run` の桁の表示だけを変えます。

## 変更対象のファイル

Table: 変更対象のファイルと課題の対応

| ファイル | 課題 | 種別 |
| --- | --- | --- |
| `framework/docsfw/.text_style_jp/90_local-katakana.json` | BL-001 | 辞書 |
| `framework/docsfw/bin_internal/table_caption_position.py` | BL-002、BL-003 | 実装 |
| `framework/docsfw/livedocs/bin/stage_livedocs.py` | BL-002 | 実装 |
| `framework/docsfw/bin_internal/text_style_jp_engine.py` | BL-006 | 実装 |
| `framework/docsfw/bin_internal/text_style_jp_frontends.py` | BL-006 | 実装 |
| `framework/docsfw/bin/text_style_jp.py` | BL-006 | 自己テスト |
| `framework/docsfw/bin_test/test_table_caption_position.py` | BL-002、BL-003 | テスト |
| `framework/docsfw/bin_test/test_table_caption_line.py` | BL-002 | テスト (Pandoc) |
| `framework/docsfw/bin_test/test_text_style_jp_table_caption.py` | BL-002、BL-003 | テスト (CLI) |
| `framework/docsfw/bin_test/test_livedocs_path_spaces.py` | BL-004 | テスト |
| `framework/docsfw/livedocs/bin_test/test_stage_livedocs.py` | BL-002 | テスト (MkDocs) |
| `app/cplat/prod/include/cplat/net/socket.h` | BL-005 | コメント |
| `framework/docsfw/docs/table-caption.md` | BL-002 | 正本文書 |
| `framework/docsfw/docs/text_style_jp.md` | BL-002、BL-003、BL-006 | 正本文書 |

`framework/docsfw/bin_internal/table-caption-preprocess.py` は `prepare_for_pandoc()` を呼ぶだけのため、変更しません。

## BL-001 自己テスト「カスタム マッチャー」

### 辞書の変更

`framework/docsfw/.text_style_jp/90_local-katakana.json` を次のとおり変更します。

- `add_space` に `"カスタム マッチャー"` を追加します。位置は、既存の `"カスタム ハンドラー"` の直後とします (同じ長さの項目の並び)。
- `no_space` から `"マッチャ"` を削除します。この語は `replace` の `from` にもあり、エンジンが保護の対象から外すため、効果がありません。

`bin/text_style_jp.py` の自己テストの期待値 `("カスタムマッチャ", "カスタム マッチャー")` は変えません。

> [!NOTE]
> `add_space` は Sudachi による分割の後に、カタカナ語の空白を除いて照合します。このため、`カスタムマッチャ` は、Sudachi が分割するかどうか (辞書の版や SudachiPy の有無) にかかわらず `カスタム マッチャー` になります。空白を入れる形は、原語 (custom matcher) の語数に合わせる辞書の方針と一致します。

### 受入条件

- `python3 framework/docsfw/bin/text_style_jp.py --test` が全件成功する。
- 入力 `カスタムマッチャ`、`カスタムマッチャー`、`カスタム マッチャ` がいずれも `カスタム マッチャー` になり、`マッチャ` 単独と `引数マッチャ` の変換結果が変更前と同じである。

## BL-002 ブロック引用の中の Table: 段落

### 仕様

Markdown のブロック引用の中でも、引用の外と同じ規則で `Table:` 段落を表のキャプションとして扱います。

- 行頭の引用の記号 (`>` と、その直後の任意の空白 1 個の繰り返し。記号の前の 3 個までの空白を含む) を引用の接頭辞とし、`>` の数を引用の深さとします。判定は、接頭辞を取り除いた内容で行います。
- 引用の深さが同じ行だけを、同じブロックとして扱います。`Table:` 段落、間の空行 (接頭辞だけの行、または空行)、表は、すべて同じ深さでなければなりません。深さの異なる行 (`>` のない遅延継続行を含む) が混ざる場合は、キャプションとして扱いません。
- 段落の先頭は、同じ深さの空行の直後とします。`> [!NOTE]` などのアラート記法の行の直後に空行を挟まずに書いた `> Table:` は、段落の先頭ではないため、キャプションとして扱いません。
- 字下げの比較は、接頭辞を取り除いた内容で行います。引用の中の箇条書きの項目でも、引用の外と同じく、段落と表の字下げの幅が一致する必要があります。
- 引用の中のフェンス付きコード ブロックの中は、判定の対象外とします。
- 対象は `Table:` だけです。引用の中の `CodeBlock:` と `Figure:` の扱いは変更しません。
- C/C++ の Doxygen コメントの中の引用の記号は扱いません (Doxygen のモードの判定は BL-003 の変更だけです)。

Pandoc 発行、`text_style_jp.py` の `table-caption-position`、MkDocs 発行の 3 つで、キャプションとみなす `Table:` 段落が一致することを、この仕様の不変条件とします。

### 関数の変更 (table_caption_position.py)

- `_classify_markdown(lines)`: 各行の分類に、引用の深さを加えます。戻り値の要素を `(種別, 接頭辞を除いた内容, 深さ)` にします。フェンスと HTML コメントの開始と終了は、接頭辞を除いた内容で判定します。引用の中のフェンスは、開始と同じ深さの行で閉じます。
- `_classify_doxygen(lines)`: 戻り値の要素に深さ 0 を加えます。判定は変えません。
- `_segments(kinds)`: 種別と深さの両方が同じ連続した行を、1 つの区間にまとめます。
- `_is_table()`、`_is_caption()`、`_indent_width()` の利用箇所: 接頭辞を除いた内容で判定します。
- 新しい補助関数 `_same_depth(kinds, left, right)`: 2 つの区間の深さが一致するかを返します。`relocate_table_captions()` と `prepare_for_pandoc()` の隣接の判定 (表、空行、`Table:` 段落、空行、表) で、関係するすべての区間に適用します。
- `prepare_for_pandoc(text)`: `Table:` のエスケープ (`Table\:`) と、行頭の `table:` / `:` のエスケープは、元の行の接頭辞を保ったまま、内容の部分に適用します。並べ替えは区間単位のまま行い、接頭辞を含む元の行を移します。
- `relocate_table_captions(text, mode, migrate)`: 上記の分類と区間で判定します。移動の一覧の形式は変えません。
- モジュールの docstring に、ブロック引用の扱い (深さが同じ行だけを組にすること) を追記します。

### 関数の変更 (stage_livedocs.py)

- 新しい正規表現 `_BLOCKQUOTE_PREFIX_RE` と補助関数 `_split_blockquote_prefix(line)`: 行を `(接頭辞, 内容, 深さ)` に分けます。
- `convert_captions(text)`:
    - 引用の中のフェンスを、内容で検出して読み飛ばします。このフェンスは図の判定 (`diagram_block`、`internal_caption`、`_wrap_diagram_with_caption()`) の対象にしません。引用の外の図とフェンスの処理は変えません。
    - 接頭辞を除いた内容が `Table:` で始まり、直前の行が同じ深さの空行 (または文書の先頭) である行を、引用の中の `Table:` 段落の先頭とします。段落は、同じ深さで内容が空でない行の連続とします。
    - キャプションとする場合は、段落の各行と属性行 (`{: .docsfw-caption .docsfw-table-caption }`、ラベルがあれば `#ラベル` を先頭に付ける) に、元の接頭辞と字下げを付けて出力します。
    - 直後が表でない場合は、引用の外と同じ警告を標準エラー出力へ書き、段落をそのまま残します。
    - 引用の中の `CodeBlock:` と `Figure:` は、従来どおり変換しません。
- `_is_followed_by_table(lines, index, indent)`: 引用の深さを引数に加え、同じ深さの空行の後に、同じ深さと字下げの表が続くかを判定します。
- `convert_captions()` の docstring に、ブロック引用の扱いを追記します。

### テストの追加

Table: BL-002 のテストの追加

| テスト ファイル | 追加するテスト |
| --- | --- |
| `bin_test/test_table_caption_position.py` | 引用の中で 1 つ目の表にキャプションがなく 2 つ目の表の前に `Table:` がある場合に、`prepare_for_pandoc()` が `Table:` を 2 つ目の表の後ろへ移すこと。引用の中の連続する表の帰属。引用の中の表の直後で次に表がない `Table:` がエスケープされ、行番号付きの警告が出ること。深さの異なる `Table:` と表 (`>` と `> >`) を組にしないこと。遅延継続行を含む `Table:` 段落を組にしないこと。`> [!NOTE]` の直後の `> Table:` を組にしないこと。引用の中のフェンスの中の `Table:` を変更しないこと。`relocate_table_captions()` が引用の中の後置きを前置きへ移すこと |
| `bin_test/test_table_caption_line.py` | Pandoc を実行し、引用の中の 2 つ目の表だけにキャプションが付くこと (1 つ目の表にキャプションが付かないこと) |
| `bin_test/test_text_style_jp_table_caption.py` | `--dry-run` が引用の中の後置きを `table-caption-position` として報告し、`--in-place` が前置きへ移すこと |
| `livedocs/bin_test/test_stage_livedocs.py` | `convert_captions()` が引用の中の `Table:` 段落に接頭辞を保ってクラスと属性行を付けること。直後が表でない場合の警告。`> [!NOTE]` の中で空行を挟んだ `Table:` が変換されること。Python-Markdown (`attr_list`、`tables`、`github-callouts`) で描画し、引用とアラートの中のキャプションの段落に `docsfw-table-caption` クラスが付き、次の要素が対応する表であること。引用の中の図のフェンスと `Figure:` が変換されないこと |

### 受入条件

- Pandoc 発行で、引用の中のキャプションが直後の表に付き、前の表に付かない。
- MkDocs 発行で、引用の中のキャプションに `.docsfw-caption .docsfw-table-caption` クラスが付く。
- 上記の各テストの入力について、Pandoc の前処理、`text_style_jp`、MkDocs の変換で、キャプションとみなす `Table:` 段落が一致する。
- 引用の外の既存のテストがすべて成功する。

## BL-003 Doxygen コメントで表が深い Table: 段落

### 仕様

C/C++ のモード (`c`、`cpp`) に限り、表の字下げが `Table:` 段落より深い場合も、表と `Table:` 段落を組として扱います。`Table:` 段落のほうが深い場合は、従来どおり組にしません。Markdown のモードの判定 (字下げの一致) は変えません。

> [!NOTE]
> Doxygen は、`@param` の説明や箇条書きの下で深く字下げした表を、空行の後では説明や箇条書きの外の段落として出力し、後ろの浅い `Table:` の段落を表の直後に続けます。前置きへ移した形でも、`Table:` の段落の直後に表が続きます。このため、表が深い場合を組として扱っても、発行結果での表と `Table:` の隣接は保たれます (Doxygen 1.17.0 で確認)。

### 関数の変更 (table_caption_position.py)

- 新しい補助関数 `_caption_fits_table(kinds, caption, table, mode)`: Markdown のモードでは字下げの幅が一致する場合、C/C++ のモードでは表の字下げの幅が `Table:` 段落以上の場合に真を返します。
- `relocate_table_captions()`: 表の直後の `Table:` 段落の判定と、`Table:` 段落の直後に表が続くかの判定 (`followed_by_table`) の両方で、`_same_indent()` の代わりに `_caption_fits_table()` を使います。
- `prepare_for_pandoc()`: Markdown だけを扱うため、`_same_indent()` のまま変えません。
- モジュールの docstring に、C/C++ のモードの字下げの扱いを追記します。

### テストの追加

- `bin_test/test_table_caption_position.py`: `@param` の説明の下の深い表と、後ろの浅い `Table:` を、`relocate_table_captions(..., "cpp")` が表の直前へ移すこと。箇条書きの下の深い表でも同様であること。`Table:` が表より深い場合は移さないこと。前置きで書かれた浅い `Table:` と深い表の組 (表に挟まれた場合を含む) を変更しないこと。Markdown のモードでは字下げが異なる組を従来どおり移さないこと。
- `bin_test/test_text_style_jp_table_caption.py`: `--mode cpp --dry-run` が上記の形を `table-caption-position` として報告すること。

### 受入条件

- 上記のテストが成功し、既存の Markdown のモードのテストが変わらず成功する。

## BL-004 test_livedocs_path_spaces の前提

### 関数の変更 (bin_test/test_livedocs_path_spaces.py)

- `test_make_livedocs_with_complete_system_environment()`: 先頭で、`livedocs/bin/resolve_python_components.py` の `load_requirements()`、`probe()`、`missing_packages()` を使い、`sys.executable` が `livedocs/requirements-compatible.txt` の採用範囲を満たすかを判定します。満たさない場合は、不足するパッケージ名を含む理由で `self.skipTest()` を呼びます。モジュールの読み込みは、同じディレクトリ以外のモジュールの読み込み方法として、`sys.path` へ `livedocs/bin` を追加してから行います。
- テストのコメントに、前提 (テストを実行する Python が採用範囲を満たすこと) と、`make bin-test` ではその Python が選ばれるためスキップしないことを記載します。
- 採用範囲 (`requirements-compatible.txt`) と固定版 (`requirements.txt`) は変更しません。

### 受入条件

- 採用範囲を満たす Python (`make livedocs-venv` が選ぶ Python) で実行すると、テストが実行されて成功する。
- 採用範囲を満たさない Python (手元の `/usr/bin/python3`。pymdown-extensions 13.1、watchdog 7.1.0) で直接実行すると、不足するパッケージ名を示してスキップする。

## BL-005 URL の直後の閉じ括弧の前の空白

### 変更 (app/cplat/prod/include/cplat/net/socket.h)

`cplat_socket_set_receive_buffer_size()` の Doxygen コメントの 2 か所で、URL と閉じ括弧の間の空白を削除します。

```c
 *  切り詰めます (see: https://man7.org/linux/man-pages/man7/socket.7.html)。\n
 *  (see: https://learn.microsoft.com/en-us/windows/win32/winsock/sol-socket-socket-options)。
```

`space-inside-brackets` の規則と、正本文書は変更しません。公開 API の関数、型、シグネチャは変えないため、`app/cplat/docs/api-cheatsheet.md` とエクスポート テストは変更しません。

### 受入条件

- `text_style_jp.py --dry-run app/cplat/prod/include/cplat/net/socket.h` が、268 行と 270 行の `space-inside-brackets` を報告しない。
- Doxygen 1.17.0 (Linux) と Doxygen 1.18.0 (Windows) の両方で、生成した XML の 2 つの `ulink url` に閉じ括弧が含まれない。

## BL-006 dry-run の桁

### 桁の定義

- `--dry-run` の桁 (`Finding.column`) は、入力ファイルの行の文字位置です。1 始まりで、Python の文字 (コード ポイント) 単位で数え、全角文字とタブも 1 と数えます。
- 挿入の桁は、元の行で挿入位置の直後にある文字の桁です。行末への挿入は、行の長さ + 1 です。
- 削除と置換の桁は、元の行で対象の範囲の先頭の桁です。
- 前の処理が挿入した文字に対する変更は、その挿入位置の桁とします。
- コメントを解析するすべてのモード (`c`、`cpp`、`csharp`、`python`、`shell`、`make`) では、ソースの行の文字位置です。Markdown の言語付きフェンスの中のコメントでは、Markdown の行の文字位置です。
- `--check` は桁を出力しないため、変わりません。整形の結果も変わりません。

### 仕組み

処理中の文字列の位置から、元の行の位置を求める写像を `DiagnosticCollector` が行ごとに持ちます。文字列を変えるすべての処理は、変換の前後の文字列を `DiagnosticCollector` に渡して写像を更新します。Finding の桁は、記録の時点の写像で元の行の桁へ変換します。

写像の更新は、変換の前後を `difflib.SequenceMatcher` (`autojunk=False`) で比較して行います。一致する部分は元の位置を引き継ぎ、置換と挿入で生じた文字は、置き換えられた範囲の先頭の元の位置 (挿入では、挿入位置の直後の文字の元の位置) を受け継ぎ、削除した文字は写像から除きます。

### 関数の変更 (text_style_jp_engine.py)

- 新しいクラス `_PositionMap`: 処理中の文字列の位置 (0 始まり) から元の行の位置 (0 始まり) への写像です。生成時は恒等写像 (列の開始位置のずれを持つ) とし、長さを知らない状態でも使えるよう、未更新の範囲は恒等として扱います。`advance(before, after)` で変換の前後から写像を更新し、`source_index(index)` で元の位置を返します。
- `DiagnosticCollector`:
    - `set_line(line, column_offset=0)`: 行を切り替え、写像を恒等写像 (`column_offset` だけずらす) に戻します。直前の行の写像は、行番号をキーとして保存します。`column_offset` は、処理する文字列の先頭が元の行の何文字目から始まるか (0 始まり) です。
    - 新しい `set_line_source(line, source, working, column_offset=0)`: 行を切り替え、元の文字列 `source` と処理を始める文字列 `working` の差分から初期の写像を作ります。C/C++ の引用符の退避のように、行の処理の開始前に長さが変わっている場合に使います。
    - 新しい `resume_line(line)`: 保存した行の写像を復元して、その行の処理を続けます。
    - 新しい `track(before, after)`: 現在の行の写像を更新します。
    - 新しい `snapshot()`: 現在の写像の複製を返します。
    - `add(column, ...)`: `column` を処理中の文字列の位置 (1 始まり) として受け取り、写像で元の行の桁へ変換して記録します。`set_line()` の直後 (写像が恒等) に元の行の桁を渡す既存の呼び出し (NBSP、罫線文字、テスト コメント、`table-caption-position`、`unattributed-change`) は、変換しても値が変わりません。
    - docstring に桁の定義を記載します。
- `_record_step_changes(before, after, ...)`: 差分の各箇所を `before` での位置で `add()` し、最後に `collector.track(before, after)` を呼びます。
- `_replace_skip_existing(text, ...)`: `dict-replace` の桁を、置換後の文字列の位置ではなく、入力 `text` での一致位置で記録します。置換の後に `collector.track(text, result)` を呼びます。
- `_apply_add_space_pairs(text, ...)`: `dict-add-space` を入力 `text` での位置で記録し、置換の後に `collector.track(text, result)` を呼びます。
- `style_text()`: `_protect_patterns()`、`_protect_urls()`、`_join_katakana_split_by_no_space()`、`_protect_no_space_words()`、`_restore_nosp_with_boundaries()`、`_restore_no_space_words()`、`_restore_replacements()` の前後で `collector.track()` を呼び、プレースホルダーへの退避と復元を写像に反映します。`dict-no-space-boundary` のように、比較のために復元した文字列で差分を記録する箇所は、復元した文字列の位置を処理中の文字列の位置へ対応付けてから記録します (退避の直前の写像を `snapshot()` で保持して変換する)。
- `style_prose()`: 変更なし (各ステップは `_record_step_changes()` を通るため)。

### 関数の変更 (text_style_jp_frontends.py)

- `style_markdown()`: 行ごとの `set_line(idx + 1)` は変えません。行の前処理 (`unordered-list-marker`、`task-list-marker`、`heading-number`、`heading-inline-code`) と後処理 (`markup-span-spacing`) は `_record_step_changes()` を通るため、写像が更新されます。言語付きフェンスの本文のコメントの Finding は、行番号の補正 (`f.line += code_body_start`) だけを行い、桁は下記のコメントの処理で Markdown の行の桁になります。
- `_style_text_with_inline_code_spacing()`: `_restore_inline_code_spacing()` の前後で `collector.track()` を呼びます。開始時に `snapshot()` を取り、`_filter_preserved_inline_code_suffix_findings()` へ渡します。
- `_filter_preserved_inline_code_suffix_findings()`: 保持する範囲 (`original` での位置) を、渡された写像で元の行の桁へ変換してから、Finding の桁と比べます。
- `_normalize_list_indent()`: `collector.set_line(i + 1)` を `collector.resume_line(i + 1)` に変え、その行の整形後の写像で `list-indent` の桁を変換します。
- `_style_c_like_comments()` の `style_comment()`: C/C++ の引用符の退避の前後のコメントを行ごとに対応付け、書式関数が各行の処理を始めるときに `set_line_source()` で初期の写像を設定できるよう、退避前の行を渡します。
- コメントの書式関数 (`_style_xml_doc_block()`、`_style_doxygen_line_block()`、`_style_doxygen_block_comment()`、`_style_general_block_comment()`、`_style_general_line_comment()` の呼び出し元、`_style_hash_comments()`): 各行の本文を整形する前に、本文がソースの行の何文字目から始まるか (コメントの開始位置と、`*`、`///`、`//!`、`//`、`#` などの行頭記号と空白の長さの和) を `column_offset` として `set_line()` (引用符の退避がある C/C++ では `set_line_source()`) に渡します。

### テストの追加 (bin/text_style_jp.py の自己テスト)

次の入力の `--dry-run` の Finding の桁を確認するテストを追加します。期待値は、この節の桁の定義から求めた値です。

Table: BL-006 の桁の自己テストの入力と期待値

| モード | 入力の行 | 規則 | 期待する桁 |
| --- | --- | --- | --- |
| markdown | `## 1. 見出しtext` | `fullwidth-halfwidth-space` | `1:10` (見出し番号の削除の後) |
| markdown | `本文は サーバ と https://example.com/a を参照text です` | `dict-replace`、`fullwidth-halfwidth-space` | `1:5`、`1:36` |
| markdown | `https://example.com/x を ( c ) と書く text日本` | `fullwidth-halfwidth-space` (`text` と `日本` の境界) | `1:39` |
| markdown | `` `code` と注釈text です `` | `fullwidth-halfwidth-space` | `1:11` |
| markdown | `- 親` の次の行の `   - 子の項目text です` | `list-indent`、`fullwidth-halfwidth-space` | `2:1`、`2:10` |
| markdown | ` ```python ` のフェンスの中の `x = 1  # 注釈note です` | `fullwidth-halfwidth-space` | `2:12` |
| cpp | `/**` の次の行の ` *  @brief  日本語text と ( x ) です` | `fullwidth-halfwidth-space` (`日本語` と `text` の境界) | `2:16` |
| cpp | `int f(void); // 注釈note と ( y )` | `fullwidth-halfwidth-space` | `1:19` |
| cpp | `int a; // "日本語ABC" と注釈note です` | `fullwidth-halfwidth-space` | `1:23` |
| csharp | `int x; /// 注釈note です` | `fullwidth-halfwidth-space` | `1:14` |
| python | `x = 1  # 注釈note です` | `fullwidth-halfwidth-space` | `1:12` |
| shell | `echo a  # 注釈note です` | `fullwidth-halfwidth-space` | `1:13` |

あわせて、複数の規則が同じ行に適用される入力 (括弧の内側の空白、全角と半角の境界、URL、インライン コード、辞書の置換を含む行) について、次の性質を確認するテストを追加します。

- `original` が空でない Finding は、元の行の `column` 桁から始まる部分文字列が `original` と一致する (前の処理が挿入した文字を対象とする Finding は除く)。
- `original` が空の Finding (挿入) は、`column` が 1 以上、元の行の長さ + 1 以下である。

既存の自己テストのうち桁を確認するもの (`dict-no-space-boundary` の `column == 4`、NBSP の `column == 2`、テスト コメントの `(3, 5)` など) は、期待値を変えずに成功することを確認します。

### 受入条件

- 上記の自己テストを含め、`text_style_jp.py --test` が全件成功する。
- `docs/` 配下などの既存の Markdown とソースに `--in-place` を適用した結果が、変更前の実装と一致する (整形の結果が変わらない)。確認は、変更前後の `text_style_jp.py` で同じファイル群を `-o` に出力して比較して行う。

## 正本ドキュメントとコード コメントへの反映

Table: 知見の反映先と内容

| 反映先 | 反映する内容 |
| --- | --- |
| `framework/docsfw/docs/table-caption.md` の「キャプションとして扱う条件」 | 条件に「段落と表が同じ深さのブロック引用の中にある (または両方とも引用の外にある)」を加える。字下げの比較は引用の記号を除いて行うこと |
| `framework/docsfw/docs/table-caption.md` の「キャプションとして扱わない場合」 | アラート記法の行の直後に空行を挟まずに書いた `Table:`、深さの異なる行が混ざる段落は、キャプションにならないこと |
| `framework/docsfw/docs/table-caption.md` の「MkDocs 発行」 | 引用の中の `Table:` 段落にも、引用の記号を保ってクラスを付けること |
| `framework/docsfw/docs/text_style_jp.md` の「表のキャプションの位置」 | ブロック引用の中も対象であること。C/C++ の Doxygen コメントでは、表が `Table:` より深い場合も組として扱うこと (変換例の表に 1 行追加) |
| `framework/docsfw/docs/text_style_jp.md` の「dry-run モード」 | 桁の定義 (元の行の文字位置、コード ポイント単位、挿入と削除の桁、コメントのモードではソースの行の位置)。出力の例を実際の出力の形式 (挿入は `"" → " "`) に合わせる |
| `table_caption_position.py`、`stage_livedocs.py` の docstring | ブロック引用の深さの扱い、C/C++ のモードの字下げの扱い |
| `text_style_jp_engine.py` の `DiagnosticCollector` の docstring | 桁の定義と、文字列を変える処理は `track()` で写像を更新する規約 |
| `test_livedocs_path_spaces.py` のコメント | テストの前提とスキップの条件 |

辞書の追加 (BL-001)、`socket.h` の空白 (BL-005) は、正本文書へ反映しません。`framework/docsfw/docs/python-components.md` は、採用範囲と Python の選び方を変えないため、変更しません。

変更した Markdown は、ファイルごとに `python3 framework/docsfw/bin/text_style_jp.py --dry-run <file>` を実行し、指摘がなければ `--in-place` を実行します。

## 検証手順

### Linux の Python の準備

手元の `framework/docsfw/livedocs/.venv` は Python 3.11 の時点で作られており、現在の `/usr/bin/python3` (3.12) からは venv 内のパッケージが見えません。そのため、手元のシステム側の pymdown-extensions 13.1 と watchdog 7.1.0 が使われ、採用範囲の外になります。`make livedocs-venv` (`resolve_python_components.py --ensure`) は、不足する固定版 (pymdown-extensions 11.0.2、watchdog 6.0.0) をこの venv へ導入して解消できます。

局所検証では、リポジトリの venv を変更せず、セッションの一時ディレクトリに作る venv を使います。この venv は `--system-site-packages` 付きで作られ、不足分だけをネットワークから導入します。リポジトリの外の一時ディレクトリだけを変更し、リポジトリの `framework/docsfw/livedocs/.venv` には触れません。

```bash
REPO=/home/user/c-modernization-kit
VENV="$SCRATCH/livedocs-venv"   # SCRATCH はセッションの一時ディレクトリ
PY=$(python3 "$REPO/framework/docsfw/livedocs/bin/resolve_python_components.py" \
      --venv "$VENV" --ensure --print-python)
```

> [!NOTE]
> この手順は 2026-11-25 に一時ディレクトリで実行し、固定版の導入と Python の選択が成功することを確認済みです。リポジトリの `.venv` を直す場合は、リポジトリ ルートで `make livedocs-venv` を実行します。これは Git 管理外 (`.gitignore` の `/livedocs/.venv/`) の手元の環境の変更で、ネットワークからの導入を伴うため、実施はユーザーの判断とします。導入が失敗する場合は、`.venv` を削除してから `make livedocs-venv` で作り直します。

### Linux の局所テスト

`make bin-test` は全 app のスクリプトのテストを実行するため使わず、対象のディレクトリだけを `run-bin-tests.py` と同じ環境変数で実行します。リポジトリでは make を実行しません (BL-004 のテストが一時ディレクトリで実行する make を除く)。

```bash
cd "$REPO"
export PYTHONSAFEPATH=1 PYTHONIOENCODING=utf-8 BIN_TEST_PYTHON="$PY"

# BL-001、BL-006: 自己テスト
"$PY" framework/docsfw/bin/text_style_jp.py --test

# BL-002、BL-003、BL-004: docsfw のスクリプトのテスト
(cd framework/docsfw/bin_test && "$PY" -m unittest discover -p 'test_*.py')

# BL-002: livedocs のスクリプトのテスト
(cd framework/docsfw/livedocs/bin_test && "$PY" -m unittest discover -p 'test_*.py')

# BL-004: 採用範囲を満たさない Python ではスキップすること
(cd framework/docsfw/bin_test && /usr/bin/python3 -m unittest -v \
  test_livedocs_path_spaces.LivedocsPathSpacesTest.test_make_livedocs_with_complete_system_environment)

# BL-005: 指摘がないことと、Doxygen の URL
"$PY" framework/docsfw/bin/text_style_jp.py --dry-run app/cplat/prod/include/cplat/net/socket.h
```

BL-005 の Doxygen の確認は、一時ディレクトリで次を実行し、2 つの URL が閉じ括弧を含まずに出力されることを確かめます。

```bash
D="$SCRATCH/doxy-socket" && mkdir -p "$D" && cd "$D"
printf 'INPUT=%s\nGENERATE_HTML=NO\nGENERATE_LATEX=NO\nGENERATE_XML=YES\nQUIET=YES\nWARN_IF_UNDOCUMENTED=NO\n' \
  "$REPO/app/cplat/prod/include/cplat/net/socket.h" > Doxyfile
doxygen Doxyfile && grep -ho 'ulink url="[^"]*man7[^"]*"\|ulink url="[^"]*sol-socket[^"]*"' xml/*.xml
```

BL-006 の整形の結果が変わらないことは、変更前の docsfw (`git -C framework/docsfw stash` は使わず、`git -C framework/docsfw show HEAD:<path>` で一時ディレクトリへ取り出した版) と変更後の `text_style_jp.py` で、`framework/docsfw/docs/*.md` と `app/cplat/prod/include/cplat/**/*.h` を `-o` で一時ディレクトリへ出力し、`diff -r` で比較して確認します。

`.warn` ファイルを生む C/C++ のビルドの変更はありません。`socket.h` の変更はコメントの空白だけのため、MSVC と GCC のビルドは行いません。

### Windows 側の Claude Code に依頼する確認

主エージェントが変更のパッチを Windows 側へ渡し、Git Bash で次を実行してもらいます。Python は Windows 側の `make livedocs-venv` が選ぶものを使います。

```bash
cd <Windows 側のリポジトリ ルート>
make livedocs-venv
PY=$(python framework/docsfw/livedocs/bin/resolve_python_components.py \
      --venv framework/docsfw/livedocs/.venv --print-python)
export PYTHONSAFEPATH=1 PYTHONIOENCODING=utf-8 BIN_TEST_PYTHON="$PY"

# 1. 自己テストと、Sudachi 辞書の版の記録
"$PY" framework/docsfw/bin/text_style_jp.py --test
"$PY" -m pip show sudachipy sudachidict-core | grep -E '^(Name|Version)'

# 2. docsfw と livedocs のスクリプトのテスト
(cd framework/docsfw/bin_test && "$PY" -m unittest discover -p 'test_*.py')
(cd framework/docsfw/livedocs/bin_test && "$PY" -m unittest discover -p 'test_*.py')

# 3. Doxygen 1.18.0 での socket.h の URL
doxygen --version
D=$(mktemp -d) && cd "$D"
printf 'INPUT=%s\nGENERATE_HTML=NO\nGENERATE_LATEX=NO\nGENERATE_XML=YES\nQUIET=YES\nWARN_IF_UNDOCUMENTED=NO\n' \
  "<Windows 側のリポジトリ ルート>/app/cplat/prod/include/cplat/net/socket.h" > Doxyfile
doxygen Doxyfile && grep -ho 'ulink url="[^"]*man7[^"]*"\|ulink url="[^"]*sol-socket[^"]*"' xml/*.xml
```

報告してもらう内容は、各コマンドの成否、失敗とスキップのテスト名と理由、SudachiPy と sudachidict-core の版、`doxygen --version` の値、`ulink url` の 2 行です。Windows で SudachiPy が未導入の場合、自己テストの初回実行時に `pip install --user` で導入されます。

## 受入条件のまとめ

- 各課題の節の受入条件をすべて満たす。
- Linux の局所テスト (`text_style_jp.py --test`、docsfw と livedocs の `bin_test`) がすべて成功する。BL-004 のテストは、採用範囲を満たす Python で実行されて成功する。
- Windows 側の同じテストが成功し、Doxygen 1.18.0 でも URL に閉じ括弧が含まれない。
- 変更した Markdown に `text_style_jp.py --dry-run` の指摘がない。
- 変更したファイルは、この文書の「変更対象のファイル」の範囲に限られる。
