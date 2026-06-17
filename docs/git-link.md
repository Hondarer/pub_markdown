# Git 単一ページ リンク機能

## 概要

`pub_markdown_core.sh` による HTML 発行において、各ページのナビバー右側に、対応する Git ホスティング上の単一ページ (blob ビュー) へのリンクを表示します。
表示位置は「詳細切り替え」と「docx ダウンロード」の間です。
リンクのアイコンはホスティング サービスの種別 (GitHub / GitLab / GitBucket) に応じて切り替わります。

## 表示条件

リンクは次のすべてを満たす場合にのみ表示します。いずれかを満たさないファイルでは自動的に非表示となります。

- `gitLinkEnable` が `true` (デフォルト)
- ソース ファイルが Git 管理下にある (追跡済み)
- ソース ファイルが `.gitignore` の対象でない (doxyfw などの生成物 `.md` を除外する)
- リポジトリの remote URL (`remote.origin.url`) が解決できる

## URL 解決の仕組み

発行処理はファイルごとにディスク上の実体パスを保持しています。
追加ドキュメント サブフォルダー機能 (`mergeSubfolderDocs`) でサブモジュール配下の `docs` を取り込んでいても、参照するのは実体パスです。
このため実体パスから `git rev-parse --show-toplevel` を行うと、そのファイルが属するリポジトリ (サブモジュールならサブモジュール ルート、メインならメイン ルート) が確定します。
これによりマージ機能とサブモジュール機能の組み合わせが吸収され、リンク先はファイルが実際に存在するリポジトリの remote に解決されます。
サブモジュール配下のファイルは、当該サブモジュール自身のリポジトリの単一ページを指します。

解決手順は次のとおりです。実装は `bin/get_file_git_url.sh` にあります。

1. 実体パスから所属リポジトリのルートを取得する。
2. リポジトリ ルートからの相対パスを求める。
3. 追跡済みかどうかを確認する。未追跡なら非表示。
4. `.gitignore` 対象かどうかを確認する。対象なら非表示。
5. `remote.origin.url` を取得する。空なら非表示。
6. remote URL を web ベース URL (`scheme://host/owner/repo`) に正規化する。
7. host から provider 種別を判定する。
8. ref を決定する。通常はブランチ名を用いる。detached HEAD (サブモジュールで多い) の場合は、そのファイルの最終コミット SHA にフォールバックする。
9. provider に応じた blob URL を組み立てる。

### remote URL の正規化

次の形式に対応します。

- `https://host/owner/repo(.git)`
- `http://host/owner/repo(.git)`
- `ssh://git@host[:port]/owner/repo(.git)` (web では port が異なるため port を除去)
- `git@host:owner/repo(.git)` (scp ライク)

### provider の判定と URL 形式

| provider | host の判定 | blob URL 形式 |
|---|---|---|
| github | `github.com` | `<base>/blob/<ref>/<path>` |
| gitlab | `gitlab.com` または host に `gitlab` を含む | `<base>/-/blob/<ref>/<path>` |
| gitbucket | host に `gitbucket` を含む、または設定で指定 | `<base>/blob/<ref>/<path>` |
| gitea | 設定で指定 | `<base>/blob/<ref>/<path>` |
| git (汎用) | 上記いずれにも該当しない | `<base>/blob/<ref>/<path>` |

GitHub / GitBucket / Gitea は同じ `/blob/` 形式で、GitLab のみ `/-/blob/` 形式です。
GitBucket がコンテキスト パス配下 (例: `https://host/gitbucket/owner/repo`) で運用されている場合も、remote URL がそのパスを含んでいれば正しく解決されます。

provider はアイコンの選択にも用います。判定できない場合は汎用 Git アイコンにフォールバックします。

## 設定

`pub_markdown.config.yaml` で次のオプションを指定します。

```yaml
# Git 単一ページ リンクの有効化 (true / false)。デフォルト: true
gitLinkEnable: true

# 自己ホスト Git の host から provider 種別へのマッピング
# host=provider 形式をスペース区切りで指定する。provider: github | gitlab | gitbucket | gitea
# github.com / *gitlab* は自動判定されるため、社内ホスト等を明示したい場合にのみ指定する。
gitLinkHostProvider: git.example.com=gitlab gitbucket.example.com=gitbucket
```

`github.com` および host に `gitlab` を含むホストは自動的に判定されます。
社内ホストの GitLab や GitBucket など、host 名から判定できないホスティングを使う場合に `gitLinkHostProvider` を指定します。

## doxyfw 生成 md の origin ヒント連携

doxyfw が生成する `Files/` 配下の Markdown は `.gitignore` 対象のため、その md 自身には Git 上に対応する単一ページがありません。
そこで doxyfw 側で、生成 md の先頭フロントマターに元ソース ファイルのパスをヒントとして埋め込みます。

埋め込むキーは `git-origin` で、値はワークスペース ルートからの相対パスです。

```yaml
---
summary: "calc ライブラリの公開アンブレラ ヘッダー。"
short-title: "calc.h"
git-origin: "app/calc/prod/include/calc.h"
---
```

docsfw は発行時に `$file` のフロントマターから `git-origin` を読み取り、`${workspaceFolder}/${git-origin}` が実体として存在すれば、md 自身ではなくこの元ソースに対して Git リンクを解決します。
この差し替えにより、生成 md が `.gitignore` 対象であっても、追跡済みの元ソースへのリンクを表示できます。
元ソースがサブモジュール配下にある場合は、上記の解決の仕組みによってサブモジュール自身のリポジトリを指します。

doxyfw 側の埋め込みは `templates/inject-source-origin.py` が担当し、`Files/` 配下の各 md のパスから元ソースを特定します。
詳細は doxyfw 側のドキュメントを参照してください。

## 補足

- リンク先 URL の到達性 (push 済みかどうか) はネットワーク確認しません。Git の追跡状態と remote の解決のみを条件とします。未 push のコミットやブランチを参照している場合、リンク先が見つからないことがあります。
- リンク先 URL は言語版・詳細版のバリアント間で不変 (ソース ファイルにのみ依存) のため、バリアント コピー最適化と両立します。docx ダウンロードや詳細切り替えのような実行時の実在確認は行いません。
- self-contain HTML にはリンクを埋め込みません (docx ダウンロード リンクと同じ扱い)。
- フロントマターの `git-origin` キーは pandoc がメタデータとして読み取りますが、テンプレートは参照しないため出力には影響しません。
