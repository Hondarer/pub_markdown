---
name: understand-japanese-docs-style
description: |
  Microsoft の日本語翻訳スタイル ガイド「Top 10 Tips」の要点を理解するスキルです。
  対象読者の想定、原文の構造と意図の尊重、用語選定、トーン、
  です・ます と だ・である の使い分け、UI ラベルの角括弧表記、
  カタカナ複合語のスペースと長音符の付与、英語のまま残す要素、参考資料を扱います。
when_to_use: |
  - 日本語ドキュメントや翻訳の文体・表記を Microsoft スタイルに合わせたいとき
  - カタカナ複合語のスペースや長音符の付与を判断したいとき
  - UI ラベルの表記や英語のまま残す要素 (製品名、プレースホルダーなど) を確認したいとき
metadata:
  reference_url: https://github.com/MicrosoftDocs/globalization/blob/38231167f453fa91b7f30323dc1082a8972bea6b/globalization/localization/ministyleguides/mini-style-guide-japanese.md
---

# Top 10 Tips for Microsoft Translation into Japanese

Are you helping with translation into Japanese, but don't have time to study all aspects of the [full Japanese Style Guide](https://aka.ms/japanese-styleguide)? Here are 10 of the most important aspects to keep in mind.

## Keep the audience in mind

Microsoft products target a broad set of users, from technology enthusiasts and professionals to consumers. Remember who you are talking to, and adjust your text to be at the right technical level.

## Stay true to the structure and intent of the source

Try to reflect the same grammatical structures as the source text. Consider the intent of the text, and convey the message precisely.

## Be flexible

Flexibility and creativity may be required in some cases. Ensure that the translation sounds natural and appropriate for Japanese culture.

## Pick the right term

The translation of key terminology can vary, depending on areas, contexts, and even which Microsoft product is being localized. Consult the appropriate glossaries and websites, such as:

- [Microsoft products](https://www.microsoft.com/ja-jp/) websites
- Third-party websites

## Be aware of expressions and tone

Check that the translations are:

- Simple and crisp.
- Clear and precise.
- Grammatically correct.
- Polite, but not too formal. Don't use honorific and humble expressions (尊敬語,謙譲語).
- Friendly, but professional.
- Free of jargon.
- Not offensive to any group or person.
- Verified for geopolitical accuracy, such as country or region names.

## Understand basic writing styles

Use polite (です・ます) style for descriptive sentences in general. Plain style (だ・である) and noun phrases are appropriate when short and simple texts are preferred. To learn more, see the "Style and tone consideration" section in the [Japanese Style Guide](https://aka.ms/japanese-styleguide).

Example:

- Use polite style in error messages and body text.
- Use plain style/noun phrases for list items, buttons, titles, and headings.

## Enclose UI labels

Add brackets (`[]`) to refer to a UI item with a label. To learn more, see the "User interface" section in the [Japanese Style Guide](https://aka.ms/japanese-styleguide).

Example:

_English_: Select Cancel.

_Our style_: [キャンセル] を選びます。

_Not our style_: キャンセルを選びます。

## Pay attention to katakana compound words and prolonged sound mark

Insert spaces to katakana compounds where they appear in the English words. To learn more, see the "Compounds" section in the [Japanese Style Guide](https://aka.ms/japanese-styleguide). For general spacing rules, see the "Symbols & spaces" section in the guide.

Example:

_English_: error message

_Our style_: エラー メッセージ

_Not our style_: エラー メッセージ

The prolonged sound mark should be added to a katakana word when:

- A source English term has the suffix -ar, -er, or -or.
- The katakana word has fewer than four characters, including the prolonged mark and excluding small characters such as 促音 and 拗音 (ッ, ャ, ュ, ョ, ァ, ィ, ゥ).

Example:

_English_: computer

_Our style_: コンピューター

_Not our style_: コンピューター

Example:

_English_: procedure

_Our style_: プロシージャ

_Not our style_: プロシージャ―

To learn more about the rules and exceptions, see the "Katakana prolonged sound mark" section in the [Japanese Style Guide](https://aka.ms/japanese-styleguide).

## Know what to leave in English

Items that aren't usually translated include:

- Product names.
- Trademarks.
- Acronyms.
- Placeholders (for example, {1} and %s).
- Escape characters (for example, \n and \r, which can be displayed as "￥n").
- Registry keys.
- Codes.
- Variables.
- Copyright information: "&copy; 2019 Microsoft Corporation. All rights reserved."
- References to UI labels from unlocalized products. Add a tentative translation in parentheses. See the example below.

Example:

_English_: The Add/Delete dialog box appears.

_Our style_: [Add/Delete](追加/削除) ダイアログ ボックスが表示されます。

## Use the right reference material

There is more, of course. If you are in doubt, consult the terminology, translation, [full Japanese Style Guide](https://aka.ms/japanese-styleguide) and the following references:

- 平成 3 年 6 月 28 日 内閣告示第 2 号「外来語の表記」  
- 昭和 61 年 7 月 1 日 内閣告示第 1 号「現代仮名遣い」  
- 平成 22 年 11 月 30 日 内閣告示第 2 号「常用漢字表」  
- 昭和 48 年 6 月 18 日 内閣告示第 2 号「送り仮名の付け方」  
- 『新しい国語表記ハンド ブック』(三省堂)  
- 『用字用語 新表記辞典』(第一法規)
