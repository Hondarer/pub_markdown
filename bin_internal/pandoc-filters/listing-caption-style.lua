-- listing-caption-style.lua
--
-- pandoc-crossref が生成したリスト (div.listing) のキャプションを整形する。
--
-- pandoc-crossref はリストのキャプション段落をコードブロックの上に配置するが、
-- docsfw ではコードブロックのキャプションを下に表示する。そのため
-- キャプション段落を末尾へ移し、codeblock-caption.lua と同じ
-- custom-style "Source Code Caption" を付与して HTML の CSS と
-- docx の SourceCodeCaption スタイルに合流させる。
--
-- pandoc-crossref を導入していない環境では div.listing が生成されないため、
-- このフィルターは何もしない。
--
-- 適用位置は pandoc-crossref よりも後 (pandoc はコマンドラインの記述順に
-- フィルターを適用する)。

local CAPTION_STYLE = "Source Code Caption"

--- Div が pandoc-crossref のリストかどうかを判定する。
local function is_listing(div)
    for _, class in ipairs(div.classes) do
        if class == "listing" then
            return true
        end
    end
    return false
end

--- キャプション部分のブロック列を取り出す。
--- pandoc-crossref は出力形式によって Para と Div のどちらかを生成する。
--- docx 出力では custom-style "Caption" の Div で包まれる。
local function caption_blocks(block)
    if block.t == "Para" then
        return { pandoc.Plain(block.content) }
    end
    if block.t == "Div" then
        local blocks = {}
        for _, inner in ipairs(block.content) do
            if inner.t == "Para" then
                table.insert(blocks, pandoc.Plain(inner.content))
            else
                table.insert(blocks, inner)
            end
        end
        return blocks
    end
    return nil
end

function Div(elem)
    if not is_listing(elem) then
        return nil
    end

    local first = elem.content[1]
    if first == nil then
        return nil
    end

    local caption = caption_blocks(first)
    if caption == nil then
        return nil
    end

    -- 先頭のキャプションを custom-style 付きで末尾へ移動する
    elem.content:remove(1)
    elem.content:insert(pandoc.Div(
        caption,
        pandoc.Attr("", {}, { ["custom-style"] = CAPTION_STYLE })
    ))
    return elem
end
