# Windows における PlantUML の `dot.exe` 自動展開 (同梱 Graphviz) 仕様

## 何が起きているか

PlantUML は **v1.2020.21 以降**、Windows 環境で外部 Graphviz (`dot.exe`) が見つからない場合に、**最小構成の Graphviz (graphviz-lite) を同梱**しており、実行時に **ユーザーの一時フォルダへ自動展開**してから利用します。展開先の既定パスは次のとおりです。
`%LOCALAPPDATA%\Temp\_graphviz\dot.exe` 。(外部の `dot.exe` が見つからない場合に限る) ([PlantUML.com][1]) ([GitHub][2])

## 導入の経緯 (タイムライン)

* **1.2020.21 以降**: Windows では **Graphviz を手動インストールしなくてもよい**運用を公式に案内。最小版 `dot.exe` を **必要時に一時フォルダへ自動解凍**して使う挙動が導入。1.2020.25 以前は生成時にメッセージが出る不具合があり、**1.2020.25 以上の利用が推奨**。 ([PlantUML.com][1])
* 同梱される `graphviz-lite` の配布元 (公式 GitHub リポジトリ) でも、**「PlantUML v1.2020.21+ はここからの lite 版を内蔵しており、外部 `dot.exe` が無いときだけ `%LOCALAPPDATA%\Temp\_graphviz` に展開する」**と明記。 ([GitHub][2])

## 探索と優先順位

PlantUML が Graphviz を探す順序・優先ルールは次のとおりです。

1. **環境変数 `GRAPHVIZ_DOT`** が指す `dot.exe` があればそれを使用。 ([PlantUML.com][1])
2. Windows の **既知パスの走査**（旧来互換）：`c:\*\graphviz*\bin\dot.exe` または `c:\*\graphviz*\release\bin\dot.exe` をルート直下からスキャン（再帰しない）。 ([PlantUML.com][1])
3. 上記で見つからない場合、**同梱の graphviz-lite を `%LOCALAPPDATA%\Temp\_graphviz` に自動展開**して使用。 ([PlantUML.com][1])

> 補足：同梱 `dot.exe` は **PlantUML 用に必要最小限のモジュールだけ**を含む「最小構成」ビルドです（`gvplugin_core.dll` と `gvplugin_dot_layout.dll` など）。 ([GitHub][2])

## 動作確認と切り替え

* **どの Graphviz が使われているか確認**

  ```bash
  plantuml -version        # または: java -jar plantuml.jar -version
  plantuml -testdot
  ```

  これらは PlantUML 公式のテスト手順として案内されています。 ([PlantUML.com][1])

* **外部 Graphviz を明示的に使う**

  * 例: `GRAPHVIZ_DOT=C:\Program Files\Graphviz\bin\dot.exe` を設定 (環境変数で上書き)。 ([PlantUML.com][1])

* **同梱 (自動展開) を使わせたい**

  * `GRAPHVIZ_DOT` を未設定にし、PATH 上にも `dot.exe` が無い状態にして実行すれば、同梱版が `%LOCALAPPDATA%\Temp\_graphviz` に展開されて使用されます。 ([PlantUML.com][1])

## Linux との違い (参考)

Linux/Mac の項では、基本的に **外部 Graphviz のインストール** (`apt`, `yum`, `brew` 等) を案内しており、Windows のような **同梱版の自動展開は前提にしていません**。必要であれば `GRAPHVIZ_DOT` で場所を指定します。 ([PlantUML.com][1])

### 参考リンク (公式)

* **Graphviz/DOT (公式ドキュメント)**: Windows セクションに「1.2020.21 以降は同梱 `dot.exe` を一時フォルダへ自動解凍して使う」旨を明記。探索順や `GRAPHVIZ_DOT`、`-testdot` もここに記載。 ([PlantUML.com][1])
* **graphviz-distributions (PlantUML 公式 GitHub)**: 同梱する **graphviz-lite** の内容と、**「`%LOCALAPPDATA%\Temp\_graphviz` に抽出する」仕様**を README に明記。 ([GitHub][2])

[1]: https://plantuml.com/graphviz-dot "Test your GraphViz installation"
[2]: https://github.com/plantuml/graphviz-distributions "GitHub - plantuml/graphviz-distributions: Some plug and play distributions for GraphViz"
