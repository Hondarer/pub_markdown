# AGENTS.md

## リポジトリ概要

Pandoc を中心に、Markdown から HTML や docx を生成するための発行フレームワークです。PlantUML、Mermaid、Widdershins、各種 Pandoc フィルターを組み合わせて文書生成を行います。

## 必須参照

- [README.md](README.md)
- [文書一覧](docs/README.md)

## 作業時の入口

- `bin/pub_markdown_core.sh` - 発行処理の中心スクリプト
- `bin/resolve-node-components.js` - npm コンポーネントの解決とオンデマンド補完
- `bin/package.json` - Node.js 依存関係
- [Node コンポーネント](docs/node-components.md) - 必須パッケージと解決順
- `bin/pandoc-filters/` - Lua、Python、Shell のフィルター群
- `bin/prepare_puppeteer_env.sh`、`bin/chrome-wrapper.sh`、`bin/mmdc-wrapper.sh` - ブラウザー依存処理の補助
- `styles/` - HTML、docx、Widdershins 向けのスタイルやテンプレート
- `livedocs/` - mkdocs による動的発行基盤 (docx は非対応)
- `lib/` - draw.io などの補助資材
- [docs/README.md](docs/README.md) - 実装メモと運用ドキュメントの入口

## 主要コマンド

```bash
bash bin/pub_markdown_core.sh --workspaceFolder=/path/to/workspace
```

必須 npm コンポーネントは `bin/resolve-node-components.js` が解決します。  
グローバルにあればそれを使い、欠けていればオンデマンドで導入します。  
詳細は [Node コンポーネント](docs/node-components.md) を参照してください。

このフレームワークは 2 本の発行系を持ちます。  
`bin/pub_markdown_core.sh` による静的発行と、`livedocs/` の mkdocs による動的発行です。

動的発行は、ワークスペース ルートで `make servedocs` (ローカル配信) または `make livedocs` (サイト生成) を実行します。  
設計は [動的発行基盤](docs/livedocs-design.md)、利用手順は [livedocs/README.md](livedocs/README.md) を参照してください。  
静的発行の処理を変更した場合は、動的発行側のステージングにも同じ規則が必要か確認してください。

## Windows でのコマンド実行

このリポジトリのコマンド (make、Python スクリプト、シェル スクリプトなど) は UTF-8 を前提としています。  
Windows コンソールのデフォルトは cp932 (Shift-JIS) のため、日本語や記号の出力が文字化けしたり `UnicodeEncodeError` になったりする場合があります。

コマンドを実行する前にコード ページを UTF-8 に切り替えてください。

```bash
chcp 65001
```

`bin/` 配下の Python スクリプトはスクリプト内で `sys.stdout.reconfigure(encoding="utf-8")` を設定済みのため、`-X utf8` オプションは不要です。  
新たに日本語出力を含む Python スクリプトを追加するときは、同様の設定を先頭に追加してください。

`python bin/text_style_jp.py --test` は `tempfile.TemporaryDirectory()` を使用してユーザーの一時ディレクトリへ書き込むため、エージェントのサンドボックス外で実行してください。

サンドボックス内で実行すると、Windows の一時ディレクトリへの書き込みが拒否され、辞書読み込みテストと `--in-place` テストが失敗します。

## 注意点

- Linux と Windows でブラウザー起動経路が異なります。Puppeteer、Edge、Chromium 関連の変更では `pub_markdown_core.sh` とラッパー スクリプトを同時に確認してください。
- `bin/pub_markdown_core.sh` は `bin/resolve-node-components.js` で npm コンポーネントを解決します。依存関係を更新する場合は、`package.json`、`package-lock.json`、[Node コンポーネント](docs/node-components.md) を同時に更新してください。
- 出力処理は Pandoc フィルターと `styles/` に分散しています。表示を変更する場合は、CSS とフィルターの影響を確認してください。
- `styles/html/html-template.html` は Pandoc テンプレートとして処理されるため、インライン JavaScript 内の literal `$` (正規表現の `/foo$/` など) は `$$` にエスケープしてください。エスケープがない場合は「Error compiling template ... expecting "()"」によりページ全体の生成が失敗します。テンプレートに JS を追加した場合は、ビルド ログの「Error compiling template」を必ず確認してください。テンプレートや CSS の変更はタイムスタンプ スキップの対象外であるため、フル ビルドでは `pages` の削除が必要です (`rm -rf pages && bash bin/pub_markdown_core.sh --workspaceFolder="$PWD" --details=both --docxOutput=true`)。オプション名は `--docxOutput=` であり、`--docx=` は指定しても無視されます。
