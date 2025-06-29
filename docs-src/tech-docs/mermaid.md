# Mermaid Pandoc フィルタ (mermaid.lua) について

## 概要

この Lua フィルタは、Pandoc 文書内の Mermaid コードブロックを自動的に SVG 画像に変換するためのフィルタです。mermaid-cli (mmdc) を使用して Mermaid 記法をレンダリングし、生成された SVG ファイルを最適化して文書に埋め込みます。

## 基本的な動作フロー

### コードブロックの検出と処理

```lua
CodeBlock = function(el) 
    local code_class = el.classes[1] or ""
    local lang, filename = code_class:match("^([^:]+):(.+)$")
    if not lang then
        lang = code_class
    end
    -- コード種別判定
    if lang ~= "mermaid" then
        return el
    end
```

- コードブロックのクラス属性を解析
- `mermaid` または `mermaid:filename` 形式をサポート
- mermaid 以外のコードブロックはそのまま通過

### キャプション処理

```lua
-- caption 属性があれば優先してキャプションに
local caption = el.attributes["caption"]
if caption then
    el.attributes["caption"] = nil
elseif filename then
    filename = filename:gsub("%.[mM][mM][dD]$", "")
    caption = filename
end
```

- `caption` 属性が指定されていればそれを使用
- なければファイル名部分 (拡張子除く) をキャプションとして使用

### クロスプラットフォーム対応

#### Windows 環境での文字エンコーディング処理

```lua
function utf8_to_active_cp(text)
    local os_name = os.getenv("OS")
    if not os_name or not string.match(os_name:lower(), "windows") then
        return text  -- Linux環境ではそのまま
    end
    
    -- PowerShellを使用してUTF-8からアクティブコードページに変換
    local temp_file = create_temp_file()
    -- ... PowerShell経由でのエンコーディング変換処理
end
```

- Windows 環境でのファイルパス文字化け対策
- PowerShell を使用して UTF-8 文字列をシステムのアクティブコードページに変換

#### 実行コマンドの選択

```lua
local MMDC_CMD
if package.config:sub(1,1) == '\\' then -- Windows
    MMDC_CMD = "\\node_modules\\.bin\\mmdc.cmd"
else -- Unix-like systems
    MMDC_CMD = "/mmdc-wrapper.sh"
end
```

### ファイル生成処理

```lua
local image_filename = string.format("mermaid_%s.svg", utils.sha1(el.text))
local mmd_filename = string.format("mermaid_%s.mmd", utils.sha1(el.text))
```

- SHA1 ハッシュを使用してユニークなファイル名を生成
- 同じ内容の Mermaid コードは同じファイル名になり、重複処理を回避

### Mermaid-CLI 実行

```lua
os.execute(string.format("cd %s && \"%s\" -i %s -o %s -b transparent | grep -v -E \"Generating|deprecated|Store is a function\"", 
    _resource_dir, _root_dir .. MMDC_CMD, _mmd_filename, _image_filename))
```

- 一時的な `.mmd` ファイルを作成
- mmdc (mermaid-cli) を実行してSVGを生成
- 背景を透明に設定 (`-b transparent`)
- 不要な出力メッセージをフィルタリング

## SVG 補正 (パッチ) 処理の詳細

### 問題の背景

Mermaid-CLI で生成される SVG には以下の問題がある:

1. **サイズ指定が不適切**: `width="100%"` で出力される
2. **スタイル属性の問題**: `max-width` が設定されているが、固定サイズが必要な場面で問題となる

### 補正処理の実装

`width="100%"` による予期しないスケーリングを防止する。

#### ViewBox からサイズ情報を抽出

```lua
local viewBox = svg_content:match('viewBox="([^"]+)"')
if viewBox then
    local _, _, w, h = viewBox:match("([%-%d%.]+) ([%-%d%.]+) ([%d%.]+) ([%d%.]+)")
    width = w
    height = h
end
```

**処理内容:**

- SVG の `viewBox` 属性から実際の描画領域サイズを取得
- `viewBox="-50 -10 485 259"` の場合、幅 485px、高さ 259px を抽出

#### スタイル属性の書き換え

```lua
patched_svg = patched_svg:gsub('(<svg[^>]-)style="([^"]*)"', function(svg_tag, style)
    -- max-width を削除
    style = style:gsub("max%-width:[^;]*;? ?", "")
    -- width / height を削除
    style = style:gsub("width:[^;]*;?", "")
    style = style:gsub("height:[^;]*;?", "")
    -- 末尾に width / height 追加
    return string.format('%sstyle="width:%spx; height:%spx; %s"', svg_tag, width, height, style)
end, 1)
```

**処理内容:**

- ルート SVG 要素の `style` 属性のみを対象 (`end, 1` で最初の要素のみ)
- `max-width`、既存の `width`、`height` プロパティを削除
- ViewBox から取得した固定サイズを設定

#### SVG 属性の書き換え

```lua
patched_svg = patched_svg
    :gsub('(<svg[^>]*)%swidth="[^"]*"', '%1', 1)
    :gsub('(<svg[^>]*)%sheight="[^"]*"', '%1', 1)
    :gsub('(<svg)', '%1 width="' .. width .. 'px" height="' .. height .. 'px"', 1)
```

**処理内容:**

- 既存の `width`、`height` 属性を削除
- ViewBox から取得したサイズで新しい `width`、`height` 属性を追加

### 補正前後の比較

**補正前:**

```xml
<svg aria-roledescription="sequence" role="graphics-document document" 
     viewBox="-50 -10 485 259" 
     style="max-width: 485px; background-color: transparent;" 
     xmlns:xlink="http://www.w3.org/1999/xlink" 
     xmlns="http://www.w3.org/2000/svg" 
     width="100%" 
     id="my-svg">
```

**補正後:**

```xml
<svg width="485px" height="259px" 
     aria-roledescription="sequence" role="graphics-document document" 
     viewBox="-50 -10 485 259" 
     style="width:485px; height:259px; background-color: transparent;" 
     xmlns:xlink="http://www.w3.org/1999/xlink" 
     xmlns="http://www.w3.org/2000/svg" 
     id="my-svg">
```
