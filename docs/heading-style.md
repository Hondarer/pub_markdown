# 見出し書式

この文書は、静的発行 (`make docs`) と動的発行 (`make livedocs` / `make servedocs`) が共通で使用する見出しと本文の文字書式を定めます。  
2 つの出力は変換経路もテーマも異なりますが、同じ Markdown を読んだときの見え方は一致させます。

## 適用範囲

対象は HTML 出力の 2 系統です。

- 静的発行 (`bin/pub_markdown_core.sh` が生成する HTML)
- 動的発行 (mkdocs が生成する HTML)

docx 出力は対象外です。  
Word の段落スタイルは `styles/docx/docx-template.dotx` が持ち、印刷媒体の慣習に従うため、この文書の規則を適用しません。

## 書式

Markdown 上の見出しレベルを基準に、次を正本とします。  
HTML のタグ名ではなく Markdown のレベルで定める点が重要です。理由は「見出しレベルの対応」で述べます。

| | font-size | font-weight | line-height | color |
|---|---|---|---|---|
| H1 (ページ見出し) | 19px | 700 | 40px | `#757575` |
| H2 | 19px | 700 | 40px | `#757575` |
| H3 | 19px | 700 | 40px | `#757575` |
| H4 | 19px | 400 | 40px | `#757575` |
| H5 | 17px | 400 | 20px | `#757575` |
| H6 | 17px | 400 | 20px | `#757575` |
| 本文 | 16px | 400 | 1.5 | `#212121` |

見出しの余白は全レベルで `margin: 20px 0 10px` とします。  
`letter-spacing` は全レベルで `normal`、`text-transform` は全レベルで `none` とします。

### 濃さと太さの考え方

濃さは 2 段です。  
本文の `#212121` がいちばん濃く、見出しは `#757575` で本文より淡くなります。

見出しを本文より淡くするのは、見出しの存在を大きさと太さで示し、読む対象である本文を最も強く見せるためです。  
太字は同じ色でも濃く見えるため、太字を使う見出しを淡い色にすることで、本文との目立ち方の差を保ちます。

階層は太さで表します。  
H1 から H3 が 700、H4 から H6 が 400 です。

大きさは 19px と 17px の 2 段階です。  
H1 から H4 が 19px、H5 と H6 が 17px です。

この結果、H1、H2、H3 は同じ見た目になります。  
これらの階層の判別は、`-N` と CSS カウンターが振る採番 (1 / 1.1 / 1.1.1) が担います。

## 見出しレベルの対応

2 つの出力では、Markdown の見出しレベルと HTML のタグ名の対応が異なります。  
書式を HTML のタグ名で定めると、この差によって Markdown 上の見え方がずれます。

### 静的発行

pandoc は `--shift-heading-level-by=-1` を使用します。  
Markdown の H1 はテンプレート (`styles/html/html-template.html`) の `<H1>$title$</H1>` へ移り、残りの見出しは 1 段浅い HTML タグになります。

| Markdown | HTML |
|---|---|
| H1 | `.span9` または `.span12` 直下の `h1` (ページ見出し) |
| H2 | `h1` |
| H3 | `h2` |
| H4 | `h3` |
| H5 | `h4` |
| H6 | `h5` |

ページ見出しと Markdown の H2 は、どちらも `h1` として出力されます。  
両者は書式が同じであるため、`h1` に対する 1 つの指定で足ります。

### 動的発行

mkdocs は H1 をページ見出しとして本文に残すため、Markdown の H1 から H6 が HTML の `h1` から `h6` にそのまま対応します。  
段のずれはありません。

## 実装

書式は次の 2 か所で実装します。  
片方だけを変更しないでください。

| 出力 | ファイル |
|---|---|
| 静的発行 | `styles/html/html-style.css` |
| 動的発行 | `livedocs/assets/docsfw-pandoc-style.css` |

pandoc 側は、本文色を `body` に指定し、見出しは HTML タグを 1 段浅く読み替えて指定します。  
`line-height` は CDN の Bootstrap `template.css` が同じ値を与えていますが、外部 CSS への暗黙の依存を残さないため明示します。

mkdocs 側は、見出しの色を直値で書かず `var(--md-default-fg-color--light)` を使用します。  
ライトでは `#757575` に解決され、ダーク (`slate`) では Material の対応色へ自動で切り替わります。  
本文の色は Material の既定 (`--md-typeset-color`) がすでに `#212121` に解決されるため指定しません。

mkdocs 側では、次の Material 既定を打ち消す必要があります。

- 全レベルの `letter-spacing: -.01em`
- `h5` の `text-transform: uppercase`
- `em` 基準の `margin`
- `h2` 直後の `h3` だけ上余白を `.8em` にする `.md-typeset h2 + h3`

`.md-typeset h2 + h3` は詳細度が (0,1,2) であり、レベルごとの指定 (0,1,1) より高くなります。  
同じセレクターで上書きしてください。

## 採番との関係

採番の実装は 2 つの出力で異なりますが、表示される番号は一致します。

- pandoc は `-N` (`--number-sections`) が `<span class="header-section-number">` を実体として出力します。
- mkdocs は `livedocs/assets/docsfw-pandoc-style.css` の CSS カウンターが `::before` で表示します。

いずれも Markdown の H2 から採番し、H1 は対象外です。  
番号は見出しの `color` を継承するため、色を変更しても追随します。

## 一致させない項目

- 見出し内のリンクの色。pandoc は Bootstrap の `h1 a { color: #333 }`、mkdocs は `.md-typeset a` の `#4183C4` です。
- 見出しのアンカー。pandoc は `a.anchor`、mkdocs は Material の `.headerlink` で、構造が異なります。
- ダーク モードの実際の色。静的発行はライト固定です。mkdocs は Material の変数を通して切り替わります。
