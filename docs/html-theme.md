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
同じ SVG を 16 px、32 px、48 px に描画した ICO を、サイト直下の `favicon.ico` としても配置します。  
アイコンを指定していないページが `/favicon.ico` を要求したとき、この ICO が SVG と同じ絵を返します。

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

Table: 出力形式別の図描画方式の対応一覧

HTML の Lua フィルターは、図ソースをエスケープして `div.docsfw-mermaid` または `div.docsfw-plantuml` に残します。  
図番号、参照 ID、キャプションは Pandoc 側で確定し、ブラウザーでは図の内側だけを置換します。  
DOCX の画像生成、変換、キャッシュの経路は変更しません。

`bin_internal/pandoc-filters/html-browser.lua` は変換後の図と数式を調べ、テンプレートに必要な資産のメタデータを設定します。  
資産の基準位置は既存の `mermaid-js` から求めます。  
値は `docsfw-mermaid-frame.html` を指し、そのディレクトリが `docsfw-browser-base` になります。  
単一 HTML だけは、同じフレーム文書をページへ埋め込むため `docsfw-embed-frames` を追加します。  
通常 HTML と `file://` はこのメタデータを付けず、開始後に兄弟ファイルを読みます。  
独自テンプレートを使用する場合は、標準テンプレートの `docsfw-browser-base`、`docsfw-has-mermaid`、`docsfw-has-plantuml`、`docsfw-has-math` の読み込み部分も反映してください。

### 図と数式に必要なライブラリだけを読み込む

Pandoc の標準・簡易テンプレートは、図があるページに共通の `docsfw-diagrams.js` を置き、数式がある場合だけ MathJax を読み込みます。  
親ページは `mermaid.min.js` と PlantUML ローダーを評価しません。  
MkDocs は `livedocs/assets/docsfw-libraries.js` を常時配置し、フレームの URL だけを共通スクリプトへ渡します。  
エンジンのフレームは、初回の描画開始条件を満たしたあと、そのページに存在する図種だけ取得します。  
図のないページはフレームを取得せず、配色の変更でも取得済みのフレームを再利用します。

MkDocs の `docsfw-mathjax.js` は、本文に `.arithmatex` がある場合だけ MathJax 3 を取得し、起動完了後に本文を組版します。  
Material の `document$` によるページ差し替え後も必要時に読み込み、組版は前の処理の完了を待って実行します。  
読み込みに失敗した場合も、本文と元ソースは表示します。

### SVG 操作ボタンは追加された範囲だけを検索する

`styles/browser/docsfw-svg-download.js` は、本文を初回に検索して画像と図へ操作ボタンを付けます。  
以後は `MutationObserver` の `addedNodes` で追加された範囲だけを調べます。  
図の内部と操作ボタンの DOM 更新では本文全体を再検索せず、後から追加された図や SVG 画像には同じ操作ボタンを付けます。

## 共通の描画処理

`styles/browser/docsfw-diagrams.js` を Pandoc HTML と MkDocs で共用します。  
`body` の `data-md-color-scheme` が `slate` ならダーク、それ以外ならライトとして描画します。  
Pandoc は `body` の直後に、`html` へ付いた配色を `body` へ写します。  
元ソースを保持し、配色が変わると再描画します。  
描画中に配色が変わった場合は古い結果を表示せず、最新の配色で描画し直します。  
DOM が読める時点で各図を整形済みの元ソース表示へ置き、`aria-busy` と最小高さ 3rem で位置を保ちます。  
この段階ではエンジンを読み込みません。  
初期表示は図で、右上のボタンから元ソースとの表示を切り替えます。  
ソース表示中に配色が変わっても表示状態を維持し、図へ戻すと現在の配色を反映します。

描画要求は Mermaid と PlantUML で 1 本のキューにまとめ、文書の先頭から 1 枚ずつ処理します。  
先行する要求の成功または失敗が確定するまで、後続の要求は送りません。  
配色の変更、表示の切り替え、保存用の描画も同じキューを通ります。  
最初の要求は、`DOMContentLoaded` の完了を確認してから `requestAnimationFrame` を 2 回重ねたあとに始めます。  
2 回の `requestAnimationFrame` は描画の機会を挟むためのもので、画面への表示そのものは保証しません。  
defer 実行中の `interactive` はイベント完了と区別し、navigation エントリの `domContentLoadedEventEnd` も見ます。  
`interactive` でも後続の defer スクリプトが読み込まれるまでイベントを待ちます。  
イベントの配送開始を navigation エントリで確認できた場合だけ、次タスクで待機を解除します。  
エントリが無いときは、`complete` なら完了済みとし、それ以外は `DOMContentLoaded` と予備の `load` 通知を待ちます。  
非表示のタブでは `requestAnimationFrame` を保留し、表示へ戻ってから開始します。  
目次の追従、ファイル一覧、画像、検索索引は待ちません。  
`requestIdleCallback` は使いません。  
開始前の通常描画は、開始時点の `body` の配色へまとめます。  
保存用に明示したテーマはまとめずに残します。  
開始後の再 scan は、この開始条件を再度待ちません。

