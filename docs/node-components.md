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
5. `PATH` 上の `mmdc` または `widdershins` から推定する `node_modules`
6. `framework/docsfw/bin/node_modules`

5 の推定では、実行ファイルと同じ階層の `node_modules` を候補にします。  
Linux ではさらに、`<prefix>/bin/<name>` に対する `<prefix>/lib/node_modules` と、シンボリック リンクのリンク先を含む `node_modules` も候補にします。  
Linux では `command -v` を起動せず、`PATH` を直接走査します。  
`command` はシェルの組み込みコマンドであり、`/usr/bin/command` を同梱しないディストリビューションでは起動できないためです。  
走査では、実行権のある通常ファイルだけを採用します。  
`PATH` の空の要素はカレント ディレクトリとして扱います。  
Windows では `where` を使用します。

グローバルの版は `package.json` の semver 範囲を満たすときだけ採用します。  
範囲外のグローバルは欠落とみなし、ローカルへ補完します。

## プラットフォームの境界

実行中のプラットフォーム以外が所有する `node_modules` は、探索順から除外します。  
WSL からは Windows ドライブのマウント配下、Windows からは `\\wsl$` と `\\wsl.localhost` 配下が対象です。  
Windows ドライブのマウントは `/proc/mounts` から判定し、`drvfs` と、`aname=drvfs` を持つ 9p や virtiofs を対象とします。

同じ規則を `mmdc` と `widdershins` の探索にも適用します。  
`PATH` に他プラットフォームのディレクトリが含まれていても、そこにある実行ファイルとその `node_modules` は採用しません。  
Linux では他プラットフォームのディレクトリを飛ばして走査を続け、`PATH` の後方にあるネイティブの実行ファイルを採用します。

`sharp` のようにネイティブ バイナリを持つパッケージは、プラットフォームごとに異なる `@img/sharp-<platform>` を必要とします。  
WSL から Windows 用のツリーを読み込むと、`Could not load the "sharp" module using the linux-x64 runtime` で失敗します。

## オンデマンド導入

| 状態 | 動作 |
|---|---|
| 必須パッケージがすべて揃っている | npm を実行しません |
| 一部だけ欠けている | 欠けたトップレベルだけ `npm install --no-save <name>@<lockfile の version>` します |
| 必須パッケージがすべて欠けている | `bin/` で `npm ci` します |

`npm ci` と部分インストールのあいだは `PUPPETEER_SKIP_DOWNLOAD=1` です。  
Chrome 本体の取得は npm の処理とは独立しています。

導入は静的発行と動的発行のどちらの経路でも同じです。  
`bin/pub_markdown_core.sh` と `livedocs/bin/vendor_assets.py` のいずれも `--ensure` で呼び出し、npm の出力と進捗をそのまま端末へ表示します。  
Chrome の導入は静的発行だけが行います。動的発行は図をブラウザー上で描画するため、発行処理からブラウザーを起動しません。

## ブラウザー

| OS | 動作 |
|---|---|
| Windows | Microsoft Edge が必須です。存在しない場合はエラーで終了します。Puppeteer 用 Chrome はダウンロードしません |
| Linux | `PUPPETEER_EXECUTABLE_PATH` が実行可能な Chrome を指すときはそれを使用します |
| Linux | 外部 Chrome が存在しないときは、puppeteer モジュール解決のあと `npx puppeteer browsers install chrome` と `chrome-headless-shell` を実行します |

npm パッケージがグローバルで揃っていても、Linux で外部 Chrome が存在しなければブラウザーの導入が実行されます。

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

グローバルから採用したパッケージは、名前とディレクトリの対を `DOCSFW_NODE_GLOBAL_PACKAGES` へ渡します。  
`bin/docsfw-prefer-global-modules.js` が子プロセスの解決先をそのディレクトリへ固定し、ローカル `node_modules` が残っていても採用したグローバルを使用します。

固定は `require` と `import` の双方に適用します。  
ES モジュールの裸の指定子は ES モジュール ローダーだけが解決し、`require` のフック、`NODE_PATH`、グローバルの `node_modules` のいずれも参照しません。  
`import` を固定しないと、グローバルだけにパッケージがある環境で `.mjs` の読み込みが `ERR_MODULE_NOT_FOUND` になります。

| 解決の経路 | 固定の方法 |
|---|---|
| `require` | `Module._resolveFilename` を差し替え、採用先を含む `node_modules` からパッケージ名のまま解決します |
| `import` | `module.registerHooks()` の解決フックで、解決の起点を採用先の `node_modules` へ変更します |

`module.registerHooks()` を持たない Node.js では、`module.register()` で `bin/docsfw-prefer-global-modules.mjs` を登録します。  
判定の規則は `bin/docsfw-pinned-packages.js` に集約し、どちらの経路でも同じディレクトリを選びます。

採用先はディレクトリを直接指定せず、パッケージ名のまま解決します。  
ディレクトリを直接指定すると `package.json` の `exports` 定義を通らず、常に `main` が読み込まれます。  
`minisearch` のように `require` 用のエントリを別に持つパッケージでは、ブラウザー向けの UMD が選ばれて実行時に失敗します。  
`NODE_PATH` で `node_modules` 以外のディレクトリを採用した場合に限り、`require` はディレクトリへの読み替えで解決します。  
`import` はこの読み替えを行わないため、`NODE_PATH` にはパッケージを `node_modules` として配置してください。

固定はパッケージ単位です。  
探索先を root 単位で差し替えると、semver の範囲外として不採用にしたバージョンが実行時に再び参照されます。  
採用していないパッケージは、通常の Node.js の解決に従います。

静的発行は `bin/pub_markdown_core.sh`、動的発行は `livedocs/bin/vendor_assets.py` が同じ規則で子プロセスの環境を構築します。  
どちらの経路も解決は `bin/resolve-node-components.js` に一本化しており、プラットフォームの境界も共通です。
