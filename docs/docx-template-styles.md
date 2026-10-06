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
| `SourceCodeCaption` | Source Code Caption | 段落 | コード ブロックのキャプション | なし | `codeblock-caption.lua`、`listing-caption-style.lua` |
| `InlineCode` | Inline Code | 文字 | インライン コード専用 | `#EAEAEA` | `inline-code-style.lua` |
| `BlockTextNote` | Block Text Note | 段落 | admonition NOTE | `#F0FAFF` | `admonition.lua` |
| `BlockTextTip` | Block Text Tip | 段落 | admonition TIP | `#EFFDF2` | `admonition.lua` |
| `BlockTextImportant` | Block Text Important | 段落 | admonition IMPORTANT | `#F8F2FF` | `admonition.lua` |
| `BlockTextWarning` | Block Text Warning | 段落 | admonition WARNING | `#FFFCE5` | `admonition.lua` |
| `BlockTextCaution` | Block Text Caution | 段落 | admonition CAUTION | `#FFF6F5` | `admonition.lua` |
| `BlockTextDeprecated` | Block Text Deprecated | 段落 | admonition DEPRECATED | `#F6F8FA` | `admonition.lua` |

Table: docsfw 固有の docx カスタム スタイル一覧

## 見出しの段落番号

見出し 1 から見出し 9 の段落スタイルには、テンプレートで段落番号を設定しています。  
形式は見出し 1 から順に `1`、`1.1`、`1.1.1`、`(1)`、`(a)`、`(i)`、`(A)`、`(I)`、`(ア)` です。  
Markdown の H2 から H6 は見出し 1 から見出し 5 になり、HTML 出力と同じ番号を表示します。  
見出し 6 以降は Markdown から使用しませんが、Word の 9 段の見出し全体で形式を統一するために定義しています。  
HTML 出力との対応は [見出し書式](heading-style.md) の「採番との関係」を参照してください。

## 見出し配下の字下げ

見出し 4 以降は、段落番号の 1 行目の字下げにより 7.5mm ずつ字下げしています。  
本文の段落スタイルは見出しのレベルを区別できないため、見出しの配下の本文は発行後の後処理で字下げします。

`bin_internal/pandoc-filters/indent-docx-heading-content.py` は、Pandoc が生成した docx の本文を先頭から読み、直前の見出しの 1 行目の位置を本文の各段落の左インデントへ加算します。  
加算する値はテンプレートの見出しスタイルと段落番号から求めるため、見出しの字下げを変更すると本文も追従します。  
見出し 1 から見出し 3 は字下げしないため、その配下の本文も字下げしません。

- 段落、箇条書き、コード ブロック、図、引用、admonition は、スタイルや段落番号が持つ字下げに加算します。
- 図の画像は、字下げ後の本文幅を超える場合に縦横比を保って縮小します。
- 表と表のキャプション (`Table Caption`) は字下げしません。Word は中央揃えの表に左インデントを適用しないため、表とキャプションをページ中央にそろえます。
- 水平線 (`horizontal-rule.lua` が出力する下罫線だけの段落) は、前後の字下げのうち浅い方で引きます。上位の見出しの直前では、その見出しの字下げに戻します。

字下げは段落ごとの直接書式として書き込みます。  
Word で段落スタイルを再適用すると、この字下げは解除されます。

HTML 出力も同じ 7.5mm で字下げします。HTML 出力の実装は [見出し書式](heading-style.md) の「見出し配下の字下げ」を参照してください。  
HTML 出力の字下げ幅は CSS に直接記載しているため、テンプレートの見出しの字下げを変更する場合は `styles/html/html-style.css` と `livedocs/assets/docsfw-pandoc-style.css` もそろえて変更します。

## コード スタイルの注意点

Pandoc 3.x の docx writer はインライン コードとハイライトなしコード ブロックの各行に同じ文字スタイル `VerbatimChar` を割り当てます。  
そのため `VerbatimChar` に背景色を付けると、インライン コードだけでなくコード ブロックにも背景が適用されます。

この問題に対処するため、docsfw は Lua フィルター `bin_internal/pandoc-filters/inline-code-style.lua` で docx 出力時のみインライン コードを `InlineCode` スタイルへ振り替えます。

```
インライン コード `x`  ->  rStyle = InlineCode  (背景色あり)
ハイライトなしブロック ->  rStyle = VerbatimChar (背景色なし)
ハイライトありブロック ->  rStyle = KeywordTok 等 (背景色なし)
```

HTML 出力では `inline-code-style.lua` は何も行わず、`html-style.css` の `code, tt` セレクターがインライン コードの背景色を担当します。

## admonition スタイルの定義詳細

`admonition.lua` は GitHub-style alert 構文 (`> [!NOTE]` 等) を検出し、docx では `custom-style` 属性付き Div に変換します。各タイプと対応スタイルの関係は以下のとおりです。

| タイプ | custom-style 値 | styleId | 基底スタイル | 左罫線色 | 背景色 |
|---|---|---|---|---|---|
| NOTE | Block Text Note | `BlockTextNote` | Block Text | `#1F6FEB` | `#F0FAFF` |
| TIP | Block Text Tip | `BlockTextTip` | Block Text | `#238636` | `#EFFDF2` |
| IMPORTANT | Block Text Important | `BlockTextImportant` | Block Text | `#8957E5` | `#F8F2FF` |
| WARNING | Block Text Warning | `BlockTextWarning` | Block Text | `#9A6700` | `#FFFCE5` |
| CAUTION | Block Text Caution | `BlockTextCaution` | Block Text | `#DA3633` | `#FFF6F5` |
| DEPRECATED | Block Text Deprecated | `BlockTextDeprecated` | Block Text | `#6A737D` | `#F6F8FA` |

Table: docx 用 admonition スタイルの定義詳細一覧

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

1. `.dotx` を Word で開きます。
2. スタイル ウィンドウから目的のスタイルを選択して変更します。
3. `.dotx` 形式で保存します。

Word による保存では ZIP の全エントリが再生成され、Git のバイナリ差分が大きくなります。

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

- `bin_internal/pandoc-filters/admonition.lua` - admonition 変換フィルター
- `bin_internal/pandoc-filters/admonition.md` - admonition フィルターの仕様説明
- `bin_internal/pandoc-filters/inline-code-style.lua` - インライン コード スタイル変換フィルター
- `bin_internal/pandoc-filters/codeblock-caption.lua` - コード キャプション変換フィルター
- `bin_internal/pandoc-filters/indent-docx-heading-content.py` - 見出し配下の本文を字下げする後処理
- `styles/html/html-style.css` - HTML 出力のコード スタイル (`code, tt` セレクター)
- `bin_internal/pub_markdown_core.sh` - Pandoc 呼び出し集約 (フィルター列の登録箇所)
