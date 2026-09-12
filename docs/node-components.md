# Node コンポーネント

docsfw が実行時に使用する npm パッケージと、その解決手順を示します。  
セットアップ操作は [Node.js モジュールの設定](../bin/how_to_setup_node_modules.md) を参照してください。

## 必須パッケージ

管理対象の宣言は `bin/package.json` です。  
版の固定は `bin/package-lock.json` が担います。

| パッケージ | 役割 | 検出 |
|---|---|---|
| `@mermaid-js/mermaid-cli` | Mermaid を SVG へ変換する `mmdc` | 実行ファイル |
| `mermaid` | HTML と動的発行へ同梱する `mermaid.min.js` | `@mermaid-js/mermaid-cli` の推移依存。直下または mermaid-cli 配下 |
| `widdershins` | OpenAPI を Markdown へ変換する CLI | 実行ファイル |
| `puppeteer` | 共有ブラウザー、`rsvg-convert.js`、`mmdc-reuse.js` | `require('puppeteer')` |
| `puppeteer-core` | `puppeteer` が利用する中核 | モジュール |
| `minimist` | 自前 Node スクリプトの引数解析 | モジュール |
| `sharp` | SVG スクリーンショットの再エンコード | モジュール |
| `minisearch` | HTML 検索インデックスと UMD バンドル | モジュールと `dist/umd` のファイル |
| `@plantuml/core` | Pandoc HTML と動的発行のブラウザー上 PlantUML | モジュール |

`mermaid` は `package.json` の直接依存ではありません。  
`@mermaid-js/mermaid-cli` が解決できれば、その配下の `mermaid.min.js` を使用します。

## 解決順

`bin/resolve-node-components.js` は次の順序で探索します。

1. `NODE_PATH`
2. `/usr/local/lib/node_modules`
3. `npm root -g`
4. `node` 実行ファイルと同じ階層の `node_modules`
5. `mmdc` または `widdershins` と同じ階層の `node_modules`
6. `framework/docsfw/bin/node_modules`

グローバルの版は `package.json` の semver 範囲を満たすときだけ採用します。  
範囲外のグローバルは欠落とみなし、ローカルへ補完します。

## オンデマンド導入

| 状態 | 動作 |
|---|---|
| 必須パッケージがすべて揃っている | npm を実行しません |
| 一部だけ欠けている | 欠けたトップレベルだけ `npm install --no-save <name>@<lockfile の version>` します |
| 必須パッケージがすべて欠けている | `bin/` で `npm ci` します |

`npm ci` と部分インストールのあいだは `PUPPETEER_SKIP_DOWNLOAD=1` です。  
Chrome 本体の取得は npm とは別段です。

## ブラウザー

| OS | 動作 |
|---|---|
| Windows | Microsoft Edge が必須です。存在しない場合はエラーで終了します。Puppeteer 用 Chrome はダウンロードしません |
| Linux | `PUPPETEER_EXECUTABLE_PATH` が実行可能な Chrome を指すときはそれを使用します |
| Linux | 外部 Chrome が存在しないときは、puppeteer モジュール解決のあと `npx puppeteer browsers install chrome` と `chrome-headless-shell` を実行します |

npm パッケージがグローバルで揃っていても、Linux で外部 Chrome が無ければブラウザーの導入が実行されます。

## 呼び出し元

後続の処理は解決済みパスのみを使用します。

| 用途 | 環境変数 |
|---|---|
| widdershins | `DOCSFW_WIDDERSHINS` |
| mmdc | `DOCSFW_MMDC` |
| Mermaid バンドル | `DOCSFW_MERMAID_JS` |
| MiniSearch UMD | `DOCSFW_MINISEARCH_JS` |
| `@plantuml/core` | `DOCSFW_PLANTUML_CORE` |
| puppeteer | `DOCSFW_PUPPETEER_ROOT` |

グローバル root があるときは `DOCSFW_NODE_GLOBAL_ROOTS` を子プロセスのモジュール探索の先頭へ追加します。  
ローカル `node_modules` が残っていても、採用したグローバルが優先されます。
