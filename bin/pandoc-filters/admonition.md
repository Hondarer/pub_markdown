# admonition.lua

GitHub 形式の admonition (注意書きブロック) を Pandoc フィルターで変換します。

## 概要

`> [!NOTE]` 等の GitHub-style alert 構文を検出し、HTML では色分けされた `<div>` に、  
docx ではカスタム段落スタイル付き Div に変換します。  
マッチしない blockquote は従来通りの表示を維持します。

## 対応タイプ

| タイプ | 用途 |
|---|---|
| NOTE | 補足情報 |
| TIP | 便利な情報やヒント |
| IMPORTANT | 重要な情報 |
| WARNING | 注意が必要な情報 |
| CAUTION | 危険や破壊的操作への警告 |
| DEPRECATED | 非推奨の機能や代替案の情報 |

## 技術的背景

Pandoc の `-f markdown+hard_line_breaks` には `alerts` 拡張がない (`-f gfm` 専用)。  
そのため、BlockQuote としてパースされた `[!TYPE]` テキストを Lua フィルターで検出して変換します。

### AST 構造

`-f markdown+hard_line_breaks` での `> [!NOTE]\n> 本文` のパース結果:

```
BlockQuote
  Para
    Str "[!NOTE]"
    LineBreak        ← hard_line_breaks による
    Str "本文"
```

フィルターは `BlockQuote.content[1]` (Para/Plain) の先頭 Inline が `[!TYPE]` パターンに  
マッチするか判定し、マッチした場合は `[!TYPE]` と直後の LineBreak/SoftBreak を除去します。

## HTML 出力

`<div class="admonition {クラス}">` に変換します。  
見出しは `<p class="admonition-title">` で出力します。記号 (絵文字) は付けません。

```html
<div class="admonition note">
  <p class="admonition-title">Note</p>
  <p>内容...</p>
</div>
```

Pandoc の `Para` は属性を持てないため、見出しの段落は `RawBlock` で組み立てています。

クラス名とマークアップは mkdocs-material にそろえています。  
動的発行が使う `github-callouts` は `CAUTION` を `danger` クラスへ写すため、`CAUTION` のクラス名だけタイプ名と異なります。

CSS は `styles/html/html-style.css` に定義します。  
形状も mkdocs-material に合わせ、全周の枠、角丸、見出し帯、SVG アイコンで表現します。  
ブロック本体の背景はページ背景のままとし、見出し帯だけを基準色の 10% で塗ります。  
アイコンは `mask-image` に SVG を与え、基準色で塗ります。

| タイプ | クラス | 見出し | 基準色 (枠・アイコン・見出し文字) | 見出し帯 |
|---|---|---|---|---|
| NOTE | `note` | Note | #1f6feb (青) | #e9f1fd |
| TIP | `tip` | Tip | #238636 (緑) | #e9f3eb |
| IMPORTANT | `important` | Important | #8957e5 (紫) | #f3eefc |
| WARNING | `warning` | Warning | #9a6700 (黄) | #f5f0e6 |
| CAUTION | `danger` | Caution | #da3633 (赤) | #fbebeb |
| DEPRECATED | `deprecated` | Deprecated | #6a737d (灰) | #f0f1f2 |

見出し帯の色は `color-mix()` で基準色から導き、表の値は非対応環境向けのフォールバックです。  
寸法と、動的発行との一致のさせ方は [動的発行基盤](../../docs/livedocs-design.md) の「admonition の実装」を参照してください。

HTML と docx で見出しの文字列は異なります。  
HTML は絵文字なし、docx は絵文字付きです。

## docx 出力

`custom-style` 属性付き Div に変換します。  
見出しには記号 (絵文字) 付きのタイトルを出力します。HTML とは異なります。  
テンプレート (`docx-template.dotx`) に対応するスタイルが定義されていれば適用される。  
未定義の場合は Normal スタイルにフォールバックします。

### 段落スタイル名

各スタイルは Block Text を基底 (`basedOn`) とします。

| タイプ | custom-style 値 | styleId (Pandoc 生成) | 基底スタイル |
|---|---|---|---|
| NOTE | Block Text Note | BlockTextNote | Block Text |
| TIP | Block Text Tip | BlockTextTip | Block Text |
| IMPORTANT | Block Text Important | BlockTextImportant | Block Text |
| WARNING | Block Text Warning | BlockTextWarning | Block Text |
| CAUTION | Block Text Caution | BlockTextCaution | Block Text |
| DEPRECATED | Block Text Deprecated | BlockTextDeprecated | Block Text |

スタイルの定義詳細 (styleId・背景色・左罫線色・styles.xml 追加例・`.dotx` 編集手順) は  
[docs/docx-template-styles.md](../../docs/docx-template-styles.md) を参照してください。

## フィルター チェーン上の位置

`pub_markdown_core.sh` 内で `pagebreak.lua` の直後に配置します。

- HTML: `pagebreak.lua` → **`admonition.lua`** → `link-to-html.lua`
- docx: `pagebreak.lua` → **`admonition.lua`** → `toc-pagebreak.lua`

admonition に変換された BlockQuote は Div になるため、  
`separate-consecutive-blockquotes.lua` の対象から外れる (意図した動作)。

## docx 出力の制約事項

### admonition 内のリスト

docx 出力で admonition 内にリスト (箇条書き・番号付きリスト) を含めると、  
リスト段落が admonition ブロックの外に描画される。

**原因**: Pandoc の docx ライターは `custom-style` 付き Div 内の段落 (Para) にスタイルを適用するが、  
BulletList / OrderedList は独自のリスト スタイル (List Paragraph 等) で段落を生成するため、  
Div の `custom-style` が適用されません。

**影響**: リスト項目が admonition の左罫線・背景色の外側に表示される。

**対応**: Pandoc の構造的な制約のため、現時点では対処しません。  
admonition 内では段落テキストのみを使用することを推奨します。  
HTML 出力ではこの制約はなく、リストも正常に admonition 内に表示される。
