-- Table 内の 改行を docx (openxml) で実現する
-- 本来は docx writer が対応すべきところではあるが、
-- lua フィルターでも実現できたので、当面これでよい。

local function CellContent(block)
    -- セル内が Plain または Para である場合
    if block.t == "Plain" or block.t == "Para" then
        local new_content = {}
        for _, inline in ipairs(block.content) do
            -- <br> または <br /> の場合
            -- NOTE: 表内の改行方法はいくつかあるので、もしかすると、ASTを調べて、他の要素 (SoftBreak など) も対象にしたほうがよいかもしれない
            if inline.t == "RawInline" and inline.format == "html" and string.match(inline.text, "^<br ?/?>$") then
                -- openxml の改行表現を挿入
                table.insert(new_content, pandoc.RawInline("openxml", "<w:br />"))
            else
                table.insert(new_content, inline) -- その他の要素はそのまま追加
            end
        end
        block.content = new_content
    end
    return block
end

local function Cell(cell)
    cell.contents = cell.contents:map(CellContent)
    return cell
end

local function Row(row)
    row.cells = row.cells:map(Cell)
    return row
end

local function TableHead(head)
    head.rows = head.rows:map(Row)
    return head
end

local function TableBody(body)
    body.body = body.body:map(Row)
    return body
end

local function TableFoot(foot)
    foot.rows = foot.rows:map(Row)
    return foot
end

function Table(table)
    if FORMAT == "docx" then
        table.head = TableHead(table.head)
        table.bodies = table.bodies:map(TableBody)
        table.foot = TableFoot(table.foot)
    end
    return table
end
