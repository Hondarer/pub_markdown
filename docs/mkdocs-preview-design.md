# mkdocs 簡易プレビュー基盤

## 概要

`bin/pub_markdown_core.sh` による発行処理とは別に、執筆中の確認を目的とした軽量なプレビュー基盤を mkdocs で提供します。  
PlantUML はビルド時に画像化せず、ブラウザー上の JavaScript でレンダリングします。  
Word (docx) 出力は対象外とし、サイト内ナビゲーションとページ内目次は維持します。

### 背景

docsfw の発行パイプラインは、成果物の品質を優先した構成です。  
Pandoc、Lua フィルター 18 本、Node.js (Puppeteer、mermaid-cli、MiniSearch)、Python 後処理を 1 本のシェル スクリプト (2837 行) が統合しています。

このため、執筆中に 1 ページの見た目を確認する用途にはコストが見合いません。  
c-modernization-kit ワークスペースにおける発行対象の実測値を次に示します。

| 指標 | 実測値 |
|---|---|
| 発行対象 Markdown | 766 ファイル |
| うち Doxybook2 生成 | 573 ファイル (74.8%) |
| PlantUML コード ブロック | 2757 出現 / 381 ファイル |
| Mermaid コード ブロック | 38 出現 / 8 ファイル |
| 出力バリアント | `ja` / `en` × 通常 / `-details` の 4 種類 |

PlantUML はすべてビルド時に SVG 化され、docx 出力ではさらに Puppeteer 経由で PNG に変換されます。  
プレビュー基盤では、この図生成コストをブラウザー側へ移すことで、ビルド時間を Markdown の変換だけに切り詰めます。

### 位置付け

本基盤は docsfw を置き換えるものではありません。  
docsfw は HTML と docx の正式な発行の正本であり続けます。

| | docsfw (`make docs`) | mkdocs プレビュー (`make preview`) |
|---|---|---|
| 目的 | 正式な発行 | 執筆中の確認 |
| 出力 | HTML + docx | HTML のみ |
| バリアント | `ja` / `en` × 通常 / `-details` | `ja` / `details=true` の 1 種類 |
| PlantUML | ビルド時に SVG 化 | ブラウザー上でレンダリング |
| 図の再現性 | 正本 | 差異が出る場合がある (後述) |

## docsfw ファンクション ポイントと対応方針

凡例を次に示します。

- **維持**: 同等の機能を実現します。
- **簡略**: 目的は満たしますが、実装または見た目が変わります。
- **対象外**: プレビューでは実現しません。

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
| 9 | 多言語ブロック `<!--ja:-->` | `bin/replace-tag.sh` | 維持 | Python へ移植し `lang=ja` 固定 |
| 10 | 詳細ブロック `<!--details:-->` | `bin/replace-tag.sh` | 維持 | `details=true` 固定 |
| 11 | `\toc` によるディレクトリ横断索引 | `bin/pandoc-filters/insert-toc.lua`、`insert-toc.sh` | 簡略 | 実使用の 5 パラメーターのみ再実装 |
| 12 | `short-title` 系の解決 | `bin/extract-short-title.sh` | 簡略 | `title:` フロント マターへ写す |
| 13 | H1 除去と `--shift-heading-level-by=-1` | `:2691-2695` | 対象外 | mkdocs は H1 をページ見出しとして扱う |

### 図の生成

