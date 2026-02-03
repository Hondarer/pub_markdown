# サブモジュール mdRoot マージ機能

## 概要

`pub_markdown_core.sh` によるドキュメント発行処理において、プロジェクトルート直下に存在するサブモジュール内の `mdRoot` ディレクトリを、メインの `mdRoot` (デフォルト: `docs-src`) 配下にマージします。

### 背景

サブモジュール構成を採用したプロジェクトでは、各サブモジュール (`doxyfw`, `testfw`, `makefw` 等) はそれぞれ独自の `docs-src` ディレクトリを持っています。  
これらのドキュメントを統合的に発行するためには、サブモジュール内のドキュメントをメインプロジェクトの `docs-src` 配下にあるかのように扱う必要があります。

## 設定

### 設定ファイル

`pub_markdown.config.yaml` で対象サブモジュールを指定します。

```yaml
# サブモジュール mdRoot マージ機能
# マージ対象のサブモジュールをスペース区切りで指定
# 空または未指定の場合は機能無効
mergeSubmoduleDocs: doxyfw makefw testfw docsfw
```

### 設定値

| 設定値 | 動作 |
|--------|------|
| 空または未指定 | 機能無効 |
| サブモジュール名リスト | 指定されたサブモジュールのみマージ対象 |

## パス変換ルール

### 基本ルール

| 種類 | 実パス | 仮想パス |
|------|--------|----------|
| サブモジュールドキュメント | `{submodule}/{mdRoot}/{path}` | `{mdRoot}/{submodule}/{path}` |
| メインドキュメント | `{mdRoot}/{path}` | `{mdRoot}/{path}` |

### パス変換の具体例

| ステップ | makefw の例 | testfw の例 |
|----------|-------------|-------------|
| 実パス | `makefw/docs-src/make-local.md` | `testfw/docs-src/how-to-mock.md` |
| 仮想パス | `docs-src/makefw/make-local.md` | `docs-src/testfw/how-to-mock.md` |
| mdRoot からの相対 | `makefw/make-local.md` | `testfw/how-to-mock.md` |
| HTML 出力 | `docs/ja/html/makefw/make-local.html` | `docs/ja/html/testfw/how-to-mock.html` |

## relativeFile パラメータ

### 受け入れ可能なパス形式

`mergeSubmoduleDocs` が指定されている場合、`relativeFile` に以下のパス形式を受け入れます。

| パス形式 | 例 | 動作 |
|----------|-----|------|
| メイン mdRoot パス | `docs-src/build-design.md` | 従来通り処理 |
| 実パス(主) | `makefw/docs-src/make-local.md` | 実パスを内部で仮想パスに変換して処理 |
| 仮想パス(拡張) | `docs-src/makefw/make-local.md` | 仮想パスを実パスに変換して処理 |

### フォルダ指定時の動作

| 指定パス | 処理対象 |
|----------|----------|
| `docs-src` | メイン mdRoot + 指定サブモジュールの mdRoot |
| `docs-src/makefw` | makefw サブモジュールの mdRoot 配下のみ |
| `makefw/docs-src` | makefw サブモジュールの mdRoot 配下のみ (実パス指定) |

## 目次生成

`\toc` コマンドによる目次生成時、指定サブモジュールのドキュメントも含まれます。

目次リンクの生成例:

```markdown
- 📁 [makefw](makefw/index.md)
  - 📄 [make-local.md](makefw/make-local.md)
  - 📄 [template-auto-selection.md](makefw/template-auto-selection.md)
```

## ネストしたサブモジュール

サブモジュール内のサブモジュールも処理可能です。

```yaml
# 例: testfw/gtest も対象にする場合
mergeSubmoduleDocs: doxyfw makefw testfw testfw/gtest
```

この場合のパス変換:

| 実パス | 仮想パス | HTML 出力 |
|--------|----------|-----------|
| `testfw/gtest/docs-src/MANUAL_BUILD.md` | `docs-src/testfw/gtest/MANUAL_BUILD.md` | `docs/ja/html/testfw/gtest/MANUAL_BUILD.html` |

## 制約事項

1. **サブモジュール名の重複**: メイン `mdRoot` 配下に同名のディレクトリが存在する場合は、メイン側を優先します。
2. **相対パスリンク**: サブモジュール内ドキュメントから他のサブモジュールへの相対パスリンクは、正しく解決されない可能性があります。
