# サブモジュールドキュメントマージ機能

## 概要

`pub_markdown_core.sh` によるドキュメント発行処理において、指定したドキュメントルートを、メインの `mdRoot` (デフォルト: `docs`) 配下にマージします。

### 背景

サブモジュール構成や補助ディレクトリを採用したプロジェクトでは、各領域 (`doxyfw`, `testfw`, `makefw`, `.claude/skills` 等) ごとに独自のドキュメントルートを持つ場合があります。  
これらを統合的に発行するために、各ドキュメントルートをメインプロジェクトの `docs` 配下にあるかのように扱います。

## 設定

### 設定ファイル

`pub_markdown.config.yaml` で対象ドキュメントルートを指定します。

```yaml
# サブモジュールドキュメントマージ機能
# マージ対象のドキュメントルートをスペース区切りで指定
# 空または未指定の場合は機能無効
mergeSubmoduleDocs: doxyfw=framework/doxyfw/docs makefw=framework/makefw/docs testfw=framework/testfw/docs docsfw=framework/docsfw/docs skills=.claude/skills
```

### 設定値

| 設定値 | 動作 |
|--------|------|
| 空または未指定 | 機能無効 |
| `alias=path` | 表示名と実パスを分離して使用 |

`path` はワークスペースルートからの相対パスで指定し、マージ対象ディレクトリそのものを指します。  
`alias` 省略記法はサポートしません。

## パス変換ルール

### 基本ルール

| 種類 | 実パス | 仮想パス |
|------|--------|----------|
| マージ対象ドキュメント | `{configuredPath}/{path}` | `{mdRoot}/{alias}/{path}` |
| メインドキュメント | `{mdRoot}/{path}` | `{mdRoot}/{path}` |

### パス変換の具体例

| ステップ | makefw の例 | testfw の例 |
|----------|-------------|-------------|
| 実パス | `framework/makefw/docs/make-local.md` | `framework/testfw/docs/how-to-mock.md` |
| 仮想パス | `docs/makefw/make-local.md` | `docs/testfw/how-to-mock.md` |
| mdRoot からの相対 | `makefw/make-local.md` | `testfw/how-to-mock.md` |
| HTML 出力 | `docs/ja/html/makefw/make-local.html` | `docs/ja/html/testfw/how-to-mock.html` |

alias を使う例:

| ステップ | docsfw の例 |
|----------|-------------|
| 設定値 | `docsfw=framework/docsfw/docs` |
| 実パス | `framework/docsfw/docs/pipeline.md` |
| 仮想パス | `docs/docsfw/pipeline.md` |
| HTML 出力 | `docs/ja/html/docsfw/pipeline.html` |

## relativeFile パラメータ

### 受け入れ可能なパス形式

`mergeSubmoduleDocs` が指定されている場合、`relativeFile` に以下のパス形式を受け入れます。

| パス形式 | 例 | 動作 |
|----------|-----|------|
| メイン mdRoot パス | `docs/build-design.md` | 従来通り処理 |
| 実パス(主) | `framework/makefw/docs/make-local.md` / `framework/docsfw/docs/pipeline.md` / `.claude/skills/create-mock/SKILL.md` | 実パスを内部で仮想パスに変換して処理 |
| 仮想パス(拡張) | `docs/makefw/make-local.md` | 仮想パスを実パスに変換して処理 |

### フォルダ指定時の動作

| 指定パス | 処理対象 |
|----------|----------|
| `docs` | メイン mdRoot + 指定ドキュメントルート |
| `docs/makefw` | makefw のドキュメントルート配下のみ |
| `framework/makefw/docs` | makefw のドキュメントルート配下のみ (実パス指定) |
| `docs/docsfw` | `framework/docsfw/docs` 配下のみ |
| `framework/docsfw/docs` | `framework/docsfw/docs` 配下のみ (実パス指定) |
| `docs/skills` | `.claude/skills` 配下のみ |
| `.claude/skills` | `.claude/skills` 配下のみ (実パス指定) |

## 目次生成

`\toc` コマンドによる目次生成時、指定ドキュメントルートの内容も含まれます。

目次リンクの生成例:

```markdown
- 📁 [makefw](makefw/index.md)
  - 📄 [make-local.md](makefw/make-local.md)
  - 📄 [template-auto-selection.md](makefw/template-auto-selection.md)
```

## ネストしたドキュメントルート

ネストしたドキュメントルートも処理可能です。

```yaml
# 例: testfw/gtest も対象にする場合
mergeSubmoduleDocs: doxyfw=framework/doxyfw/docs makefw=framework/makefw/docs testfw=framework/testfw/docs testfw/gtest=framework/testfw/gtest/docs docsfw=framework/docsfw/docs
```

この場合のパス変換:

| 実パス | 仮想パス | HTML 出力 |
|--------|----------|-----------|
| `framework/testfw/gtest/docs/MANUAL_BUILD.md` | `docs/testfw/gtest/MANUAL_BUILD.md` | `docs/ja/html/testfw/gtest/MANUAL_BUILD.html` |

## 制約事項

1. **エントリ形式**: `mergeSubmoduleDocs` は `alias=path` 形式のみ受け付けます。旧形式や alias 省略記法はエラーです。
2. **親ディレクトリ指定の禁止**: 指定した `path` の直下に `mdRoot` ディレクトリが存在する場合は、旧形式とみなしてエラーにします。`framework/makefw` ではなく `framework/makefw/docs` を指定してください。
3. **サブディレクトリ名の衝突**: メイン `mdRoot` 配下に同名のディレクトリが存在する場合は、メイン側を優先します。
4. **相対パスリンク**: マージ対象ドキュメント間の相対パスリンクは、正しく解決されない可能性があります。
