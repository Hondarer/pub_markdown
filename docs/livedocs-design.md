# 動的発行基盤 (mkdocs)

## 概要

docsfw は 2 本の発行系を持ちます。  
`bin/pub_markdown_core.sh` による静的発行と、mkdocs による動的発行です。  
この文書は動的発行の設計を定めます。

静的発行は、図をビルド時に画像化した self-contained な HTML と docx を、4 バリアント同時に出力します。  
動的発行は、図をブラウザー上の JavaScript でレンダリングする HTML を 1 バリアント出力し、Web サーバーからの配信を前提とします。  
どちらもサイト内ナビゲーションとページ内目次を持ちます。

### 背景

静的発行のパイプラインは、成果物の品質を優先した構成です。  
Pandoc、Lua フィルター 18 本、Node.js (Puppeteer、mermaid-cli、MiniSearch)、Python 後処理を 1 本のシェル スクリプト (2837 行) が統合しています。

この構成では、1 ページの見た目を確認するだけでもワークスペース全体のビルド コストがかかります。  
c-modernization-kit ワークスペースにおける発行対象の実測値を次に示します。

| 指標 | 実測値 |
|---|---|
| 発行対象 Markdown | 766 ファイル |
| うち Doxybook2 生成 | 573 ファイル (74.8%) |
| PlantUML コード ブロック | 2757 出現 / 381 ファイル |
| Mermaid コード ブロック | 38 出現 / 8 ファイル |
| 出力バリアント | `ja` / `en` × 通常 / `-details` の 4 種類 |

PlantUML はすべてビルド時に SVG 化され、docx 出力ではさらに Puppeteer 経由で PNG に変換されます。  
動的発行では、この図生成コストをブラウザー側へ移すことで、ビルド時間を Markdown の変換だけに切り詰めます。  
配信を前提にすることで初めて成立する設計であり、これが静的発行と別系統になっている理由です。

### 位置付け

動的発行は静的発行を置き換えるものではありません。  
静的発行は HTML と docx の正本であり続け、配布可能な成果物を必要とする用途はすべてこちらが担います。  
動的発行は、配信を前提とすることで得られる短いビルド時間、保存に追従する再生成、Doxygen HTML との統合を担います。

| | 静的発行 (`make docs`) | 動的発行 (`make livedocs` / `make servedocs`) |
|---|---|---|
| 成果物 | HTML + docx | HTML |
| 配布 | `file://` で単体動作 | Web サーバーからの配信が前提 |
| バリアント | `ja` / `en` × 通常 / `-details` を同時に出力 | 同じ 4 値を `LIVEDOCS_VARIANT` で 1 つ選ぶ。既定は `ja-details` |
| PlantUML | ビルド時に SVG 化 | ブラウザー上でレンダリング |
| 図の再現性 | 正本 | 差異が出る場合がある (後述) |
| 変更の反映 | 再実行 | `mkdocs serve` 中は保存に追従 |

## docsfw ファンクション ポイントと対応方針

凡例を次に示します。

- **維持**: 同等の機能を実現します。
- **簡略**: 目的は満たしますが、実装または見た目が変わります。
- **対象外**: 動的発行では実現しません。

### 入力と発行対象の決定

| # | ファンクション ポイント | docsfw の実装場所 | 対応 | 備考 |
|---|---|---|---|---|
| 1 | `mdRoot` 配下の再帰収集 | `bin/pub_markdown_core.sh:1762-1790` | 維持 | ステージング スクリプトで再現 |
| 2 | `mergeSubfolderDocs` による仮想マージ | `:1226-1460` | 維持 | 同じ設定を読み `docs/<alias>/` へ配置 |
| 3 | `.md` / `.yaml` / `.json` は `.gitignore` を無視 | `:1791-1855` | 維持 | Doxybook2 生成物を含めるため必須 |
| 4 | `pub_markdown.skip: true` による除外 | `bin/pub-markdown-skip.sh` | 維持 | ステージングで判定 |
| 5 | `index.md` > `README.md` > `SKILL.md` の索引正規化 | `:2325-2352` | 維持 | ステージングで `index.md` にリネーム |
| 6 | OpenAPI の widdershins 変換 | `:2091` | 対象外 | 対象 1 件のみ |
| 7 | `pubpart.yaml` 等の `defaults:` | `:42-89`, `:116-161` | 対象外 | 当該ファイルの実在数 0 |
| 8 | `publocal.yaml` の `order:` | `bin/generate-nav-tree.py:110` | 簡略 | `.nav.yml` 生成フックのみ用意 |

### 前処理

| # | ファンクション ポイント | docsfw の実装場所 | 対応 | 備考 |
|---|---|---|---|---|
| 9 | 多言語ブロック `<!--ja:-->` | `bin/replace-tag.sh` | 維持 | Python へ移植。`LIVEDOCS_VARIANT` の言語側を使う |
| 10 | 詳細ブロック `<!--details:-->` | `bin/replace-tag.sh` | 維持 | Python へ移植。`LIVEDOCS_VARIANT` の details 側を使う |
| 11 | `\toc` によるディレクトリ横断索引 | `bin/pandoc-filters/insert-toc.lua`、`insert-toc.sh` | 簡略 | 実使用の 5 パラメーターのみ再実装。ネスト字下げは 4 スペース (Python-Markdown と list-indent に合わせる) |
| 12 | `short-title` 系の解決 | `bin/extract-short-title.sh` | 簡略 | `title:` フロント マターへ写す |
| 13 | H1 除去と `--shift-heading-level-by=-1` | `:2691-2695` | 対象外 | mkdocs は H1 をページ見出しとして扱う |

### 図の生成

| # | ファンクション ポイント | docsfw の実装場所 | 対応 | 備考 |
|---|---|---|---|---|
| 14 | PlantUML の SVG 化 | `bin/pandoc-filters/plantuml.lua:503-560`, `:731-758` | 簡略 | `@plantuml/core` によるブラウザー描画 |
| 15 | PlantUML の LibDeflate エンコード | `plantuml.lua:157-211` | 対象外 | サーバーを使わない |
| 16 | `skinparam backgroundColor transparent` の注入 | `plantuml.lua:663-668` | 維持 | クライアント側 JavaScript で実施 |
| 17 | `caption` 行と `@startuml <名前>` からのキャプション抽出 | `plantuml.lua:579-644` | 維持 | 同じ優先順を実装。`CodeBlock:` 行がある場合はそちらを優先する点も同じ |
| 18 | SVG の処理命令移動とフォント パッチ | `plantuml.lua:358-400`, `:464-500` | 対象外 | docx 向けの対策 |
| 19 | SVG から PNG への変換 | `plantuml.lua:781-802`、`bin/rsvg-convert.js` | 対象外 | docx 専用 |
| 20 | Mermaid のブラウザー描画 | `bin/pandoc-filters/mermaid.lua:150-166` | 維持 | 同じ方式。ローカルの `mermaid.min.js` を使用 |
| 21 | Mermaid の mmdc 変換 | `mermaid.lua:259-330` | 対象外 | docx 専用 |
| 22 | 共有ブラウザー インスタンス | `bin/browser-server.js` ほか | 対象外 | ビルド時にブラウザーを使わない |
| 23 | draw.io SVG の `foreignObject` 除去 | `bin/strip-foreignobject.py` | 対象外 | ブラウザーは `foreignObject` を解釈できる |
| 24 | 画像リソースの事前コピー | `:2473-2492` | 維持 | ステージングで画像も配置 |
| 58 | SVG のダウンロード ボタン | `styles/html/html-template.html:975-1052` | 維持 | `assets/docsfw-svg-download.js`。画像として参照する SVG に加え、インライン描画した図も直列化して保存する |

### Markdown 記法の変換

| # | ファンクション ポイント | 出現数 | 対応 | 備考 |
|---|---|---|---|---|
| 25 | GitHub アラート 6 種 | 616 | 維持 | `markdown-callouts`。`DEPRECATED` はステージングで変換 |
| 26 | `+hard_line_breaks` | 371 ファイル | 維持 | `markdown.extensions.nl2br` |
| 27 | 表 | 789 | 維持 | `tables` 拡張 |
| 28 | `Table:` キャプション | 73 | 簡略 | ステージングでキャプション段落へ変換 |
| 29 | `CodeBlock:` キャプション | 68 | 簡略 | PlantUML / Mermaid フェンスの直後にある場合は、フェンスとともに `md_in_html` の `figure` へ包む。それ以外は `.docsfw-caption` の段落にする |
| 30 | pandoc-crossref の採番と相互参照 | ラベル 22 / 参照 7 | 対象外 | ラベルは id として残す |
| 31 | 数式 | 51 | 維持 | `pymdownx.arithmatex` と MathJax |
| 32 | 脚注 | 29 | 維持 | `footnotes` 拡張 |
| 33 | タスク リスト | 176 | 維持 | `pymdownx.tasklist` |
| 34 | `==mark==` | 少数 | 維持 | `pymdownx.mark` |
| 35 | `\newpage` / `\pagebreak` | 4 | 対象外 | ステージングで削除 |
| 36 | docx 専用フィルター 8 本 | - | 対象外 | |
| 57 | `implicit_figures` | 画像 12 | 維持 | 画像 1 個だけの段落を、ステージングで `md_in_html` の `figure` へ変換する |

### リンク解決

| # | ファンクション ポイント | 出現数 | 対応 | 備考 |
|---|---|---|---|---|
| 37 | `.md` から `.html` への書き換え | 963 | 維持 | mkdocs が標準で解決 |
| 38 | 実パスと仮想パスの相互変換 | 114 | 維持 | ステージングで書き換える |
| 39 | `README.md` / `SKILL.md` のリンク正規化 | - | 維持 | ステージングで書き換える |
| 40 | Git 単一ページ リンク | フロント マター 392 | 対象外 | 将来対応の候補 |
| 41 | Doxygen 単一ページ リンク | フロント マター 523 | 簡略 | `doxygen-page-url` を `/doxygen/` へ写し、見出し横の操作ボタンへ出す。ヘッダー右端の完全再現はしない |

### 出力とナビゲーション

