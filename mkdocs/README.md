# mkdocs 簡易プレビュー

docsfw の発行対象を mkdocs で表示する、執筆中の確認用のプレビュー基盤です。  
PlantUML と Mermaid はブラウザー上でレンダリングするため、ビルド時に図を生成しません。

正式な発行 (HTML と docx) は従来どおり `make docs` で行います。  
設計と、docsfw の各機能に対する対応方針は [mkdocs 簡易プレビュー基盤](../docs/mkdocs-preview-design.md) を参照してください。

## 前提

- Python 3.9 以降
- Node.js。`@plantuml/core` と `mermaid` は `bin/resolve-node-components.js` が解決します。未配置ならオンデマンドで導入します。詳細は [Node コンポーネント](../docs/node-components.md) を参照してください。

## 使用方法

ワークスペース ルートで次を実行します。

```bash
make preview
```

初回は `mkdocs/.venv` を作成し、`requirements.txt` の依存を導入します。  
その後、ステージングを行い `mkdocs serve` を起動します。  
ブラウザーで <http://127.0.0.1:8000/> を開いてください。

`make doxy` 済みで `pages/doxygen/` があるときは、`/doxygen/` で Doxygen HTML と依存関係レポートを開けます。  
Doxybook2 の各ページからは、見出し横の Doxygen アイコンで対応する単一ページへ飛べます。  
依存関係レポートの Page リンクからは、起動中の preview にある Doxybook2 ページを開けます。  
`make preview` は `make doxy` に依存しません。`pages/doxygen/` が無くてもプレビュー本体は起動します。  
Doxygen HTML の閲覧は `make preview` が正本です。`make preview-build` の `site/` には入れません。

アドレスを変える場合は `PREVIEW_ADDR` を指定します。

```bash
make preview PREVIEW_ADDR=0.0.0.0:8100
```

言語と詳細ブロックは `PREVIEW_VARIANT` で選びます。既定は `ja-details` です。  
値は `make docs` と同じ `ja` / `ja-details` / `en` / `en-details` です。1 回の起動では 1 つだけ出します。

```bash
make preview PREVIEW_VARIANT=en
make preview-build PREVIEW_VARIANT=ja
```

切り替えるときは `make preview` を再起動してください。  
2 つ目の `make preview` を起動すると、先に動いていたこのワークスペースの serve が消えるまで待ってからステージングします。  
止めきれなければ起動しません。後から起動した側が残ります。

ナビゲーションの展開可能なフォルダーには、対応する README のタイトルを表示します。  
選択したプレビュー バリアントの言語と details を反映したタイトルを使用し、README またはタイトルがない場合はフォルダー名を表示します。

リンク切れの確認だけを行う場合は次を実行します。

```bash
make preview-build
```

`PREVIEW_STRICT=1` を付けると `mkdocs build --strict` になり、警告が 1 件でもあれば失敗します。  
現状は docsfw でも解決しないリンクが残るため、既定では `--strict` を使用しません。  
内訳は [設計ドキュメントの「既知の警告」](../docs/mkdocs-preview-design.md) を参照してください。

生成物を消す場合は次を実行します。  
`cleanpreview` は削除の前に、このワークスペースの `mkdocs serve` を停止します。  
ルートの `make clean` と `make cleandocs` も同じ停止を行います。

```bash
make cleanpreview
```

serve だけを止めて `pages/preview/` を残す場合は次を実行します。

```bash
make preview-stop
```

停止の対象範囲と Windows でのツリー終了は [設計ドキュメント](../docs/mkdocs-preview-design.md) を参照してください。

## 構成