| # | ファンクション ポイント | docsfw の実装場所 | 対応 | 備考 |
|---|---|---|---|---|
| 14 | PlantUML の SVG 化 | `bin/pandoc-filters/plantuml.lua:503-560`, `:731-758` | 簡略 | `@plantuml/core` によるブラウザー描画 |
| 15 | PlantUML の LibDeflate エンコード | `plantuml.lua:157-211` | 対象外 | サーバーを使わない |
| 16 | `skinparam backgroundColor transparent` の注入 | `plantuml.lua:663-668` | 維持 | クライアント側 JavaScript で実施 |
| 17 | `caption` 行と `@startuml <名前>` からのキャプション抽出 | `plantuml.lua:579-644` | 維持 | 同じ優先順を実装 |
| 18 | SVG の処理命令移動とフォント パッチ | `plantuml.lua:358-400`, `:464-500` | 対象外 | docx 向けの対策 |
| 19 | SVG から PNG への変換 | `plantuml.lua:781-802`、`bin/rsvg-convert.js` | 対象外 | docx 専用 |
| 20 | Mermaid のブラウザー描画 | `bin/pandoc-filters/mermaid.lua:150-166` | 維持 | 同じ方式。ローカルの `mermaid.min.js` を使用 |
| 21 | Mermaid の mmdc 変換 | `mermaid.lua:259-330` | 対象外 | docx 専用 |
| 22 | 共有ブラウザー インスタンス | `bin/browser-server.js` ほか | 対象外 | ビルド時にブラウザーを使わない |
| 23 | draw.io SVG の `foreignObject` 除去 | `bin/strip-foreignobject.py` | 対象外 | ブラウザーは `foreignObject` を解釈できる |
| 24 | 画像リソースの事前コピー | `:2473-2492` | 維持 | ステージングで画像も配置 |

### Markdown 記法の変換

| # | ファンクション ポイント | 出現数 | 対応 | 備考 |
|---|---|---|---|---|
| 25 | GitHub アラート 6 種 | 616 | 維持 | `markdown-callouts`。`DEPRECATED` はステージングで変換 |
| 26 | `+hard_line_breaks` | 371 ファイル | 維持 | `markdown.extensions.nl2br` |
| 27 | 表 | 789 | 維持 | `tables` 拡張 |
| 28 | `Table:` キャプション | 73 | 簡略 | ステージングでキャプション段落へ変換 |
| 29 | `CodeBlock:` キャプション | 68 | 簡略 | フェンス属性または図キャプションへ畳み込む |
| 30 | pandoc-crossref の採番と相互参照 | ラベル 22 / 参照 7 | 対象外 | ラベルは id として残す |
| 31 | 数式 | 51 | 維持 | `pymdownx.arithmatex` と MathJax |
| 32 | 脚注 | 29 | 維持 | `footnotes` 拡張 |
| 33 | タスク リスト | 176 | 維持 | `pymdownx.tasklist` |
| 34 | `==mark==` | 少数 | 維持 | `pymdownx.mark` |
| 35 | `\newpage` / `\pagebreak` | 4 | 対象外 | ステージングで削除 |
| 36 | docx 専用フィルター 8 本 | - | 対象外 | |

### リンク解決

| # | ファンクション ポイント | 出現数 | 対応 | 備考 |
|---|---|---|---|---|
| 37 | `.md` から `.html` への書き換え | 963 | 維持 | mkdocs が標準で解決 |
| 38 | 実パスと仮想パスの相互変換 | 114 | 維持 | ステージングで書き換える |
| 39 | `README.md` / `SKILL.md` のリンク正規化 | - | 維持 | ステージングで書き換える |
| 40 | Git 単一ページ リンク | フロント マター 392 | 対象外 | 将来対応の候補 |
| 41 | Doxygen 単一ページ リンク | フロント マター 523 | 対象外 | 将来対応の候補 |

### 出力とナビゲーション

