# AGENTS.md

## 対象

Pandoc による静的発行と、mkdocs による動的発行を提供します。

## 作業別の入口

- 発行処理は `bin/pub_markdown_core.sh`、フィルターは `bin/pandoc-filters/`、出力書式は `styles/`
- Node.js 依存関係を変更する場合は `bin/resolve-node-components.js`、`bin/package.json`、`bin/package-lock.json` と [Node コンポーネント](docs/node-components.md)
- 動的発行を変更する場合は `livedocs/` と [動的発行基盤](docs/livedocs-design.md)
- ブラウザー起動を変更する場合は `pub_markdown_core.sh` と `bin/prepare_puppeteer_env.sh`、`bin/chrome-wrapper.sh`、`bin/mmdc-wrapper.sh` の Linux / Windows の分岐
- 利用方法が必要な場合は [README.md](README.md)、文書を探す場合は [文書一覧](docs/README.md)

## 変更時の確認

表示を変更する場合は CSS とフィルターの影響を確認してください。  
静的発行を変更する場合は、動的発行側にも同じ規則が必要か確認してください。  
テンプレートの literal `$` は Pandoc 用のエスケープが必要です。  
該当する変更や Windows の実行障害では、[保守と検証](docs/maintenance-verification.md) の該当節を参照してください。  
局所発行のコマンドと再生成の条件も同文書にあります。
