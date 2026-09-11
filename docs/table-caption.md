# 表のキャプション

表のキャプションは、表の直後に空行をはさんで `Table:` 行を記載して指定します。  
キャプションは静的発行と動的発行のどちらでも表の上に表示され、本文カラム幅で折り返されます。

```markdown
| 項目 | 値 |
|---|---|
| A | B |

Table: 表のキャプション {#tbl:sample}
```

キャプションの末尾に `{#tbl:xxx}` を記載すると、pandoc-crossref による採番と相互参照の対象になります。  
ラベルがない場合も、キャプションの位置と表示は同じです。

## HTML の構造

Pandoc HTML と MkDocs は、どちらもキャプション ブロックと `table` が隣り合う構造で出力します。  
Pandoc HTML のキャプションは `div` 要素です。

```html
<div class="docsfw-caption docsfw-table-caption">表のキャプション</div>
<table id="tbl:sample">...</table>
```

MkDocs のキャプションは、同じクラスを持つ `p` 要素です。ラベルを指定した場合、id もこの `p` 要素に付きます。  
Material for MkDocs の JavaScript 実行後は `table` が `.md-typeset__table` と `.md-typeset__scrollwrap` に包まれます。  
要素種別やラッパーの有無にかかわらず、キャプションは表の上に置き、キャプションと表の間隔を 8px にします。  
キャプションの行高とインライン コード、および表のフォント、セルの内余白、罫線、最小幅も両発行系で同じ値にします。

表の罫線は、交点で色が重ならない不透明色です。  
外枠と内罫線はどちらも 1px とし、外枠を内罫線より高いコントラストで表示します。  
ライト配色では外枠を `#adadad`、内罫線を `#c4c4c4`、ダーク配色では外枠を `#66686d`、内罫線を `#53565d` にします。

## 処理の流れ

Pandoc HTML では、pandoc-crossref の後に `table-caption-style.lua` を適用します。  
このフィルターは採番済みのキャプションを `table` の直前へ移し、表の identifier は `table` に残します。  
pandoc-crossref がない場合も同じフィルターがキャプションを移します。  
docx 出力にはこのフィルターを適用しません。

```text
pandoc-crossref
  -> listing-caption-style.lua
  -> table-caption-style.lua
```

MkDocs では、ステージング時に直前の Markdown 表を判定し、`Table:` の段落を表の前へ移します。  
直前が表でない `Table:` 段落は、その位置に残します。
