---
name: japanese-tech-writing
description: 日本語の技術文書を作成・推敲する際に、リポジトリの文章規範を適用します。
---

# 日本語技術文書の作成と推敲

`framework/docsfw/docs/japanese-technical-writing-guideline.md` の対象となる文章構成、表現、整形の節を参照してください。  
対象読者と目的に合わせ、一段落一論点、一文一行、本文のです・ます調を適用してください。

重複を整理する場合も依頼された範囲に限定し、他の文書の再構成は必要性がある場合に限ってください。  
翻訳や UI 表記の固有判断が必要なら `understand-japanese-docs-style` を参照してください。

Markdown を変更した場合は、変更ファイルへ `text_style_jp.py --dry-run` を実行し、不自然な変換がなければ `--in-place` を実行してください。  
会話内の回答やレビューだけの場合は、ファイルの作成や整形コマンドの実行を必要としません。