Mermaid は SVG の viewBox に基づいて表示寸法を 0.875 倍に補正します。  
PlantUML は線幅が viewBox の外へはみ出さないよう、描画後に viewBox をわずかに広げます。  
ダウンロードと画像コピーではページの配色にかかわらずライト テーマで描画します。  
ダウンロード形式は SVG、画像コピー形式は透明背景の PNG です。  
ソース表示中のコピーは、利用者が記述した元ソースをテキストとしてコピーします。  
Mermaid の保存・コピー用 SVG は Canvas で PNG に変換できるよう、HTML ラベルを使用せず描画します。  
描画待ち (`[aria-busy="true"]`) の縞模様と、描画失敗時 (`.docsfw-diagram--error`) の枠は `styles/browser/docsfw-diagrams.css` に置き、Pandoc HTML と MkDocs で共用します。  
Pandoc HTML の `figure` は `display: flex` のため、描画待ちの間だけ `align-self: stretch` で幅を本文全体に広げます。

### 両エンジンの描画を iframe へ分離する

Mermaid の描画と PlantUML のエンジン評価は、それぞれ自己完結したフレーム文書の中で行います。  
親ページは `mermaid.render` と `renderToString` を呼びません。  
フレームはエンジンごとに 1 つで、要求のキューは共通です。  
HTTP と `file://` は、開始条件のあと `iframe.src` でフレーム HTML を読みます。  
単一 HTML は、実行されない `text/plain` のブロックに同じ文書を埋め、開始後に `srcdoc` へ渡します。  
埋め込み時の `</script>` は予約語へ置き換え、`srcdoc` に戻す直前に復元します。  
`sandbox="allow-scripts"` は `allow-same-origin` を含めないため、`iframe` は不透明オリジンになります。  
親は `event.source` が対象 `iframe` の `contentWindow` であることを確認し、子は `event.source` が `parent` であることを確認します。  
不透明オリジンでは送信先に `"*"` が必要です。  
不透明オリジンだけで、すべてのブラウザーが別プロセスで実行するとは扱いません。  
WebKit 系 (Safari / iOS) のプロセス分離は未確認です。

親から送る描画要求は `{ kind, requestId, source, dark, portable }` です。  
`source` はエンジンへ渡す描画用ソースで、PlantUML の前処理後のテキストと、表示用の元ソースは分けたままです。  
`portable` が true のときは保存・コピー用です。  
フレームは準備ができた時点で `{ kind: "ready" }` を返し、失敗時は `{ kind: "init-error", error }` を返します。  
描画結果は `{ kind: "result", requestId, svg }` または `{ kind: "result", requestId, error }` です。  
Mermaid の通常表示は `htmlLabels` を有効にし、`portable` では無効にして `foreignObject` による Canvas の汚染を避けます。  
表示用と保存用のキャッシュは、テーマと `portable` の組み合わせで区別します。  
`securityLevel` は `"loose"` です。  
JavaScript 関数を呼ぶ Mermaid の `click` は、`bindFunctions` を `postMessage` で渡せないため対象外です。  
SVG の文字列として残るリンクは維持します。

Mermaid はフレーム内の DOM で文字寸法を測ります。  
`display: none` にすると寸法が変わり、ビューポート外の不透明オリジンでは `requestAnimationFrame` が保留されます。  
iframe は `position: fixed` でビューポートへ重ね、`opacity: 0`、`pointer-events: none`、`inert`、`aria-hidden` により操作と表示へ影響しないようにします。  
幅は親の `documentElement.clientWidth` で下限は 320px、高さは 4000px です。  
フレーム内の本文フォントは `"trebuchet ms", verdana, arial, sans-serif`、大きさは 16px、行送りは `normal` です。  
測定要素は絶対配置で左上に置き、幅はフレームのビューポートに任せます。  
フォントの `document.fonts.ready` と、描画前の `requestAnimationFrame` 1 回をフレーム内で待ちます。  
HTTP、`file://`、`srcdoc` でこの条件は同じです。

