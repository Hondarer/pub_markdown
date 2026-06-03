# 展開可能リスト機能 (collapsible-list)

## 概要

ネストされたリストを折りたたみ/展開可能にする機能です。HTML5 の `<details>/<summary>` 要素を使用して、JavaScript により動的に変換されます。

### 特徴

- 子要素を持つリスト項目は、初期状態で折りたたまれます。
- 項目をクリックすると子要素が展開されます。
- ブラウザーの「戻る」操作時には、折りたたみ/展開状態が復元されます。
- ブラウザーの JavaScript が有効である必要があります。
- HTML5 ネイティブ要素を使用するため、スクリーン リーダー等に対応します。
- 通常のリスト (`.collapsible-list` クラスなし) には影響しません。
- すでに `<details>` 要素でラップされている項目は変換されません。
- 深くネストされたリストでも正しく動作します。

## クラス

### collapsible-list

展開可能なリストを示す汎用クラスです。

```html
<div class="collapsible-list">
<ul>
<li>親項目1
<ul>
<li>子項目1-1</li>
<li>子項目1-2</li>
</ul></li>
<li>親項目2</li>
</ul>
</div>
```

**注意**: このクラスは追加クラス (modifier class) として設計されています。既存のスタイルを上書きせず、展開機能のみを付与します。

## 使用方法

### insert-toc での自動適用

`\toc` コマンドで生成される目次リストには、自動的に `collapsible-list` クラスが付与されます。

Markdown:

```markdown
\toc depth=-1
```

生成される HTML:

```html
<div class="collapsible-list">
<ul>
<li>📁 <a href="index.html">トップレベル</a>
<ul>
<li>📄 <a href="file.html">ファイル</a></li>
</ul></li>
</ul>
</div>
```

### Markdown での手動使用

Pandoc の fenced div 記法を使用して、任意のリストに展開機能を付与できます。

```markdown
::: {.collapsible-list}
- 親項目1
  - 子項目1-1
  - 子項目1-2
- 親項目2
  - 子項目2-1
:::
```

### デフォルト展開状態の指定 (open-level)

`open-level=N` 属性を指定すると、初回表示時に第 N 階層まで展開された状態になります。

| 値 | 動作 |
|---|---|
| `open-level=1` | 最上位項目のみ展開 (子は折りたたみ) |
| `open-level=2` | 2 階層目まで展開 |
| `open-level=-1` | すべて展開 |
| 指定なし | すべて折りたたみ (デフォルト) |

**level の数え方**: 最上位の `<details>` 要素を level 1 とし、祖先 `<details>` の数 + 1 で深さを判定します。

**手動 fenced div での使用例**:

```markdown
::: {.collapsible-list open-level=1}
- 親項目1        <- 展開
  - 子項目1-1    <- 折りたたみ
    - 孫項目     <- 折りたたみ
- 親項目2        <- 展開
:::
```

**`\toc` コマンドでの使用例**:

```markdown
\toc depth=-1 open-level=1
```

目次のトップ階層のみを展開した状態で表示されます。

## 変換後の HTML 構造

JavaScript により、子要素を持つ `<li>` 要素が以下のように変換されます。

変換前:

```html
<li>親項目
<ul>
<li>子項目</li>
</ul></li>
```

変換後:

```html
<li>
<details>
<summary>親項目</summary>
<ul>
<li>子項目</li>
</ul>
</details>
</li>
```

## スタイル

### CSS 変数

```css
.collapsible-list {
  /* 現時点ではデフォルトスタイルのみ */
}

.collapsible-list details > summary {
  cursor: pointer;
  list-style: none;
}

.collapsible-list details > summary::-webkit-details-marker {
  display: none;
}
```

### 展開マーカー

展開/折りたたみ状態を示すマーカーは、CSS の `::before` 疑似要素で実装されます。Windows 11 エクスプローラー風のシェブロン (>) を CSS の `border` プロパティで描画しています。

- **折りたたみ時**: 右向きシェブロン `>`
- **展開時**: 下向きシェブロン `∨`

```css
.collapsible-list details > summary::before {
  content: "";
  display: inline-block;
  width: 6px;
  height: 6px;
  border-right: 2px solid #000;
  border-bottom: 2px solid #000;
  transform: rotate(-45deg);  /* 折りたたみ時: 右向き */
}

.collapsible-list details[open] > summary::before {
  transform: rotate(45deg);   /* 展開時: 下向き */
}
```

展開マーカーを持つ項目 (子リストを持つ `<li>`) は、Bullet (・) が非表示になります。これは CSS の `:has()` セレクターにより実現されています。

### 対象要素

JavaScript は以下の条件を満たす要素を変換します。

1. `.collapsible-list` クラスを持つ要素の子孫
2. `<li>` 要素
3. 子要素として `<ul>` または `<ol>` を持つ

## 状態の保存と復元

折りたたみ/展開状態は `sessionStorage` を使用してブラウザーの「戻る」操作時に復元されます。

### 動作仕様

- **初回表示 (open-level 指定なし)**: すべての項目が折りたたまれた状態 (デフォルト)
- **初回表示 (open-level=N 指定あり)**: 第 N 階層まで展開された状態
- **ブラウザーの「戻る」/「進む」(操作後)**: リスト操作時に保存された開閉状態が復元される
- **ブラウザーの「戻る」/「進む」(未操作)**: 保存済み状態がないため初回表示と同じ状態になる
- **ページのリロード**: 初回表示と同じ状態に戻る (open-level 指定があれば再適用)
- **タブを閉じる**: 保存された状態は破棄される (`sessionStorage` のため)

### 技術詳細

- `PerformanceNavigationTiming` API を使用して、ナビゲーション種別 (`back_forward`) を判定します。
- `sessionStorage` のキーは `collapsible-state:{pathname}` の形式で、ページごとに状態を管理します。
- 各 `<details>` 要素の `toggle` イベントを監視し、状態変更時に自動保存します。

## 関連ドキュメント

- [Pandoc 目次挿入 Lua フィルター (insert-toc.lua)](insert-toc.md)
