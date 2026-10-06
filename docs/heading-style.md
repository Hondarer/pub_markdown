# 見出し書式

この文書は、静的発行 (`make docs`) と動的発行 (`make livedocs` / `make servedocs`) が共通で使用する見出しと本文の文字書式を定めます。  
2 つの出力は変換経路もテーマも異なりますが、同じ Markdown を読んだときの見え方は一致させます。

## 適用範囲

対象は HTML 出力の 2 系統です。

- 静的発行 (`bin_internal/pub_markdown_core.sh` が生成する HTML)
- 動的発行 (MkDocs が生成する HTML)

docx 出力の文字書式は対象外です。  
Word の段落スタイルは `styles/docx/docx-template.dotx` が持ち、印刷媒体の慣習に従うため、この文書の書式の規則を適用しません。  
ただし、見出しの採番形式は docx 出力にも揃えます。詳細は「採番との関係」で述べます。

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
| 本文 | 16px | 400 | 1.5 | `#333333` |
| 本文のリスト項目 (`ul` / `ol` の `li`) | 16px | 400 | 1.6 | `#333333` |

Table: 見出しレベル別のタイポグラフィ書式仕様

見出しの余白は全レベルで `margin: 20px 0 10px` とします。  
`letter-spacing` は全レベルで `normal`、`text-transform` は全レベルで `none` とします。

リスト項目の行送りだけを本文より広くするのは、階層リストで項目の切れ目を見分けやすくするためです。  
リスト項目の余白は箇条書きと番号付きの双方で 8px とし、項目の間隔は行送りと余白の合計で決まります。  
この規則の対象は本文のリストだけです。サイドバーの文書ツリーとページ内目次、ヘッダーのナビゲーションは対象に含めません。

### 濃さと太さの考え方

濃さは 2 段です。  
本文の `#333333` が最も濃く、見出しは `#757575` で本文より淡くなります。

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

Table: 静的発行における Markdown 見出しと HTML 要素の対応

ページ見出しと Markdown の H2 は、どちらも `h1` として出力されます。  
両者は書式が同じであるため、`h1` に対する 1 つの指定で十分です。

### 動的発行

MkDocs は H1 をページ見出しとして本文に残すため、Markdown の H1 から H6 が HTML の `h1` から `h6` にそのまま対応します。  
段のずれはありません。

## 実装

書式は次の 2 か所で実装します。  
片方だけを変更しないでください。

| 出力 | ファイル |
|---|---|
| 静的発行 | `styles/html/html-style.css` |
| 動的発行 | `livedocs/assets/docsfw-pandoc-style.css` |

Table: 出力形式別の見出しスタイル定義ファイル一覧

pandoc 側は、本文色を `body` に指定し、見出しは HTML タグを 1 段浅く読み替えて指定します。  
`line-height` は CDN の Bootstrap `template.css` が同じ値を与えていますが、外部 CSS への暗黙の依存を残さないため明示します。  
本文のリスト項目の `line-height` は、同じ `template.css` が `li { line-height: 20px }` を与えて `body` からの継承に勝つため、これを打ち消す目的でも明示が必要です。  
本文のリストだけを対象にするため、静的発行では本文を囲む `.docsfw-main-content` を前置し、動的発行では Material が本文へ付ける `.md-typeset` を前置します。

`styles/html/html-simple-template.html` は雛形の中に配置用の CSS を持ち、Bootstrap の `template.css` も `html-style.css` も前提にしません。  
そのため本文リストの行送りだけは、この雛形の `<style>` にも同じ 1.6 を記述します。値を変更する場合は、この雛形も合わせて更新してください。

MkDocs 側は、見出しの色を直接記述せず `var(--md-default-fg-color--light)` を使用します。  
ライトでは `#757575` に解決され、ダーク (`slate`) では Material の対応色へ自動で切り替わります。  
本文の色は、Material の既定 (`--md-typeset-color`) が参照する `--md-default-fg-color` を `rgba(0, 0, 0, 0.80)` に上書きし、白地で `#333333` に解決させます。  
Material の既定は `rgba(0, 0, 0, 0.87)` (白地で `#212121`) であり、本文を少し淡くするためです。

MkDocs 側では、次の Material 既定を打ち消す必要があります。

- 全レベルの `letter-spacing: -.01em`
- `h5` の `text-transform: uppercase`
- `em` 基準の `margin`
- `h2` 直後の `h3` だけ上余白を `.8em` にする `.md-typeset h2 + h3`

`.md-typeset h2 + h3` は詳細度が (0,1,2) であり、レベルごとの指定 (0,1,1) より高くなります。  
同じセレクターで上書きしてください。

## 採番との関係

採番の実装は出力ごとに異なりますが、表示される番号形式は一致します。  
対象は静的発行、動的発行、docx 出力の 3 つです。

Markdown の H2 から H6 に対する採番形式は次のとおりです。ページ見出しである H1 は採番しません。

- H2: `1`
- H3: `1.1`
- H4: `1.1.1`
- H5: `(1)`
- H6: `(a)`

### 出力系統別の採番実装