| # | ファンクション ポイント | 対応 | 備考 |
|---|---|---|---|
| 42 | HTML 出力 | 維持 | mkdocs-material |
| 43 | self-contained HTML 出力 | 対象外 | |
| 44 | docx 出力 | 対象外 | 本基盤の要件どおり |
| 45 | ページ内目次 | 維持 | Material の右サイドバー。`toc_depth: 3` |
| 46 | サイト内ナビゲーション ツリー | 維持 | Material の左サイドバー。自動生成 |
| 47 | ページ内目次のナビゲーション ツリーへのマージ | 維持 | 1400px 以上は左右分離、未満は左ドロワーへ統合 |
| 48 | 全文検索 | 簡略 | Material 標準検索。日本語の既知の弱点があり、緩和策を実装済み (詳細は後述) |
| 49 | `file://` での動作 | 対象外 | `mkdocs serve` の HTTP 前提 |
| 50 | モバイル オフキャンバス ドロワー | 維持 | Material 標準 |
| 51 | 展開可能リスト | 簡略 | Material のナビ折り畳みで代替。ページ本文中の手動 fenced div (`::: {.collapsible-list open-level=N}`) は mkdocs 側に対応する拡張が無いため、`stage_livedocs.py` の `strip_collapsible_list_fences` が開始行と終了行だけを取り除き、中身は折り畳み無しの通常リストとして表示する |
| 52 | コード ブロック エキスパンダーとコピー ボタン | 簡略 | Material の `content.code.copy` |
| 53 | 概要版と詳細版の切替リンク | 対象外 | バリアントを 1 つに固定するため |
| 54 | バリアント コピーとタイムスタンプ スキップ | 簡略 | ステージングの mtime 比較 |
| 55 | 並列実行と無進捗ウォッチドッグ | 対象外 | ビルドが十分に速いため不要 |
| 56 | `docs.warn` への警告抽出 | 簡略 | `mkdocs build --strict` で代替 |

### 発行と直交する機能

`bin/text_style_jp.py` 系の日本語表記スタイル チェッカー、`.text_style_jp/` の辞書、`.agents/skills/` のスキル、`lib/drawio/` の資材は発行パイプラインとは独立しています。  
本基盤の対象外です。

## 構成

### ディレクトリ

```text
framework/docsfw/
+-- livedocs/
|   +-- bin/
|   |   +-- stage_livedocs.py    # ステージング (収集、前処理、リンク書き換え)
|   |   +-- lang_details_filter.py   # replace-tag.sh の Python 移植
|   |   +-- expand_toc.py            # \toc の展開
|   |   +-- vendor_assets.py         # アセットの配置と mkdocs.yml の生成
|   |   +-- livedocs_autostage_hook.py  # mkdocs serve 中の自動ステージング (on_serve hook)
|   |   +-- livedocs_doxygen_hook.py  # /doxygen/ の静的サーブと単一ページ リンク
|   |   +-- livedocs_versioned_hook.py  # 完成済み版を維持する無停止再生成
|   |   +-- stop_livedocs_serve.sh    # このワークスペースの mkdocs serve を停止する
|   +-- mkdocs.yml.in                # 設定テンプレート
|   +-- theme/
|   |   +-- partials/actions.html    # Doxygen 単一ページ リンクのボタン
|   +-- assets/
|   |   +-- docsfw-plantuml.js       # クライアント側 PlantUML レンダラー
|   |   +-- docsfw-mermaid.js        # Mermaid 初期化
|   |   +-- docsfw-mathjax.js        # MathJax の設定
|   |   +-- docsfw-responsive-nav.js # 共通レイアウトと単一ドロワーの制御
|   |   +-- docsfw-svg-download.js   # SVG のダウンロード ボタン
|   |   +-- docsfw-livedocs.css       # 追加スタイル
|   |   +-- docsfw-doxygen-link.css  # Doxygen アイコンのサイズ
|   +-- tests/
|   |   +-- test_livedocs_doxygen.py  # リンク変換と静的サーブの純関数テスト
|   |   +-- test_livedocs_versioned.py  # 再生成中の配信と版切り替えのテスト
|   +-- requirements.txt
|   +-- README.md                    # 利用手順
+-- docs/
    +-- livedocs-design.md     # この文書 (設計の正本)
```

### 生成物

生成物はワークスペースの `pages/livedocs/` 以下に出します。  
`/pages/` はワークスペースの `.gitignore` で除外済みのため、追加の設定は不要です。

```text
pages/livedocs/
+-- mkdocs.yml     # mkdocs.yml.in から生成される実際の設定
+-- theme/         # Material の custom_dir 上書き
+-- src/           # ステージング済み Markdown (docs_dir)
+-- site/          # mkdocs build の出力 (serve 時は未使用)
```

`make cleandocs` は `pages/` 配下から `doxygen` だけを残して削除するため、`pages/livedocs/` も同時に消えます。  
これは意図した挙動です。

## mkdocs serve 中の自動ステージング

### 背景

`mkdocs serve` は既定で `docs_dir` (`pages/livedocs/src/`) だけを監視する。  
執筆者が実際に編集するのは元の Markdown (`app/*/docs` 等) であり、そのままではステージング (`stage_livedocs.py`) を手動で再実行しない限り画面へ反映されない。配信を前提とする発行系である以上、元の Markdown を保存するだけで反映される方が自然なため、`bin/livedocs_autostage_hook.py` を mkdocs の `hooks:` として追加した。

### mkdocs 側の制約

mkdocs 1.6.1 の `LiveReloadServer.watch(path, func=None)` は、変更されたファイルのパスを受け取れるカスタム コールバックを渡せない。`func` は `None` かビルダー本体のみに限定されており、それ以外を渡すと `TypeError` になる  
(`framework/docsfw/mkdocs/.venv/Lib/site-packages/mkdocs/livereload/__init__.py:139-161`)。

このため `livedocs_autostage_hook.py` は、mkdocs 本体が使う `PollingObserver` とは別に、`on_serve` イベントで独自の `watchdog.observers.polling.PollingObserver` を登録し、変更されたファイルを 1 件ずつ捕捉する。`watchdog` は mkdocs 自身の推移的依存としてすでに導入されているが (`watchdog==6.0.0`)、直接 import して使うため `requirements.txt` にも明記した。

以前は `mkdocs.yml` の `watch:` に元の Markdown ディレクトリを列挙し、mkdocs 本体の監視に変更検知だけを任せていた (`vendor_assets.py` の `build_watch_list` が生成)。しかし `docs_dir` はステージング先 (`src/`) のままのため、この `watch:` は「元ファイルの変更を検知してビルドをやり直す」だけで、ビルドに使う内容自体は古いステージング済みコピーのままだった。実質的に反映には寄与しない仕組みだったため、`livedocs_autostage_hook.py` の導入とあわせて `watch:` および `build_watch_list` は削除した。

### ファイル単位の軽量な再ステージングと索引の遅延同期

`stage_livedocs.py` の `stage()` は、索引構築 (`build_stage_index`: `collect_sources` によるワークスペース全体の走査、`DocIndex`、実パス→ステージング後パスの対応表 `real_to_staged` の構築) と、構築済み索引からの書き出し (`stage_index`) に分かれています。  
自動再同期は構築した索引をそのまま書き出しへ渡すため、1 回の全体再同期で索引を二度構築しません。

`livedocs_autostage_hook.py` は起動時に一度だけ `build_stage_index()` を実行し、結果をプロセス内にキャッシュします。  
以降は次の方針で処理します。

- 既知の Markdown ファイルの内容変更では、`stage_single()` でその 1 ファイルだけを再変換して書き出します。ワークスペース全体は再走査しません。
- ファイルの作成、削除、移動、または索引にないファイルの検出では、ディレクトリ構成やファイル一覧が変わるため、直ちに全体再同期します。
- 索引 (`\toc` の一覧、タイトル、リンク対応表) は単一ファイルの再ステージングでは更新しません。最初の内容変更を検知してから 120 秒後に全体再同期します。
- 120 秒の待機中に検知した変更は同じ全体再同期へ集約し、待機期限を延長しません。

### サイト再生成を含む収束

変更検出、単一ファイルのステージング、索引同期、ステージング出力、公開サイトには、それぞれ世代番号を記録します。  
ファイル監視のイベントを受信した時点で変更世代を進めるため、デバウンス待ちや処理ロック待ちの変更も未処理として残ります。

索引再同期でステージング先が変化した場合は、その出力世代を含むサイトが完成版として公開されるまで再同期を完了扱いにしません。  
`livedocs_autostage_hook.py` は `livedocs_versioned_hook.py` が設定したサイト生成関数を包むため、候補サイトの生成だけでなく完成版の公開後に完了を記録します。  
公開前に呼ばれる mkdocs の `on_post_build` は完了判定に使用しません。

サイト再生成中にステージング先が変化した場合、mkdocs 1.6.1 の `LiveReloadServer` は `_want_rebuild` を保持し、現在の生成後にもう一度生成します。  
自動再同期も、生成開始時より新しい出力世代を現在の完成版へ取り込まれたとはみなしません。  
最新の出力世代を含む完成版が公開された後、未処理の変更世代があれば、その時点から次の 120 秒を待ちます。  
したがって、サイト再生成時間は次の待機時間に含まれません。

保証対象は、個々の変更に対する最大反映時間ではなく、変更が止まった後の最終的な安定状態です。  
検出した変更、ステージング、索引、公開サイトの各世代が一致し、デバウンス、タイマー、サイト再生成が残っていない状態を安定状態とします。  
有限回の変更後に索引処理とサイト生成が成功すれば、この状態へ収束します。

索引処理に失敗した場合は、既存の索引キャッシュと公開サイトを維持し、120 秒後に再試行します。  
サイト生成または完成版の公開に失敗した場合は公開世代を進めず、直前の完成版を配信しながら 120 秒後にサイト再生成を再要求します。

### make livedocs-stage を残す理由

上記の自動ステージングは `mkdocs serve` の実行中にしか働かない (`on_serve` フックのため)。次の経路では、引き続き `make livedocs-stage` (フル ステージング) が唯一の同期手段であり、削除していない。

- `make servedocs` が `mkdocs serve` を起動する前の `pages/livedocs/` 一式 (初回の `src/`、`mkdocs.yml`、vendored assets) の準備。
- `make livedocs` (`mkdocs serve` を経由しない one-shot ビルドによるリンク切れ検査)。
- `vendor_assets.py` が扱う JS/CSS アセットや `mkdocs.yml` 自体の更新 (自動ステージングの対象は Markdown のみ)。

## 再生成中の配信

### mkdocs 側の待機動作

