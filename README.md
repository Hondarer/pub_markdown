# pub_markdown

Markdown to html and docx with Pandoc.

## 前提環境

+ Visual Studio Code on Windows
+ Microsoft Word
+ Git for Windows (Git Bash)
+ [Markdown Preview Enhanced](https://marketplace.visualstudio.com/items?itemName=shd101wyy.markdown-preview-enhanced)
+ [Draw.io Integration](https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio)
+ [PlantUML](https://marketplace.visualstudio.com/items?itemName=jebbs.plantuml)
+ [pandoc](https://github.com/jgm/pandoc)
+ [console-rsvg-convert](https://github.com/miyako/console-rsvg-convert)
+ node.js

### オプション

+ [gitbucket](https://github.com/gitbucket/gitbucket)
+ [Pegmatite-gitbucket](https://chromewebstore.google.com/detail/pegmatite-gitbucket/gkdjfofhecooaojkhbohidojebbpcene?pli=1)
+ [fix-jpdotx-for-pandoc](https://github.com/Hondarer/fix-jpdotx-for-pandoc)

## 利用方法

### セットアップ

+ pandoc.exe に PATH を通す。bin フォルダ直下に pandoc.exe を配置してもよい。
+ rsvg-convert.exe に PATH を通す。bin フォルダ直下に rsvg-convert.exe を配置してもよい。Linux では rsvg2-tools パッケージに含まれる。
+ node.exe に PATH を通す。bin フォルダ直下に node.exe を配置してもよい。Linux では nodejs モジュールパッケージに含まれる。
+ bin/modules/LibDeflate に、[SafeteeWoW/LibDeflate](https://github.com/SafeteeWoW/LibDeflate) を配置する。
+ bin 配下で、`npm install` を行う。詳細手順は [how_to_setup_node_modules.md](bin/how_to_setup_node_modules.md) を参照のこと。

### Markdown の発行方法

+ Visual Studio Code で、タスク "exec pandoc" (Ctrl + Shift + B) を実行する。
+ 現在開いている Markdown のみを対象に発行を行う場合は、タスク "exec pandoc (current file)" を実行する。

## 解決済の問題

### 多言語対応時に title を得られない問題

以下のような記載で `--shift-heading-level-by=-1` を指定していても title タグを得ることができない。
Pandoc に渡す前に、第 1 レベルの内容を取得して設定した。
(lua フィルタの段階では、`--shift-heading-level-by=-1` が効果を出してしまうため、第 1 レベルの内容は得られない。)

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
pu_config.format が svg の場合は、font-family="sans-serif" (デフォルトの場合のフォント名) を、font-family="メイリオ, Helvetica Neue, Helvetica, Arial, sans-serif" に置換するように改修。

## 既知の問題

### widdershins の問題

+ テンプレートが Slate 向けのため、Pandoc 向けに変更する必要がある(一部作業中)。
+ Request Body のサンプル記述が複数個ある場合に、最初の 1 つしか処理対象とされない(そもそも複数あることを想定していない)。
+ operationId が重複した場合に、処理が不正となる。

### docx 変換時に表示される警告

docx 変換時に rsvg-convert.exe が存在しない場合、以下の警告が表示される。
rsvg-convert.exe を配置することで解消される。

```text
check that rsvg-convert is in path.\nrsvg-convert: createProcess: does not exist (No such file or directory)
```

### Linux 環境における rsvg-convert

PlantUML の svg など、解釈できない旨のエラーを rsvg-convert が出力することがある。  
rsvg-convert が生成する png イメージは docx においてフォールバック画像として扱われるため、この処理が正しく動作しないと svg が docx に正しく埋め込まれない。

→ Linux 環境では、完全に動作しない。

## TODO:

+ 多言語ブロック内に `:` があると、Pandoc が正しく解釈しない。
+ シンプル版の html template で、toc と本文のそれぞれをスクロール可能にする。
+ [WeasyPrint](https://github.com/Kozea/WeasyPrint) の導入。
+ plantuml の caption に '\n' を含む場合、docx writer で改行が正しく出力されない。
