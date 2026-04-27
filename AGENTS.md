# AGENTS.md

## 重要事項

- 自動ステージング、コミット禁止。指示があるまでステージング、コミットは行わないこと。
- 思考の断片は英語でもよいが、ユーザーに気づきを与えたり報告する際は日本語を用いること。

## リポジトリ概要

Pandoc を中心に、Markdown から HTML や docx を生成するための発行フレームワークです。PlantUML、Mermaid、Widdershins、各種 Pandoc フィルタを組み合わせて文書生成を行います。

## 作業時の入口

- `bin/pub_markdown_core.sh` - 発行処理の中心スクリプト
- `bin/package.json` - Node.js 依存関係
- `bin/pandoc-filters/` - Lua、Python、Shell のフィルタ群
- `bin/prepare_puppeteer_env.sh`、`bin/chrome-wrapper.sh`、`bin/mmdc-wrapper.sh` - ブラウザー依存処理の補助
- `styles/` - HTML、docx、Widdershins 向けのスタイルやテンプレート
- `lib/` - draw.io などの補助資材
- `docs/` - 実装メモと運用ドキュメント

## 主要コマンド

```bash
cd bin
npm install
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

Python スクリプトを単体で実行する場合は `-X utf8` オプションも有効。

```bash
python -X utf8 bin/text_style_jp.py --test
```

## 注意点

- Linux と Windows でブラウザー起動経路が異なる。Puppeteer、Edge、Chromium 関連の変更では `pub_markdown_core.sh` とラッパー スクリプトを同時に確認すること。
- `bin/pub_markdown_core.sh` は `node_modules` がなければ自動で `npm install` を試みる。依存更新では `package.json` とスクリプト双方の整合を保つこと。
- 出力整形は Pandoc フィルタと `styles/` に分散しているため、見た目の変更では CSS だけでなくフィルタの影響も確認すること。
