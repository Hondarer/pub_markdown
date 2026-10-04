-- 図の変換後に、標準テンプレートが必要とするブラウザー資産を選ぶ。
local FRAME_SENTINEL = "DOCSFW_FRAME_SCRIPT_END_7f3a9c"

local function read_frame(path)
    local handle = io.open(path, "rb")
    if not handle then
        error("図のフレーム文書を読めません: " .. path)
    end
    local text = handle:read("*a")
    handle:close()
    if text:find(FRAME_SENTINEL, 1, true) then
        error("図のフレーム文書に予約語が含まれます: " .. path)
    end
    -- script 要素の本文は </script> で終わる。フレーム内の終端は埋め込み時だけ置き換える。
    return text:gsub("</[Ss][Cc][Rr][Ii][Pp][Tt]", FRAME_SENTINEL)
end

local function append_frame(doc, id, path)
    local text = read_frame(path)
    doc.blocks:insert(pandoc.RawBlock("html",
        '<script type="text/plain" id="' .. id .. '">' .. text .. "</script>\n"))
end

function Pandoc(doc)
    if not FORMAT:match("html") then return doc end
    doc.meta["docsfw-has-math"] = false
    doc:walk({ Math = function()
        doc.meta["docsfw-has-math"] = true
    end, RawBlock = function(block)
        if block.format == "html" then
            if block.text:find('class="docsfw%-mermaid"') then
                doc.meta["docsfw-has-mermaid"] = true
            end
            if block.text:find('class="docsfw%-plantuml"') then
                doc.meta["docsfw-has-plantuml"] = true
            end
        end
    end })
    if not doc.meta["docsfw-browser-base"] and doc.meta["mermaid-js"] then
        local script = pandoc.utils.stringify(doc.meta["mermaid-js"])
        local base = script:gsub("[^/]+$", "")
        -- 空文字列はテンプレートの $if$ で偽になる。直下のページも資産を読む。
        doc.meta["docsfw-browser-base"] = base == "" and "./" or base
    end
    -- 単一 HTML だけ、同じフレーム文書を実行されないブロックへ入れる。
    -- 通常 HTML と file:// は、開始後に iframe.src で兄弟ファイルを読む。
    if doc.meta["docsfw-embed-frames"] and doc.meta["mermaid-js"] then
        local script = pandoc.utils.stringify(doc.meta["mermaid-js"])
        local base = script:gsub("[^/\\]+$", "")
        if doc.meta["docsfw-has-mermaid"] then
            append_frame(doc, "docsfw-mermaid-frame", base .. "docsfw-mermaid-frame.html")
        end
        if doc.meta["docsfw-has-plantuml"] then
            append_frame(doc, "docsfw-plantuml-frame", base .. "docsfw-plantuml-frame.html")
        end
    end
    return doc
end
