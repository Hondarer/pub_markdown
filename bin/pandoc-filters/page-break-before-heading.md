# page-break-before-heading.lua

見出し 1〜N がページ下部に配置される場合、直前に改ページを挿入する Pandoc Lua フィルター。

**デフォルトは無効**。メタデータで明示的に有効化した文書にのみ機能する。

## 概要

文書のレイアウトにおいて、見出しがページ下部にあり本文が次ページから始まる配置は読みにくい。このフィルターは AST 上の文字数からページ位置を推定し、閾値を超えた位置に見出しが来る場合に改ページを挿入する。

## 使い方

```bash
pandoc input.md -o output.docx --lua-filter=page-break-before-heading.lua
```

フィルターを有効化するにはメタデータで `page-break-before-heading` を指定する。

**ショートハンド (有効化のみ)**:

```bash
pandoc input.md -o output.docx --lua-filter=page-break-before-heading.lua \
  -M page-break-before-heading=true
```

**個別設定 (`--metadata-file` を使用)**:

```yaml
# pbh-settings.yaml
page-break-before-heading:
  enabled: true
  threshold: 70
  chars-per-page: 2000
  heading-level-to: 2
```

```bash
pandoc input.md -o output.docx --lua-filter=page-break-before-heading.lua \
  --metadata-file=pbh-settings.yaml
```

**フロントマターで設定**:

```yaml
---
page-break-before-heading:
  enabled: true
  threshold: 70
---
```

## オプション

すべてのオプションは `page-break-before-heading:` 配下のネスト YAML で指定する。

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `enabled` | false | フィルターの有効フラグ |
| `threshold` | 75 | 改ページを挿入する閾値 [%] |
| `chars-per-page` | 1500 | 1 ページあたりの推定文字数 |
| `heading-level-always` | 1 | 常に改ページする見出しレベルの上限 (0 で無効) |
| `heading-level-to` | 3 | 対象見出しレベルの上限 (1〜N) |
| `image-height-chars` | 300 | 画像高さ不明時のフォールバック文字数 |
| `table-row-chars` | 80 | 表の 1 行あたりの推定文字数 |

## 動作原理

### ページ位置の推定

AST を走査しながら各ブロック要素の「文字数相当」を累積し、`chars-per-page` で割った剰余からページ内位置を推定する。見出し 1〜N が `threshold` [%] 以上の位置に来る場合、直前に改ページ (OOXML の `<w:br w:type="page"/>`) を挿入する。

### 要素ごとの文字数換算

| 要素 | 換算方法 |
|------|----------|
| 段落 | テキスト文字数 + 20 (余白) |
| 見出し | テキスト文字数 + 50 (余白) |
| コードブロック | 行数 × 40 |
| 表 | (行数 + 1) × `table-row-chars` |
| 図 | 画像高さ推定値 + 30 (キャプション) |
| リスト | 各項目の合計 + 20 |
| 引用 | 内容の合計 + 30 |

### 画像高さの推定

以下の優先順位で高さを決定し、ページ高さ (945px) に対する比率で文字数に換算する。

1. Markdown 属性 `height` (例: `{height=200px}`)
2. Markdown 属性 `width` から 16:9 比で推定 (例: `{width=320px}` → 180px)
3. 実ファイルから取得
4. フォールバック値 `image-height-chars`

### 対応画像形式

| 形式 | 取得方法 |
|------|----------|
| PNG | ファイルヘッダー (IHDR チャンク) |
| JPEG | SOF0/SOF2 マーカー |
| SVG | `height` 属性 → `viewBox` 属性 |
| その他 | フォールバック値 |

### 対応単位

Markdown 属性や SVG で指定可能な単位は以下の通り。

| 単位 | 変換 |
|------|------|
| px, 無指定 | そのまま |
| pt | × 1.333 |
| cm | × 37.8 |
| mm | × 3.78 |
| in | × 96 |
| % | ページ高さの割合 |

## 制限事項

AST レベルでの文字数推定のため、実際のページ位置とはずれが生じる。以下の要因で誤差が発生する可能性がある。

- フォントサイズ・行間・余白の設定
- 画像の実際の表示サイズ (縮小・拡大)
- 表のセル内での折り返し
- ページヘッダー・フッターの有無

`chars-per-page` を実際の文書設定に合わせて調整することで精度を改善できる。

## 使用例

### 見出し 2 のみを対象にする

```yaml
---
page-break-before-heading:
  enabled: true
  heading-level-to: 2
---
```

### 閾値を下げて積極的に改ページ

```yaml
---
page-break-before-heading:
  enabled: true
  threshold: 30
---
```

### 大きめのフォントを使う文書

1 ページあたりの文字数が少ない場合は `chars-per-page` を下げる。

```yaml
---
page-break-before-heading:
  enabled: true
  chars-per-page: 1000
---
```

### H1 は常に改ページ、H2〜H3 は閾値で判定する

```yaml
---
page-break-before-heading:
  enabled: true
  heading-level-always: 1   # H1 は常に改ページ (デフォルト)
  heading-level-to: 3       # H2, H3 は threshold で判定
  threshold: 50
---
```

### 常に改ページを無効化して閾値判定のみにする

```yaml
---
page-break-before-heading:
  enabled: true
  heading-level-always: 0   # 常改ページなし
  heading-level-to: 3
  threshold: 50
---
```

## 出力形式

DOCX 形式専用。改ページは OOXML の RawBlock として挿入されるため、他の出力形式では無視される。
