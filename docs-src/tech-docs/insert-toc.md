# Pandoc 目次挿入 Lua フィルタ (insert-toc.lua)

## 概要

この Lua フィルタは、指定された Markdown ファイルが存在する階層以下の Markdown ファイルから、自動的に目次リストを生成し、対象ファイルに挿入します。

## 目次挿入の書式

### 基本書式

Pandoc Lua フィルタの慣例に従い、`\toc` コマンドを使用します。

```markdown
\toc
```

### パラメータ付き書式

```markdown
\toc depth=1 exclude="temp.md" exclude="draft/*"
```

### 書式の特徴

- `\newpage`, `\pagebreak` 等の既存 Pandoc コマンドと一貫性を持ちます。
- インライン記述で設定が完結します。
- 同一文書内で異なる設定の目次を複数配置可能です。

## パラメータ仕様

### 階層数指定 (depth)

```text
現在のディレクトリ/
├── index.md           # 階層0 (自身、目次挿入対象)
├── file1.md           # 階層0 (現在のディレクトリ)
├── subfolder1/        # 階層1 (1階層下)
│  ├── file2.md       # 階層1
│  └── subsubfolder/  # 階層2 (2階層下)
│      └── file3.md   # 階層2
└── subfolder2/        # 階層1 (1階層下)
    └── file4.md       # 階層1
```

指定方法を次に示す。

- `depth=0`: 現在のディレクトリのみ (デフォルト)
- `depth=1`: 現在のディレクトリ + 1階層下まで
- `depth=2`: 現在のディレクトリ + 2階層下まで
- `depth=-1`: 制限なし (全階層を掘り下げ)

### 除外パターン (exclude)

指定方法を次に示す。

```markdown
\toc exclude="temp.md"                    # 単一ファイル除外
\toc exclude="draft/*"                    # パターン除外
\toc exclude="temp.md" exclude="draft/*"  # 複数除外
```

除外パターン例を次に示す。

- `"README.md"`: 特定ファイル
- `"draft/*"`: ディレクトリ配下全て
- `"*.tmp"`: 拡張子による除外
- `"temp.md"`: 特定ファイル名

### 起点ディレクトリ指定 (basedir)

目次生成の起点となるディレクトリを指定します。指定しない場合は、`\toc` コマンドが記述されているファイルの存在するディレクトリが起点となります。

指定方法を次に示す。

```markdown
\toc basedir="docs"           # 現在のディレクトリからの相対パス
\toc basedir="docs/api"       # サブディレクトリを指定
\toc basedir="../other"       # 親ディレクトリからの相対パス
```

#### パス指定の基準

- **相対パス**: `\toc` コマンドが記述されているファイルの存在するディレクトリからの相対パス
- **絶対パス**: サポートされません（相対パスのみ）

#### 使用例

プロジェクトルートの `index.md` から、`docs/` サブディレクトリ以下の目次を生成する場合:

```text
project/
├── index.md          # \toc basedir="docs" を記述
├── README.md
└── docs/
    ├── guide.md
    └── api/
        └── reference.md
```

`index.md` 内で以下のように記述:

```markdown
# ドキュメント一覧

\toc basedir="docs" depth=-1
```

生成される目次:

```markdown
- 📄 [ガイド](docs/guide.md)
- 📁 [API](docs/api/index.md)
  - 📄 [リファレンス](docs/api/reference.md)
```

**注意**: 生成されるリンクは、`\toc` コマンドが記述されているファイルからの相対パスになります。

### デフォルト値

Lua フィルタ内で定義されるデフォルト値は以下の通りです。

```lua
local defaults = {
    depth = 0,        -- 現在のディレクトリのみ
    exclude = {},     -- 除外なし
    basedir = ""      -- 起点ディレクトリ指定なし（現在のディレクトリ）
}
```

## 使用例

### 基本的な使用例

#### 最小構成

```markdown
\toc
```

実行結果 (現在のディレクトリのみ)。