mkdocs 1.6.1 の `LiveReloadServer` は、ファイル変更を検知すると再生成の開始時刻を記録し、再生成が完了するまで通常の HTTP 要求を待機させます。  
同じ出力ディレクトリを消去して再生成する途中の内容を配信しないための動作ですが、再生成に時間がかかると、表示済みページから別ページへの移動や CSS などの取得も完了待ちになります。

`bin/livedocs_versioned_hook.py` は、初回生成で完成した出力を公開版として保持します。  
変更検知後の生成先は別の一時ディレクトリとし、生成が正常に完了した場合だけ公開版を次版へ切り替えます。  
生成に失敗した場合は候補版を破棄し、直前の公開版を配信し続けます。

### HTTP 要求と版の寿命

通常の HTTP 要求は、要求開始時の公開版を参照し、mkdocs の再生成完了を待ちません。  
HTML へ挿入する LiveReload の時刻は要求開始時の公開時刻を使用するため、次版の公開後に mkdocs 標準の通知でブラウザーを再読み込みします。

公開版の切り替え時に旧版からファイルを送信中の場合は、その応答が閉じるまで旧版のディレクトリを残します。  
応答が完了して参照数がゼロになった版だけを削除するため、Windows でも使用中のファイルを削除しません。  
初回生成物の一時ディレクトリは mkdocs 自身が所有するためフックから削除せず、フックが生成した一時ディレクトリだけを終了時に回収します。

`/livereload/` は mkdocs 標準の長時間ポーリングへ委譲します。  
`/doxygen/` は `livedocs_doxygen_hook.py` の静的配信へ委譲するため、版管理の対象に含めません。

## Doxygen HTML の静的サーブ

`make doxy` は Doxygen HTML と依存関係レポートを `pages/doxygen/` へ出します。  
このツリーは約 244 MB、約 1.8 万ファイルです。  
動的発行はこれを Markdown 変換せず、`make servedocs` (`mkdocs serve`) の `/doxygen/` として配信します。

`make servedocs` は `make doxy` に依存しません。  
`pages/doxygen/` が無いときはマウントを省略し、配信本体は起動します。

### コピーしない理由

`docs_dir` へコピーすると、mkdocs が毎回 1.8 万ファイルを走査し、Material テーマで包んでしまいます。  
シンボリック リンクとジャンクションは、動的発行が Windows で使わないと決めている手段です。  
`pages/livedocs/site/doxygen/` へネストするとパスが伸び、Windows の MAX_PATH に当たりやすくなります。

そのため配信の正本は `mkdocs serve` の WSGI マウントだけです。  
`bin/livedocs_doxygen_hook.py` が `PATH_INFO` の `/doxygen/` を横取りし、`pages/doxygen/` を直接開きます。  
livereload 用の JavaScript は挿入せず、Doxygen と Cytoscape の HTML を改変しません。  
依存関係レポートの `dependency-data.js` だけは、Page リンクを動的発行のページへ向けるため、HTTP 応答をメモリ上で補正します。

URL は POSIX のまま扱い、ファイルを開くときだけ OS のパスへ結合します。  
`posixpath.normpath` で `..` を潰したあと `/` で分割し、`os.path.join(root, *parts)` します。  
結合結果が `pages/doxygen/` の外なら 404 です。ドライブが違う `ValueError` も 404 です。

`make livedocs` の `site/` には Doxygen ツリーを入れません。  
閲覧の正本は `make servedocs` です。

### 依存関係レポートの Page リンク

依存関係レポートの通常の Page リンクは、docsfw の発行レイアウトを前提とした `../../../{variant}/html/<alias>/<doxybook>/Files/<file>.html` 形式です。  
動的発行には言語階層と `html/` 階層がなく、`use_directory_urls: true` によりページ URL の末尾も `.html` ではなく `/` になるため、そのままでは開けません。

`livedocs_doxygen_hook.py` は `dependency/dependency-data.js` の HTTP 応答を JSON として読み、標準の発行用テンプレートから `/<alias>/<doxybook>` を導出して `livedocsPageUrlTemplate` を追加します。  
ディスク上の `dependency-data.js` とダウンロード用の `dependency-data.json` は変更しません。  
JSON が不正な場合や発行用テンプレートを認識できない場合は、元の JavaScript をそのまま返します。

依存関係レポートは `livedocsPageUrlTemplate` がある場合、Page リンクを `/<alias>/<doxybook>/Files/<file>/` 形式にします。  
動的発行は起動時に選んだ `LIVEDOCS_VARIANT` のみを生成するため、依存関係レポートのページ種別メニューは表示しません。

### 本文リンクの書き換え

README や依存関係レポートのリンクは、docsfw の発行レイアウト (`pages/ja/html/<alias>/...`) を前提に `../../../doxygen/` と書かれています。  
mkdocs は `use_directory_urls: true` で、かつ `ja/html/` 相当の階層が無いため、この相対パスは段数が合いません。

`stage_livedocs.py` はフェンス外の `(?:\.\./)+doxygen/` を `/doxygen/` へ置き換えます。  
Markdown リンクと生 HTML の `href` の両方が対象です。  
絶対リンクは `validation.links.absolute_links: ignore` のため、`pages/doxygen/` が無くてもリンク検査の警告にはなりません。

### Doxygen 単一ページ リンク

doxyfw は Doxybook2 の Markdown へ `doxygen-page-url: "pages/doxygen/...html"` を埋め込みます。  
docsfw の発行ではナビバー右の Doxygen アイコンになります。

動的発行では `pages/doxygen/` を `/doxygen/` へ写し、Material のページ操作ボタン (見出し横) へ出します。  
`target="doxygen-page"` で、単一ページと依存関係レポートが同じタブを再利用します。  
`doxygenLinkEnable` は `.vscode/pub_markdown.config.yaml` を読み、未指定なら有効です。  
リンク先ファイルの存在は確認しません。

ヘッダー右端への配置は、Material の `header.html` を丸ごと上書きすることになり、テーマ更新で壊れやすいため採用しません。  
Git 単一ページ リンクは対象外のままです。

アイコン画像は `styles/html/docsfw-doxygen-icon.svg` を `vendor_assets.py` が実ファイルとしてコピーします。

## PlantUML のブラウザー レンダリング

### 採用するライブラリ

npm の `@plantuml/core` を使用します。  
PlantUML 本体を TeaVM で JavaScript へコンパイルしたもので、Graphviz のレイアウトは WebAssembly の `viz-global.js` が担当します。

参考として、採用に至らなかった選択肢を残します。

| 選択肢 | 状態 |
|---|---|
| `plantuml-core` (CheerpJ 版) | 上流が discontinued。ネイティブ JavaScript ビルドへ移行済み |
| `plantuml.js` | SVG 出力が未実装 (PNG のみ) |
| PlantUML サーバーへの HTTP | 図ごとに通信が発生し、オフラインで動作しない |

`@plantuml/core` は MIT ライセンス版の PlantUML から構築されています。  
docsfw が使用する GPL 版とは一部の図種やスプライトで結果が異なる可能性があります。  
差異の実測結果は「PlantUML の描画差」節に記録します。

### 読み込み方法

`viz-global.js` を classic script として先に読み、`plantuml.js` を ES モジュールとして読みます。  
API は `renderToString(lines, onSuccess, onError)` です。  
`lines` は行の配列で、レンダリングは非同期です。

配布物は `framework/docsfw/bin/package.json` の依存に追加し、`bin/resolve-node-components.js` の解決対象に乗せます。  
`bin/vendor_assets.py` が解決済みの `@plantuml/core` から必要なファイルだけをステージング先へコピーします。

### レンダラーの責務

`assets/docsfw-plantuml.js` は次を行います。

- `pymdownx.superfences` の `custom_fences` が出力した要素から PlantUML ソースを取得します。
- `caption` 行、または `@startuml <名前>` からキャプションを取り、`figcaption` として出力します。優先順は `plantuml.lua:579-644` と同じです。  
  キャプションがある場合はブロックを `figure` で包みます。`CodeBlock:` 行によってステージングがすでに `figure` を作っている場合は、そちらの `figcaption` を優先します。
- `skinparam backgroundColor transparent` を注入します。処理は `plantuml.lua:663-668` と同じです。
- `IntersectionObserver` で、ビューポートに入った図だけをレンダリングします。
- Material のカラー スキームを参照し、ダーク モードの指定を切り替えます。  
  `data-md-color-scheme` 属性が `slate` のとき、`renderToString(lines, onSuccess, onError, { dark: true })` のように第 4 引数へ `{ dark: true }` を渡します。  
  この引数は `render(lines, targetId, { dark })` と同じ内部フラグを共有しており、README には `renderToString` 側の記載がありませんが、`plantuml.js` のコンパイル済みコードで動作を確認済みです。  
  `MutationObserver` (`watchColorScheme()`) がスキーム変更を検知すると、描画済みの図をこのオプション付きで再描画します。

遅延描画は必須です。  
`app/example/docs/sequence.md` のような 1 ページに多数の PlantUML を含む文書や、Doxybook2 のページは各ページにインクルード グラフと呼び出しグラフを持つためです。

## 図の枠とキャプション

静的発行は、キャプションを持つ図を `figure` で包み、枠と中央寄せを与えます (`styles/html/html-style.css` の `figure`)。  
キャプションを持たない図は `figure` になりません。動的発行もこの条件をそろえます。

`figure` は 2 つの経路で組み立てます。

| 経路 | 実装 | 対象 |
|---|---|---|
| ステージング | `bin/stage_livedocs.py` の `convert_captions` | PlantUML / Mermaid フェンスの直後にある `CodeBlock:` キャプション |
| ステージング | 同 `convert_implicit_figures` | 画像 1 個だけの段落 (Pandoc の `implicit_figures` 相当) |
| ブラウザー | `assets/docsfw-plantuml.js` の `addCaption` | PlantUML ソース内の `caption` 行 |

ステージングは `md_in_html` を使い、`figure` の内側を Markdown のまま残します。  
生の `<img>` を出力すると、`use_directory_urls: true` の下で `index.md` 以外のページから画像の相対パスを解決できなくなるためです。  
`figcaption` は `markdown="span"` とします。`markdown="1"` は内側に `<p>` を作り、`figure` 側を `markdown="span"` にすると `nl2br` が余分な `<br>` を作ります。

枠と余白は `assets/docsfw-livedocs.css` の `.docsfw-figure` が与えます。  
キャプションの色は静的発行の `figcaption` と同じく本文色 (`--md-typeset-color`) です。  
枠線は `--md-default-fg-color--lighter` で、静的発行側もこの色を白地で解決した `rgba(0, 0, 0, 0.32)` へそろえています。

