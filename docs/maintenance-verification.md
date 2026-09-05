# 発行処理の保守と検証

## Windows の文字コード

日本語出力が文字化けする場合や `UnicodeEncodeError` が出る場合は、使用しているコンソールと Python の出力エンコーディングを確認します。  
Windows コンソールでコード ページを変更する必要がある場合は `chcp 65001` を使用します。  
Python の UTF-8 モードは `python -X utf8` で指定できます。  
日本語出力を持つスクリプトでは、既存の `sys.stdout.reconfigure(encoding="utf-8")` と stderr の設定に合わせます。

`python bin/text_style_jp.py --test` は一時ディレクトリへ書き込みます。  
書き込みが拒否された場合は、実行環境で許可された一時ディレクトリを `TMPDIR`、`TEMP`、`TMP` に指定できるか確認します。  
権限の拡大は実行環境の規則に従い、サンドボックス外実行を一律の前提にしません。

## HTML テンプレートと CSS

`styles/html/html-template.html` は Pandoc テンプレートです。  
インライン JavaScript の literal `$` は `$$` にエスケープします。  
正規表現の末尾アンカーも対象です。  
追加後は局所発行で表示とログを確認し、`Error compiling template` がないことを確認します。

テンプレートなどの変更が入力 Markdown のタイムスタンプ判定へ反映されない場合は、対象の生成出力を特定して再生成します。  
削除や退避の前に、絶対パスが対象ワークスペースの生成先であることを確認します。  
全ページの再生成は全体への影響を確認する必要がある場合に限定します。  
発行コマンドの作業ディレクトリは docsfw ルート、`--workspaceFolder` は発行するワークスペースの絶対パスです。

```bash
bash bin/pub_markdown_core.sh --workspaceFolder=/path/to/workspace --details=both --docxOutput=true
```

DOCX のオプションは `--docxOutput=` です。  
`--docx=` は使用しません。

## 静的発行と動的発行

静的発行の規則を変更する場合は、`livedocs/` のステージングにも同じ規則が必要か確認します。  
検証対象は変更した形式と影響する経路から選び、すでに得た同じ結果を繰り返し生成しません。
