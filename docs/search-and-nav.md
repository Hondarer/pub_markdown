# 全文検索・全体ナビゲーション機能

## 概要

HTML 出力に外部ネットワーク不要の全文検索と、全ページ常設のナビゲーションツリーを追加する機能です。
発行後の HTML を `file://` で直接開いた場合でも、またローカル HTTP サーバ経由でも動作します。

| 機能 | 説明 |
|---|---|
| 全文検索 | ページ タイトル・見出し・本文を対象に高速検索。日本語は bigram トークナイズで対応 |
| ナビゲーションツリー | 全ページを階層ツリーで常時表示。現在ページをハイライトし祖先ディレクトリを展開 |

## 動作の仕組み

### ビルド時 (pub_markdown_core.sh)

全 HTML ファイルの生成完了後、バリアント (`pages/<lang>[-details]/html/`) ごとに後処理として 2 つのスクリプトを実行します。

```
make docs → pub_markdown_core.sh
  ├─ [既存] 各 .md → pandoc → .html (テンプレートに検索/ナビ UI を注入)
  └─ [後処理] html ルートごとに:
       generate-nav-tree.py   → nav-tree.js      (ナビツリーデータ)
       build-search-index.mjs → search-index.js  (全文検索インデックス)
```

### 実行時 (ブラウザ)

各 HTML は `defer` でナビ関連スクリプトを読み込みます。
検索インデックス (3 MB 程度) は初回の検索操作まで遅延ロードして、ページ表示速度に影響しません。

```
各 .html の <body> 末尾:
  window.__DOCSFW_BASE__    = "../../";   ← html ルートへの相対パス
  window.__DOCSFW_CURRENT__ = "calc/index.html"; ← このページの相対パス
  <script defer src="../../nav-tree.js">  ← __DOCSFW_NAV__ を設定
  <script defer src="../../docsfw-nav.js"> ← ナビツリーを描画
  <script defer src="../../docsfw-search.js"> ← 検索 UI (遅延ロード管理)

初回検索時に動的ロード:
  minisearch.min.js → docsfw-tokenize.js → search-index.js
  → MiniSearch.loadJSON(__DOCSFW_INDEX__, options) で検索可能に
```

## 生成ファイル

### html ルート直下に配置される静的アセット

発行のたびに `pub_markdown_core.sh` が `styles/html/` 等からコピーします。

| ファイル | 内容 |
|---|---|
| `minisearch.min.js` | MiniSearch ライブラリ UMD ビルド (MIT ライセンス) |
| `docsfw-tokenize.js` | CJK bigram + ASCII tokenizer (Node / ブラウザ共有) |
| `docsfw-search.js` | 検索 UI スクリプト |
| `docsfw-nav.js` | ナビツリー描画スクリプト |
| `docsfw-ui.css` | 検索・ナビの CSS |

### html ルート直下に生成される動的アセット

発行のたびに後処理スクリプトが生成します。

| ファイル | 内容 | サイズ目安 |
|---|---|---|
| `nav-tree.js` | `window.__DOCSFW_NAV__` にツリー構造 JSON を設定 | 〜 70 KB |
| `search-index.js` | `window.__DOCSFW_INDEX__` に MiniSearch 直列化インデックス、`window.__DOCSFW_DOCS__` にページ一覧を設定 | 〜 3 MB |

## ファイル構成

```
framework/docsfw/
├── bin/
│   ├── docsfw-tokenize.js          bigram tokenizer (Node / ブラウザ共有)
│   ├── build-search-index.mjs      Node: 検索インデックス生成
│   └── generate-nav-tree.py        Python: ナビツリー生成
└── styles/html/
    ├── docsfw-search.js            ブラウザ: 検索 UI
    ├── docsfw-nav.js               ブラウザ: ナビツリー描画
    └── docsfw-ui.css               ブラウザ: スタイル
```

## 設定

`.vscode/pub_markdown.config.yaml` で機能を制御できます。デフォルトはどちらも `true` です。

```yaml
# 全文検索機能の有無 (true / false)
# デフォルト: true
#htmlSearchEnable: true

# 全体ナビゲーションツリーの表示有無 (true / false)
# デフォルト: true
#htmlNavTreeEnable: true
```

## テンプレート変更点

`styles/html/html-template.html` に以下を追加しています。

### 本文マーカー

検索インデックス生成スクリプトが本文テキストを抽出する際のマーカーです。
テンプレートの chrome (navbar、サイドバー等) を除外し、本文のみを索引対象にします。

```html
<main id="docsfw-content">
  $body$
</main>
```

### サイドバー (`.span3`) への UI 挿入

`$if(search-enable)$` ガードの下、BACK/HOME リンクの直後に挿入します。

```html
<div id="docsfw-search-container"></div>   ← 検索ボックスが動的に挿入される
<nav id="docsfw-tree"></nav>               ← ナビツリーが描画される
<hr class="docsfw-toc-separator" />
```

### `</body>` 直前の JS

```html
<div id="docsfw-search-results"></div>
<script>
  window.__DOCSFW_BASE__    = "$search-base$";
  window.__DOCSFW_CURRENT__ = "$search-current$";
</script>
<script defer src="${search-base}nav-tree.js"></script>
<script defer src="${search-base}docsfw-nav.js"></script>
<script defer src="${search-base}docsfw-search.js"></script>
```

