-- 図の変換後に、標準テンプレートが必要とするブラウザー資産を選ぶ。
function Pandoc(doc)
    if not FORMAT:match("html") then return doc end
    doc:walk({ RawBlock = function(block)
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
    return doc
end
