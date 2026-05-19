---
title: docx カスタムプロパティのサンプル
document-id: DOCSFW-SAMPLE-001
---

# docx カスタムプロパティのサンプル

このサンプルは、Pandoc の YAML メタデータから docx のカスタムプロパティを出力する例である。

## 記載方法

Markdown の先頭に YAML front matter として、標準プロパティではないルート階層の文字列メタデータを記載する。

```yaml
---
title: docx カスタムプロパティのサンプル
document-id: DOCSFW-SAMPLE-001
---
```

## 仕組み

Pandoc は docx 出力時に、Markdown の YAML メタデータを Office Open XML の文書プロパティへ変換する。

`title` や `author` などの標準プロパティに対応するメタデータは、docx 内の `docProps/core.xml` に出力される。

一方、標準プロパティに該当しないルート階層の文字列メタデータは、docx 内の `docProps/custom.xml` にカスタムプロパティとして出力される。

このサンプルの `document-id` は標準プロパティではないため、docx ではカスタムプロパティ `document-id` になる。

`docsfw` では `pub_markdown_core.sh` が Markdown を Pandoc に渡して docx を生成するため、通常の発行手順でこのメタデータが docx に反映される。

## 確認方法

Word では、以下の手順で確認できる。

1. 「ファイル」を開く。
2. 「情報」を開く。
3. 「プロパティ」から「詳細プロパティ」を開く。
4. 「ユーザー設定」タブで `document-id` の値を確認する。

コマンドラインでは、docx を ZIP として扱い、`docProps/custom.xml` を確認できる。

```bash
unzip -p output.docx docProps/custom.xml
```

`document-id` が反映されていれば、以下のような要素が出力される。

```xml
<property name="document-id"><vt:lpwstr>DOCSFW-SAMPLE-001</vt:lpwstr></property>
```

## Word 文書内での表示

Word 文書内にプロパティ値を表示する場合は、`DOCPROPERTY` フィールドを使用する。

手動で挿入する場合は、以下の手順で設定する。

1. Word で docx を開く。
2. プロパティ値を表示したい位置にカーソルを置く。
3. 「挿入」タブを開く。
4. 「クイック パーツ」から「フィールド」を開く。
5. フィールド名で `DocProperty` を選択する。
6. プロパティ一覧から `document-id` を選択する。
7. 「OK」を押す。

フィールドコードで記載すると、以下の形式になる。

```text
{ DOCPROPERTY "document-id" }
```

波括弧はキーボードで入力した `{` と `}` ではなく、Word 上で `Ctrl + F9` により挿入するフィールド用の波括弧を使用する。

値を更新する場合は、フィールドを選択して `F9` を押す。文書全体のフィールドを更新する場合は、`Ctrl + A` で全文書を選択してから `F9` を押す。

`document-id` のようにハイフンを含むプロパティ名は、引用符で囲む。

## 未設定時の挙動

`DOCPROPERTY` フィールドで存在しないカスタムプロパティを参照すると、Word はエラー文字列を表示する。

```text
エラー! プロパティ名が不明です。
```

このため、以下のようなフィールドは、docx 内に `document-id` カスタムプロパティが存在しない場合にエラー表示になる。

```text
{ DOCPROPERTY "document-id" }
```

`DOCPROPERTY` フィールド自体には、プロパティが存在しない場合の既定値を直接指定する機能はない。

## 未設定時の回避方法

未設定時のエラー表示を避ける方法は、主に以下の 2 つである。

### カスタムプロパティを必ず作成する

文書内で `document-id` を参照する場合は、値が未確定でも docx 内に `document-id` カスタムプロパティを作成しておく。

```yaml
---
title: docx カスタムプロパティのサンプル
document-id: ""
---
```

値を未設定にしたい場合でも、プロパティ自体が存在すれば `DOCPROPERTY` はプロパティ名不明のエラーにはならない。

Pandoc 3.9 では、以下のいずれの書き方でも空文字のカスタムプロパティとして `docProps/custom.xml` に出力されることを確認している。

```yaml
---
document-id: ""
---
```

```yaml
---
document-id:
---
```

出力される `docProps/custom.xml` の該当部分は、以下のようになる。

```xml
<property name="document-id"><vt:lpwstr></vt:lpwstr></property>
```

### IF フィールドでエラー文字列を隠す

Word のフィールドだけで回避する場合は、`IF` フィールドで `DOCPROPERTY` の結果を比較し、エラー文字列の場合に空文字を表示する。

```text
{ IF "{ DOCPROPERTY "document-id" }" = "エラー! プロパティ名が不明です。" "" "{ DOCPROPERTY "document-id" }" }
```

この方法は Word の表示言語に依存する。英語環境などではエラー文字列が異なるため、複数言語環境で使用するテンプレートには向かない。

## 組み込みプロパティを使う方法

Word の組み込みプロパティを使う場合、プロパティが存在しないことによる `プロパティ名が不明です` のエラーを避けやすい。

例えば、文書 ID を `keywords` に流用する場合は、Markdown の YAML front matter に以下のように記載する。

```yaml
---
title: docx プロパティのサンプル
keywords: DOCSFW-SAMPLE-001
---
```

Word では、以下のフィールドで表示できる。

