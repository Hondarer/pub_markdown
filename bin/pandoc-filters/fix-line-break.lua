-- 以下のようなケースで、-f markdown+hard_line_breaks を指定した場合に、
-- para1 と para2 の間に不要な改行が挿入されることを防ぐ。
--
-- <!---->
-- para1
-- <!---->
-- para2
--
-- 上記において、para1 と para2 の間に、①改行、②コメント、③改行と入るのが原因なので、
-- ①の改行を取り除くことで整合を図る。

function Para (block)
    -- Para ブロック内の要素を処理

    local deleted = 0
    for i = 1, #block.content do
        local current = block.content[i - deleted]

        -- 要素が LineBreak でかつ次の要素が RawInline の場合
        if current.t == "LineBreak" and ((i + 1 - deleted) <= #block.content) and (block.content[i + 1 - deleted].t == "RawInline") then
            -- LineBreak を削除する
            table.remove(block.content, i - deleted)
            deleted = deleted + 1
        end
    end
  
    return block
end
