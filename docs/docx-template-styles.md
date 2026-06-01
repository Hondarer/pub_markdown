# docx テンプレートのスタイル定義

`styles/docx/docx-template.dotx` は Pandoc の `--reference-doc` に渡す Word テンプレート ファイルです。  
出力される docx のフォント、段落スタイル、文字スタイル、配色はすべてこのファイルで定義されます。

Pandoc docx writer と docsfw の Lua フィルターは `w:styleId` でスタイルを参照します。  
Pandoc 標準の見出しスタイル (`Heading 1` 等) と構文ハイライト用トークン スタイル (`KeywordTok` 等) は  
Pandoc が自動生成するため、ここでは docsfw 固有のカスタム スタイルのみを説明します。

## 独自スタイル一覧

| styleId | Word 表示名 | 種別 | 用途 | 背景色 | 参照元 |
|---|---|---|---|---|---|
| `SourceCode` | Source Code | 段落 | コード ブロック (枠線あり) | なし | Pandoc docx writer |
| `VerbatimChar` | Verbatim Char | 文字 | ハイライトなしコード ブロック内 run | なし | Pandoc docx writer |
| `SourceCodeCaption` | Source Code Caption | 段落 | コード ブロックのキャプション | なし | `codeblock-caption.lua` |
| `InlineCode` | Inline Code | 文字 | インライン コード専用 | `#EAEAEA` | `inline-code-style.lua` |
| `BlockTextNote` | Block Text Note | 段落 | admonition NOTE | `#F0FAFF` | `admonition.lua` |
| `BlockTextTip` | Block Text Tip | 段落 | admonition TIP | `#EFFDF2` | `admonition.lua` |
| `BlockTextImportant` | Block Text Important | 段落 | admonition IMPORTANT | `#F8F2FF` | `admonition.lua` |
| `BlockTextWarning` | Block Text Warning | 段落 | admonition WARNING | `#FFFCE5` | `admonition.lua` |
| `BlockTextCaution` | Block Text Caution | 段落 | admonition CAUTION | `#FFF6F5` | `admonition.lua` |

## コード スタイルの注意点

Pandoc 3.x の docx writer はインライン コードとハイライトなしコード ブロックの各行に  
同じ文字スタイル `VerbatimChar` を割り当てます。  
そのため `VerbatimChar` に背景色を付けると、インライン コードだけでなくコード ブロックにも背景が乗ります。

この問題に対処するため、docsfw は Lua フィルター `bin/pandoc-filters/inline-code-style.lua` で  
docx 出力時のみインライン コードを `InlineCode` スタイルへ振り替えます。

```
インラインコード `x`  ->  rStyle = InlineCode  (背景色あり)
ハイライトなしブロック ->  rStyle = VerbatimChar (背景色なし)
ハイライトありブロック ->  rStyle = KeywordTok 等 (背景色なし)
```

HTML 出力では `inline-code-style.lua` は何も行わず、`html-style.css` の `code, tt` セレクターが  
インライン コードの背景色を担当します。

## admonition スタイルの定義詳細

`admonition.lua` は GitHub-style alert 構文 (`> [!NOTE]` 等) を検出し、docx では  
`custom-style` 属性付き Div に変換します。各タイプと対応スタイルの関係は以下のとおりです。

| タイプ | custom-style 値 | styleId | 基底スタイル | 左罫線色 | 背景色 |
|---|---|---|---|---|---|
| NOTE | Block Text Note | `BlockTextNote` | Block Text | `#1F6FEB` | `#F0FAFF` |
| TIP | Block Text Tip | `BlockTextTip` | Block Text | `#238636` | `#EFFDF2` |
| IMPORTANT | Block Text Important | `BlockTextImportant` | Block Text | `#8957E5` | `#F8F2FF` |
| WARNING | Block Text Warning | `BlockTextWarning` | Block Text | `#9A6700` | `#FFFCE5` |
| CAUTION | Block Text Caution | `BlockTextCaution` | Block Text | `#DA3633` | `#FFF6F5` |

各スタイルは Block Text (`styleId=af3`) を基底 (`basedOn`) とします。  
`af3` の実際の値はテンプレートによって異なります。`word/styles.xml` を確認してください。

`word/styles.xml` に追加するスタイル定義の例 (NOTE の場合):

```xml
<w:style w:type="paragraph" w:customStyle="1" w:styleId="BlockTextNote">
  <w:name w:val="Block Text Note"/>
  <w:basedOn w:val="af3"/>
  <w:uiPriority w:val="9"/>
  <w:unhideWhenUsed/>
  <w:qFormat/>
  <w:pPr>
    <w:pBdr>
      <w:left w:val="single" w:sz="24" w:space="4" w:color="1F6FEB"/>
    </w:pBdr>
    <w:shd w:val="clear" w:color="auto" w:fill="F0FAFF"/>
  </w:pPr>
</w:style>
```

他のタイプも同様の構造で、`styleId` / `w:val` の名称・`w:color` (左罫線色) / `w:fill` (背景色) を変更します。

## .dotx の編集手順

`.dotx` は ZIP 形式のファイルです。直接テキスト編集できないため、次の手順で編集します。

### Python + zip で差分最小化する方法 (推奨)

変更するエントリのみを上書きし、他のエントリを変更しません。

```bash
mkdir -p /tmp/dotx && cd /tmp/dotx
unzip -o /path/to/docx-template.dotx word/styles.xml
# word/styles.xml を編集
zip /path/to/docx-template.dotx word/styles.xml
```

XML は 1 行に圧縮されているため、編集には `python3` と正規表現を使うと確実です。

### Word で開いて編集する方法

1. `.dotx` を Word で開く
2. スタイル ウィンドウから目的のスタイルを選択して変更
3. `.dotx` 形式で保存

Word 保存では ZIP の全エントリが再生成され git のバイナリ差分が大きくなります。

### 編集後の反映確認

`.dotx` はバイナリのため `git diff` に内容が表示されません。以下のコマンドで確認します。

```bash
unzip -p styles/docx/docx-template.dotx word/styles.xml \
  | python3 -c "
import re, sys
c = sys.stdin.read()
# 例: InlineCode が存在するか
print('InlineCode:', 'styleId=\"InlineCode\"' in c)
# 例: VerbatimChar に shd が残っていないか
m = re.search(r'styleId=\"VerbatimChar\".*?</w:style>', c, re.S)
print('shd in VerbatimChar:', 'w:shd' in m.group(0))
"
```

## 関連ファイル

- `bin/pandoc-filters/admonition.lua` - admonition 変換フィルター
- `bin/pandoc-filters/admonition.md` - admonition フィルターの仕様説明
- `bin/pandoc-filters/inline-code-style.lua` - インライン コード スタイル変換フィルター
- `bin/pandoc-filters/codeblock-caption.lua` - コード キャプション変換フィルター
- `styles/html/html-style.css` - HTML 出力のコード スタイル (`code, tt` セレクター)
- `bin/pub_markdown_core.sh` - Pandoc 呼び出し集約 (フィルター列の登録箇所)
