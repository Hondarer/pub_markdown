# pub_markdown

Markdown ソースから HTML や PDF などの技術文書を発行するフレームワークです。

Pandoc による静的発行と MkDocs による動的発行 (livedocs) の 2 系統を備え、文章規範の機械検査、図や数式の描画、目次や検索機能を提供します。

## 重要な文書

### 文書の執筆と表記規範

Markdown の文章や記法を作成・推敲する際に参照します。

- [日本語技術文書の文章規範](japanese-technical-writing-guideline.md) - リポジトリ共通の文章構成・表現ルール
- [日本語スタイル チェッカー](text_style_jp.md) - 機械的な表記・Markdown 書式の自動整形ツール
- [表のキャプション](table-caption.md) - 表題と Table: 記法の指定規則
- [見出し書式](heading-style.md) - 見出しレベルと目次生成の規則

### ドキュメントの発行と構成

ドキュメントの発行処理や発行対象を設定する際に参照します。

- [発行処理の構成](pipeline.md) - 静的発行パイプラインのアーキテクチャーと処理フロー
- [動的発行基盤](livedocs-design.md) - MkDocs による動的発行基盤 (livedocs) の設計
- [発行対象の指定](pubparts.md) - pubpart.mk による発行対象ファイルの構成

### フレームワークの保守

docsfw のテンプレートやスクリプトを変更する際に参照します。

- [発行処理の保守と検証](maintenance-verification.md) - テンプレートやスクリプト変更時の検証手順

## 文書一覧

\toc depth=-1 exclude-basedir=true