## SVG のダウンロード

本文中の SVG へ、ホバー時だけ右上にダウンロード ボタンを重ねます。  
静的発行の `styles/html/html-template.html` にある同名の処理を `assets/docsfw-svg-download.js` へ移植したものです。

静的発行は PlantUML も draw.io も `<img src="*.svg">` のため画像だけを対象にします。  
動的発行は PlantUML と Mermaid をブラウザー上でインライン描画するため、対応する SVG ファイルが存在しません。  
このため描画済みの `<svg>` を `XMLSerializer` で直列化し、`Blob` として保存します。  
描画は非同期のため、`MutationObserver` で `<svg>` の挿入を検知してボタンを付けます。描画側のスクリプトへ呼び出しを埋め込まないため、読み込み順に依存しません。

インライン描画した図のファイル名は、`figcaption` があればそのテキスト、無ければ `<ページ スラグ>-<plantuml|mermaid><連番>.svg` とします。  
静的発行のファイル名 (`puml_<sha1>.svg`) はキャッシュ キーであり、利用者にとって意味を持たないため踏襲しません。

## Mermaid

`custom_fences` で Mermaid のフェンスを `pre.mermaid` として出力し、`assets/docsfw-mermaid.js` が初期化します。  
docsfw の HTML 出力も同じ方式であるため、`styles/html/html-template.html` の初期化処理とサイズ正規化 (viewBox から実寸を取り 0.875 倍する処理) をそのまま流用します。

`mermaid.min.js` は解決済みの Mermaid バンドルから取り出して同梱します。

Material にも Mermaid 連携がありますが、こちらは unpkg から `mermaid.min.js` を取得します。  
docsfw が同梱方式であることと、描画結果を docsfw の HTML 出力にそろえることを優先し、  
クラス名を `docsfw-mermaid` として Material 側の処理と競合しないようにしています。

## mkdocs の設定

`mkdocs.yml.in` の主要部分を次に示します。

```yaml
theme:
  name: material
  language: ja
  font: false
  features:
    - navigation.indexes
    - navigation.sections
    - navigation.top
    - toc.follow
    - content.code.copy
    - search.suggest

markdown_extensions:
  - tables
  - footnotes
  - attr_list
  - md_in_html
  - nl2br
  - toc: { permalink: true, toc_depth: 3 }
  - admonition
  - callouts
  - pymdownx.superfences
  - pymdownx.tasklist: { custom_checkbox: true }
  - pymdownx.mark
  - pymdownx.arithmatex: { generic: true }

plugins:
  - search: { lang: en, separator: "... CJK 文字境界を追加 (後述) ..." }
```

`site_name` は `siteName` と選択中のバリアント名から組み立てます。  
`siteName` は `.vscode/pub_markdown.config.yaml` を読み、未指定ならワークスペース フォルダー名です。  
docsfw はサブモジュールとして任意のワークスペースから使うため、テンプレートにワークスペース名を持ちません。  
静的発行はサイト名の概念を持たず、タイトルをページ単位で扱うため、この設定は動的発行だけが読みます。

同じ理由で、`hooks:` のパスもテンプレートに固定値を持ちません。  
mkdocs は `hooks:` を `mkdocs.yml` の位置を基準に解決するため、`vendor_assets.py` が docsfw の実際の配置と生成先から相対パスを求めて展開します。  
docsfw をワークスペース内の既定位置以外へ置いた場合や、生成先を `--livedocsDir` で変えた場合も、生成後のパスは実ファイルを指します。

`theme.font` は `false` にします。  
本文と等幅のフォントは `extra_css` 側で与えるため、Material 既定の Google Fonts (Roboto / Roboto Mono) は不要です。  
詳細は「フォント」を参照してください。

`mkdocs.yml` には `nav:` を記述しません。  
ステージング時にルートの `.nav.yml` へ `use_index_title: true` を設定し、各フォルダーの `index.md` にある `title` を展開可能なフォルダーの表示名に使用します。  
README または SKILL を `index.md` へ正規化するときに `title` がなければ、選択中の言語と details を反映した最初の H1 を `title` として補います。  
索引ページや有効なタイトルがないフォルダーでは、フォルダー名を使用します。  
`publocal.yaml` に `order:` が存在する場合は、同じ `.nav.yml` に並び順も生成します。

`nl2br` は docsfw の `-f markdown+hard_line_breaks` に相当します。  
本ワークスペースの Markdown は一文一行で記述し、行末の半角空白 2 個による強制改行を 371 ファイルで使用しているため、この拡張が必要です。

## 配色の一致

### 正とする側

`make docs` (pandoc) の配色を正とし、`make servedocs` の CSS だけを調整します。  
静的発行が成果物の正本であり、動的発行はその配色に従うためです。  
`assets/docsfw-pandoc-style.css` は、もともとタイポグラフィと表とコード枠を 静的発行へ寄せるためのファイルです。  
配色もこのファイルに集約します。

例外が 5 つあります。  
見出しと本文の文字色は、どちらか一方を正とせず [見出し書式](heading-style.md) を正本とし、両側をそこへ合わせます。  
TOC の枠や塗りつぶしは Material を正とし、pandoc の `styles/html/html-style.css` を合わせます。  
ページ内目次と左ナビゲーションの状態表現 (通常、通過済み、アクティブ) も Material を正とし、pandoc の `styles/html/docsfw-ui.css` を合わせます。  
admonition の形状とアイコンも Material を正とし、pandoc 側を合わせます。  
スクロール バーは、どちらか一方を正とせず両側を同じ仕様へ寄せます。  
詳細は「見出しと本文の文字色」「admonition の実装」「スクロール バー」「TOC の枠と塗りつぶし」「ページ内目次の状態表現」を参照してください。

`mkdocs.yml.in` の `palette` には `primary` と `accent` を指定しません。  
Material の名前付きパレットに pandoc のリンク色 `#4183C4` は存在せず、CSS 変数の上書きであればライト (`default`) とダーク (`slate`) の双方を 1 か所で扱えるためです。  
`extra_css` は Material の `palette.css` より後に読まれるため、属性セレクター 1 個どうしでも後勝ちで上書きできます。

### フォント

本文と等幅のフォントは 静的発行を正とします。  
本文は `styles/html/html-style.css` の `body`、等幅は同じく `code, tt` の指定に合わせます。

指定は `assets/docsfw-pandoc-style.css` の `body` で、Material の CSS 変数 `--md-text-font-family` と `--md-code-font-family` を上書きして行います。  
Material は `main.css` の `body` でこの 2 つを定義し、`aside, body, input` へ `font-family: var(--md-text-font-family)` を、`code, kbd, pre` へ `font-family: var(--md-code-font-family)` を当てます。  
既定値は `base.html` がインラインの `<style>` で `--md-text-font` と `--md-code-font` へ与え、あわせて Google Fonts を読み込みます。

個別のセレクターではなく変数を上書きするのは、ヘッダー、ナビゲーション、検索 UI、ページ先頭へ戻るボタン (`.md-top`)、フッター、ツールヒントまでを 1 か所で決められるためです。  
`.md-typeset` だけを上書きすると、本文以外は `body` から継承する Material 既定のフォントのまま残ります。

`extra_css` は Material の `main.css` より後に読まれるため、同じ `body` セレクター (詳細度 (0,0,1)) でも後勝ちで上書きできます。  
`.md-tooltip` と `--md-mermaid-font-family` は Material 側が `var(--md-text-font-family)` を明示して参照します。  
`.md-top` は `<button>` で、既定では `font-family` を継承しませんが、Material のリセットが `button` へ `font-family: inherit` を当てているため、こちらも追従します。

自前の font stack を与えるため、`mkdocs.yml.in` の `theme` では `font: false` を指定し、Google Fonts の取得を止めます。  
`--md-text-font` と `--md-code-font` が未定義になりますが、上書き後の `--md-text-font-family` と `--md-code-font-family` はこれらを参照しないため、表示は変わりません。

### 色の対応

| 用途 | pandoc (正) | 出典 | 動的発行 `default` | 動的発行 `slate` |
|---|---|---|---|---|
| 本文リンク | `#4183C4` | `styles/html/html-style.css` の `a` | `#4183C4` | `#6EA9DD` |
| 本文リンク ホバー | `#005580` | Bootstrap `template.css` の `a:hover` | `#005580` | `#9CC7EA` |
| ナビ ホバーと現在ページ | `#1A5FAA` | `styles/html/docsfw-ui.css` | `#1A5FAA` | `#9CC7EA` |
| ページ内目次 通常 | `#212121` | Material `--md-typeset-color` (Material が正) | 同左 | Material 既定 |
| ページ内目次 通過済み | `#757575` | Material `--md-default-fg-color--light` (Material が正) | 同左 | Material 既定 |
| accent 背景に載る文字 | 対応なし | Material `--md-accent-bg-color` | `#FFFFFF` (Material 既定) | `#1F2129` |
| ヘッダー背景 | `#F7F7F7` | `styles/html/html-style.css` の `.navbar-inner` | `#F7F7F7` | `#1F2129` |
| ヘッダー下端 | `#D4D4D4` | 同上 | `#D4D4D4` | `#14161C` |
| ヘッダー文字 | 濃色 | 同上 | `rgba(0,0,0,.87)` | `rgba(255,255,255,.87)` |
| フッター背景 | - | ヘッダーからの流用 | `#F7F7F7` | `#1F2129` |
| フッター上端 | - | 同上 | `#D4D4D4` | `#14161C` |
| フッター文字 | - | 同上 | `rgba(0,0,0,.87)` | `rgba(255,255,255,.87)` |
| NOTE | `#1F6FEB` | `bin/pandoc-filters/admonition.lua` | 同左 | `#58A6FF` |
| TIP | `#238636` | 同上 | 同左 | `#3FB950` |
| IMPORTANT | `#8957E5` | 同上 | 同左 | `#A371F7` |
| WARNING | `#9A6700` | 同上 | 同左 | `#D29922` |
| CAUTION | `#DA3633` | 同上 | 同左 | `#F85149` |
| DEPRECATED | `#6A737D` | 同上 | 同左 | `#8B949E` |
| コード背景 | `#F8F8F8` | `html-style.css` の `code, tt` | 同左 | Material 既定 |
| コード文字 | `black` | 同上 | 同左 | Material 既定 |
| `==mark==` | `#FFFF00` | `html-style.css` の `mark` | 同左 | Material 既定 |
| 本文 | `#212121` | [見出し書式](heading-style.md) | 同左 | Material 既定 |
| 見出し | `#757575` | 同上 | 同左 | `--md-default-fg-color--light` |