`$search-base$` は `up_dir` (ページ深さ分の `../`) と同じ値です。
`$search-current$` はページの `html/` ルートからの相対パス (例: `calc/index.html`) です。

## 検索エンジン (MiniSearch)

[MiniSearch](https://github.com/lucaong/minisearch) v7 を使用します。

### インデックスフィールド

| フィールド | 重み | 内容 |
|---|---|---|
| `title` | 5 | `<title>` タグのテキスト |
| `headings` | 3 | `<h1>`〜`<h3>` のテキスト |
| `text` | 1 | `<main id="docsfw-content">` 内の本文 (上位 30,000 文字) |

### 日本語対応 (bigram トークナイザ)

`bin/docsfw-tokenize.js` でインデックス構築時とブラウザ検索時の両方に同一トークナイザを適用します。

| 文字種 | トークナイズ方式 |
|---|---|
| CJK (ひらがな/カタカナ/漢字等) | 重なり 2-gram。1 文字のみの場合は 1-gram |
| ASCII/英数 | 非英数字で分割、小文字化 |

例: `電卓計算機` → `["電卓", "卓計", "計算", "算機"]`

### file:// 対応

`fetch()` は `file://` スキームで CORS により失敗します。
本機能では検索インデックスを `<script src>` で読む `.js` 形式にすることで、`file://` でも動作します。

## ナビゲーションツリー (generate-nav-tree.py)

`html/` 配下の `*.html` を走査し、各ページの `<title>` を抽出してツリーを構築します。

- `index.html` はそのディレクトリのノードとして扱います (URL はそのページを指します)
- 子要素はファイル名の大文字小文字を無視したアルファベット順にソートします
- 除外: `search-index.js`、`nav-tree.js`、`docsfw-*.js`、`docsfw-*.css`、`html-style.css`、`mermaid.min.js`

ブラウザ側の `docsfw-nav.js` は `__DOCSFW_NAV__` を読み込み、`<details>`/`<summary>` で折り畳みツリーを描画します。
現在ページは `__DOCSFW_CURRENT__` と URL 照合してハイライトし、祖先ディレクトリを自動展開します。

## 部分発行 (`--relativeFile`) 時の動作

VS Code タスクや `pub_markdown_core.sh --relativeFile=...` で特定のファイル/フォルダーのみを発行した場合の挙動を示します。

### HTML 生成

**指定した対象のみ**が pandoc で変換され、新テンプレートが適用されます。

| 実行モード | 対象 | 出力クリーン |
|---|---|---|
| `singlefile` | 指定した 1 ファイル | なし |
| `folder` | 指定フォルダー配下の全ファイル | 指定フォルダーの出力を削除後に再生成 |

指定範囲外の既存 HTML は変更されません。

### 後処理 (nav-tree.js / search-index.js)

**後処理フックは実行モードによらず常に実行**されます。
対象の `.md` が 1 ファイルであっても、後処理は **html/ ルート全体**を走査して全バリアント分を再生成します。

```
どの実行モードでも同じ後処理ループ:

lang (ja en) × details_suffixes ("" "-details") の全組み合わせに対して
  generate-nav-tree.py  → html/ 全 HTML を走査 → nav-tree.js を再生成
  build-search-index.mjs → html/ 全 HTML を走査 → search-index.js を再生成
```

結果として、部分発行後でも **nav-tree.js と search-index.js は常に全ページ分が最新**になります。

### 再生成済みページと旧ページの混在

部分発行後は、新テンプレートが適用されたページとそうでないページが混在します。

| | 今回の発行で再生成されたページ | 今回の発行対象外の旧ページ |
|---|---|---|
| 検索ボックス・ナビツリーの表示 | される | されない |
| nav-tree.js の収録 | される | される |
| search-index.js の索引 | `<main id="docsfw-content">` から高精度抽出 | `<body>` 全体からのフォールバック抽出 |

旧ページ自体には UI が表示されませんが、再生成済みページの検索・ナビツリーから旧ページへ遷移することは可能です。

### 後処理のコスト

後処理は常に html/ 全体を読み込むため、**1 ファイルの変更でも全件処理のコストが発生**します。

```
例: 1 ファイルの部分発行 (details: both, lang: ja en の場合)

  pandoc 変換:                      〜1 秒
  後処理 4 バリアント × 2 スクリプト:  〜20 秒
    (4 バリアント × 614 ページ走査 × nav + search)
```

### フルビルドとの整合

`make cleandocs && make docs` を実行すると、全ページが新テンプレートで再生成され完全に整合します。
部分発行は作業中のページを確認する目的では問題なく機能しますが、公開前にはフルビルドを推奨します。

## 注意事項

### インデックスの更新タイミング

`pub_markdown_core.sh` のタイムスタンプスキップにより、変更のない `.md` は再生成されません。
`search-index.js` と `nav-tree.js` は毎回の発行で再生成されますが、索引対象の HTML 自体が古い場合、
そのページの `<main id="docsfw-content">` マーカーが存在しないため本文抽出の精度がやや下がります。
フルビルド (`make cleandocs && make docs`) で全ページに新テンプレートが適用されます。

### インデックスサイズ

614 ページを索引化した場合の目安:

| ファイル | サイズ |
|---|---|
| `search-index.js` | 約 3 MB |
| `nav-tree.js` | 約 70 KB |

`htmlSearchEnable: false` にすると `search-index.js` の生成とビルド時間を削減できます。
