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

## 解決済の問題

### 多言語対応時に title を得られない問題

以下のような記載で `--shift-heading-level-by=-1` を指定していても title タグを得ることができない。
pandoc に渡す前に、第 1 レベルの内容を取得して設定した。
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

### docx 変換時に表示される警告

docx 変換時に、以下の警告が表示される。
動作に支障ないため、表示しないようにしている。

```
check that rsvg-convert is in path.\nrsvg-convert: createProcess: does not exist (No such file or directory)
```

### PlantUML を docx に取り込んだ際のフォント名

svg ファイルの指定フォントが Sans Serif となっているため、docx に取り込んだ際にフォントが正しく設定されない。
pu_config.format が svg の場合は、font-family="sans-serif" (デフォルトの場合のフォント名) を、font-family="メイリオ, Helvetica Neue, Helvetica, Arial, sans-serif" に置換するように改修。

## 既知の問題

## TODO:

- メタデータを本文と分離したい。コマンドライン上で Markdown ファイルと並列して与えるか、--metadata-file オプションで与える。
- 出力先を /doc にしたほうがいいか。(GitBucket Pages でのデフォルトパスは、/doc)
- Word に出力した表を中央揃えにする方法が不明。