本文と見出しの 2 行だけは pandoc を正とせず、[見出し書式](heading-style.md) を正本とします。  
表には、その正本が定めるライトでの値を載せています。

静的発行はライト固定のため、`slate` に対応する正はありません。  
そこで、色相を保ったまま明度を上げた値を使います。  
admonition の 6 色は、pandoc が採用している GitHub のライト色に対応する GitHub のダーク色をそのまま当てます。  
コード背景と `==mark==` は暗背景で成立しないため、`slate` では Material の既定に任せます。

### ヘッダーとフッターを淡色のフラットにする理由

静的発行のヘッダーは Bootstrap の `.navbar-inner` です。  
Bootstrap の既定は、白から `#F2F2F2` への淡いグラデーション、四辺の枠、角丸、外側の影を持つカード風の帯でした。  
`styles/html/html-style.css` でこれらを外し、単色 `#F7F7F7` の帯に下端 1px の境界線 (`#D4D4D4`) だけを残すフラットな表現へ変更しています。  
`text-shadow: 0 1px 0 #FFFFFF` も、グラデーションの上で文字を浮かせるための指定であり、フラットな帯では不要なため外します。

Material の既定は indigo の単色バーであり、本文リンクを `#4183C4` に合わせると、ヘッダーの indigo だけが別系統の青として残ります。  
`--md-primary-fg-color` 系を上書きして同じ淡色に寄せ、`.md-header` へ下端の境界線を足します。

Material はスクロール時に JavaScript で `.md-header--shadow` を付け、ヘッダーの下へ影を落とします。  
静的発行と表現をそろえるため、`.md-header--shadow` の `box-shadow` を `none` で打ち消します。  
`transition` は残すため、ヘッダーの表示と非表示の動きは変わりません。

淡色ヘッダーでは、Material が濃色ヘッダーを前提に指定している検索フォームの背景 (`#00000042`) では入力文字が読めません。  
`default` のときだけ薄いティントへ変更します。

フッターも同じ淡色にそろえます。  
Material の既定は `.md-footer` に `rgba(0,0,0,.87)`、その全面を覆う `.md-footer-meta` に `rgba(0,0,0,.32)` を重ねるため、白地のページの下に黒帯が出ます。

静的発行の HTML に `<footer>` は無く、フッターには正とする対応先が存在しません。  
そのため、ヘッダーと同じ値を流用します。  
`--md-footer-bg-color` 系を上書きし、`.md-footer` へ上端の境界線を足すと、ページの上端と下端が同じ色でそろいます。

背景の 2 変数には同じ値を指定してください。  
`.md-footer-meta` は `.md-footer` の全面を覆うため、値が違うと帯が 2 色に分かれて見えます。

フッターの文字は 3 段階です。  
`--md-footer-fg-color` (ホバー時のリンク)、`--md-footer-fg-color--light` (リンク)、`--md-footer-fg-color--lighter` (「Made with」の地の文) の順に淡くなります。  
不透明度は `--md-primary-bg-color` 系と同じ 0.87 と 0.54 にそろえ、いちばん淡い段は 0.32 とします。

前後ページのリンク (`.md-footer__inner`) は出しません。  
`mkdocs.yml.in` の `features` に `navigation.footer` を入れていないためです。  
フッターに出るのは「Made with Material for MkDocs」だけです。

### admonition の実装

`github-callouts` は `NOTE` / `TIP` / `WARNING` を Material と同名のクラスへ写し、`CAUTION` は `danger` へ写します。  
そのため `caution` ではなく `danger` を対象にします。

`IMPORTANT` は同名のクラスのまま出力されますが、Material に `important` は存在せず、既定の admonition として Note と同じ色で描画されます。  
`deprecated` と同じく、アイコンを含む定義を `assets/docsfw-livedocs.css` へ追加します。  
色は `assets/docsfw-pandoc-style.css` が `--docsfw-admonition-*` で供給し、`docsfw-livedocs.css` 側は `var()` のフォールバックを持たせて単体でも成立させます。

見出し帯の淡いティントは `color-mix()` で基準色から導きます。  
未対応の環境では宣言ごと無視され、Material の既定色に戻るだけで表示は壊れません。

#### 形状とアイコンを Material に合わせる

admonition は、配色だけでなく形状とアイコンも Material を正とし、静的発行をそちらへ合わせます。  
配色の原則 (pandoc が正) の例外です。  
枠付きの表現の方が読みやすいという判断によるもので、`styles/html/html-style.css` と `bin/pandoc-filters/admonition.lua` を変更しました。

pandoc 側の変更点は次のとおりです。

- ブロックは左罫線だけの表現をやめ、全周の枠、角丸、見出し帯にします。ブロック全体を塗っていた淡色の背景は廃止し、見出し帯だけを基準色の 10% で塗ります。
- 見出しの絵文字をやめ、Material と同じ SVG を `mask-image` で描きます。
- クラス名を Material にそろえます。`admonition admonition-note` から `admonition note` へ、`CAUTION` は `github-callouts` に合わせて `danger` へ変更します。
- 見出しの要素を `<p><span class="admonition-title">` から `<p class="admonition-title">` へ変更します。Pandoc の `Para` は属性を持てないため、`RawBlock` で組み立てます。

アイコンの SVG は両側で同一です。  
note / tip / warning / danger は Material の `--md-admonition-icon--*`、Material に無い important / deprecated は `assets/docsfw-livedocs.css` の定義を、`styles/html/html-style.css` へ複写しています。  
別々のパイプラインのため共有はできません。両ファイルに相互参照のコメントを置いています。

docx は対象外です。見出しは絵文字付きのままで、`admonition.lua` の docx 分岐は変更していません。

#### 寸法を px で固定する理由

Material の admonition は `rem` と `em` で寸法を持ちます。  
`html { font-size: 125% }` (1rem = 20px) が基準ですが、`@media (min-width: 100em)` で 137.5% へ上がるため、1600px 以上の画面では動的発行だけが約 10% 大きくなります。

そこで、1rem = 20px として px へ換算した固定値を両側へ置きます。  
`assets/docsfw-pandoc-style.css` が見出しの書式で採っている方針と同じです。

| 部位 | Material | 採用値 |
|---|---|---|
| ブロックの枠 | `.075rem solid` | `1.5px solid` |
| ブロックの角丸 | `.2rem` | `4px` |
| ブロックの左右パディング | `0 .6rem` | `0 12px` |
| ブロックの上下マージン | `1.5625em` (font-size 16px) | `25px` |
| 末尾要素の下マージン | `.6rem` | `12px` |
| 見出し帯の左右マージン | `0 -.6rem` | `0 -12px` |
| 見出し帯のパディング | 上下 `.4rem` / 左 `2rem` / 右 `.6rem` | `8px 12px 8px 40px` |
| 見出し帯の上端角丸 | `.1rem` | `2px` |
| アイコンの寸法 | `1rem` 四方 | `20px` 四方 |
| アイコンの位置 | `left: .6rem` / `top: .625em` | `left: 12px` / `top: 10px` |

`details` と `summary` は Material の指定のままとします。  
発行対象の Markdown に生の `<details>` は無く、`pymdownx.details` も有効にしていないため、admonition と同じ寸法へ寄せる必要がありません。

admonition 内の段落の余白は `8px` です。  
動的発行側は `assets/docsfw-pandoc-style.css` の `.md-typeset p { margin: 0.5em 0 }` がすでに `8px` を与えているため、pandoc 側の `.admonition p` をそこへ合わせます。  
pandoc 側の本文全体は Bootstrap `template.css` の `p { margin: 0 0 10px }` のままで、admonition の内部だけ `8px` になります。

なお `.admonition-title` も `p` 要素です。  
`.admonition p` (詳細度 0,1,1) が `.admonition-title` (0,1,0) に勝つため、見出し帯の指定は `.admonition > .admonition-title` (0,2,0) と子結合子で書きます。  
そうしないと見出し帯に段落の余白が入り、枠との間に隙間ができます。

### スクロール バー

スクロール バーは、どちらか一方を正とするのではなく、両側を同じ仕様へ寄せます。

#### そろえる前の状態

`make servedocs` の Material は、`.md-sidebar__scrollwrap`、`.md-typeset pre > code`、`.md-search__scrollwrap`、`.md-tooltip2__inner` の 4 か所だけを細く塗ります。  
ページ本体はブラウザーの既定のままです。

静的発行は、`styles/html/` には指定がありませんが、CDN から読む Bootstrap テンプレート `template.css` がセレクターなしの全称指定を持っています。

```css
::-webkit-scrollbar       { width: 12px; height: 12px; }
::-webkit-scrollbar-track { background: rgba(0, 0, 0, 0.1); }
::-webkit-scrollbar-thumb { background: rgba(0, 0, 0, 0.5); }
```

これがページ本体を含むすべてのスクロール領域へ効きます。  
同じページを 1400x900 で描画して画素を計測すると、次の差がありました。

| | make docs | make servedocs |
|---|---|---|
| thumb の幅 | 12px | 6px |
| thumb の色 | `#727272` | `#ADADAD` |
| トラック | `#E5E5E5` (可視) | 透明 |
| ページ本体 | 12px / `#E5E5E5` / `#727272` | 15px / `#FCFCFC` / `#8B8B8B` (ブラウザー既定) |

#### そろえた後の仕様

幅 6px、角丸のない四角い thumb、トラックは `--md-default-fg-color--lightest` (白地で約 `#EDEDED`)、thumb の色は `--md-default-fg-color--lighter` (白地で `#ADADAD`) にそろえます。  
トラックは thumb より薄い前景色で、スクロール可能領域の存在だけを示します。  
ページ本体のスクロール バーも対象に含めます。

コード ブロックの上では thumb が `#A8A8A8` と計測されますが、これは同じ色の指定がコード ブロックの背景 `#F8F8F8` の上に載るためで、指定は同一です。

#### 実装で守る 2 つの制約

計測で分かった Chrome の挙動が、実装方法を縛ります。

1. `scrollbar-width: auto` と `scrollbar-color: auto` では、Bootstrap の `::-webkit-scrollbar` を打ち消せません。`auto` は「指定なし」を意味し、擬似要素側の描画に戻るだけです。そのため「両方ともブラウザー既定へ戻す」案は成立せず、明示指定でそろえます。
2. `scrollbar-width: thin` を指定すると、Chrome は `::-webkit-scrollbar` 系ではなく標準側の描画へ切り替わり、thumb が角丸になって幅も変わります。四角い thumb を保つため、Chrome へは `scrollbar-width` を渡しません。

