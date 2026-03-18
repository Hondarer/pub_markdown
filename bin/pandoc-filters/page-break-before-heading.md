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
| `heading-level-to` | 2 | 対象見出しレベルの上限 (1〜N) |
| `shift-heading-level-by` | 0 | `--shift-heading-level-by` と同じ値を指定 (後述) |
| `image-height-chars` | 300 | 画像高さ不明時のフォールバック文字数 |
| `table-row-chars` | 80 | 表の 1 行あたりの推定文字数 |

`heading-level-always` と `heading-level-to` は、`shift-heading-level-by` を設定した場合は**出力上のレベル**で指定する。設定しない場合は Markdown ソース上のレベルで指定する。

## 動作原理

### ページ位置の推定

AST を走査しながら各ブロック要素の「文字数相当」を累積し、`chars-per-page` で割った値をページ内位置 [%] として推定する。閾値チェック対象の見出しに対して以下の 2 段階で改ページを判定する。

```
page_position [%] = current_page_chars / chars_per_page × 100
```

`current_page_chars` は直前の改ページ以降の累積値であり、複数ページにわたる場合は 100% を超える。剰余演算は行わないため、「複数ページ分の内容の後に来る見出し」も確実に改ページ対象となる。

### 改ページ判定の 2 段階ロジック

以下のいずれかを満たす場合に改ページを挿入する。

**① 閾値チェック**: ページ内位置が `threshold` [%] 以上

```
page_position >= threshold
```

**② あふれチェック**: 閾値未満でも、当該セクションがページに収まらない場合

```
current_page_chars + section_chars > chars_per_page
```

`section_chars` は当該見出しから**次の改ページ候補**直前までのブロック文字数の合計。次の改ページ候補とは、明示的な改ページ (OpenXML `w:type="page"`) または改ページ対象レベルの見出し (effective level 1〜N)。

あふれチェックにより、見出しがページ上部にあっても続くセクションが 1 ページを超えるなら先行して改ページする。`section_chars` は実行前の事前スキャンで計算する。

**あふれチェックの抑制条件**: あふれチェックが BREAK と判定した場合でも、直前の改ページ要因が自身より 1 レベル上の見出し (`last_break_effective_level == effective_level - 1`) であれば改ページを挿入しない。

```
あふれチェック BREAK 条件:
  current_page_chars + section_chars > chars_per_page
  AND NOT (last_break_effective_level == effective_level - 1)
```

`last_break_effective_level` は always-break・threshold・overflow のいずれの改ページ時にも記録する。外部由来の改ページ (OpenXML `w:type="page"`) では `nil` にリセットされるため、抑制条件は成立しない。

親見出しの直後にあるセクションは同じページに配置する方が読みやすく、むやみに分離しない設計とする。例として、`## 関数` (eff H1、常時改ページ) の直後の `### potrOpenService` (eff H2) がセクション長超過でも改ページしない。

### `--shift-heading-level-by` との関係

Pandoc の `--shift-heading-level-by` は **Lua フィルター実行後**に AST へ適用される。そのため、このフィルターが見る見出しレベルはソース上のレベル (例: `###` = H3) であり、出力上のレベル (H2) とは異なる。

`shift-heading-level-by` を設定すると、各見出しの**実効レベル**を次式で算出し、出力上のレベルで判定できる:

```
effective_level = raw_level + shift_heading_level_by
```

例: `--shift-heading-level-by=-1` の場合、`raw=3` の見出しは `effective=2` として扱われる。

`effective_level <= 0` になる見出し (ソースの H1 が出力でタイトルに昇格する場合など) は改ページ対象外となる。

> **なぜ `PANDOC_WRITER_OPTIONS` から自動取得できないか**
>
> `--shift-heading-level-by` は Pandoc 内部の `WriterOptions` ではなく、CLI オプション集合の `Opt` 型フィールド (`optShiftHeadingLevelBy`) として保持される。`PANDOC_WRITER_OPTIONS` は `WriterOptions` を直接マッピングしたものであり、`Opt` 由来のフィールドは含まれない。

### `pub_markdown_core.sh` との連携

`pub_markdown_core.sh` の docx 変換コマンドでは `--shift-heading-level-by=-1` と組み合わせて `--metadata shift-heading-level-by=-1` を自動付与するため、文書側での `shift-heading-level-by` 指定は不要。

### 他フィルターの改ページとの連携

`toc-pagebreak.lua` など他フィルターが先に挿入した OpenXML 改ページ (`w:type="page"`) を検出した場合、ページ内文字数カウンターをリセットする。これにより、目次直後の最初の見出しへの二重改ページを防ぐ。

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

### `--shift-heading-level-by=-1` と組み合わせる

`--shift-heading-level-by=-1` を使用する場合、`###` (ソース H3) が出力上 H2 になる。`heading-level-always` と `heading-level-to` を**出力レベル**で指定すると意図通りに動作する。

コマンドライン:

```bash
pandoc input.md -o output.docx \
  --shift-heading-level-by=-1 \
  --metadata shift-heading-level-by=-1 \
  --lua-filter=page-break-before-heading.lua
```

フロントマター:

```yaml
---
page-break-before-heading:
  enabled: true
  heading-level-always: 1   # 出力 H1 (ソース ##) は常に改ページ
  heading-level-to: 2       # 出力 H2 (ソース ###) は閾値判定
---
```

`pub_markdown_core.sh` 経由の場合は `--metadata shift-heading-level-by=-1` が自動付与されるため、文書のフロントマターへの追記は不要。

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
