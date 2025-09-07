# Pandoc Markdown インデックス挿入 Lua フィルタ (insert-toc.lua)

## 概要

この Lua フィルタは、指定された Markdown ファイルが存在する階層以下の Markdown ファイルから、自動的にインデックス (目次) リストを生成し、対象ファイルに挿入します。

## インデックス挿入の書式

### 基本書式

Pandoc Lua フィルタの慣例に従い、`\toc` コマンドを使用します。

```markdown
\toc
```

### パラメータ付き書式

```markdown
\toc depth=1 exclude="temp.md" exclude="draft/*" sort=name format=ul
```

### 書式の特徴

- `\newpage`, `\pagebreak` 等の既存 Pandoc コマンドと一貫性
- インライン記述で設定が完結
- 同一文書内で異なる設定のインデックスを複数配置可能

## パラメータ仕様

### 階層数指定 (depth)

```text
現在のディレクトリ/
├── index.md           # 階層0 (自身、インデックス挿入対象)
├── file1.md           # 階層0 (現在のディレクトリ)
├── subfolder1/        # 階層1 (1階層下)
│   ├── file2.md       # 階層1
│   └── subsubfolder/  # 階層2 (2階層下)
│       └── file3.md   # 階層2
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

### ソート方法 (sort)

指定方法を次に示す。

- `sort=name`: ファイル名順 (デフォルト)
- `sort=title`: タイトル順

### 出力形式 (format)

指定方法を次に示す。

- `format=ul`: 番号なしリスト (デフォルト)
- `format=ol`: 番号付きリスト

### デフォルト値

Lua フィルタ内で定義される値を示す。

```lua
local defaults = {
    depth = 0,        -- 現在のディレクトリのみ
    sort = "name",    -- ファイル名順
    format = "ul",    -- 番号なしリスト
    exclude = {}      -- 除外なし
}
```

## 使用例

### 基本的な使用例

#### 最小構成

```markdown
# プロジェクト概要

\toc

## 詳細
```

実行結果 (現在のディレクトリのみ)。

```markdown
# プロジェクト概要

- [Chapter1](chapter1.md)
- [Chapter2](chapter2.md)

## 詳細
```

#### 1 階層下まで指定

```markdown
# プロジェクト概要

\toc depth=1

## 詳細
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

#### 複合設定例

```markdown
# プロジェクト概要

\toc depth=2 exclude="draft/*" exclude="temp.md" sort=title format=ol

## 詳細
```

実行結果 (番号付きリスト、タイトル順、除外あり)。

```markdown
# プロジェクト概要

1. [API リファレンス](reference/api.md)
2. [イントロダクション](intro.md)
3. [チュートリアル](tutorial/index.md)
   1. [応用](tutorial/advanced.md)
   2. [基本操作](tutorial/basics.md)

## 詳細
```

### 複数インデックスの例

```markdown
# プロジェクト概要

## 現在のディレクトリ
\toc depth=0

## 全体構造
\toc depth=-1 format=ol

## チュートリアルのみ
\toc depth=1 exclude="reference/*" exclude="intro.md"
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

## TODO

- 言語を意識したタイトルの抽出ができていない。
