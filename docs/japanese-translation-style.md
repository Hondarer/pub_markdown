# 日本語翻訳と UI 表記

## 適用範囲

この文書は、英語の技術文書、UI、メッセージを日本語へ翻訳するときの表記を示します。  
日本語文書全般の文章構成は [日本語技術文書の文章規範](japanese-technical-writing-guideline.md) を参照してください。

## 読者と原文

対象読者の技術水準に合わせ、専門用語を必要な範囲で使用します。  
原文の意図と情報構造を保ちながら、日本語として自然な文へ変換します。

本文、説明、エラー メッセージは、簡潔なです・ます調を使用します。  
尊敬語と謙譲語を常用せず、専門的で過度に堅くない表現にします。

## UI ラベル

UI 上のラベルは角括弧で囲みます。

```text
[キャンセル] を選択します。
```

未翻訳製品の UI ラベルは英語を保持し、必要に応じて日本語訳を括弧で補います。  
Markdown のリンクと誤認されるため、`[Add/Delete](追加/削除)` のような表記は使用せず、`[Add/Delete] (追加/削除)` と記載します。

## カタカナ語

カタカナ複合語の区切りと長音符は、リポジトリの辞書と Microsoft 日本語スタイル ガイドに従います。  
既存文書で採用済みの用語を確認し、同じ概念の表記を統一します。

## 英語のまま残す要素

次の要素は原則として翻訳しません。

- 製品名、商標、略語
- コード、変数、レジストリ キー
- プレースホルダーとエスケープ文字
- 著作権表示
- 未翻訳製品の UI ラベル

## 主体と態

ユーザーが行う操作は、ユーザーを暗黙の主体とする能動表現にします。  
コンピューターが自動的に行う処理は、利用者から見た受動表現を使用できます。

## 参考資料

- [Microsoft Japanese Style Guide](https://aka.ms/japanese-styleguide)
- [Microsoft Japanese mini style guide](https://github.com/MicrosoftDocs/globalization/blob/38231167f453fa91b7f30323dc1082a8972bea6b/globalization/localization/ministyleguides/mini-style-guide-japanese.md)
