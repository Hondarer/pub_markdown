# 動的発行の Python 依存

動的発行は、必要な依存が揃っていればシステム Python を使用します。  
不足または範囲外の依存がある場合だけ、`livedocs/.venv` へ補完します。  
依存の判定と導入、実行する Python の選択は `livedocs/bin/resolve_python_components.py` に集約します。

## 採用範囲と補完用の固定版を分ける

既存環境から採用する安定版の範囲は `livedocs/requirements-compatible.txt` に記載します。  
不足分を補完する固定版は `livedocs/requirements.txt` に記載します。  
補完用の固定版は、採用範囲を満たす必要があります。  
範囲の記法は `==`、`>=`、`<` と数値のリリース番号に限定し、プレリリース、開発版、ローカル版は採用しません。

MkDocs Material は `9.7.7` に固定します。  
独自の `theme/partials/` がこの版のテンプレートを基にしているため、許容する版を広げる場合はテンプレートと関連テストを確認します。

| 項目 | Pandoc の Node.js 依存 | MkDocs の Python 依存 |
|---|---|---|
| 探索順 | グローバル、ローカルの順 | システム Python、専用 venv の順 |
| 採用条件 | `package.json` の版指定を満たす | 採用範囲を満たし、必要なモジュールを読み込める |
| 全依存が揃っている場合 | npm を実行しない | venv 作成と pip 導入を実行しない |
| 一部不足する場合 | 不足分だけローカルへ導入 | venv に不足分だけ導入 |
| 全部不足する場合 | `npm ci` | 固定版一覧から全依存を導入 |
| 補完する版 | `package-lock.json` の固定版 | `requirements.txt` の固定版 |
| 既存のローカル環境 | 依存を再確認して再利用 | 依存を再確認して再利用 |

Table: 静的発行と動的発行の依存を採用する条件

## 不足分はシステム側を参照する venv へ導入する

`make livedocs-venv` は毎回システム Python の依存を確認します。  
システム Python は既定で `python3` です。  
別の実行ファイルを使う場合は `LIVEDOCS_SYSTEM_PYTHON` にそのパスを指定します。

システム側で全依存が揃っている場合は、既存 venv があってもシステム Python を使用します。  
不足がある場合は、`--system-site-packages` 付きの venv を使用します。  
従来の独立した venv は、導入済みパッケージを保持してシステム側への参照を有効にします。  
venv 内のパッケージがシステム側より優先されるため、venv の依存も確認します。

一部不足する場合は、そのパッケージの固定版だけを pip に指定します。  
全部不足する場合は `requirements.txt` 全体を指定します。  
推移的依存が必要な場合は、pip がそれらも導入します。  
導入時には採用範囲のファイルを制約として渡し、システム側へは導入しません。  
同じ固定版が導入済みでも読み込みに失敗する場合は再導入し、導入後も不足が残れば失敗します。

発行と `make bin-test` は、選択した同じ Python を使用します。  
文書の準備とアセット配置も、この Python で実行します。  
スクリプトのテストでは `PYTHON` に選択結果を渡し、Python と Node.js のテストで共有します。  
MkDocs は選択した Python の `-m mkdocs` で実行します。  
`stopdocs` は設定ファイルの絶対パスで配信を識別するため、システム Python による配信も停止できます。

## CI ではローカル環境とダウンロードをキャッシュする

統合ワークスペースの GitHub Actions は、スクリプトのテスト前に Node.js と Python のキャッシュを復元します。  
動的発行のキャッシュ対象は `.venv` と pip キャッシュです。  
システム Python に pip がない場合、pip キャッシュのパスは出力せず、`.venv` だけを対象とします。  
Node.js 側は `node_modules` と npm キャッシュを対象とし、Linux では Puppeteer のブラウザー キャッシュも保持します。

| 状態 | Pandoc の Node.js 依存のキャッシュ対象 | MkDocs の Python 依存のキャッシュ対象 |
|---|---|---|
| システム側に全依存が揃っている | パッケージ導入用には原則不要 | 原則不要 |
| 一部不足・版が範囲外 | `bin_internal/node_modules/` と npm キャッシュ | `livedocs/.venv/` と pip キャッシュ |
| 全部不足 | npm キャッシュ。`npm ci` は `node_modules/` を再作成する | `livedocs/.venv/` と pip キャッシュ |
| 既存のローカル環境を再利用 | `bin_internal/node_modules/` | `livedocs/.venv/` |

Table: 依存の充足状況に応じた CI のキャッシュ対象

npm と pip のキャッシュ パスは、`npm config get cache` と `python -m pip cache dir` で取得します。  
Puppeteer のブラウザー キャッシュは、npm パッケージが揃っている場合も別途必要になることがあります。

venv のキャッシュ キーには、OS、CPU、Python の版と絶対パス、venv の絶対パス、システム側の配布物の一覧、依存定義と導入処理の内容を含めます。  
復元後も依存を再確認します。  
venv は配置を移せないため、Python や配置が変わった場合は再作成します。  
別の Python で作成された venv が残っている場合は、自動で上書きせず再作成を求めます。  
詳細は [Python の venv の仕様](https://docs.python.org/3/library/venv.html#how-venvs-work) を参照してください。

Node.js のキャッシュ キーには、OS、CPU、Node.js の版と `package.json`、`package-lock.json` の内容を含めます。
