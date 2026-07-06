# Doxygen 単一ページ リンク機能

## 概要

`pub_markdown_core.sh` による HTML 発行において、各ページのナビバー右側に、対応する Doxygen HTML 単一ページへのリンクを表示します。  
表示位置は「詳細切り替え」と「Git 単一ページ リンク」の間です。  
リンクのアイコンには Doxygen ロゴを使用します。

## 表示条件

リンクは次の条件を満たす場合に表示します。

- `doxygenLinkEnable` が `true` である。
- Markdown の front matter に `doxygen-page-url` が存在する。

`doxygen-page-url` が存在しない通常の手書き Markdown では、リンクは表示されません。

## URL 解決の仕組み

doxyfw は Doxygen tag file を読み取り、Doxybook2 が生成した `Files/` 配下の Markdown に `doxygen-page-url` を埋め込みます。  
値は workspace ルートからの相対パスです。

```yaml
---
summary: "calc ライブラリの公開アンブレラ ヘッダー。"
short-title: "calc.h"
doxygen-page-url: "pages/doxygen/calc_public/calc_8h.html"
---
```

docsfw は発行時に、出力 HTML のディレクトリから `doxygen-page-url` が指すファイルへの相対 URL を計算します。  
この計算は通常 HTML と self-contain HTML の両方で同じです。  
self-contain HTML では Doxygen アイコンの SVG も HTML に埋め込まれます。
Doxygen リンクは `doxygen-page` を `target` に指定し、シングルページと依存関係レポートで同じタブまたはウィンドウを再利用します。

## 設定

`pub_markdown.config.yaml` で次のオプションを指定します。

```yaml
# Doxygen 単一ページ リンクの有効化 (true / false)。デフォルト: true
doxygenLinkEnable: true
```

この設定を `false` にすると、`doxygen-page-url` が存在するページでも Doxygen リンクを表示しません。

## doxyfw 生成 md の連携

Doxygen HTML の実ファイル名は Doxygen が生成する tag file から取得します。  
このため、`calc_8h.html` や `md_README.html` のような Doxygen 固有のファイル名を docsfw 側で再実装しません。

doxyfw 側の埋め込みは `templates/inject-doxygen-url.py` が担当します。  
詳細は doxyfw 側の `docs/doxygen-page-url-hint.md` を参照してください。

## 補足

リンク先 URL の到達性はネットワーク確認しません。  
Doxygen HTML と docsfw HTML が同じ workspace の `pages/` 配下に生成される前提で、発行時に相対 URL を計算します。