| # | ファンクション ポイント | 対応 | 備考 |
|---|---|---|---|
| 42 | HTML 出力 | 維持 | mkdocs-material |
| 43 | self-contained HTML 出力 | 対象外 | |
| 44 | docx 出力 | 対象外 | 本基盤の要件どおり |
| 45 | ページ内目次 | 維持 | Material の右サイドバー。`toc_depth: 3` |
| 46 | サイト内ナビゲーション ツリー | 維持 | Material の左サイドバー。自動生成 |
| 47 | ページ内目次のナビゲーション ツリーへのマージ | 簡略 | Material は左右分離。`toc.follow` で代替 |
| 48 | 全文検索 | 簡略 | Material 標準検索。日本語の既知の弱点あり |
| 49 | `file://` での動作 | 対象外 | `mkdocs serve` の HTTP 前提 |
| 50 | モバイル オフキャンバス ドロワー | 維持 | Material 標準 |
| 51 | 展開可能リスト | 簡略 | Material のナビ折り畳みで代替。ページ本文中の手動 fenced div (`::: {.collapsible-list open-level=N}`) は mkdocs 側に対応する拡張が無いため、`stage_preview_docs.py` の `strip_collapsible_list_fences` が開始行と終了行だけを取り除き、中身は折り畳み無しの通常リストとして表示する |
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
+-- mkdocs/
|   +-- bin/
|   |   +-- stage_preview_docs.py    # ステージング (収集、前処理、リンク書き換え)
|   |   +-- lang_details_filter.py   # replace-tag.sh の Python 移植
|   |   +-- expand_toc.py            # \toc の展開
|   |   +-- vendor_assets.py         # アセットの配置と mkdocs.yml の生成
|   +-- mkdocs.yml.in                # 設定テンプレート
|   +-- assets/
|   |   +-- docsfw-plantuml.js       # クライアント側 PlantUML レンダラー
|   |   +-- docsfw-mermaid.js        # Mermaid 初期化
|   |   +-- docsfw-mathjax.js        # MathJax の設定
|   |   +-- docsfw-preview.css       # 追加スタイル
|   +-- requirements.txt
|   +-- README.md                    # 利用手順
+-- docs/
    +-- mkdocs-preview-design.md     # この文書 (設計の正本)
```

### 生成物

生成物はワークスペースの `pages/preview/` 以下に出します。  
`/pages/` はワークスペースの `.gitignore` で除外済みのため、追加の設定は不要です。

```text
pages/preview/
+-- mkdocs.yml     # mkdocs.yml.in から生成される実際の設定
+-- src/           # ステージング済み Markdown (docs_dir)
+-- site/          # mkdocs build の出力 (serve 時は未使用)
```

`make cleandocs` は `pages/` 配下から `doxygen` だけを残して削除するため、`pages/preview/` も同時に消えます。  
これは意図した挙動です。

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

配布物は `framework/docsfw/bin/package.json` の依存に追加し、既存の `npm ci` フローに乗せます。  
`bin/vendor_assets.py` が `node_modules/@plantuml/core/` から必要なファイルだけをステージング先へコピーします。

### レンダラーの責務

`assets/docsfw-plantuml.js` は次を行います。

- `pymdownx.superfences` の `custom_fences` が出力した要素から PlantUML ソースを取得します。
- `caption` 行、または `@startuml <名前>` からキャプションを取り、`figcaption` として出力します。優先順は `plantuml.lua:579-644` と同じです。
- `skinparam backgroundColor transparent` を注入します。処理は `plantuml.lua:663-668` と同じです。
- `IntersectionObserver` で、ビューポートに入った図だけをレンダリングします。
- Material のカラー スキームを参照し、ダーク モードの指定を切り替えます。  
  `data-md-color-scheme` 属性が `slate` のとき、`renderToString(lines, onSuccess, onError, { dark: true })` のように第 4 引数へ `{ dark: true }` を渡します。  
  この引数は `render(lines, targetId, { dark })` と同じ内部フラグを共有しており、README には `renderToString` 側の記載がありませんが、`plantuml.js` のコンパイル済みコードで動作を確認済みです。  
  `MutationObserver` (`watchColorScheme()`) がスキーム変更を検知すると、描画済みの図をこのオプション付きで再描画します。

遅延描画は必須です。  
`app/porter/docs/sequence.md` は 1 ページに 30 個の PlantUML を含み、Doxybook2 のページも各ページにインクルード グラフと呼び出しグラフを持つためです。

## Mermaid

`custom_fences` で Mermaid のフェンスを `pre.mermaid` として出力し、`assets/docsfw-mermaid.js` が初期化します。  
docsfw の HTML 出力も同じ方式であるため、`styles/html/html-template.html` の初期化処理とサイズ正規化 (viewBox から実寸を取り 0.875 倍する処理) をそのまま流用します。

`mermaid.min.js` は `bin/node_modules/mermaid/dist/` から取り出して同梱します。

Material にも Mermaid 連携がありますが、こちらは unpkg から `mermaid.min.js` を取得します。  
docsfw が同梱方式であることと、描画結果を docsfw の HTML 出力にそろえることを優先し、  
クラス名を `docsfw-mermaid` として Material 側の処理と競合しないようにしています。

## mkdocs の設定

`mkdocs.yml.in` の主要部分を次に示します。

```yaml
theme:
  name: material
  language: ja
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
  - search: { lang: ja }
