# AGENTS.md

## 重要事項

- 自動ステージング、コミット禁止。指示があるまでステージング、コミットは行わないこと。
- 思考の断片は英語でもよいが、ユーザーに気づきを与えたり報告する際は日本語を用いること。

## リポジトリ概要

Pandoc を中心に、Markdown から HTML や docx を生成するための発行フレームワークです。PlantUML、Mermaid、Widdershins、各種 Pandoc フィルターを組み合わせて文書生成を行います。

## 作業時の入口

- `bin/pub_markdown_core.sh` - 発行処理の中心スクリプト
- `bin/package.json` - Node.js 依存関係
- `bin/pandoc-filters/` - Lua、Python、Shell のフィルター群
- `bin/prepare_puppeteer_env.sh`、`bin/chrome-wrapper.sh`、`bin/mmdc-wrapper.sh` - ブラウザー依存処理の補助
- `styles/` - HTML、docx、Widdershins 向けのスタイルやテンプレート
- `lib/` - draw.io などの補助資材
- `docs/` - 実装メモと運用ドキュメント

## 主要コマンド

```bash
cd bin
npm ci / npm install
cd ..
bash bin/pub_markdown_core.sh --workspaceFolder=/path/to/workspace
```

## Windows でのコマンド実行

このリポジトリのコマンド (make、Python スクリプト、シェル スクリプトなど) は UTF-8 を前提としている。  
Windows コンソールのデフォルトは cp932 (Shift-JIS) のため、日本語や記号の出力が文字化けしたり `UnicodeEncodeError` になる場合がある。

コマンドを実行する前にコード ページを UTF-8 に切り替えること。

```bash
chcp 65001
```

`bin/` 配下の Python スクリプトはスクリプト内で `sys.stdout.reconfigure(encoding="utf-8")` を設定済みのため、`-X utf8` オプションは不要。  
新たに日本語出力を含む Python スクリプトを追加するときは、同様の設定を先頭に追加すること。

`python bin/text_style_jp.py --test` は `tempfile.TemporaryDirectory()` を使用してユーザーの一時ディレクトリへ書き込むため、エージェントのサンドボックス外で実行すること。

サンドボックス内で実行すると、Windows の一時ディレクトリへの書き込みが拒否され、辞書読み込みテストと `--in-place` テストが失敗する。

## 注意点

- Linux と Windows でブラウザー起動経路が異なる。Puppeteer、Edge、Chromium 関連の変更では `pub_markdown_core.sh` とラッパー スクリプトを同時に確認すること。
- `bin/pub_markdown_core.sh` は `node_modules` がなければ自動で `npm ci` を試みる。依存更新では `package.json` とスクリプト双方の整合を保つこと。
- 出力整形は Pandoc フィルターと `styles/` に分散しているため、見た目の変更では CSS だけでなくフィルターの影響も確認すること。
- `styles/html/html-template.html` は Pandoc テンプレートとして処理されるため、インライン JavaScript 内の literal `$` (正規表現の `/foo$/` など) は `$$` にエスケープすること。エスケープ漏れは「Error compiling template ... expecting "()"」でページ全体の生成が失敗する。テンプレートに JS を追加したらビルド ログの「Error compiling template」を必ず確認する。テンプレートや CSS の変更はタイムスタンプ スキップの対象外のため、フルビルドでは `pages` の削除が必要 (`rm -rf pages && bash bin/pub_markdown_core.sh --workspaceFolder="$PWD" --details=both --docxOutput=true`)。オプション名は `--docxOutput=` であり、`--docx=` は黙って無視される。