この結果、実装は次の切り分けになります。

- Chrome と Edge は `::-webkit-scrollbar` 系の擬似要素だけで指定します。Material が 4 か所へ入れている `scrollbar-width` と `scrollbar-color` は、`@supports selector(::-webkit-scrollbar)` の中で `auto` へ戻します。ホバー時の指定も同時に戻さないと、ホバーした瞬間だけ角丸へ変わります。
- Firefox は擬似要素に対応しないため、`@supports not selector(::-webkit-scrollbar)` の中で標準プロパティを与えます。`scrollbar-color` と `scrollbar-width` は継承するので、`html` への指定がすべてのスクロール領域へ届きます。

Material が個別に持つ `::-webkit-scrollbar` は全称指定より詳細度が高いため、同じセレクターでサイズをそろえます。  
`.md-tabs__list` と `.md-typeset .tabbed-labels` は `::-webkit-scrollbar { display: none }` を持ち、全称指定より詳細度が高いので非表示のまま保たれます。

#### ホバー時の着色

Material は、スクロール バーにホバーしたとき thumb をアクセント色で着色します。  
静的発行にホバーの指定はないため、着色をやめて通常時と同じ色に固定します。

Material は標準の `scrollbar-color` と `::-webkit-scrollbar-thumb` の 2 通りで指定しています。  
`::-webkit-scrollbar-thumb:hover` だけを上書きしても着色は消えないため、両方を上書きします。

上書きは Material と同じセレクターで行い、詳細度をそろえます。  
Material 側の指定は `@media (min-width: 60em)` の中にもありますが、メディア クエリは詳細度を変えないため、後から読まれる `extra_css` が勝ちます。

### 見出しと本文の文字色

ここは Material も pandoc も正とせず、[見出し書式](heading-style.md) を正本とし、両側をそこへ合わせます。  
書式の一覧と、大きさや太さを含む全体の規則は正本を参照してください。  
この節では、`make servedocs` 側で必要になる調整だけを述べます。

濃さは 2 段です。  
本文の `#212121` がいちばん濃く、見出しは `#757575` で本文より淡くなります。

| 対象 | 動的発行の指定 | 白地での値 |
|---|---|---|
| 見出し (Markdown の H1 - H6) | `--md-default-fg-color--light` | `#757575` |
| 本文 | Material 既定の `--md-typeset-color` | `#212121` |

本文の色は Material の既定がすでに仕様どおりであるため、`assets/docsfw-pandoc-style.css` では指定しません。  
pandoc 側は `body` に `color` の指定がなく Bootstrap の `#333333` が効いていたため、`styles/html/html-style.css` の `body` へ `#212121` を追加しました。

見出しの色は直値で書かず `var(--md-default-fg-color--light)` を使用します。  
ダーク (`slate`) でも「見出しは本文より淡い」という関係が保たれるためです。

Material の既定のうち、次の 3 つは打ち消す必要があります。

- 全レベルの `letter-spacing: -.01em`
- `h5` の `text-transform: uppercase`
- `em` 基準の `margin` と、`h2` 直後の `h3` だけ上余白を `.8em` にする `.md-typeset h2 + h3`

`.md-typeset h2 + h3` は詳細度が (0,1,2) であり、レベルごとの指定 (0,1,1) より高いため、同じセレクターで上書きします。

### リンクのホバー

ホバー時は下線ありに統一します。

静的発行は、本文リンクが Bootstrap の `a:hover`、ナビゲーション ツリーが `docsfw-ui.css` の `#docsfw-tree a:hover` で、いずれも下線を引きます。  
Material は色を変えるだけで下線を引かないため、`.md-typeset a` と `.md-nav__link` のホバーとフォーカスに `text-decoration: underline` を足します。

見出しのアンカー (`.headerlink`) は本文リンクではないため、対象から外します。  
アンカーは静的発行でも `docsfw-nav.js` が付与します。仕様は [見出し書式](heading-style.md) を正本とし、Material 側は遷移だけを打ち消します。

ナビゲーションの色と下線は、Material と同じ形のセレクターで指定します。  
`.md-nav__link:hover` の詳細度 (0,2,0) では、Material が左ナビの現在ページへ当てる `.md-nav--primary .md-nav__item--active > .md-nav__link:hover` (0,4,0) に負け、ナビの色 `#1A5FAA` ではなく本文リンクのホバー色 `#005580` が出るためです。  
アクティブ側も同じ理由で、`.md-nav__link--active` (0,1,0) は Material の `.md-nav__item .md-nav__link--active` (0,2,0) に負けます。  
`extra_css` は `main.css` より後に読まれるため、詳細度を同じまで上げれば後勝ちします。

色の変わり方は静的発行を正とし、瞬時に切り替えます。  
Material は `.md-nav__link` に `transition: color 125ms` を持ちますが、静的発行に対応する指定がないため `transition: none` で打ち消します。  
`.md-nav` の `transition: max-height` は狭い画面のドロワー開閉に必要なので、対象にしません。

### TOC の枠と塗りつぶし

`make docs` の TOC は、`styles/html/html-template.html` が `<div class="well toc">` として出力します。  
`well` は Bootstrap `template.css` (CDN) のクラスで、塗りつぶし `#F5F5F5`、枠 `#E3E3E3`、角丸 4px、内側の影を持つカード風の装飾です。

`make servedocs` の Material は、デスクトップ幅では `.md-sidebar { padding: 1.2rem 0 }` だけを持ち、背景も枠も影もありません。  
そこで `#TOC > .well` でカードの装飾を打ち消し、素の一覧の見た目にそろえます。

`padding` は Bootstrap の 19px のまま残します。  
カードが消えれば見えない余白になるだけで、TOC の字下げと横幅、本文の開始位置が変わらないためです。

`.well` はテンプレート内で TOC にしか使われていないため、この指定の影響は TOC に閉じます。  
1400px 未満ではページ内目次を左ドロワーへ移すため、右側の `.well` は表示しません。

TOC 内の区切り (`.toc-navi + ul` の `border-top` と `hr.docsfw-toc-separator`) は、狭い画面で文書ツリーとページ内目次を区切るために使用します。

### ページ内目次の状態表現

読んでいる位置を示す表現は Material を正とし、pandoc の `styles/html/docsfw-ui.css` を合わせます。  
状態は次の 4 つです。

| 状態 | 白地 (`default`) | ダーク (`slate`) | 由来 |
|---|---|---|---|
| 通常 (未通過) | `#212121` | Material 既定 | Material の `--md-typeset-color` |
| 通過済み | `#757575` | Material 既定 | Material の `--md-default-fg-color--light` |
| アクティブ | `#1A5FAA` | `#9CC7EA` | 「色の対応」の「ナビ ホバーと現在ページ」 |
| ホバーとフォーカス | `#1A5FAA` | `#9CC7EA` | 同上。下線を引く |

強調に太字は使いません。  
太字は文字幅が変わるため、幅 210px の目次ではスクロール追従のたびに省略記号 (`text-overflow: ellipsis`) の出方が変わり、行の見え方が動きます。  
色だけで示せば、追従しても幅は変わりません。

同じ理由で、静的発行の左ナビゲーション ツリーからも現在ページの太字を外します。  
現在ページは色と左のアクセント バーで示します。  
アクセント バーの `#4A90D9` は「一致させない項目」のとおり、動的発行に対応物がありません。

「通過済み」は、現在の見出しより上にある見出しすべてに付きます。  
現在の見出しにも付きますが、アクティブの色が後勝ちします。  
Material は `md-nav__link--passed` を、静的発行の `styles/html/docsfw-nav.js` は `docsfw-toc-passed` を付与します。

指定の順序は「通常」「通過済み」「アクティブ」「ホバー」です。  
`docsfw-ui.css` の 4 つの規則は詳細度が等しいため、後に置いたものが勝ちます。  
Material もホバーの詳細度 (0,3,0) がアクティブ (0,2,0) より高く、ホバーが最優先である点は同じです。

項目の間隔も Material に合わせ、リンク 1 件ごとに上へ `8.75px` を取ります。  
Material の `.md-nav__link` が持つ `margin-top: .625em` を、両側でそろえている 14px を基準に換算した値です。  
先頭のリンクでも打ち消しません。Material も同じで、余白は外側の `.well` の `padding` に吸収され、目次の開始位置は変わりません。

節番号はリンクの文字色に従わせます。  
静的発行は `docsfw-nav.js` の `normalizeTocLinks()` が目次リンクを 1 つのテキスト ノードへ平坦化するため、`span.toc-section-number` は実行時に存在せず、番号はリンクの色になります。  
動的発行は Material の `::before` にカウンターで番号を出すので、`--md-default-fg-color--light` による独自の色付けをやめて同じ扱いにします。  
これにより、通過済みとアクティブでも番号と本文が同じ色で動きます。

静的発行の目次には Bootstrap の `template.css` (CDN) が `.toc ul > li > a` (0,2,3) で `padding: 3px 15px` を当て、`.toc ul > li > a:hover` で `text-decoration: none` と `background-color: #eeeeee` を当てます。  
どちらも `docsfw-ui.css` の指定より詳細度が高いため、行間もホバーの下線も効かず、ホバーで灰色の帯が出ていました。  
また 1400px 未満では目次が文書ツリーの中へ移るため、`#docsfw-tree a` (1,0,1) が状態の色に勝ちます。

そこで `docsfw-ui.css` の目次の状態指定は、クラスではなく `#docsfw-page-toc` を起点にします。  
`#docsfw-page-toc a` は両方より詳細度が高いか同等で、同等の `#docsfw-tree a` に対してはファイル内で後に置いて勝たせます。  
Bootstrap の `padding` とホバーの装飾は、`#docsfw-page-toc ul > li > a` と `#docsfw-page-toc ul > li > a:hover` で打ち消します。

ページ先頭で、どのリンクをアクティブにするかは一致させません。  
静的発行は常に先頭の見出しをアクティブにし、Material は最初の見出しを通過するまでどれもアクティブにしません。  
目次として現在位置が常に 1 つ示される方が分かりやすいため、静的発行の挙動を残します。

### ナビゲーションの幅と切り替え

