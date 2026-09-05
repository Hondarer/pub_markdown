---
name: understand-japanese-docs-style
description: 英語から日本語への技術文書・UI・メッセージの翻訳とレビューで、表記や用語を判断する際に使います。
---

# 日本語翻訳と UI 表記の確認

`framework/docsfw/docs/japanese-translation-style.md` の対象に該当する節を参照してください。  
読者と原文の意図を保ち、製品名、コード、変数、プレースホルダーなど英語のまま残す要素を確認してください。

文書中で UI ラベルを参照する場合は角括弧を使い、Markdown リンクと誤認されない表記にしてください。  
実際の UI ラベル文字列へ説明用の括弧を追加しないでください。  
一般的な段落構成を推敲する場合だけ、`framework/docsfw/docs/japanese-technical-writing-guideline.md` の該当節も参照してください。

Markdown ファイルを変更した場合は、対象への `text_style_jp.py --dry-run` と目視確認後に `--in-place` を実行してください。  
UI リソースや会話内の翻訳には Markdown 整形を適用せず、その形式のプレースホルダーと構文を確認してください。