```

`nav:` は記述しません。  
mkdocs の自動ナビゲーションに任せ、`publocal.yaml` が存在する場合だけ `.nav.yml` をステージング時に生成します。

`nl2br` は docsfw の `-f markdown+hard_line_breaks` に相当します。  
本ワークスペースの Markdown は一文一行で記述し、行末の半角空白 2 個による強制改行を 371 ファイルで使用しているため、この拡張が必要です。

## make からの起動

ワークスペースのルート `makefile` に次のターゲットを追加します。  
既存の `docs` ターゲットは変更しません。

| ターゲット | 内容 |
|---|---|
| `preview` | ステージング後に `mkdocs serve` を起動する |
| `preview-build` | ステージング後に `mkdocs build --strict` を実行する |
| `cleanpreview` | `pages/preview/` を削除する |

Python の依存は `framework/docsfw/mkdocs/.venv` に閉じ込め、`requirements.txt` で固定します。

## 対応しない機能

次の機能が必要な場合は `make docs` で docsfw を使用します。

- Word (docx) 出力と、docx 専用フィルター、rsvg-convert、共有ブラウザー
- `en` バリアントと `details=false` バリアント
- pandoc-crossref による図表とリストの採番、および相互参照
- Git 単一ページ リンクと Doxygen 単一ページ リンク
- self-contained HTML と `file://` での動作
- OpenAPI からの Markdown 生成
- MiniSearch と CJK bigram による日本語全文検索

全文検索について補足します。  
docsfw は重なり 2-gram のトークナイザーを自前で実装し、日本語の検索精度を確保しています。  
mkdocs-material の標準検索は lunr と TinySegmenter を使用するため、日本語の長い複合語を取りこぼします。

実測した挙動を次に示します。

| 検索語 | 結果 |
|---|---|
| 同期 | 294 件 |
| ビルド | 130 件 |
| モック | 23 件 |
| 同期プリミティブ | 0 件 |

