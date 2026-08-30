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

アドレスを変える場合は `PREVIEW_ADDR` を指定します。

```bash
make preview PREVIEW_ADDR=0.0.0.0:8100
```

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
| `bin/stop_preview_serve.sh` | このワークスペースの `mkdocs serve` を停止する |
| `mkdocs.yml.in` | mkdocs 設定のテンプレート |
| `assets/docsfw-plantuml.js` | ブラウザー上の PlantUML レンダラー |
| `assets/docsfw-mermaid.js` | ブラウザー上の Mermaid の初期化 |
| `assets/docsfw-mathjax.js` | MathJax の設定 |
| `assets/docsfw-preview.css` | 追加スタイル |
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

`mkdocs serve` を起動する前の準備 (`make preview` の前提) や、  
`make preview-build` (`mkdocs serve` を経由しない one-shot ビルド) では、  
上記のフル ステージングが唯一の同期手段です。  
また `assets/` (JS/CSS) や `mkdocs.yml` 自体の更新は自動ステージングの対象外  
のため、更新した場合はこのフル ステージングを手動で実行するか、  
`make preview` を再起動してください。

## 対応しない機能

Word (docx) 出力、`en` バリアント、`details=false` バリアント、pandoc-crossref の採番、  
Git と Doxygen の単一ページ リンク、`file://` での動作は対象外です。  
詳細は [設計ドキュメント](../docs/mkdocs-preview-design.md) を参照してください。
