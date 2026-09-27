-- codeblock-caption.lua
--
-- コードブロックの caption 属性を、キャプション段落として出力する。
-- caption 属性は codeblock-caption-line.lua が "CodeBlock:" 行から設定する。
--
-- ラベル (identifier) が付いたコードブロックは pandoc-crossref がリストとして
-- 採番するため、pandoc-crossref が利用できる場合はここでは処理せず、
-- caption 属性を残したまま素通しする。表示位置とスタイルの調整は
-- listing-caption-style.lua が行う。
--
-- pandoc-crossref が無い環境では採番なしのキャプション段落として出力する。
-- 有無は pub_markdown_core.sh がメタデータ docsfw-crossref で通知する。

local pandoc = require("pandoc")

local CAPTION_STYLE = "Source Code Caption"

-- pandoc-crossref が利用できるかどうか
local crossref_available = false

--- キャプション文字列をインライン列へ変換する。"\n" は改行として扱う。
local function caption_inlines(caption)
    caption = caption:gsub("\\n", "\n")
    local inlines = {}
    for line in caption:gmatch("[^\n]+") do
        table.insert(inlines, pandoc.Str(line))
        table.insert(inlines, pandoc.LineBreak())
    end
    if #inlines == 0 then
        return { pandoc.Str(caption) }
    end
    -- 末尾の LineBreak を除去する
    table.remove(inlines)
    return inlines
end

--- キャプション段落を作成する。
local function caption_block(caption)
    return pandoc.Div(
        { pandoc.Plain(caption_inlines(caption)) },
        pandoc.Attr("", {}, { ["custom-style"] = CAPTION_STYLE })
    )
end

return {
    {
        Meta = function(meta)
            local value = meta["docsfw-crossref"]
            if value ~= nil then
                crossref_available = (pandoc.utils.stringify(value) == "true")
            end
            return meta
        end
    },
    {
        CodeBlock = function(elem)
            local caption = elem.attributes["caption"]
            if not caption then
                return nil
            end

            -- ラベル付きは pandoc-crossref に委譲する
            if crossref_available and elem.identifier ~= "" then
                return nil
            end

            elem.attributes["caption"] = nil
            return { elem, caption_block(caption) }
        end
    }
}
