# 図キャッシュ

## 対象

インラインの PlantUML と Mermaid が DOCX 出力のために生成する画像を、発行先の外へ集約する仕組みです。

対象は `bin/pandoc-filters/plantuml.lua` と `bin/pandoc-filters/mermaid.lua` が生成する画像だけです。Markdown が `![](images/foo.png)` のように参照する画像は対象外であり、`--resource-path` の解決規則に従います。

## 画像を生成する条件

画像を生成するのは DOCX 出力のときだけです。`docxOutput` が `false` の場合は、キャッシュは使用されません。

HTML 出力では、両フィルターがファイルを一切生成せずに早期リターンします。図の描画元テキストを属性として埋め込み、ブラウザー側のスクリプトによってインライン SVG として描画されます。

動的発行 (MkDocs) は Pandoc を経由しません。`livedocs/assets/docsfw-plantuml-loader.js` とベンダー済みの Mermaid がブラウザーで描画します。

## 命名と共有の単位

画像のファイル名は、図のソースのハッシュ値のみに基づいて決定されます。

| フィルター | ファイル名 | ハッシュの対象 |
|---|---|---|
| PlantUML | `puml_<sha1>.svg` / `puml_<sha1>.png` | 前処理後のテキストをエンコードした結果 |
| Mermaid | `mermaid_<sha1>.svg` / `mermaid_<sha1>.png` | フェンス本文 |

言語や詳細度はファイル名に含まれません。同一の図はバリアントや実行回数を問わず 1 つのファイルに集約されます。

## 配置

キャッシュは発行先 (`pubRoot`) 直下のドット ディレクトリに配置します。

```text
pages/
+-- .cache/
|   +-- diagrams/
|       +-- puml_<sha1>.svg     完成した画像
|       +-- puml_<sha1>.png
|       +-- mermaid_<sha1>.svg
|       +-- mermaid_<sha1>.png
|       +-- tmp/                生成中の作業ファイル
|       +-- hits/               実行ごとの参照記録
+-- ja/
+-- ja-details/
+-- en/
+-- en-details/
+-- doxygen/
```

発行対象は `pubRoot` 配下の `<言語><詳細度>/` と `doxygen/` だけです。`.cache/` は配布物に含まれません。

`pubRoot` は `.gitignore` の対象であるため、キャッシュも Git の管理外です。

### レンダリング条件を変えた場合

ファイル名は図のソースのハッシュだけで決まります。SVG のパッチ内容、PNG 変換の DPI や減色設定、レンダラーの入れ替えなど、**図のソースが同じでも出力が変わる変更** を加えた場合、ファイル名は変わりません。キャッシュにある画像がそのまま再利用されます。

新しい条件で作り直すには、キャッシュを破棄します。

```bash
make cleandocs
```

`cleandocs` は `pages/` 直下を `doxygen` 以外すべて削除するため、`pages/.cache/` も対象になります。`make clean` は `cleandocs` を含みます。

## 環境変数

`pub_markdown_core.sh` が設定します。

| 変数 | 内容 |
|---|---|
| `DOCSFW_DIAGRAM_CACHE_DIR` | キャッシュのルート (絶対パス) |
| `DOCSFW_DIAGRAM_CACHE_HITS_DIR` | 当該実行における参照記録の格納先ディレクトリ |
| `PUB_MARKDOWN_DIAGRAM_CACHE_KEEP_DAYS` | 参照されない画像を保持する日数 (既定値: 7) |

`DOCSFW_DIAGRAM_CACHE_DIR` が未設定の場合、キャッシュは無効となり、フィルターは `--resource-path` の先頭ディレクトリへ画像を生成します。フィルターを単体で Pandoc に渡す場合はこの経路が適用されます。

Windows では `pandoc.exe` の Lua が POSIX パスを解決できないため、`cygpath -m` で変換した値を渡します。

## Pandoc への渡し方

キャッシュが有効な場合、フィルターは画像を絶対パスで参照します。Pandoc は絶対パスを指定された場合、`--resource-path` の探索を経由せずに読み込みます。

`--resource-path` は Markdown が参照する画像の解決のみを対象とし、図の生成画像には関与しません。`pub_markdown_core.sh` が行う参照画像の事前コピーも同様です。

## 生成の手順

`pub_markdown_core.sh` は最大 `MAX_PARALLEL` 個の Pandoc プロセスを並行して実行します。同一の図を複数のプロセスが同時に生成する可能性があるため、次の手順で確定します。

1. 最終配置パスに画像が存在する場合は、その画像を使用する
2. 存在しない場合は `tmp/` 配下の一意なパスへ生成する
3. SVG へのパッチ適用も作業用ファイルに対して実施する
4. `os.rename` により最終配置パスへ移動する

POSIX の `rename` は不可分に置換されるため、読み込み側のプロセスが不完全な生成途中状態を参照することはありません。Windows の `rename` は既存ファイルが存在すると失敗するため、その場合は並行プロセスが先行して生成完了した結果を採用し、自身の作業用ファイルを破棄します。

最終配置パスには生成完了したファイルのみが配置されます。そのため、手順 1 のファイル存在確認をそのまま生成完了の判定として使用できます。

Mermaid は `mmdc` が `-i` および `-o` の引数クオートに対応していないため、図ごとに専用の作業ディレクトリを作成してディレクトリを移動した上で実行します。これにより、入力と出力が他のプロセスと競合しません。

DOCX 用の PNG も同一の手順で生成します。SVG から `rsvg-convert` により変換し、作業用パスを経て確定します。

## 保持期間

実行の開始時に、`PUB_MARKDOWN_DIAGRAM_CACHE_KEEP_DAYS` 日を超えて更新のない画像を削除します。

参照された画像はフィルターによって `hits/` へ記録され、実行終了時に `touch` によりタイムスタンプを更新します。継続して参照されている図は削除されません。

`tmp/` および `hits/` は、中断された実行の一時ファイルが 1 日を超えて残留している場合に限り削除します。現在実行中のプロセスが使用しているファイルは削除対象に含まれません。

## 検証

局所発行で確認します。

```bash
bash bin/pub_markdown_core.sh --workspaceFolder=/path/to/workspace --details=both --docxOutput=true
```

確認する内容は次のとおりです。

- `pages/<バリアント>/html/` に `puml_*` および `mermaid_*` が出力されていないこと
- `pages/.cache/diagrams/` に画像が集約して配置されていること
- DOCX に画像が埋め込まれていること
- 2 回目の実行で画像が再生成されず、inode が変化しないこと
- `tmp/` に一時ファイルが残留していないこと
