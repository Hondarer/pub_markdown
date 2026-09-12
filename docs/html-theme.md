# HTML のテーマと図の描画

Pandoc HTML は、OS の配色設定に合わせてライト モードまたはダーク モードで開きます。  
ヘッダーのボタンで配色を切り替えると、選択をブラウザーに保存します。  
保存領域を利用できない場合も、そのページ内では切り替えを利用できます。  
保存済みの選択がない場合は、OS の配色変更にも追従します。

本文、表、コード、注意書き、検索、目次の色は `styles/html/html-style.css` の CSS 変数で管理します。  
ライト モードは従来の配色、ダーク モードは MkDocs Material の `slate` に合わせています。  
図ソース内で明示された色や独自テーマ、既存画像の色は変更しません。

## Favicon

Pandoc HTML と MkDocs は、発行方式を識別できる異なる favicon を使用します。  
Pandoc HTML は Pandoc の P、MkDocs は Material の本を前景に使用します。  
両方とも暗い円形グラデーションの背景と白い前景を使用し、ブラウザーの配色に依存せず判別できるようにします。

SVG の正本は `styles/html/docsfw-{pandoc,mkdocs}-favicon.svg` です。  
Pandoc の発行処理は各 HTML ルートへ Pandoc 用 SVG を配置し、標準テンプレートと簡易テンプレートから参照します。  
MkDocs の `vendor_assets.py` は MkDocs 用 SVG を `assets/` へ配置し、生成した `mkdocs.yml` の `theme.favicon` から参照します。

標準 HTML のヘッダーは MkDocs と同じく 48px で、直後に 12px の本文背景帯を置きます。  
ページ タイトルは 18px、発行者と発行日時は 14px、右上の操作アイコンは 20px、左端のロゴとメニューは 24px です。  
ライトのロゴは黒、ダークのロゴは MkDocs ヘッダー文字と同じ白系です。  
1400px 以上ではロゴ、未満ではドロワーを開くメニュー ボタンを左端に表示します。  
1400px から 1624px は、左右列を 2/3 幅にした中間 3 列です。詳細は [動的発行基盤の「ナビゲーションの幅と切り替え」](livedocs-design.md) を参照してください。

## HTML と DOCX の分岐

| 出力 | Mermaid | PlantUML |
|---|---|---|
| Pandoc HTML / MkDocs | ブラウザーで描画 | `@plantuml/core` でブラウザー描画 |
| DOCX | 従来の Mermaid CLI と画像変換 | 従来のローカル CLI / サーバーと画像変換 |

HTML の Lua フィルターは、図ソースをエスケープして `div.docsfw-mermaid` または `div.docsfw-plantuml` に残します。  
図番号、参照 ID、キャプションは Pandoc 側で確定し、ブラウザーでは図の内側だけを置換します。  
DOCX の画像生成、変換、キャッシュの経路は変更しません。

`bin/pandoc-filters/html-browser.lua` は変換後の図を調べ、テンプレートに必要な資産のメタデータを設定します。  
資産の基準位置は既存の `mermaid-js` から求めるため、発行 CLI や設定キーの追加はありません。  
独自テンプレートを使用する場合は、標準テンプレートの `docsfw-browser-base`、`docsfw-has-mermaid`、`docsfw-has-plantuml` の読み込み部分も反映してください。

## 共通の描画処理

`styles/browser/docsfw-diagrams.js` を Pandoc HTML と MkDocs で共用します。  
`body` の `data-md-color-scheme` が `slate` ならダーク、それ以外ならライトとして描画します。  
元ソースを保持し、配色が変わると再描画します。  
描画中に配色が変わった場合は古い結果を表示せず、最新の配色で描画し直します。  
DOM 構築直後と描画待ちでは元ソースを左寄せで表示し、描画後の図だけを中央寄せにします。  
描画後の初期表示は図で、右上のボタンから元ソースとの表示を切り替えます。  
ソース表示中に配色が変わっても表示状態を維持し、図へ戻すと現在の配色を反映します。

PlantUML は共有状態を持つため、描画完了まで直列に処理します。  
DOM 構築完了後、画面内外を問わず文書内の先頭から順に PlantUML を描画します。  
Mermaid は SVG の viewBox に基づいて表示寸法を 0.875 倍に補正します。  
PlantUML は線幅が viewBox の外へはみ出さないよう、描画後に viewBox をわずかに広げます。  
ダウンロードと画像コピーではページの配色にかかわらずライト テーマで描画します。  
ダウンロード形式は SVG、画像コピー形式は透明背景の PNG です。  
ソース表示中のコピーは、利用者が記述した元ソースをテキストとしてコピーします。  
Mermaid の保存・コピー用 SVG は Canvas で PNG に変換できるよう、HTML ラベルを使用せず描画します。  
描画待ち (`[aria-busy="true"]`) の縞模様と、描画失敗時 (`.docsfw-diagram--error`) の枠は `styles/browser/docsfw-diagrams.css` に置き、Pandoc HTML と MkDocs で共用します。  
Pandoc HTML の `figure` は `display: flex` のため、描画待ちの間だけ `align-self: stretch` で幅を本文全体に広げます。