Pandoc HTML と mkdocs は、1400px 以上で左 240px、本文約 870px、右 210px の三列を 25px 間隔で表示します。  
全体幅は 1370px です。

1400px 未満では本文を最大 870px で中央配置し、`docsfw-responsive-nav.js` が Material のページ内目次を左の文書ナビゲーション内へ移します。  
画面幅の変更時は同じ DOM 要素を元の右サイドバーと左ドロワーの間で移し、Material の `toc.follow` と現在見出し表示を維持します。

### 一致させない項目

- `styles/html/docsfw-ui.css` が検索 UI とナビゲーション ツリーに使う `#4A90D9`。Material の検索 UI とは構造が異なり、動的発行に対応物がありません。

## make からの起動

ワークスペースのルート `makefile` に次のターゲットを置きます。  
静的発行の `docs` ターゲットは変更しません。

| ターゲット | 内容 |
|---|---|
| `servedocs` | 既存のこのワークスペースの `mkdocs serve` を止めてからステージングし、`mkdocs serve` を起動する。`LIVEDOCS_VARIANT` で言語と details を選ぶ (既定 `ja-details`) |
| `livedocs` | ステージング後に `mkdocs build` を実行する。`LIVEDOCS_STRICT=1` のときは `--strict` を付ける。バリアントは `servedocs` と同じ |
| `livedocs-stage` | ステージングとアセット配置だけを実行する。`servedocs` と `livedocs` の前提 |
| `livedocs-venv` | `livedocs/.venv` を作成し `requirements.txt` の依存を導入する。未作成のときだけ動く |
| `stopdocs` | このワークスペースの動的発行の venv で動いている `mkdocs serve` を停止する |
| `cleanlivedocs` | serve を停止してから `pages/livedocs/` を削除する |

ルートの `make clean` は `cleandocs` を呼び、`cleandocs` と `cleanlivedocs` は削除の前に `stopdocs` を実行します。  
`mkdocs serve` は `pages/livedocs` を監視し続けるため、Windows では削除対象が busy になり `rm -rf` が失敗します。  
`stopdocs` はこのワークスペースの動的発行の venv をコマンド ラインに含み、かつ引数がちょうど `serve` であるプロセスとその子孫だけを止めます。  
ポート番号や作業ディレクトリだけでは判定しません。  
Linux では TERM のあと残っていれば KILL します。プロセス グループ全体へは送りません。`make servedocs` は端末とグループを共有するためです。  
Windows では SIGTERM がネイティブの python や watchdog に届かず、親だけが先に死ぬとハンドルが残ります。  
そのため `/proc/<pid>/winpid` 経由で `taskkill /T /F` し、ツリーごと終了します。  
停止直後でもハンドルが残ることがあるため、削除は短い間隔で最大 5 回やり直します。  
対象プロセスが無い、または停止しきれない場合も `stopdocs` 自体は失敗しません。削除できなければ `clean` が失敗します。

`make servedocs` はステージングの前に同じ停止処理を `--require-stopped` 付きで実行します。  
先に動いていたこのワークスペースの `mkdocs serve` が消えるまで待ち、消えてからステージングします。  
バリアントが違うと `pages/livedocs/src/` の本文が差し替わるため、古い serve が監視したまま書き込むと、旧バリアントと新バリアントが混ざります。  
止めきれなければステージングへ進まず失敗します。`stopdocs` と `cleanlivedocs` は、停止しきれなくても失敗しません。  
停止とステージングはレシピ内で順に実行し、`make -j` でも同時に走らないようにします。  
先に起動した側の `make servedocs` は、`mkdocs serve` が止まった時点で終了します。

Python の依存は `framework/docsfw/livedocs/.venv` に閉じ込め、`requirements.txt` で固定します。

### バリアントの指定

`make docs` と同じ 4 値を、起動時に 1 つだけ選びます。同時に 4 系統は出しません。

| `LIVEDOCS_VARIANT` | 言語 | 詳細ブロック | `make docs` の出力に相当 |
|---|---|---|---|
| `ja` | ja | 除く | `pages/ja/html/` |
| `ja-details` (既定) | ja | 残す | `pages/ja-details/html/` |
| `en` | en | 除く | `pages/en/html/` |
| `en-details` | en | 残す | `pages/en-details/html/` |

```bash
make servedocs
make servedocs LIVEDOCS_VARIANT=en
make livedocs LIVEDOCS_VARIANT=ja
```

選んだ値はステージングと `mkdocs.yml` の `extra.livedocs_variant` に書き、serve 中の自動ステージングも同じフィルターを使います。  
切り替えるときは `make servedocs` を再起動します。後から起動した `make servedocs` が、先に動いていた serve を止めて置き換わります。  
ページ内の概要 / 詳細切替リンクは出しません。

## 静的発行だけが持つ機能

次の機能は動的発行では扱いません。必要な場合は `make docs` を使用します。

- Word (docx) 出力と、docx 専用フィルター、rsvg-convert、共有ブラウザー
- 4 バリアントの同時出力と、ページ内の概要 / 詳細切替リンク
- pandoc-crossref による図表とリストの採番、および相互参照
- Git 単一ページ リンク
- self-contained HTML と `file://` での動作
- OpenAPI からの Markdown 生成
- MiniSearch と CJK bigram による日本語全文検索

全文検索について補足します。  
docsfw は重なり 2-gram のトークナイザーを自前で実装し、日本語の検索精度を確保しています。  
mkdocs-material の標準検索 (`lang: ja`) は lunr と TinySegmenter を使用しますが、TinySegmenter には複合語の分割漏れという upstream の既知バグがあり、日本語の長い複合語を取りこぼします。

実測した挙動 (`lang: ja` 使用時) を次に示します。

| 検索語 | 結果 |
|---|---|
| 同期 | 294 件 |
| ビルド | 130 件 |
| モック | 23 件 |
| 同期プリミティブ | 0 件 |

2 文字程度の語やカタカナ語は引けますが、`同期プリミティブ` のような複合語は引けません。  
また `同期` が `同梱` にも一致するなど、分かち書きの精度は docsfw の 2-gram より劣ります。

