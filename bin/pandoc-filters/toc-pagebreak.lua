-- toc-pagebreak.lua
-- docx かつ toc: true のとき、目次の直後（最初の見出し直前）に改ページを挿入する
--
-- pandoc の docx writer は toc: true のとき、Lua フィルター処理後に
-- TOC を文書先頭（最初の見出しの前）に挿入する。
-- そのため、本フィルターで最初の Header の直前に改ページを入れることで、
-- 最終的な docx では「目次 → 改ページ → 本文」の順序になる。

local function is_toc_enabled(meta)
  local toc = meta and meta.toc
  if toc == nil then return false end
  if type(toc) == "boolean" then return toc end
  if toc.t == "MetaBool" then return toc.c end
  return false
end

local function make_page_break()
  return pandoc.RawBlock("openxml", '<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
end

function Pandoc(doc)
  if FORMAT ~= "docx" then return doc end
  if not is_toc_enabled(doc.meta) then return doc end

  local new_blocks = {}
  local inserted = false

  for _, block in ipairs(doc.blocks) do
    if not inserted and block.t == "Header" then
      table.insert(new_blocks, make_page_break())
      inserted = true
    end
    table.insert(new_blocks, block)
  end

  if not inserted then return doc end
  return pandoc.Pandoc(new_blocks, doc.meta)
end