| パス | 内容 |
|---|---|
| `bin/stage_preview_docs.py` | 収集、前処理、リンク書き換え、書き出し |
| `bin/lang_details_filter.py` | `bin/replace-tag.sh` の Python 移植 |
| `bin/expand_toc.py` | `\toc` の索引展開 |
| `bin/vendor_assets.py` | アセットの配置と `mkdocs.yml` の生成 |
| `bin/preview_doxygen_hook.py` | `/doxygen/` の静的サーブと単一ページ リンク |
| `bin/preview_versioned_hook.py` | 再生成中の完成済み版の配信と版切り替え |
| `bin/stop_preview_serve.sh` | このワークスペースの `mkdocs serve` を停止する |
| `mkdocs.yml.in` | mkdocs 設定のテンプレート |
| `theme/partials/actions.html` | Doxygen 単一ページ リンクのボタン |
| `assets/docsfw-plantuml.js` | ブラウザー上の PlantUML レンダラー |
| `assets/docsfw-mermaid.js` | ブラウザー上の Mermaid の初期化 |
| `assets/docsfw-mathjax.js` | MathJax の設定 |
| `assets/docsfw-preview.css` | 追加スタイル |
| `assets/docsfw-doxygen-link.css` | Doxygen アイコンのサイズ |
| `requirements.txt` | Python 依存 |

生成物は `pages/preview/` に出力します。

| パス | 内容 |
|---|---|
| `pages/preview/mkdocs.yml` | `mkdocs.yml.in` から生成した設定 |
| `pages/preview/src/` | ステージング済みの Markdown (`docs_dir`) |
| `pages/preview/site/` | `mkdocs build` の出力 |

`pages/` はワークスペースの `.gitignore` で除外済みです。  
`make cleandocs` は `pages/doxygen` 以外を削除するため、`pages/preview` も同時に消えます。

## 元の Markdown を編集したときの反映

`make preview` で `mkdocs serve` を実行している間は、元の Markdown  
(`app/*/docs` 等) を保存すると自動的に反映されます。  
`mkdocs.yml.in` の `hooks:` に登録した `bin/preview_autostage_hook.py` が  
元の Markdown ディレクトリを監視し、変更されたファイルだけを軽量に  
再ステージングします (ワークスペース全体の再走査は行いません)。  
ステージング結果は `mkdocs serve` が監視しているステージング先  
(`pages/preview/src/`) に書き込まれるため、続けて mkdocs 標準の仕組みが  
ビルドとブラウザーの自動リロードを行います。

再生成中の通常の HTTP 要求には、直前に完成した版を返します。  
次版は別の一時ディレクトリへ生成し、正常に完了した場合だけサイト全体を  
切り替えます。  
生成に失敗した場合も、ブラウザーでは直前の完成済み版を操作できます。  
詳細は [設計ドキュメントの「再生成中の配信」](../docs/mkdocs-preview-design.md) を参照してください。

ページ内リンクの解決や `\toc` の索引一覧は、ワークスペース全体を再走査した  
ときの情報をキャッシュして使い回しているため、対象ファイル自身の内容以外  
(タイトル変更や新規ファイルの追加など) は反映が遅れることがあります。  
ファイルの作成・削除・移動を検知した場合は自動でフル ステージングへ  
切り替わり、また一定回数の軽量な再ステージングごとにも索引を再同期します。  
詳細は [設計ドキュメント](../docs/mkdocs-preview-design.md) を参照してください。

## ステージングだけを実行する

`make` を介さず、直接実行することもできます。

```bash
python3 framework/docsfw/mkdocs/bin/stage_preview_docs.py --workspaceFolder="$PWD"
python3 framework/docsfw/mkdocs/bin/vendor_assets.py --workspaceFolder="$PWD"
```

バリアントを変えるときは、両方に `--variant` を付けます。

```bash
python3 framework/docsfw/mkdocs/bin/stage_preview_docs.py --workspaceFolder="$PWD" --variant=en
python3 framework/docsfw/mkdocs/bin/vendor_assets.py --workspaceFolder="$PWD" --variant=en
```

`mkdocs serve` を起動する前の準備 (`make preview` の前提) や、  
`make preview-build` (`mkdocs serve` を経由しない one-shot ビルド) では、  
上記のフル ステージングが唯一の同期手段です。  
また `assets/` (JS/CSS) や `mkdocs.yml` 自体の更新は自動ステージングの対象外  
のため、更新した場合はこのフル ステージングを手動で実行するか、  
`make preview` を再起動してください。

## 対応しない機能

Word (docx) 出力、4 バリアントの同時出力、pandoc-crossref の採番、  
Git 単一ページ リンク、`file://` での動作は対象外です。  
詳細は [設計ドキュメント](../docs/mkdocs-preview-design.md) を参照してください。