mkdocs-material のメンテナーは、この不具合を「TinySegmenter (lunr-languages が使用) 側のバグであり、mkdocs-material では直せない」と upstream に帰責しています  
([squidfunk/mkdocs-material Discussion #3916](https://github.com/squidfunk/mkdocs-material/discussions/3916))。  
検索クエリのトークン化処理を差し替える機能も、2026 年 8 月時点で未実装です  
([squidfunk/mkdocs-material Issue #4980](https://github.com/squidfunk/mkdocs-material/issues/4980))。

#### 緩和策 (実装済み)

`mkdocs.yml.in` の `plugins.search` で、`lang: ja` (TinySegmenter) をやめ、`separator` の正規表現に「隣接する CJK 文字 (ひらがな/カタカナ/漢字) の間」を境界として追加している。

lunr の `separator` は索引構築時とクエリ解析時の両方に同じ正規表現が使われるため、TinySegmenter のような言語別の分かち書きに頼らずに、文字単位に近い粒度で索引語とクエリを対称に分割できる。  
これにより `同期プリミティブ` のような複合語も検索でヒットするようになる。

再現率を優先するトレードオフとして、`同` のような 1 文字の一致でもヒットしやすくなり、docsfw の  
2-gram 実装と同程度のノイズ (無関係な部分一致) が生じる。`lang: en` を明示しているのは、  
Porter stemmer や英語ストップワード フィルターが ASCII 文字列にしか作用しないため日本語トークンへの  
副作用がなく、かつ `lang: ja` を指定した場合に自動的に読み込まれる TinySegmenter を確実に外すためである。

見直しの合図: 上記 Discussion #3916 または関連 issue で TinySegmenter 側の根本修正が upstream で  
取り込まれた場合、あるいは mkdocs-material 側でクエリ トークン化のカスタム パイプライン  
(Issue #4980) が実装された場合は、この緩和策 (`separator` への CJK 境界追加と `lang: en` 指定) を  
見直すこと。

索引の大きさは 791 ページで約 13 MB です。  
初回の検索操作から結果が出るまで、ブラウザー上で約 10 秒の索引構築が入ります。  
docsfw の `search-index.js` はビルド時に構築するため、この待ち時間はありません。

## PlantUML の描画差

`@plantuml/core` 1.2026.7 (MIT ライセンス版、ブラウザー) と、ローカルの PlantUML 1.2026.2 (GPL 版、CLI) で  
[PlantUML ショーケース](sample/plantuml-showcase.md) の 19 図を描画し、SVG の viewBox 面積と text 要素数を比較しました。

結果は次のとおりです。

| 判定 | 図種 | 内容 |
|---|---|---|
| 一致 | Sequence, Use Case, Class, Object, Activity, Component, Deployment, State, Timing, Network, Mindmap, WBS, Work Breakdown, JSON, YAML, EBNF, Regex (17 図) | 面積比 0.77 〜 1.21。text 要素数は Class を除いて一致 |
| 差あり | Gantt | ブラウザー側に Start / End / Duration の一覧が付き、面積比 1.80。PlantUML のバージョン差と考えられる |
| 非対応 | Salt | `@startsalt` が「Diagram not supported by this release」となり、エラー図が返る |

面積比の 0.8 前後から 1.2 前後の差は、ブラウザーと Java AWT のフォント計測の違いによるものです。  
図の内容そのものは一致します。

Salt は現時点の `@plantuml/core` では描画できません。  
Salt を含むページを確認する場合は `make docs` を使用してください。

### skinparam の挿入位置

`skinparam backgroundColor transparent` とスタイル設定は、`@start<種別>` の行の直後へ挿入します。  
この規則は静的発行の `bin/pandoc-filters/plantuml.lua` と、動的発行の `assets/docsfw-plantuml.js` で共通です。

もともと `plantuml.lua` は挿入位置を `@startuml` / `@startmindmap` / `@startjson` / `@startyaml` の  
4 種類だけから探していました。  
`@startebnf` や `@startregex` では該当行が見つからず、`@start` より前の行へ挿入されます。

PlantUML の CLI とサーバーは `@start` より前の行を無視するため、docsfw では表面化しませんでした。  
一方 `@plantuml/core` は認識できない指示としてエラー図を返します。

そのため、探索を `@start<種別>` 全般 (Lua は `^%s*@start%w+`、JavaScript は `/^\s*@start\w+/`) へ広げ、  
docsfw 側にも同じ対策を入れました。

変更の影響は次のとおり確認済みです。

- ショーケースの 19 図を GPL 版 CLI (1.2026.2) で描画し、すべて成功しました。viewBox は変更前と同一です。
- `plantuml.lua` を直接通した 19 図も、すべて成功し viewBox が変更前と同一でした。
- `@startuml` 系の図は挿入位置が変わらないため、キャッシュ キー (SVG のファイル名) も変わりません。  
  列挙外の図種だけファイル名が変わるため、既存の出力には古い SVG が残ります。`make cleandocs` で解消します。

### キャプションの採用範囲

`caption` 行がないとき、`@start<種別>` に続く名前をキャプションとして採用します。  
この探索も、もとは `@startuml` / `@startmindmap` / `@startjson` / `@startyaml` の 4 種類だけが対象でした。  
挿入位置と同じく `@start<種別>` 全般へ広げ、`plantuml.lua` と `assets/docsfw-plantuml.js` の双方にそろえています。

パターンは Lua が `^%s*@start%w+%s+(.+)%s*$`、JavaScript が `/^\s*@start\w+\s+(.+?)\s*$/` です。  
名前のない `@startuml` は空白の繰り返しが 1 個以上必要なため、対象になりません。

旧実装との差は次のとおりです。

| 入力 | 旧 | 新 |
|---|---|---|
| `@startuml sequence-sample` | `sequence-sample` | 同じ |
| `@startjson JSON Example` | `JSON Example` | 同じ |
| `@startuml` | 採用しない | 同じ |
| `@startgantt gantt-sample` | 採用しない | `gantt-sample` |
| `@startwbs wbs-sample` | 採用しない | `wbs-sample` |
| `@startsalt` / `@startebnf` / `@startregex` の名前 | 採用しない | 採用する |
| `@startuml ` (名前なし、末尾に空白) | 空白 1 文字を採用 | 採用しない |

最後の 1 件だけが採用されなくなります。  
旧実装が空白 1 文字をキャプションとして拾っていたもので、本ワークスペースに該当行はありません。

本ワークスペースで列挙外の図種を名前付きで使っている 5 件 (`@startwbs`, `@startgantt`, `@startsalt`,  
`@startebnf`, `@startregex`) は、いずれも `caption` 行を明示しています。  
`caption` 行が優先されるため、現時点の出力は変わりません。  
ショーケースの 19 図を `plantuml.lua` へ通し、キャプションが変更前と一致することを確認しました。

## 検証方法

### ビルドの健全性

```bash
make livedocs
```

`LIVEDOCS_STRICT=1` を付けると `mkdocs build --strict` になります。

791 ファイルのステージングは約 1.4 秒、`mkdocs build` は約 53 秒、合計で約 55 秒です。  
docsfw の `make docs` は 4 バリアントの HTML と docx を生成するため、これより桁違いに長くかかります。

#### リンク検証

Doxygen HTML への本文リンクは `/doxygen/` へ書き換えるため、MkDocs の文書リンク検査では扱いません。  
その他の相対リンクは、ステージング後の論理ツリーに存在する対象だけを有効なリンクとして残します。  
静的発行と動的発行に共通する判定規則は、[リンク解決の規則](link-resolution.md) に定めます。

`README.md` と `SKILL.md` は、同じディレクトリの優先順位に従って `index.md` へ読み替えた後の論理パスへ書き換えます。  
論理ツリー外の README、AGENTS、ソース コード、ヘッダー、ディレクトリ、未生成ファイルへの参照は、動的発行へ対象ファイルを追加せず、表示文字列と元のパスを残した非リンクの参照へ変換します。

この変換により、動的発行は公開対象外のファイルを誤って公開せず、元の参照情報も保持します。  
リンク切れの確認は次の strict ビルドで行えます。

```bash
make livedocs LIVEDOCS_STRICT=1
```

存在しない相対リンクを別のファイルへ推測して書き換えることはありません。  
リンク先が論理ツリーに存在しない場合は、原文側の参照先を修正するか、対象ファイルを発行対象へ追加してください。

見出しの id は `pymdownx.slugs.slugify` で GitHub と同じ規則にそろえています。  
Python-Markdown の既定では非 ASCII が落ちるため、この設定がないと日本語見出しへのリンクが約 35 件切れます。

### 表示の確認

```bash
make servedocs
```

次のページを確認します。

| 確認対象 | ページ | 確認内容 |
|---|---|---|
| PlantUML の多量描画 | `app/example/docs/sequence.md` | 遅延描画がスクロールに追従すること |
| PlantUML の図種 | `framework/docsfw/docs/sample/plantuml-showcase.md` | 図種ごとの描画結果と docsfw との差異 |
| Mermaid | `framework/docsfw/docs/sample/mermaid-showcase.md` | 描画とサイズ正規化 |
| キャプション | `framework/docsfw/docs/sample/mermaid-caption.md` | `CodeBlock:` 由来のキャプション |
| `\toc` の展開 | `docs/README.md` | 索引の内容と越境リンクの解決 |
| Doxybook2 ページ | `app/example/docs/doxybook2_public/` 配下 | ナビゲーション、目次、グラフの描画 |
| Doxygen HTML | `/doxygen/example_public/index.html` | `make doxy` 済みなら無変換で表示されること |
| 依存関係レポート | `/doxygen/example_internal/dependency/index.html` | Cytoscape の HTML と付随アセットが読み込まれること |
| 依存関係レポートの Page リンク | `/doxygen/example_internal/dependency/index.html` | 配信中のファイル ページと関数アンカーを開くこと |
| Doxygen 単一ページ リンク | `doxygen-page-url` を持つ Doxybook2 ページ | 見出し横のアイコンが `/doxygen/...` を `target="doxygen-page"` で開くこと |
| GitHub アラート | 各 app の `coding-guideline.md` | 6 種の表示。特に `DEPRECATED` |
| 数式 | `app/example/docs/build-design.md` | MathJax の描画 |
| 日本語パス | `framework/docsfw/docs/sample/日本語を含むサブフォルダ/` | パス解決とナビゲーション表示 |
| 検索 | 任意 | 日本語語句での検索 |

### クロスプラットフォーム

Windows の Git Bash と Python でも `make livedocs` が通ることを確認します。  
ステージングは Python で実装するため、シェル スクリプトへの依存を持ちません。  
シンボリック リンクは Windows で不安定なため使用せず、実ファイルのコピーで構成します。  
`pages/doxygen/` もコピーせず、`make servedocs` の WSGI が直接読みます。Windows でもジャンクションは使いません。  
`make livedocs` の `site/` には Doxygen ツリーを入れないため、Doxygen HTML の閲覧確認は `make servedocs` で行います。

### docsfw への非干渉

`make docs` が従来どおり成功し、`pages/ja/html/` 等の出力が変わらないことを確認します。  
`bin/package.json` への依存追加が、`bin/resolve-node-components.js` の必須集合と [Node コンポーネント](node-components.md) に反映されることを確認します。

## 実装状況

| ステップ | 内容 | 状態 |
|---|---|---|
| 0 | 設計ドキュメントの作成 | 完了 |
| 1 | ステージング基盤 | 完了 |
| 2 | `\toc` の展開 | 完了 |
| 3 | mkdocs 設定とテーマ資産 | 完了 |
| 4 | PlantUML のクライアント レンダラー | 完了 |
| 5 | make 統合と文書化 | 完了 |
| 6 | Doxygen HTML の静的サーブと単一ページ リンク | 完了 |
| 7 | 配色の pandoc への一致 | 完了 |

### 実装で判明したこと

- `pymdownx.superfences` の `custom_fences` が出す要素は、Material の Mermaid 連携と競合します。クラス名を `docsfw-mermaid` に変えて回避しました。
- GitHub アラート記法には `markdown-callouts` の `callouts` ではなく `github-callouts` が必要です。`callouts` は `NOTE:` 形式だけを扱います。
- `attr_list` はブロック要素の属性を、段落の直後の属性だけの行から読み取ります。段落の末尾に続けて書いても効きません。
- `nl2br` を有効にすると、キャプション段落の末尾に `<br>` が付きます。`assets/docsfw-livedocs.css` で非表示にしています。
- 見出しの id は `pymdownx.slugs.slugify` で GitHub と同じ規則にする必要があります。
- `.venv` は docsfw の `.gitignore` に追加しました。
- `skinparam` の挿入位置の不備は docsfw 側にも存在したため、`plantuml.lua` にも同じ対策を入れました。
- キャプションの採用範囲も同様に `@start<種別>` 全般へ広げ、両ルートをそろえました。
- `mkdocs-awesome-nav` の `use_index_title` により、README から生成した索引ページのタイトルをフォルダー表示名に使用できます。
- `github-callouts` は `CAUTION` を `danger` クラスへ写します。`IMPORTANT` は同名のまま出力されますが、Material に `important` は存在しないため、既定の admonition として描画されます。
- `extra_css` は Material の `palette.css` より後に読まれます。属性セレクター 1 個どうしでも後勝ちになるため、パレットの CSS 変数はここで上書きできます。
- Material の `--md-accent-bg-color` は accent パレット由来で `#FFFFFF` 固定であり、配色方式では変わりません。`--md-accent-fg-color` をダークで明色にすると、それを背景に敷く部品 (`.md-top` と `.md-button` のホバー、`.md-tag` のホバー) の文字色が白のまま残ります。`slate` 側で対にして上書きする必要があります。
- Material の本文以外のフォントは、`main.css` が `body` で定義する `--md-text-font-family` で決まります。`.md-typeset` だけを上書きすると、ヘッダー、左右 TOC、ページ先頭へ戻るボタン (`.md-top`) などが Material 既定のフォントのまま残ります。
- Material は `.md-typeset h5` を `text-transform: uppercase` にします。英字を含む H5 だけ表示が変わるため、`text-transform: none` で打ち消しています。
- Material の `.md-typeset h2 + h3` は詳細度が (0,1,2) で、レベルごとの指定 (0,1,1) より高くなります。上余白を `.8em` に縮める指定が残るため、同じセレクターで上書きしています。
- 見出しの書式を HTML のタグ名でそろえると、pandoc の `--shift-heading-level-by=-1` による 1 段のずれで Markdown 上の見え方が食い違います。[見出し書式](heading-style.md) は Markdown のレベルを基準に定めています。

### 未着手の課題

- Salt 図が `@plantuml/core` で描画できません。
- `publocal.yaml` の `order:` に対応する `.nav.yml` の生成は実装済みですが、実際の発行対象には `publocal.yaml` が存在しません。
