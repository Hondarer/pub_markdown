<!--
生成元: agree-before-implement スキル
文書種別: 残課題一覧 (backlog)
最終更新日時: 2026-11-26 04:08:00 JST
最終更新エージェント: claude code (主セッション session_01KJc53UFydnbt2gLXTJC1ZC)
稼働 OS: Linux (WSL)
上流文書: `261125-docsfw-table-caption-backlog-overview.md` (全体管理文書)、`261125-docsfw-table-caption-backlog-design.md` (最終仕様)、`261125-docsfw-table-caption-backlog-discussion.md` (検討用 Markdown)、`261125-docsfw-table-caption-backlog-lightadr.md` (簡易 ADR)。いずれも削除されている場合があります。
下流文書: この残課題一覧を対策する継続作業が開始された場合は、その全体管理文書・検討用 Markdown・最終仕様・残課題一覧のパスを追記します。未作成の場合や、削除されている場合があります。
再開手順: このファイルを開いたエージェントは、作業の前に agree-before-implement スキルを読み込んでください。「整理状態」が「随時追記中」であれば、案件の作業中です。気付いた事項を追記し、第 3 ゲートの前に文書を再構築して整理します。上流文書が存在する場合は、各課題の背景と見送りの判断を上流文書で確認します。存在しない場合は、この文書を単体の残課題一覧として扱います。このファイルの残課題を参照して新たな成果物の作成または更新を始めるときは、元案件の再開とは別の作業として扱います。その開始には agree-before-implement を原則として使い、新しい全体管理文書と検討用 Markdown から開始してください。継続作業によってこのファイルの残課題を対策する場合は、このファイルや各項目の記載を削除することなく、継続作業の開始時 (全体管理文書と検討用 Markdown の作成時) から検討・設計・実装・整理の各段階において、このファイルのメタ情報、各項目の状態、および経緯と対処を随時更新することを原則とします。また、フェーズ分けした対策で対処できていない項目がある場合は、当該継続作業の backlog にも必ず転記し、最新作業の backlog を見れば残件が把握できるようにしてください。最終更新エージェントのセッション情報や稼働 OS・最終更新日時が参照可能であれば再開時のコンテキストや環境差分の把握に利用し、別エージェントや別環境・別 OS からの引き継ぎ、担当変更によりセッションが見つからない場合も異常とせず、文書の記載から継続してください。
-->

# 表のキャプションの前置きの残課題の対策 残課題一覧

ファイル名: `261125-docsfw-table-caption-backlog-backlog.md`

## 案件の識別

案件名: `261125-docsfw-table-caption-backlog`  
作成日: `2026-11-25`  
整理状態: 整理済み

この文書は、見送る決定がなされた問題点や、作業中に潜在的な問題や別問題として判明したものの、今回は対策しなかった最終的な残渣 (残課題) を記録したものです。作業期間中は気付いた時点で随時追記し、設計および実装・検証作業がすべて完了した後に、再構築して整理します。

## 残課題一覧

| 課題 ID | 題名 | 区分 | 優先度 / 影響度 | 状態 |
| --- | --- | --- | --- | --- |
| BL-001 | 90_local-katakana.json の no_space の重複登録 | 作業中摘出 | 低 | 未着手 |
| BL-002 | ブロック引用の中の CodeBlock: と Figure: の Pandoc と MkDocs の非対称 | 作業中摘出 | 低 | 未着手 |

## BL-001 90_local-katakana.json の no_space の重複登録

### 概要と問題点

- **現状の事象**: `framework/docsfw/.text_style_jp/90_local-katakana.json` の `no_space` に、`マッチング` と `サブフォルダー` が 2 回ずつ登録されています。
- **本来あるべき姿**: 同じ語は 1 回だけ登録されていること。

### 経緯と見送り理由

- **摘出契機**: `マッチャ` の項目の扱い (検討用 Markdown の Q-003) を調べた際に発見しました。
- **今回の見送り理由**: 振る舞いに影響せず、ユーザーが合意した変更 (`マッチャ` の削除) の範囲外のためです。

### 影響範囲とリスク

- **影響対象**: `90_local-katakana.json` の保守。
- **放置した場合のリスク**: 振る舞いへの影響はありません。辞書を編集する人が、片方だけを削除して効果が残る、などの誤解を招きます。

### 推奨される対応策

- **恒久対応案**: 重複を削除します。あわせて、辞書の読み込み時または自己テストで、同じ分類内の重複を検出する確認を検討します。
- **参考情報**: `framework/docsfw/bin_internal/text_style_jp_engine.py` の `load_dictionaries()`。

## BL-002 ブロック引用の中の CodeBlock: と Figure: の Pandoc と MkDocs の非対称

### 概要と問題点

- **現状の事象**: ブロック引用の中で、コード ブロックの直後に `> CodeBlock: 表題` を書くと、Pandoc 発行では `codeblock-caption-line.lua` がキャプションとして扱い、MkDocs 発行では `stage_livedocs.py` の `convert_captions()` が行頭の `>` を扱わないため、`CodeBlock: 表題` という通常の段落として表示されます。`Figure:` の引用の中での扱いは、Pandoc と MkDocs のどちらも未確認です。
- **本来あるべき姿**: ブロック引用の中でも、`CodeBlock:` と `Figure:` のキャプションが Pandoc 発行と MkDocs 発行で同じに表示されること。

### 経緯と見送り理由

- **摘出契機**: ブロック引用の中の `Table:` 段落の扱い (検討用 Markdown の Q-008) を調べた際に、`CodeBlock:` で再現しました。
- **今回の見送り理由**: 対策元の BL-002 は `Table:` を対象とする課題で、`CodeBlock:` と `Figure:` は範囲外です。MkDocs は図を生の HTML (`md_in_html` の `figure`) で包むため、引用の中で同じ方式が使えるかの検証と設計が別に必要です。

### 影響範囲とリスク

- **影響対象**: ブロック引用 (GitHub のアラート記法を含む) の中に、キャプション付きのコード ブロックや図を書いた文書の MkDocs 発行。
- **放置した場合のリスク**: MkDocs 発行で、キャプションが `CodeBlock: 表題` のような生の記法のまま表示されます。

### 推奨される対応策

- **恒久対応案**: `convert_captions()` で、`Table:` と同じく行頭の `>` の深さを取り除いて判定し、`CodeBlock:` は `.docsfw-caption` の段落にします。`Figure:` は、引用の中で `md_in_html` の `figure` が使えるかを確認してから方式を決めます。Pandoc 側の `Figure:` の引用の中での扱いも確認し、Pandoc と MkDocs の双方のテストで対称性を確認します。
- **参考情報**: `framework/docsfw/livedocs/bin/stage_livedocs.py` の `convert_captions()`、`framework/docsfw/bin_internal/pandoc-filters/codeblock-caption-line.lua`。