```markdown
- [Chapter1](chapter1.md)
- [Chapter2](chapter2.md)
```

#### 1 階層下まで指定

```markdown
\toc depth=1
```

実行結果。

index.md または index.markdown が存在する場合は、階層名に index.md または index.markdown へのリンクが生成される。そうでない場合は、階層名はリンクなし項目となる。

**ファイル優先順位**：

- `index.md` > `index.markdown`
- 大文字小文字は正規化 (`INDEX.md` → `index.md`として処理)

**階層名の表示ロジック**：

1. index.md が存在する場合：
   - index.md内の最初の `# タイトル` を使用
   - タイトルがない場合 → フォルダ名を使用
2. index.md が存在しない場合：
   - フォルダ名のみ (リンクなし)

```markdown
# プロジェクト概要

- [イントロダクション](intro.md)
- [チュートリアル](tutorial/index.md)
  - [基本操作](tutorial/basics.md)
  - [応用](tutorial/advanced.md)
- reference
  - [API](reference/api.md)

## 詳細
```

### 複数の目次の例

```markdown
## 現在のディレクトリ
\toc depth=0

## 全体構造
\toc depth=-1

## チュートリアルのみ
\toc depth=1 exclude="reference/*" exclude="intro.md"

## docs ディレクトリ以下のすべて
\toc basedir="docs" depth=-1

## API リファレンス（別ディレクトリ指定 + 除外）
\toc basedir="docs/api" depth=-1 exclude="internal/*"
```

## コマンド実行例

### 基本実行

```bash
pandoc -L index-filter.lua index.md -o output.html
```

### デバッグ実行

```bash
pandoc -L index-filter.lua --verbose index.md -o output.html
```

## キャッシュストレージ仕様

### 概要

`insert-toc.sh` は性能向上のため、ファイル情報と Markdown タイトルをキャッシュファイルに永続化します。

### キャッシュファイル

- **ファイルパス**: `/tmp/insert-toc-cache.tsv`
- **フォーマット**: TSV（タブ区切り）形式
- **文字エンコーディング**: UTF-8

### データ構造

各行は以下の 5 つのフィールドをタブで区切った構造です。

```text
絶対パス	ファイル名	種別	ベースタイトル	言語別タイトル
```

#### フィールド定義

1. **絶対パス**: ファイルまたはディレクトリの絶対パス
2. **ファイル名**: パスの最後の要素（ファイル名またはディレクトリ名）
3. **種別**: `file` または `directory`
4. **ベースタイトル**: ファイル名（拡張子除く）またはディレクトリ名
5. **言語別タイトル**: `言語コード:タイトル` の形式、複数言語は `|` で区切り

#### キャッシュ例

```text
/home/user/docs/intro.md	intro.md	file	intro	ja:イントロダクション
/home/user/docs/tutorial	tutorial	directory	tutorial
/home/user/docs/tutorial/basics.md	basics.md	file	basics	ja:基本操作
/home/user/docs/tutorial/index.md	index.md	file	index	ja:チュートリアル
```

### キャッシュ管理

- **リセット**: 外部でキャッシュファイルを削除してリセット
- **更新**: 一度作成されたエントリは無効化されず、言語別タイトルの追加のみ実行
- **スコープ**: パラメータに依存しない汎用的なキャッシュ

### Markdown タイトル抽出

- **対象**: Markdownファイル（`.md`, `.markdown`）のみ
- **抽出ルール**: 最初にヒットしたレベル 1 見出し（`# タイトル`）を採用
- **言語**: 現在は `ja`（日本語）固定

### ディレクトリタイトル解決

ディレクトリのタイトルは以下の優先順位で解決されます。

1. `index.md` > `index.markdown` の順で検索
2. 大文字小文字を正規化（`INDEX.md` → `index.md`）
3. 見つかった場合、そのファイルの言語別タイトルを使用
4. 見つからない場合、ディレクトリ名を使用

## TODO

- 言語を意識したタイトルの抽出は現段階で未サポートです。
