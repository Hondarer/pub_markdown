-- heading-content-indent.lua
--
-- Markdown の H5 以降の見出しと、その配下の本文を字下げする。
-- 見出しには docsfw-heading-indent-N クラスを付け、次の見出しまでの本文を
-- 同じクラスの Div で囲む。N は H5 が 1、H6 が 2 で、CSS が 1 段ごとに
-- docx テンプレートと同じ 7.5mm を字下げする。
--
-- 見出しは Div の外に残し、見出し同士を兄弟要素に保つ。
-- 見出しの id、CSS カウンター、目次の追従処理は見出しを直接参照するため、
-- 見出しを囲むと動作が変わる。
-- Lua フィルターは --shift-heading-level-by の適用前のレベルを受け取るため、
-- Markdown のレベルで判定する。
-- 表のキャプションなど、ほかのフィルターが生成したブロックも囲むため、
-- HTML 用フィルター列の最後に適用する。

local FIRST_INDENTED_LEVEL = 5

local function indent_class(depth)
    return "docsfw-heading-indent-" .. depth
end

function Pandoc(doc)
    if not FORMAT:match("html") then
        return nil
    end

    local blocks = pandoc.Blocks({})
    local body = pandoc.Blocks({})
    local depth = 0

    local function flush()
        if #body == 0 then
            return
        end
        if depth > 0 then
            blocks:insert(pandoc.Div(body, pandoc.Attr("", { indent_class(depth) })))
        else
            blocks:extend(body)
        end
        body = pandoc.Blocks({})
    end

    for _, block in ipairs(doc.blocks) do
        if block.t == "Header" then
            flush()
            depth = math.max(0, block.level - FIRST_INDENTED_LEVEL + 1)
            if depth > 0 then
                block.classes:insert(indent_class(depth))
            end
            blocks:insert(block)
        else
            body:insert(block)
        end
    end
    flush()

    doc.blocks = blocks
    return doc
end