```text
{ DOCPROPERTY "Keywords" }
```

`keywords` は Pandoc から Word の組み込みプロパティ `Keywords` に対応する。未設定の場合でも組み込みプロパティとして扱われるため、カスタムプロパティ名が存在しない場合のエラーは避けやすい。

ただし、`keywords` は本来検索用キーワードであり、文書 ID 専用の意味を持つプロパティではない。検索用キーワードも同時に使用する文書では、文書 ID とキーワードが混在する。

文書 ID としての意味を優先する場合は `document-id` カスタムプロパティを使用し、表示時の未設定エラー回避を優先する場合は組み込みプロパティの流用を検討する。

## 組み込みプロパティの一覧

`DOCPROPERTY` フィールドは、Word の「詳細プロパティ」ダイアログにあるプロパティ名を指定して表示する。Microsoft の `WdBuiltInProperty` 一覧では、Word の組み込み文書プロパティとして以下が定義されている。

この表の「フィールド指定例」は、`DOCPROPERTY` で指定する英語名である。Word の UI 表示名は、Word のバージョンや表示言語により異なる場合がある。

| Pandoc メタデータ | フィールド指定例 | 用途 | 備考 |
|---|---|---|---|
| `title` | `{ DOCPROPERTY "Title" }` | タイトル | Pandoc から設定可能 |
| `subject` | `{ DOCPROPERTY "Subject" }` | 件名 | Pandoc から設定可能 |
| `author` | `{ DOCPROPERTY "Author" }` | 作成者 | Pandoc から設定可能 |
| `keywords` | `{ DOCPROPERTY "Keywords" }` | キーワード | Pandoc から設定可能 |
| `description` | `{ DOCPROPERTY "Comments" }` | コメント | Pandoc から設定可能 |
| - | `{ DOCPROPERTY "Template" }` | テンプレート名 | Word が管理 |
| - | `{ DOCPROPERTY "Last Author" }` | 最終更新者 | Word が管理 |
| - | `{ DOCPROPERTY "Revision Number" }` | 改訂番号 | Word が管理 |
| - | `{ DOCPROPERTY "Application Name" }` | アプリケーション名 | Word が管理 |
| - | `{ DOCPROPERTY "Last Print Date" }` | 最終印刷日時 | Word が管理 |
| - | `{ DOCPROPERTY "Creation Date" }` | 作成日時 | Word が管理 |
| - | `{ DOCPROPERTY "Last Save Time" }` | 最終保存日時 | Word が管理 |
| - | `{ DOCPROPERTY "Total Editing Time" }` | 編集時間 | Word が管理 |
| - | `{ DOCPROPERTY "Number of Pages" }` | ページ数 | Word が管理 |
| - | `{ DOCPROPERTY "Number of Words" }` | 単語数 | Word が管理 |
| - | `{ DOCPROPERTY "Number of Characters" }` | 文字数 | Word が管理 |
| - | `{ DOCPROPERTY "Security" }` | セキュリティ設定 | Word が管理 |
| `category` | `{ DOCPROPERTY "Category" }` | 分類 | Pandoc から設定可能 |
| - | `{ DOCPROPERTY "Manager" }` | 管理者 | Word のプロパティとして設定可能 |
| - | `{ DOCPROPERTY "Company" }` | 会社 | Word のプロパティとして設定可能 |
| - | `{ DOCPROPERTY "Number of Bytes" }` | バイト数 | Word が管理 |
| - | `{ DOCPROPERTY "Number of Lines" }` | 行数 | Word が管理 |
| - | `{ DOCPROPERTY "Number of Paragraphs" }` | 段落数 | Word が管理 |
| - | `{ DOCPROPERTY "Number of Notes" }` | ノート数 | Word の組み込み定義 |
| - | `{ DOCPROPERTY "Number of Characters (with spaces)" }` | 空白を含む文字数 | Word が管理 |

Microsoft の `WdBuiltInProperty` には、`Format`、`Number of Slides`、`Number of Hidden Slides`、`Number of Multimedia Clips`、`Hyperlink Base` も定義されている。ただし、Word の `WdBuiltInProperty` 一覧では `Not supported` とされているため、未定義エラーの回避を目的にした `DOCPROPERTY` では使用しない。

例として、`subject` を文書内に表示する場合は以下のフィールドを使用する。

```text
{ DOCPROPERTY "Subject" }
```

Microsoft の `BuiltInDocumentProperties` の説明では、組み込みプロパティであっても Word が値を定義していない場合、VBA で `Value` を読むとエラーになるとされている。`DOCPROPERTY` で未定義プロパティ名エラーを避ける目的では、上記の対応プロパティ名を使用し、値そのものが空になるケースは許容する前提で扱う。

参考:

- [Field codes: DocProperty field](https://support.microsoft.com/en-us/office/field-codes-docproperty-field-bf00526e-18cd-4515-8c8e-39d59094395a)
- [WdBuiltInProperty enumeration (Word)](https://learn.microsoft.com/en-us/office/vba/api/word.wdbuiltinproperty)
- [Document.BuiltInDocumentProperties property (Word)](https://learn.microsoft.com/en-us/office/vba/api/word.document.builtindocumentproperties)
