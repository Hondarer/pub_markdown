# pubpart.yaml / pubchild.yaml / publocal.yaml について

## 概要

docsfw では、ディレクトリ階層の発行時の振る舞いを制御するためのマジックファイルを提供します。
これらはワークスペース全体の設定 (`.vscode/pub_markdown.config.yaml`) とは独立した、ディレクトリ単位の制御ファイルです。

命名とスコープの考え方は、makefw の `makepart.mk` / `makechild.mk` / `makelocal.mk` を踏襲しています。
makefw 側の詳細は [makeparts.md](../../makefw/docs/makeparts.md) を参照してください。

| ファイル | スコープ | 適用対象 | 現在の用途 |
|---|---|---|---|
| `pubpart.yaml` | 階層継承 (親から子に伝播) | 自ディレクトリ + 子階層すべて | フロントマター デフォルト値 |
| `pubchild.yaml` | 子階層限定 (自身は除く) | 子階層以降のみ (自ディレクトリは除く) | フロントマター デフォルト値 |
| `publocal.yaml` | 自ディレクトリ限定 | 自ディレクトリのみ | 並び順の指定 / フロントマター デフォルト値 |

これらのファイルは、記述する内容がある場合にだけ作成すれば十分です。
設定が不要なときは、空のファイルを作成する必要はありません。

マジックファイル自身は発行対象には含まれません (HTML や docx として出力されません)。

## publocal.yaml: 並び順の指定

`publocal.yaml` の `order` に、そのディレクトリ直下の子 (ファイル・サブフォルダー) を並べたい順に列挙します。
この指定は、ナビゲーション ツリーと TOC (目次) の両方の並び順に反映されます。

```yaml
order:
  - overview.md       # ファイルは拡張子つきの実ファイル名で指定する
  - reference.md
  - advanced/         # サブフォルダーは名前で指定する (末尾の / は任意)
```

### 並び順のルール

- `order` に列挙されたものを、先頭にこの順で並べます。
- `order` に列挙されていない子は、従来どおり名前順 (大文字小文字を無視したアルファベット順) で末尾に追加します。
- ファイルはソース名 (`.md` / `.markdown`) で指定します。サブフォルダーは末尾の `/` の有無を問いません。

### 配置例

```
docs/
+-- guide.md
+-- api/
    +-- publocal.yaml      # api/ 直下の並び順を指定する
    +-- overview.md
    +-- reference.md
    +-- advanced/
        +-- index.md
```

上記の `docs/api/publocal.yaml` が以下の場合、

```yaml
order:
  - reference.md
  - overview.md
```

`api/` 直下は `reference.md`, `overview.md`, `advanced/` の順で並びます (`advanced/` は未列挙のため名前順で末尾)。

### マージ フォルダー (エイリアス) の並び順

`mergeSubfolderDocs` で取り込んだサブフォルダーは、主 mdRoot (既定 `docs/`) の直下にエイリアス名のフォルダーとして現れます。
このエイリアス フォルダー同士の並び順も `publocal.yaml` で指定できます。

主 mdRoot の直下 (`docs/publocal.yaml`) に置き、`order` に **エイリアス名** を列挙します。

```yaml
# docs/publocal.yaml
order:
  - docsfw
  - calc
  - calc.net          # ドットを含むエイリアス名もそのまま指定する
```

この場合、ナビゲーション ツリーと TOC の最上位は `docsfw`, `calc`, `calc.net` の順で並び、未列挙のエイリアスは名前順で末尾に続きます。

- エイリアス名はファイル名ではなくフォルダー名として扱うため、末尾の `/` の有無は問いません。
- `calc.net` のようにドットを含むエイリアス名は、`.md` / `.markdown` / `.html` 以外の語尾を除去しないため、そのまま指定します。

マージ元の各サブフォルダー内部 (例: `app/calc/docs/`) の並び順は、そのサブフォルダーの実ディレクトリに置いた `publocal.yaml` で指定します。

## defaults: フロントマター デフォルト値

マジックファイルの `defaults:` ブロックに `key: value` を書くと、スコープ内の Markdown が
その属性を自前のフロントマターに持たない場合にだけ、指定した値が pandoc のメタデータとして適用されます。
ドキュメント自身がフロントマターで同じキーを指定していれば、そちらが優先されます。

