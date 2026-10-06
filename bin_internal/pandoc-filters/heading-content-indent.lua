-- heading-content-indent.lua
--
-- Markdown の H5 以降の見出しと、その配下の本文を字下げする。
-- 見出しには docsfw-heading-indent-N クラスを付け、次の見出しまでの本文を
-- 同じクラスの Div で囲む。N は H5 が 1、H6 が 2 で、CSS が 1 段ごとに
-- docx テンプレートと同じ 7.5mm を字下げする。
--
-- 水平線は区切りのため、前後の字下げのうち浅い方で引く。
-- 本文の途中の水平線は本文と同じ字下げに、上位の見出しの直前の水平線は
-- その見出しの字下げになる。文書の末尾は字下げ 0 とみなす。
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

local function heading_depth(header)
    return math.max(0, header.level - FIRST_INDENTED_LEVEL + 1)
end

function Pandoc(doc)
    if not FORMAT:match("html") then
        return nil
    end

    local blocks = pandoc.Blocks({})
    local body = pandoc.Blocks({})
    local depth = 0

    local function wrap(content, content_depth)
        if content_depth > 0 then
            blocks:insert(pandoc.Div(content, pandoc.Attr("", { indent_class(content_depth) })))
        else
            blocks:extend(content)
        end
    end

    local function flush()
        if #body > 0 then
            wrap(body, depth)
            body = pandoc.Blocks({})
        end
    end

    for index, block in ipairs(doc.blocks) do
        if block.t == "Header" then
            flush()
            depth = heading_depth(block)
            if depth > 0 then
                block.classes:insert(indent_class(depth))
            end
            blocks:insert(block)
        elseif block.t == "HorizontalRule" then
            local next_block = doc.blocks[index + 1]
            local next_depth = depth
            if next_block == nil then
                next_depth = 0
            elseif next_block.t == "Header" then
                next_depth = heading_depth(next_block)
            end
            if next_depth >= depth then
                body:insert(block)
            else
                flush()
                wrap(pandoc.Blocks({ block }), next_depth)
            end
        else
            body:insert(block)
        end
    end
    flush()

    doc.blocks = blocks
    return doc
end
