# Mermaid ショーケース

Mermaid の各図種のサンプルを示します。

## Flowchart

```{.mermaid caption="Flowchart のサンプル"}
flowchart LR
    Start([開始]) --> Check{確認}
    Check -->|OK| Done([完了])
    Check -->|NG| Fix[修正]
    Fix --> Check
```

## Sequence

```{.mermaid caption="Sequence のサンプル"}
sequenceDiagram
    participant User as 利用者
    participant App as アプリ
    User->>App: リクエスト
    App-->>User: レスポンス
```

## Class

```{.mermaid caption="Class のサンプル"}
classDiagram
    class Document {
        +string title
        +publish()
    }
    class Renderer {
        +render(Document doc)
    }
    Renderer --> Document
```

## State

```{.mermaid caption="State のサンプル"}
stateDiagram-v2
    [*] --> Draft
    Draft --> Review: 提出
    Review --> Published: 承認
    Review --> Draft: 差し戻し
    Published --> [*]
```

## ER

```{.mermaid caption="ER のサンプル"}
erDiagram
    CUSTOMER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    CUSTOMER {
        string name
        string email
    }
    ORDER {
        int order_id
        date ordered_at
    }
```

## User Journey

```{.mermaid caption="User Journey のサンプル"}
journey
    title ドキュメント発行
    section 作成
      Markdown を編集する: 5: Writer
      レビューを依頼する: 3: Writer
    section 発行
      HTML を生成する: 4: Publisher
      成果物を確認する: 5: Publisher
```

## Gantt

```{.mermaid caption="Gantt のサンプル"}
gantt
    title サンプル工程
    dateFormat  YYYY-MM-DD
    section 作業
    設計      :a1, 2026-05-01, 3d
    実装      :after a1, 4d
    確認      :2d
```

## Pie

```{.mermaid caption="Pie のサンプル"}
pie title 作業割合
    "設計" : 30
    "実装" : 50
    "確認" : 20
```

## Quadrant

```{.mermaid caption="Quadrant のサンプル"}
quadrantChart
    title Priority Matrix
    x-axis Low Cost --> High Cost
    y-axis Low Value --> High Value
    TaskA: [0.25, 0.80]
    TaskB: [0.70, 0.60]
    TaskC: [0.45, 0.35]
```

## Requirement

```{.mermaid caption="Requirement のサンプル"}
requirementDiagram
    requirement req_publish {
        id: 1
        text: Markdown を発行できる
        risk: medium
        verifymethod: test
    }

    element cli {
        type: tool
    }

    cli - satisfies -> req_publish
```

## GitGraph

```{.mermaid caption="GitGraph のサンプル"}
gitGraph
    commit id: "init"
    branch feature
    checkout feature
    commit id: "edit"
    checkout main
    merge feature
```

<!--
## C4

```{.mermaid caption="C4 のサンプル"}
C4Context
    title C4 Context のサンプル
    Person(user, "利用者")
    System(pub, "pub_markdown", "Markdown を発行する")
    Rel(user, pub, "Markdown を発行")
```
-->

## Mindmap

```{.mermaid caption="Mindmap のサンプル"}
mindmap
  root((pub_markdown))
    入力
      Markdown
      Mermaid
    出力
      HTML
      docx
```

## Timeline

```{.mermaid caption="Timeline のサンプル"}
timeline
    title 発行処理の流れ
    受付 : 対象 Markdown を確認
    変換 : Pandoc とフィルタを実行
    出力 : HTML と docx を生成
```

<!--
## ZenUML

```{.mermaid caption="ZenUML のサンプル"}
zenuml
    title API 呼び出し
    User->App.method() {
        App->Service.fetch()
        return result
    }
```
-->

## Sankey

```{.mermaid caption="Sankey のサンプル"}
sankey-beta
    Markdown,HTML,60
    Markdown,docx,40
    Mermaid,SVG,30
```

## XY Chart

```{.mermaid caption="XY Chart のサンプル"}
xychart-beta
    title "テスト件数"
    x-axis ["月", "火", "水", "木", "金"]
    y-axis "件数" 0 --> 10
    bar [3, 5, 7, 6, 8]
```

## Block

```{.mermaid caption="Block のサンプル"}
block-beta
    columns 3
    A["入力"] B["変換"] C["出力"]
    A --> B
    B --> C
```

## Packet

```{.mermaid caption="Packet のサンプル"}
packet-beta
    title TCP Packet
    0-15: "Source Port"
    16-31: "Destination Port"
    32-63: "Sequence Number"
```

## Kanban

```{.mermaid caption="Kanban のサンプル"}
kanban
    todo[未着手]
        task1[構成を確認]
    doing[作業中]
        task2[本文を作成]
    done[完了]
        task3[レビュー済み]
```

## Architecture

```{.mermaid caption="Architecture のサンプル"}
architecture-beta
    group app(cloud)[Application]
    service user(internet)[User]
    service docs(server)[Docs] in app
    service store(database)[Storage] in app
    user:R --> L:docs
    docs:R --> L:store
```

## Radar

```{.mermaid caption="Radar のサンプル"}
radar-beta
    axis d["Design"], i["Implement"], t["Test"], doc["Docs"]
    curve current["Current"]{4,3,5,4}
    curve target["Target"]{5,5,5,5}
    max 5
    min 0
```

## Treemap

```{.mermaid caption="Treemap のサンプル"}
treemap
    title 成果物の内訳
    "HTML": 60
    "docx": 30
    "SVG": 10
```

## Venn

```{.mermaid caption="Venn のサンプル"}
venn-beta
    title Scope
    set HTML: 50
    set docx: 40
    set Markdown: 30
    union HTML,Markdown: 20
    union docx,Markdown: 15
```

## Ishikawa

```{.mermaid caption="Ishikawa のサンプル"}
ishikawa
    title 品質課題
    "表示崩れ"
        "入力"
            "Markdown"
            "図"
        "変換"
            "Pandoc"
            "フィルタ"
        "出力"
            "HTML"
            "docx"
```

## Wardley

```{.mermaid caption="Wardley のサンプル"}
wardley-beta
    title Publish Flow
    anchor User [0.95, 0.75]
    component Markdown [0.70, 0.55]
    component Pandoc [0.45, 0.35]
    component Output [0.25, 0.20]
    User -> Markdown
    Markdown -> Pandoc
    Pandoc -> Output
```

## TreeView

```{.mermaid caption="TreeView のサンプル"}
treeView-beta
    "docs"
      "sample"
        "mermaid.md"
        "plantuml.md"
      "README.md"
```
