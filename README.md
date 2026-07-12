# pub_markdown

Markdown to html and docx with Pandoc.

## 前提環境

- Visual Studio Code on Windows
- Microsoft Word
- Git for Windows (Git Bash)
- [Markdown Preview Enhanced](https://marketplace.visualstudio.com/items?itemName=shd101wyy.markdown-preview-enhanced)
- [vscode-multilang-md](https://marketplace.visualstudio.com/items?itemName=TetsuoHonda.vscode-multilang-md)
- [Draw.io Integration](https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio)
- [PlantUML](https://marketplace.visualstudio.com/items?itemName=jebbs.plantuml)
- [pandoc](https://github.com/jgm/pandoc)
- node.js

### オプション

- [gitbucket](https://github.com/gitbucket/gitbucket)
- [Pegmatite-gitbucket](https://chromewebstore.google.com/detail/pegmatite-gitbucket/gkdjfofhecooaojkhbohidojebbpcene?pli=1)
- [pandoc-crossref](https://github.com/lierdakil/pandoc-crossref)

## 利用方法

### セットアップ

- pandoc に PATH を通す。
- pandoc-crossref に PATH を通す。
    - pandoc-crossref はオプション。存在しなくても動作する。
- node.exe に PATH を通す。Linux では nodejs モジュール パッケージに含まれる。
- bin 配下で、`npm ci` を行う。詳細手順は [how_to_setup_node_modules.md](bin/how_to_setup_node_modules.md) を参照のこと。

### Markdown の発行方法

- Visual Studio Code で、タスク "exec pandoc" (Ctrl + Shift + B) を実行する。
- 現在開いている Markdown のみを対象に発行を行う場合は、タスク "exec pandoc (current file)" を実行する。
- YAML front matter に `pub_markdown.skip: true` を定義した Markdown は HTML/docx の発行対象および目次生成対象から除外する。

### 進捗ログ

長時間処理の位置を確認したい場合は、`PUB_MARKDOWN_PROGRESS_LOG=1` を付けて実行する。  
共有ブラウザーの起動待機、対象ファイル収集、各出力形式の生成、TOC 生成の段階が stderr に出力される。

```bash
PUB_MARKDOWN_PROGRESS_LOG=1 bash bin/pub_markdown_core.sh --workspaceFolder=/path/to/workspace
```

### 無進捗監視

通常の発行では、時間を基準に Markdown ジョブを停止しない。  
大きな PlantUML 図や Pandoc の docx 変換は長時間になる場合があるためです。

ハング調査などで無進捗ジョブを停止したい場合だけ、`FILE_PROCESS_TIMEOUT_SEC` に秒数を指定する。  
タイムアウト時は対象ファイルと最後に記録した工程を出力する。  
未指定または `0` の場合は監視を無効にする。  
負数、小数、文字列を指定した場合は、Markdown ジョブを開始せずにエラーで終了する。

```bash
FILE_PROCESS_TIMEOUT_SEC=300 bash bin/pub_markdown_core.sh --workspaceFolder=/path/to/workspace
```

## ビルド結果公開 Pages

- [https://hondarer.github.io/pub_markdown/](https://hondarer.github.io/pub_markdown/)

## Third-Party Libraries

This project uses the following third-party libraries:

- [LibDeflate](https://github.com/SafeteeWoW/LibDeflate) (zlib License) - Copyright (C) 2018-2021 Haoqian He

## 解決済の問題

### 多言語対応時に title を得られない問題

以下のような記載で `--shift-heading-level-by=-1` を指定していても title タグを得ることができない。  
Pandoc に渡す前に、第 1 レベルの内容を取得して設定した。  
(lua フィルターの段階では、`--shift-heading-level-by=-1` が効果を出してしまうため、第 1 レベルの内容は得られない。)

```html
<!--ja:-->
# トップレベルの index
<!--:ja-->
<!--en:
# index of top level
:en-->
```

```text
This document format requires a nonempty <title> element.
  Defaulting to '-' as the title.
  To specify a title, use 'title' in metadata or --metadata title="...".
```

### PlantUML を docx に取り込んだ際のフォント名

svg ファイルの指定フォントが Sans Serif となっているため、docx に取り込んだ際にフォントが正しく設定されない。  
`pub_markdown.config.yaml` の `plantuml.format` が svg の場合は、font-family を、Word で日本語フォントとして解釈されやすい font-family="Segoe UI, メイリオ" に置換するように改修。

### 多言語ブロック内に : があると Pandoc が正しく解釈しない問題

旧 replace-tag.sh は、多言語タグを HTML コメントとして本文に残したまま Pandoc に渡していた。  
このため、多言語ブロック内に定義リスト記法 (`: 定義`) など `:` で始まる行があると、閉じタグや後続の言語ブロックが定義リストの `<dd>` 要素に取り込まれ、出力が破壊された。  
replace-tag.sh を行単位処理に再実装し、タグ行と非対象言語のコンテンツを Pandoc に渡す前に除去するようにしたことで解消。

## 既知の問題

### widdershins の問題

- テンプレートが Slate 向けのため、Pandoc 向けに変更する必要がある (一部作業中)。
- Request Body のサンプル記述が複数個ある場合に、最初の 1 つしか処理対象とされない (そもそも複数あることを想定していない)。
- operationId が重複した場合に、処理が不正となる。

### caption に改行を含む場合

plantuml の caption に '\n' を含む場合、docx writer で改行が正しく出力されない。

### 実行時に Error: Failed to launch the browser process! のエラーが発生する場合

Edge を更新後、`Error: Failed to launch the browser process!` が発生する場合がある。

この問題は、Windows を再起動することで解消する。

## ライセンス

[LICENSE](./LICENSE) を参照してください。

## TODO:

- [WeasyPrint](https://github.com/Kozea/WeasyPrint) の導入。
