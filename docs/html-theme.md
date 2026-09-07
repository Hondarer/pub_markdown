# HTML のテーマと図の描画

Pandoc HTML は、OS の配色設定に合わせてライト モードまたはダーク モードで開きます。  
ヘッダーのボタンで配色を切り替えると、選択をブラウザーに保存します。  
保存領域を利用できない場合も、そのページ内では切り替えを利用できます。  
保存済みの選択がない場合は、OS の配色変更にも追従します。

本文、表、コード、注意書き、検索、目次の色は `styles/html/html-style.css` の CSS 変数で管理します。  
ライト モードは従来の配色、ダーク モードは MkDocs Material の `slate` に合わせています。  
図ソース内で明示された色や独自テーマ、既存画像の色は変更しません。

標準 HTML のヘッダーは MkDocs と同じく 48px で、直後に 12px の本文背景帯を置きます。  
ページ タイトルは 18px、発行者と発行日時は 14px、操作アイコンは 24px です。  
1625px 以上ではロゴ、未満ではドロワーを開くメニュー ボタンを左端に表示します。

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

PlantUML は共有状態を持つため、描画完了まで直列に処理します。  
DOM 構築完了後、画面内外を問わず文書内の先頭から順に PlantUML を描画します。  
Mermaid は SVG の viewBox に基づいて表示寸法を 0.875 倍に補正します。  
PlantUML は線幅が viewBox の外へはみ出さないよう、描画後に viewBox をわずかに広げます。  
SVG ダウンロードは、ボタンを押した時点の図を保存します。

Salt は同梱するブラウザー版 PlantUML の非対応図種です。  
HTML 内に非対応の説明と元ソースを表示し、他の図の描画は継続します。  
描画に失敗した図も、その位置にエラーと元ソースを表示します。  
プリレンダ画像への切り替えは行いません。  
Salt の画像が必要な場合は DOCX を使用してください。

## 直接閲覧と単一 HTML

`bin/build-browser-assets.js` が共通資産と PlantUML のローダーを生成します。  
PlantUML エンジンを data URL のモジュールとして読み込み、Graphviz と同梱アイコン資産もローダーに含めます。  
ローカルの ES モジュールを相対パスで取得しないため、`file://` での直接閲覧と Pandoc の `--embed-resources` に対応します。  
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
実際の図の描画、配色切り替え、選択の復元、SVG 保存、描画中の配色変更を検証します。  
HTML UI のブラウザー テストでは、ヘッダー、ドロワー、階層切替、ページ内目次、全文検索を検証します。  
発行処理を含む確認手順は [発行処理の保守と検証](maintenance-verification.md) を参照してください。
