-- docx 出力時に、連続する引用ブロックが視覚的に結合しないようにする。
-- Word では隣接する引用段落が 1 つの連続した引用領域に見えることがあるため、
-- 連続する BlockQuote の間に空の通常段落を挿入する。

local function is_blockquote(block)
  return block ~= nil and block.t == "BlockQuote"
end

local function minimal_separator_paragraph()
  -- 0.06 行 ~= 14.4 / 240。OpenXML は整数指定のため 14 (約 0.058 行) を採用する。
  -- before/after も 0 固定にして、スタイル由来の段落余白継承を防ぐ。
  return pandoc.RawBlock(
    "openxml",
    "<w:p><w:pPr><w:spacing w:before=\"0\" w:after=\"0\" w:line=\"14\" w:lineRule=\"auto\"/></w:pPr></w:p>"
  )
end

function Pandoc(doc)
  local out = {}
  local prev_was_blockquote = false

  for _, block in ipairs(doc.blocks) do
    local curr_is_blockquote = is_blockquote(block)

    if prev_was_blockquote and curr_is_blockquote then
      table.insert(out, minimal_separator_paragraph())
    end

    table.insert(out, block)
    prev_was_blockquote = curr_is_blockquote
  end

  doc.blocks = out
  return doc
end