`defaults:` は 3 ファイル (`pubpart.yaml` / `pubchild.yaml` / `publocal.yaml`) のいずれでも使えます。
`order:` とは独立したブロックであり、`publocal.yaml` には両方を併記できます。

```yaml
# 例: docs/api/publocal.yaml
order:
  - overview.md
  - reference.md
defaults:
  category: API リファレンス
  author: 開発チーム
```

任意のフロントマター キーを指定できます (許可リストはありません)。値の解釈 (クォート、コメント、型) は
pandoc 側の YAML パーサーに委ねます。

### スコープと適用対象

ファイル F が在るディレクトリを D とすると、各ファイルの作用は次のとおりです。

| ファイル | デフォルト値の適用先 | D 直下の F への作用 |
|---|---|---|
| `publocal.yaml` | D 自身のみ | 適用される (最も局所的な既定) |
| `pubpart.yaml` | D とその配下すべて | 適用される |
| `pubchild.yaml` | D の配下のみ (D 自身は除く) | 適用されない (D の祖先の `pubchild.yaml` は適用される) |

### 優先順位

複数のスコープが同じキーを与えた場合は、次の規則で 1 つに決まります。

- ドキュメント自身のフロントマター > 近いディレクトリ > 遠いディレクトリ。
- 同一ディレクトリ内では `local` > `part` > `child` (`local` が最優先)。
- `child` は配下にのみ作用するため、宣言したディレクトリ自身のファイルには効きません。

例えば次の配置では、`docs/api/guide.md` の `category` は `publocal.yaml` の `API ガイド` になり、
`author` は親の `pubpart.yaml` の `開発チーム` を継承します。`guide.md` 自身が `category` を
書いていれば、その値が最優先で勝ちます。

```
docs/
+-- pubpart.yaml       # defaults: { author: 開発チーム }
+-- api/
    +-- publocal.yaml  # defaults: { category: API ガイド }
    +-- guide.md
```

### 既知の制限

- ナビゲーション ツリーと TOC の見出し (`short-title` 系) は別経路 (`extract_short_title`) で
  読み込むため、`defaults:` の対象外です。
- `category` などの値を出力に表示するには、HTML / docx テンプレート側で対応するメタデータ
  (`$category$` など) を参照している必要があります。本機能は値を pandoc に渡すところまでを担います。
- `author` / `date` を `defaults:` で与えると pandoc のメタデータに載るため、`autoSetAuthor` /
  `autoSetDate` による環境変数 (`DOCUMENT_AUTHOR` / `DOCUMENT_DATE`) のフォールバックよりも優先されます。

## 実装上の注意

- `publocal.yaml` は `order` を記述するディレクトリの直下に置きます。
- 並び順はそのディレクトリ直下の子にのみ作用します。孫以降の並び順は、それぞれのディレクトリに置いた `publocal.yaml` で指定します。
- ナビゲーション ツリー (`generate-nav-tree.py`) は出力 HTML を走査するため、ソース mdRoot と mergeSubfolderDocs のマッピングを参照して対応する `publocal.yaml` を読み込みます。
- TOC (`insert-toc.sh`) はソースを走査するため、各ディレクトリの `publocal.yaml` を直接読み込みます。mergeSubfolderDocs で取り込んだ仮想パスは、実ソース ディレクトリへ逆引きして `publocal.yaml` を解決します。
- mergeSubfolderDocs で取り込んだサブフォルダー内部の並び順も、マージ元の実ディレクトリに置いた `publocal.yaml` で指定できます。
- `defaults:` は `pub_markdown_core.sh` が Markdown ごとに、ファイルの所属ディレクトリからソース ルートまで階層を遡って収集し、pandoc の `--metadata-file` 群として渡します。pandoc は後に渡したファイルを優先し、ドキュメント自身の YAML が最終的にすべてを上書きします。
- ソース ルートの上端は、mergeSubfolderDocs のサブフォルダー配下ならそのサブフォルダーの実 mdRoot、それ以外は主 mdRoot です。走査はその範囲に収まります。
