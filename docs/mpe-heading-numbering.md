# Markdown Preview Enhanced での見出し自動採番

## 概要

VS Code の拡張機能「Markdown Preview Enhanced」のプレビュー表示において、CSS カウンターを使用して見出し (h2〜h6) に自動的に章番号を振る方法を説明します。

注: Pandoc にて h1 はドキュメントの見出しとして使用しているため、番号を付与するのは Markdown 上では h2 からとし、Pandoc の出力との一貫性を確保しています。

参考: [Markdown の見出しに章番号を振る方法(ついでに目次にも) - Qiita](https://qiita.com/UKawamura/items/42f907c88686fb3be4da)

## 前提環境

- Visual Studio Code
- 拡張機能: Markdown Preview Enhanced

## 設定手順

### スタイルファイルを開く

1. VS Code で任意の Markdown ファイルを開く
2. `Ctrl+Shift+P` でコマンドパレットを開く
3. 「Markdown Preview Enhanced: Customize CSS (Global)」を選択する

`style.less` ファイルが開きます。このファイルの CSS を編集します。

### 見出し自動採番の CSS を追記する

`style.less` を以下のように置換します。すでに他のカスタマイズが行われている場合は適宜マージを行ってください。

```css
/* Please visit the URL below for more information: */
/*   https://shd101wyy.github.io/markdown-preview-enhanced/#/customize-css */

h1 {
  counter-reset: chapter;
}

h2 {
  counter-reset: sub-chapter;
}

h3 {
  counter-reset: section;
}

h4 {
  counter-reset: sub-section;
}

h5 {
  counter-reset: sub-sub-section;
}

.markdown-preview.markdown-preview {
  h2::before {
    counter-increment: chapter;
    content: counter(chapter) " ";
  }

  h3::before {
    counter-increment: sub-chapter;
    content: counter(chapter) "." counter(sub-chapter) " ";
  }

  h4::before {
    counter-increment: section;
    content: counter(chapter) "." counter(sub-chapter) "." counter(section) " ";
  }

  h5::before {
    counter-increment: sub-section;
    content: counter(chapter) "." counter(sub-chapter) "." counter(section) "." counter(sub-section) " ";
  }

  h6::before {
    counter-increment: sub-sub-section;
    content: counter(chapter) "." counter(sub-chapter) "." counter(section) "." counter(sub-section)  "." counter(sub-sub-section) " ";
  }
}
```

### プレビューで確認する

設定後、Markdown ファイルのプレビューを開くと、各見出しの先頭に章番号が自動的に表示されます。

表示例を次に示します。

```text
見出し1
1 見出し2
1.1 見出し3
1.1.1 見出し4
1.1.1.1 見出し5
1.1.1.1.1 見出し6
```

## CSS カウンターの仕組み

### counter-reset

上位の見出しが出現したとき、下位のカウンターをリセットします。

- `h1` で `chapter` カウンターをリセット
- `h2` で `sub-chapter` カウンターをリセット
- `h3` で `section` カウンターをリセット
- `h4` で `sub-section` カウンターをリセット
- `h5` で `sub-sub-section` カウンターをリセット

### counter-increment と content

`::before` 疑似要素を使用して、見出しの前に番号を挿入します。

- `counter-increment` で対応するカウンターを加算する
- `content` で各階層のカウンター値を連結して表示する

### カウンター変数の対応関係

| 見出し | カウンター変数 | 表示例 |
|--------|---------------|--------|
| h2 | chapter | 1 |
| h3 | sub-chapter | 1.1 |
| h4 | section | 1.1.1 |
| h5 | sub-section | 1.1.1.1 |
| h6 | sub-sub-section | 1.1.1.1.1 |

### セレクタの重複指定

`.markdown-preview.markdown-preview` のようにセレクタを重複指定することで、CSS の詳細度 (specificity) を高め、Markdown Preview Enhanced のデフォルトスタイルを確実に上書きします。
