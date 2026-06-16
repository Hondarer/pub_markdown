# pubpart.yaml / pubchild.yaml / publocal.yaml について

## 概要

docsfw では、ディレクトリ階層の発行時の振る舞いを制御するためのマジックファイルを提供します。
これらはワークスペース全体の設定 (`.vscode/pub_markdown.config.yaml`) とは独立した、ディレクトリ単位の制御ファイルです。

命名とスコープの考え方は、makefw の `makepart.mk` / `makechild.mk` / `makelocal.mk` を踏襲しています。
makefw 側の詳細は [makeparts.md](../../makefw/docs/makeparts.md) を参照してください。

| ファイル | スコープ | 適用対象 | 現在の用途 |
|---|---|---|---|
| `pubpart.yaml` | 階層継承 (親から子に伝播) | 自ディレクトリ + 子階層すべて | 予約 (未実装) |
| `pubchild.yaml` | 子階層限定 (自身は除く) | 子階層以降のみ (自ディレクトリは除く) | 予約 (未実装) |
| `publocal.yaml` | 自ディレクトリ限定 | 自ディレクトリのみ | 並び順の指定 |

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

## 実装上の注意

- `publocal.yaml` は `order` を記述するディレクトリの直下に置きます。
- 並び順はそのディレクトリ直下の子にのみ作用します。孫以降の並び順は、それぞれのディレクトリに置いた `publocal.yaml` で指定します。
- ナビゲーション ツリー (`generate-nav-tree.py`) は出力 HTML を走査するため、ソース mdRoot と mergeSubfolderDocs のマッピングを参照して対応する `publocal.yaml` を読み込みます。
- TOC (`insert-toc.sh`) はソースを走査するため、各ディレクトリの `publocal.yaml` を直接読み込みます。mergeSubfolderDocs で取り込んだ仮想パスは、実ソース ディレクトリへ逆引きして `publocal.yaml` を解決します。
- mergeSubfolderDocs で取り込んだサブフォルダー内部の並び順も、マージ元の実ディレクトリに置いた `publocal.yaml` で指定できます。