静的発行 (Pandoc) では、`-N` (`--number-sections`) オプションが出力した番号を、`bin_internal/format-section-numbers.sh` が発行時に変換します。  
`pub_markdown_core.sh` の `format_html_section_numbers` が、Pandoc で生成した HTML ごとにこのスクリプトを呼び出します。  
変換の対象は、本文の `<span class="header-section-number">` と目次の `<span class="toc-section-number">` です。見出し要素の `id` とリンク先 (`href`) は変更しません。

動的発行 (MkDocs) では、本文の番号を `livedocs/assets/docsfw-pandoc-style.css` の CSS カウンターが `::before` 疑似要素で表示します。  
目次の番号は、`livedocs_heading_numbering_hook.py` が本文の見出しレベルから求め、`page.toc` のタイトルへ `<span class="docsfw-toc-number">` として挿入します。

docx 出力では、Pandoc が Markdown の H2 から H6 を Word の見出し 1 から見出し 5 として出力し、`styles/docx/docx-template.dotx` の見出しスタイルに設定した段落番号が番号を表示します。  
テンプレートは見出し 6 から見出し 9 にも `(i)`、`(A)`、`(I)`、`(ア)` の形式を定義しています。  
Markdown の見出しは H6 までのため、これらの段は使用しません。Word の 9 段の見出し全体で形式を統一するために定義しています。

HTML 出力では、番号は見出しの `color` を継承するため、色を変更しても追随します。

## 見出し配下の字下げ

Markdown の H5 以降の見出しと、次の見出しまでの本文を、1 段ごとに 7.5mm 字下げします。  
H5 とその本文は 7.5mm、H6 とその本文は 15mm です。H4 以前の見出しと本文は字下げしません。  
字下げ幅は docx テンプレートの見出し 4 以降の字下げと同じ値です。

HTML 出力では、見出しに `docsfw-heading-indent-N` クラス (H5 が 1、H6 が 2) を付け、次の見出しまでの本文を同じクラスの `div` で囲みます。  
CSS がこのクラスに左マージンを与えます。  
見出しは `div` の外に残し、見出し同士を兄弟要素に保ちます。見出しの `id`、CSS カウンター、目次の追従処理が見出しを直接参照するためです。  
水平線は区切りのため、前後の字下げのうち浅い方で引きます。  
本文の途中の水平線は本文と同じ字下げになり、上位の見出しの直前の水平線はその見出しの字下げになります。文書の末尾の水平線は字下げしません。

- 静的発行 (Pandoc) は `bin_internal/pandoc-filters/heading-content-indent.lua` が構造を作り、`styles/html/html-style.css` が字下げします。
- 動的発行 (MkDocs) は `livedocs_heading_indent_hook.py` が Python-Markdown の treeprocessor を登録して同じ構造を作り、`livedocs/assets/docsfw-pandoc-style.css` が字下げします。

HTML 出力では、表と表のキャプションも `div` の内側に入り、字下げした範囲の中央にそろいます。  
docx 出力では、Word が中央揃えの表に左インデントを適用しないため、表と表のキャプションだけは字下げしません。  
docx 出力の実装は [docx テンプレートのスタイル定義](docx-template-styles.md) の「見出し配下の字下げ」を参照してください。

## 見出しのアンカー

どちらの出力も、見出しの末尾に `¶` のパーマリンクを表示します。  
MkDocs は Material の `toc.permalink` が `<a class="headerlink">` を生成し、pandoc は `styles/html/docsfw-nav.js` が同じ構造を実行時に付与します。

| 項目 | 仕様 |
|---|---|
| 文字 | `¶` (`U+00B6`) |
| リンク先 | 見出しの `id` (`href="#<id>"`) |
| `title` | `Permanent link` |
| 通常 | `opacity: 0` で非表示。左に 11px の余白 |
| 見出しのホバーと `:target` | `opacity: 1` で表示 |
| 色 | `#ADADAD`。アンカー自体のホバーとフォーカスでリンクのホバー色 `#346FA8`、下線なし |
| 印刷 | `display: none` |

Table: 見出しパーマリンク アンカーの表示仕様

`opacity` と色は瞬時に切り替えます。  
Material は既定で `transition: color .25s, opacity 125ms` を持ちますが、静的発行に対応する指定がないため打ち消します。

ページ タイトルの見出しにはアンカーを付けません。  
静的発行のタイトルはテンプレートが `id` のない `<H1>` として出力するため、リンク先がありません。

GitHub 由来の `a.anchor` は `styles/html/html-style.css` に定義が残っていますが、生成物に該当要素はなく、見出し左側へ重ねる別形式のため使用しません。

## 一致させない項目

- 見出し内のリンクの色。pandoc は Bootstrap の `h1 a { color: #333 }`、MkDocs は `.md-typeset a` の `#4183C4` です。
- ダーク モードの実際の色。静的発行と MkDocs は、それぞれの配色変数を通して切り替わります。

見出し以外の差異は、[動的発行基盤の「HTML 出力で残る差異」](livedocs-design.md) を参照してください。
