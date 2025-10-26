# drawio.svg 変換テスト

draw.io の SVG と Pandoc による Word 変換の問題について、整理しますね。

## 問題

draw.io は図を SVG (Scalable Vector Graphics: 拡大縮小可能なベクター画像形式) としてエクスポートする際、テキスト部分を `foreignObject` という要素で表現することがあります。この `foreignObject` は、SVG の中に HTML を埋め込むための仕組みです。draw.io はこれを使って、テキストの改行や装飾を柔軟に表現しています。

しかし、この `foreignObject` は比較的新しい SVG の機能で、すべてのソフトウェアが対応しているわけではありません。特に Microsoft Word は `foreignObject` を処理できないため、Pandoc で Markdown から Word へ変換する際に以下のような問題が起きます。

- Word 上で「Text is not SVG - cannot display」という警告が表示される
- 図の中のテキストが表示されない
- 図形だけが表示され、説明文や注釈が消える

これらは、

- テキスト
    - ワードラップ
    - フォーマットされたテキスト

のチェックを外すことで Pandoc が正しく処理できるようになります。

## 正常に動作するもの

![ok](images/ok.drawio.svg)

## 正しく動作しないもの

![ng](images/ng.drawio.svg)