2 文字程度の語やカタカナ語は引けますが、`同期プリミティブ` のような複合語は引けません。  
また `同期` が `同梱` にも一致するなど、分かち書きの精度は docsfw の 2-gram より劣ります。

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
この規則は docsfw の `bin/pandoc-filters/plantuml.lua` と、プレビューの `assets/docsfw-plantuml.js` で共通です。

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
make preview-build
```

`PREVIEW_STRICT=1` を付けると `mkdocs build --strict` になります。

791 ファイルのステージングは約 1.4 秒、`mkdocs build` は約 53 秒、合計で約 55 秒です。  
docsfw の `make docs` は 4 バリアントの HTML と docx を生成するため、これより桁違いに長くかかります。

#### 既知の警告

現在のビルドでは 60 件の警告が出ます。  
いずれもステージングの不具合ではなく、ソース側に元からあるリンクです。  
docsfw の発行でも同じリンクは解決しません。

| 件数 | 内容 | 備考 |
|---:|---|---|
| 24 | `../../../doxygen/*.html` | docsfw の出力レイアウトを前提としたリンク。`pages/preview/site/` では届かない |
| 19 | Doxybook2 が生成した `Classes/`, `Namespaces/`, `Modules/` への相対リンク | 生成時点で相対パスが誤っている |
| 11 | `../prod/` 配下のファイルへのリンク | ドキュメント ツリーの外 |
| 6 | `../../README.md`, `../../AGENTS.md`, `../bin/text_style_jp.md` など | ドキュメント ツリーの外 |

このほか、見出しへのアンカー リンクの不一致が 6 件あります。  
いずれもリンク先のアンカーに半角空白が含まれており、GitHub でも解決しません。

見出しの id は `pymdownx.slugs.slugify` で GitHub と同じ規則にそろえています。  
Python-Markdown の既定では非 ASCII が落ちるため、この設定がないと日本語見出しへのリンクが約 35 件切れます。

### 表示の確認

```bash
make preview
```

次のページを確認します。

| 確認対象 | ページ | 確認内容 |
|---|---|---|
| PlantUML の多量描画 | `app/porter/docs/sequence.md` | 遅延描画がスクロールに追従すること |
| PlantUML の図種 | `framework/docsfw/docs/sample/plantuml-showcase.md` | 図種ごとの描画結果と docsfw との差異 |
| Mermaid | `framework/docsfw/docs/sample/mermaid-showcase.md` | 描画とサイズ正規化 |
| キャプション | `framework/docsfw/docs/sample/mermaid-caption.md` | `CodeBlock:` 由来のキャプション |
| `\toc` の展開 | `docs/README.md` | 索引の内容と越境リンクの解決 |
| Doxybook2 ページ | `app/c-platform/docs/doxybook2_public/` 配下 | ナビゲーション、目次、グラフの描画 |
| GitHub アラート | 各 app の `coding-guideline.md` | 6 種の表示。特に `DEPRECATED` |
| 数式 | `app/general/docs/build-design.md` | MathJax の描画 |
| 日本語パス | `framework/docsfw/docs/sample/日本語を含むサブフォルダ/` | パス解決とナビゲーション表示 |
| 検索 | 任意 | 日本語語句での検索 |

### クロスプラットフォーム

Windows の Git Bash と Python でも `make preview-build` が通ることを確認します。  
ステージングは Python で実装するため、シェル スクリプトへの依存を持ちません。  
シンボリック リンクは Windows で不安定なため使用せず、実ファイルのコピーで構成します。

### docsfw への非干渉

`make docs` が従来どおり成功し、`pages/ja/html/` 等の出力が変わらないことを確認します。  
`bin/package.json` への依存追加が、既存の `npm ci` とセットアップ スタンプに影響しないことを確認します。

## 実装状況

| ステップ | 内容 | 状態 |
|---|---|---|
| 0 | 設計ドキュメントの作成 | 完了 |
| 1 | ステージング基盤 | 完了 |
| 2 | `\toc` の展開 | 完了 |
| 3 | mkdocs 設定とテーマ資産 | 完了 |
| 4 | PlantUML のクライアント レンダラー | 完了 |
| 5 | make 統合と文書化 | 完了 |

### 実装で判明したこと

- `pymdownx.superfences` の `custom_fences` が出す要素は、Material の Mermaid 連携と競合します。クラス名を `docsfw-mermaid` に変えて回避しました。
- GitHub アラート記法には `markdown-callouts` の `callouts` ではなく `github-callouts` が必要です。`callouts` は `NOTE:` 形式だけを扱います。
- `attr_list` はブロック要素の属性を、段落の直後の属性だけの行から読み取ります。段落の末尾に続けて書いても効きません。
- `nl2br` を有効にすると、キャプション段落の末尾に `<br>` が付きます。`assets/docsfw-preview.css` で非表示にしています。
- 見出しの id は `pymdownx.slugs.slugify` で GitHub と同じ規則にする必要があります。
- `.venv` は docsfw の `.gitignore` に追加しました。
- `skinparam` の挿入位置の不備は docsfw 側にも存在したため、`plantuml.lua` にも同じ対策を入れました。
- キャプションの採用範囲も同様に `@start<種別>` 全般へ広げ、両ルートをそろえました。

### 未着手の課題

- Salt 図が `@plantuml/core` で描画できません。
- Doxygen HTML へのリンクがプレビューでは解決しません。`pages/doxygen` がステージング ツリーの外にあるためです。
- `publocal.yaml` の `order:` に対応する `.nav.yml` の生成は実装済みですが、対象ファイルが存在しないため未検証です。