iframe 化だけでは、親ページと別プロセスでの実行を保証しません。  
局所テストは実 Mermaid フレームに 1.5 秒の同期負荷を加え、親ページへのクリック時刻を `parent-responsiveness.json` に記録します。  
2026-10-04 の headless Edge では、クリックへの応答は同期負荷の完了後でした。  
本文の先行表示は開始条件で確保しますが、描画中の操作性はブラウザーのプロセス分離に依存します。

フレームの load は準備完了を意味しません。  
親は `ready` を受け取ってから要求を送ります。  
初期化のタイムアウトは 30 秒、描画のタイムアウトは 15 秒です。  
2026-10-04 に headless の Edge、ビューポート幅 1440px、高さ 1100px、`file://` で既存のサンプルを測ると、Mermaid の初回準備は 434ms、フローチャートの描画は 68ms、日本語の複数行ラベルは 60ms、保存用は 55ms でした。  
PlantUML の準備は 823ms と 728ms、描画は 187ms と 165ms でした。  
タイムアウトは、この実測の最大 (準備 823ms、描画 187ms) に対して、キャッシュの無い解析と遅い端末を見込んだ余裕です。  
局所テストは `window.docsfwDiagramTimeouts` の `init` と `render` で上書きできます。  
初期化の失敗と描画のタイムアウトでは、その要求を失敗させ、元ソースと理由を表示して次の図へ進みます。  
タイムアウト後のフレームは破棄し、遅れて届く応答は無視します。  
エンジンが返した描画エラーではフレームを破棄せず、次の図で再利用します。

Salt は同梱するブラウザー版 PlantUML の非対応図種です。  
HTML 内に非対応の説明と元ソースを表示し、他の図の描画は継続します。  
描画に失敗した図も、その位置にエラーと元ソースを表示します。  
プリレンダ画像への切り替えは行いません。  
Salt の画像が必要な場合は DOCX を使用してください。

## 直接閲覧と単一 HTML

`bin_internal/build-browser-assets.js` が共通資産と、両エンジンの自己完結したフレーム HTML を生成します。  
フレームは別のローカル JavaScript を読みません。  
PlantUML エンジンを Base64 からバイト列へ復元し、フレーム内で Blob URL のモジュールとして読み込みます。  
Graphviz と同梱アイコン資産もフレームに含めます。  
iPhone の Edge で data URL の import が失敗し、Blob URL では描画できたため、この方式を採用しています。  
比較条件は [PlantUML の切り分け試験](https://github.com/Hondarer/plantuml-core-test) の試験 09 と 13 を参照してください。  
Blob URL は追加処理と再描画のため、iframe の破棄まで保持します。  
Mermaid は `mermaid.min.js` をフレーム内の classic script として埋め込みます。  
図の描画のためにサーバーへソースを送信しません。  
既存の HTML テンプレートが参照する CDN 資産は、このフレームとは別です。

アイコン資産は PlantUML の内部ローダーの完了表にも登録します。  
`@plantuml/core` を更新する際は、完了表の契約とオフラインのアイコン描画を確認してください。  
PlantUML のライセンスは、フレーム先頭の HTML コメントと、同じ場所の `docsfw-plantuml-LICENSE.txt` に置きます。  
Mermaid のライセンス表記は、埋め込んだ `mermaid.min.js` の中に残します。

## 局所検証

docsfw ルートで次を実行します。

```bash
node bin_internal/test-html-diagrams.js
node bin_internal/test-html-ui.js
node tests/test_page_performance_browser.js
node tests/test_page_libraries_browser.js
python -m unittest discover -s livedocs/tests -p test_vendor_assets.py
```

ブラウザー テストは一時ディレクトリに HTML と画面画像を生成し、その場所を表示します。  
既存 CDN への依存を除いた標準・簡易テンプレートで、通常 HTML、単一 HTML、直接閲覧、HTTP 配信を確認します。  
実際の図の描画、配色切り替え、ソースとの切り替え、ライト テーマの SVG 保存と PNG コピー、描画中の配色変更を検証します。  
HTML UI のブラウザー テストでは、ヘッダー、ドロワー、階層切り替え、ページ内目次、全文検索を検証します。  
`test_page_performance_browser.js` は図の更新時の検索回数、折り畳み状態の保存回数、開閉後の外観を確認します。  
`test_page_libraries_browser.js` は局所 MkDocs サイトでライブラリの取得条件と実描画を確認し、Pandoc の標準・簡易テンプレートの数式読み込み条件も検証します。  
取得済みの MathJax 3 `tex-mml-chtml.js` のパスを `DOCSFW_TEST_MATHJAX_SCRIPT` へ設定すると、実エンジンによる数式描画も確認します。  
発行処理を含む確認手順は [発行処理の保守と検証](maintenance-verification.md) を参照してください。
