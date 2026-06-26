# admonition.lua

GitHub 形式の admonition (注意書きブロック) を Pandoc フィルターで変換する。

## 概要

`> [!NOTE]` 等の GitHub-style alert 構文を検出し、HTML では色分けされた `<div>` に、  
docx ではカスタム段落スタイル付き Div に変換する。  
マッチしない blockquote は従来通りの表示を維持する。

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
そのため、BlockQuote としてパースされた `[!TYPE]` テキストを Lua フィルターで検出して変換する。

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
マッチするか判定し、マッチした場合は `[!TYPE]` と直後の LineBreak/SoftBreak を除去する。

## HTML 出力

`<div class="admonition admonition-{type}">` に変換する。  
タイトル行は種類ごとの記号を付けて `<span class="admonition-title">` で出力する。

```html
<div class="admonition admonition-note">
  <p><span class="admonition-title">ℹ️ Note</span></p>
  <p>内容...</p>
</div>
```

CSS は `styles/html/html-style.css` に定義。左罫線色とタイトル色は GitHub 準拠とし、背景色は淡色化した配色:

| タイプ | 見出し | 左罫線色 | 背景色 | タイトル色 |
|---|---|---|---|---|
| NOTE | ℹ️ Note | #1f6feb (青) | #f0faff | #1f6feb |
| TIP | 💡 Tip | #238636 (緑) | #effdf2 | #238636 |
| IMPORTANT | ❗ Important | #8957e5 (紫) | #f8f2ff | #8957e5 |
| WARNING | ⚠️ Warning | #9a6700 (黄) | #fffce5 | #9a6700 |
| CAUTION | 🛑 Caution | #da3633 (赤) | #fff6f5 | #da3633 |
| DEPRECATED | 🏚️ Deprecated | #6a737d (灰) | #f6f8fa | #6a737d |

## docx 出力

`custom-style` 属性付き Div に変換する。  
見出しには HTML と同じ記号付きタイトルを出力する。  
テンプレート (`docx-template.dotx`) に対応するスタイルが定義されていれば適用される。  
未定義の場合は Normal スタイルにフォールバックする。

### 段落スタイル名

各スタイルは Block Text を基底 (`basedOn`) とする。

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

`pub_markdown_core.sh` 内で `pagebreak.lua` の直後に配置する。

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
Div の `custom-style` が適用されない。

**影響**: リスト項目が admonition の左罫線・背景色の外側に表示される。

**対応**: Pandoc の構造的な制約のため、現時点では対処しない。  
admonition 内では段落テキストのみを使用することを推奨する。  
HTML 出力ではこの制約はなく、リストも正常に admonition 内に表示される。
