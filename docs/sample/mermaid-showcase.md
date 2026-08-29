# Mermaid ショーケース

Mermaid の各図種のサンプルを示します。

## Flowchart

```mermaid
flowchart LR
    Start([開始]) --> Check{確認}
    Check -->|OK| Done([完了])
    Check -->|NG| Fix[修正]
    Fix --> Check
```

CodeBlock: Flowchart のサンプル

## Sequence

```mermaid
sequenceDiagram
    participant User as 利用者
    participant App as アプリ
    User->>App: リクエスト
    App-->>User: レスポンス
```

CodeBlock: Sequence のサンプル

## Class

```mermaid
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

CodeBlock: Class のサンプル

## State

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Review: 提出
    Review --> Published: 承認
    Review --> Draft: 差し戻し
    Published --> [*]
```

CodeBlock: State のサンプル

## ER

```mermaid
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

CodeBlock: ER のサンプル

## User Journey

```mermaid
journey
    title ドキュメント発行
    section 作成
      Markdown を編集する: 5: Writer
      レビューを依頼する: 3: Writer
    section 発行
      HTML を生成する: 4: Publisher
      成果物を確認する: 5: Publisher
```

CodeBlock: User Journey のサンプル

## Gantt

```mermaid
gantt
    title サンプル工程
    dateFormat  YYYY-MM-DD
    section 作業
    設計      :a1, 2026-05-01, 3d
    実装      :after a1, 4d
    確認      :2d
```

CodeBlock: Gantt のサンプル

## Pie

```mermaid
pie title 作業割合
    "設計" : 30
    "実装" : 50
    "確認" : 20
```

CodeBlock: Pie のサンプル

## Quadrant

```mermaid
quadrantChart
    title Priority Matrix
    x-axis Low Cost --> High Cost
    y-axis Low Value --> High Value
    TaskA: [0.25, 0.80]
    TaskB: [0.70, 0.60]
    TaskC: [0.45, 0.35]
```

CodeBlock: Quadrant のサンプル

## Requirement

```mermaid
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

CodeBlock: Requirement のサンプル

## GitGraph

```mermaid
gitGraph
    commit id: "init"
    branch feature
    checkout feature
    commit id: "edit"
    checkout main
    merge feature
```

CodeBlock: GitGraph のサンプル

<!--
## C4

```mermaid
C4Context
    title C4 Context のサンプル
    Person(user, "利用者")
    System(pub, "pub_markdown", "Markdown を発行する")
    Rel(user, pub, "Markdown を発行")
```

CodeBlock: C4 のサンプル
-->

## Mindmap

```mermaid
mindmap
  root((pub_markdown))
    入力
      Markdown
      Mermaid
    出力
      HTML
      docx
```

CodeBlock: Mindmap のサンプル

## Timeline

```mermaid
timeline
    title 発行処理の流れ
    受付 : 対象 Markdown を確認
    変換 : Pandoc とフィルタを実行
    出力 : HTML と docx を生成
```

CodeBlock: Timeline のサンプル

<!--
## ZenUML

```mermaid
zenuml
    title API 呼び出し
    User->App.method() {
        App->Service.fetch()
        return result
    }
```

CodeBlock: ZenUML のサンプル
-->

## Sankey

```mermaid
sankey-beta
    Markdown,HTML,60
    Markdown,docx,40
    Mermaid,SVG,30
```

CodeBlock: Sankey のサンプル

## XY Chart

```mermaid
xychart-beta
    title "テスト件数"
    x-axis ["月", "火", "水", "木", "金"]
    y-axis "件数" 0 --> 10
    bar [3, 5, 7, 6, 8]
```

CodeBlock: XY Chart のサンプル

## Block

```mermaid
block-beta
    columns 3
    A["入力"] B["変換"] C["出力"]
    A --> B
    B --> C
```

CodeBlock: Block のサンプル

## Packet

```mermaid
packet-beta
    title TCP Packet
    0-15: "Source Port"
    16-31: "Destination Port"
    32-63: "Sequence Number"
```

CodeBlock: Packet のサンプル

## Kanban

```mermaid
kanban
    todo[未着手]
        task1[構成を確認]
    doing[作業中]
        task2[本文を作成]
    done[完了]
        task3[レビュー済み]
```

CodeBlock: Kanban のサンプル

## Architecture

```mermaid
architecture-beta
    group app(cloud)[Application]
    service user(internet)[User]
    service docs(server)[Docs] in app
    service store(database)[Storage] in app
    user:R --> L:docs
    docs:R --> L:store
```

CodeBlock: Architecture のサンプル

## Radar

```mermaid
radar-beta
    axis d["Design"], i["Implement"], t["Test"], doc["Docs"]
    curve current["Current"]{4,3,5,4}
    curve target["Target"]{5,5,5,5}
    max 5
    min 0
```

CodeBlock: Radar のサンプル

## Treemap

```mermaid
treemap
    title 成果物の内訳
    "HTML": 60
    "docx": 30
    "SVG": 10
```

CodeBlock: Treemap のサンプル

## Venn

```mermaid
venn-beta
    title Scope
    set HTML: 50
    set docx: 40
    set Markdown: 30
    union HTML,Markdown: 20
    union docx,Markdown: 15
```

CodeBlock: Venn のサンプル

## Ishikawa

```mermaid
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

CodeBlock: Ishikawa のサンプル

## Wardley

```mermaid
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

CodeBlock: Wardley のサンプル

## TreeView

```mermaid
treeView-beta
    "docs"
      "sample"
        "mermaid.md"
        "plantuml.md"
      "README.md"
```

CodeBlock: TreeView のサンプル
