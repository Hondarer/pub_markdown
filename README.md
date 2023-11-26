# pub_markdown

markdown to html and docx with pandoc.

# 前提環境

+ Visual Studio Code on Windows
+ Microsoft Word
+ Git for Windows (Git Bash)
+ [Markdown Preview Enhanced](https://marketplace.visualstudio.com/items?itemName=shd101wyy.markdown-preview-enhanced)
+ [Draw.io Integration](https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio)
+ [PlantUML](https://marketplace.visualstudio.com/items?itemName=jebbs.plantuml)
+ [pandoc](https://github.com/jgm/pandoc)

## オプション

+ [gitbucket](https://github.com/gitbucket/gitbucket)
+ [Pegmatite-gitbucket](https://chromewebstore.google.com/detail/pegmatite-gitbucket/gkdjfofhecooaojkhbohidojebbpcene?pli=1)

# 利用方法

## セットアップ

+ Git Bash の bash.exe に PATH を通す。
+ pandoc.exe に PATH を通す。
  bin フォルダ直下に pandoc.exe を配置してもよい。
+ bin/modules/LibDeflate に、[SafeteeWoW/LibDeflate](https://github.com/SafeteeWoW/LibDeflate) を配置する。

## Markdown のビルド方法

+ Visual Studio Code で、タスク "exec pandoc" を実行する。
  (Ctrl + Shift + B)

あるいは

+ Git Bash で、exec-pandoc.sh を実行する。

## 既知の問題

以下のような記載で `--shift-heading-level-by=-1` を指定していても title タグを得ることができない。
pandoc に渡す前に、第 1 レベルの内容を取得して設定する必要がある。
(lua フィルタの段階では、`--shift-heading-level-by=-1` が効果を出してしまうため、第 1 レベルの内容は得られない。)

```
<!--ja:-->
# トップレベルの index
<!--:ja-->
<!--en:
# index of top level
:en-->
```

```
This document format requires a nonempty <title> element.
  Defaulting to '-' as the title.
  To specify a title, use 'title' in metadata or --metadata title="...".
```