# PlantUML ショーケース

PlantUML の各図種のサンプルを示します。

## Sequence

```plantuml
@startuml sequence-sample
    caption Sequence のサンプル
    actor 利用者 as User
    participant アプリ as App
    database DB

    User -> App: リクエスト
    activate App
    App -> DB: 取得
    DB --> App: 結果
    App --> User: レスポンス
    deactivate App
@enduml
```

## Use Case

```plantuml
@startuml usecase-sample
    caption Use Case のサンプル
    left to right direction
    actor 利用者 as User
    rectangle 発行ツール {
        usecase "Markdown を読む" as Read
        usecase "HTML を生成する" as Html
        usecase "docx を生成する" as Docx
    }

    User --> Read
    Read --> Html
    Read --> Docx
@enduml
```

## Class

```plantuml
@startuml class-sample
    caption Class のサンプル
    class Document {
        +title: string
        +publish()
    }

    class Renderer {
        +render(doc: Document)
    }

    Renderer --> Document
@enduml
```

## Object

```plantuml
@startuml object-sample
    caption Object のサンプル
    object document {
        title = "README"
        format = "Markdown"
    }

    object output {
        path = "docs.html"
        format = "HTML"
    }

    document --> output
@enduml
```

## Activity

```plantuml
@startuml activity-sample
    caption Activity のサンプル
    start
    :Markdown を読み込む;
    if (図を含む?) then (はい)
        :図を SVG に変換する;
    else (いいえ)
        :本文だけを変換する;
    endif
    :成果物を出力する;
    stop
@enduml
```

## Component

```plantuml
@startuml component-sample
    caption Component のサンプル
    package docsfw {
        [pub_markdown_core.sh] as Pub
        [Pandoc] as Pandoc
        [PlantUML フィルタ] as Filter
    }

    Pub --> Pandoc
    Pandoc --> Filter
    Filter --> [SVG]
@enduml
```

## Deployment

```plantuml
@startuml deployment-sample
    caption Deployment のサンプル
    node "開発 PC" as Dev {
        artifact "README.md" as Md
        artifact "pub_markdown_core.sh" as Tool
    }

    node "成果物フォルダ" as Dist {
        artifact "index.html" as Html
        artifact "index.docx" as Docx
    }

    Tool --> Md
    Tool --> Html
    Tool --> Docx
@enduml
```

## State

```plantuml
@startuml state-sample
    caption State のサンプル
    [*] --> Draft
    Draft --> Review: 提出
    Review --> Published: 承認
    Review --> Draft: 差し戻し
    Published --> [*]
@enduml
```

## Timing

```plantuml
@startuml timing-sample
    caption Timing のサンプル
    robust "発行処理" as Publish
    concise "ブラウザ" as Browser

    @0
    Publish is "待機"
    Browser is "未起動"

    @5
    Publish is "変換中"
    Browser is "起動中"

    @10
    Browser is "描画中"

    @15
    Publish is "完了"
    Browser is "終了"
@enduml
```

## Network

```plantuml
@startuml network-sample
    caption Network のサンプル
    cloud "利用者ネットワーク" as ClientNet
    node "発行サーバ" as Server
    database "共有フォルダ" as Share

    ClientNet --> Server: HTTPS
    Server --> Share: SMB
@enduml
```

## Mindmap

```plantuml
@startmindmap mindmap-sample
    caption Mindmap のサンプル
    * pub_markdown
    ** 入力
    *** Markdown
    *** PlantUML
    ** 出力
    *** HTML
    *** docx
@endmindmap
```

## WBS

```plantuml
@startwbs wbs-sample
    caption WBS のサンプル
    * ドキュメント発行
    ** Markdown 作成
    ** 図の変換
    ** HTML 生成
    ** docx 生成
@endwbs
```

## Gantt

```plantuml
@startgantt gantt-sample
    caption Gantt のサンプル
    project starts 2026-05-01
    [設計] lasts 3 days
    [実装] starts at [設計]'s end and lasts 4 days
    [確認] starts at [実装]'s end and lasts 2 days
@endgantt
```

## Work Breakdown

```plantuml
@startuml work-breakdown-sample
    caption Work Breakdown のサンプル
    rectangle 入力
    rectangle 変換
    rectangle 出力

    入力 --> 変換
    変換 --> 出力
@enduml
```

## Salt

```plantuml
@startsalt salt-sample
{
    caption Salt のサンプル
    {+ 文書発行 }
    {T
        + docs
        ++ sample
        +++ plantuml-showcase.md
    }
    [発行] [確認]
}
@endsalt
```

## JSON

```plantuml
@startjson json-sample
{
    "document": "README.md",
    "outputs": ["html", "docx"],
    "diagrams": {
        "plantuml": true,
        "mermaid": true
    }
}
@endjson
```

## YAML

```plantuml
@startyaml yaml-sample
document: README.md
outputs:
  - html
  - docx
diagrams:
  plantuml: true
  mermaid: true
@endyaml
```

## EBNF

```plantuml
@startebnf ebnf-sample
    caption EBNF のサンプル
    document = heading, { block };
    heading = "#", text;
    block = paragraph | diagram;
    diagram = "```plantuml", text, "```";
@endebnf
```

## Regex

```plantuml
@startregex regex-sample
    caption Regex のサンプル
    title Markdown 見出し
    ^#{1,6}\s+.+$
@endregex
```