### PlantUML の描画をメイン スレッドから分離する

`@plantuml/core` のエンジン (`plantuml.js`) は数 MB あり、評価と `renderToString` 呼び出し自体がメイン スレッド上の同期処理になります。  
文書内の PlantUML 図をすべてメイン スレッドで直接実行すると、描画中に UI の応答が停止したように見え、ブラウザーによっては描画エラーや無応答につながります。  
これを避けるため、PlantUML の実描画は隠し `<iframe sandbox="allow-scripts">` の中で行います。  
この `iframe` はページ内で 1 つだけ遅延生成し、`srcdoc` に自己完結した HTML を設定して構築します。外部ファイルや `data-src` によるナビゲーションは行いません。  
`docsfw-diagrams.js` からは `postMessage` で `{ requestId, lines, dark }` を送り、`iframe` 側は `renderToString` の結果を `{ requestId, svg }` または `{ requestId, error }` として返します。  
`window.docsfwLoadPlantuml()` が返すオブジェクトの形 (`renderToString(lines, onSuccess, onError, options)`) は変わらないため、`docsfw-diagrams.js` の直列キューや配色切り替えの扱いはこの分離と無関係に動作します。  
`sandbox="allow-scripts"` は `allow-same-origin` を含めないため、`iframe` は不透明オリジンになり、`postMessage` の相手確認は `event.origin` ではなく `event.source` で行います。  
Chromium 系ブラウザーでは不透明オリジンの `iframe` が別プロセスに分離されやすく、メイン スレッドの応答性が改善しやすいことを局所検証で確認しています。  
WebKit 系 (Safari / iOS) が同一文書内の `srcdoc` `iframe` をどこまでプロセスまたはスレッド分離するかは未確認です。改善が見られない場合は、実機での再現手順を添えて報告してください。

Salt は同梱するブラウザー版 PlantUML の非対応図種です。  
HTML 内に非対応の説明と元ソースを表示し、他の図の描画は継続します。  
描画に失敗した図も、その位置にエラーと元ソースを表示します。  
プリレンダ画像への切り替えは行いません。  
Salt の画像が必要な場合は DOCX を使用してください。

## 直接閲覧と単一 HTML

`bin/build-browser-assets.js` が共通資産と PlantUML のローダーを生成します。  
PlantUML エンジンを Base64 からバイト列へ復元し、隠し iframe 内で Blob URL のモジュールとして読み込みます。  
Graphviz と同梱アイコン資産もローダーに含めます。  
iPhone の Edge で data URL の import が失敗し、Blob URL では描画できたため、この方式を採用しています。  
比較条件は [PlantUML の切り分け試験](https://github.com/Hondarer/plantuml-core-test) の試験 09 と 13 を参照してください。  
Blob URL は追加処理と再描画のため、iframe の破棄まで保持します。  
ローカルの ES モジュールを相対パスで取得しないため、`file://` での直接閲覧と Pandoc の `--embed-resources` に対応します。  
上記の隠し `iframe` も `srcdoc` による同一文書内の構築であり、追加のファイルや外部 URL を必要としません。  
図の描画のためにサーバーへソースを送信しません。  
既存の HTML テンプレートが参照する CDN 資産は、この図のローダーとは別です。

アイコン資産は PlantUML の内部ローダーの完了表にも登録します。  
`@plantuml/core` を更新する際は、完了表の契約とオフラインのアイコン描画を確認してください。  
PlantUML のライセンスは、ローダーと同じ場所の `docsfw-plantuml-LICENSE.txt` に配置します。

## 局所検証

docsfw ルートで次を実行します。

```bash
node bin/test-html-diagrams.js
node bin/test-html-ui.js
python -m unittest discover -s livedocs/tests -p test_vendor_assets.py
```

ブラウザー テストは一時ディレクトリに HTML と画面画像を生成し、その場所を表示します。  
既存 CDN への依存を除いた標準・簡易テンプレートで、通常 HTML、単一 HTML、直接閲覧、HTTP 配信を確認します。  
実際の図の描画、配色切り替え、ソースとの切り替え、ライト テーマの SVG 保存と PNG コピー、描画中の配色変更を検証します。  
HTML UI のブラウザー テストでは、ヘッダー、ドロワー、階層切り替え、ページ内目次、全文検索を検証します。  
発行処理を含む確認手順は [発行処理の保守と検証](maintenance-verification.md) を参照してください。
