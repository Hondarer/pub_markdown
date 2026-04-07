-- admonition.lua
-- GitHub-style admonitions (alerts) を検出し、出力形式に応じた要素に変換する。
-- BlockQuote の先頭行が [!NOTE], [!TIP], [!IMPORTANT], [!WARNING], [!CAUTION] の
-- いずれかにマッチした場合のみ変換する。マッチしない場合は従来の blockquote のまま。

local stringify = pandoc.utils.stringify

local TYPES = {
  NOTE      = { class = "note",      title = "Note",       color = "1F6FEB" },
  TIP       = { class = "tip",       title = "Tip",        color = "238636" },
  IMPORTANT = { class = "important", title = "Important",  color = "8957E5" },
  WARNING   = { class = "warning",   title = "Warning",    color = "9A6700" },
  CAUTION   = { class = "caution",   title = "Caution",    color = "DA3633" },
}

--- BlockQuote の先頭 Para/Plain から [!TYPE] を検出し、タイプ名を返す。
--- マッチしなければ nil。
local function detect_type(bq)
  if #bq.content == 0 then return nil end
  local first_block = bq.content[1]
  if first_block.t ~= "Para" and first_block.t ~= "Plain" then return nil end

  local inlines = first_block.content
  if #inlines == 0 then return nil end

  local first_str = stringify(inlines[1])
  local adm_type = first_str:match("^%[!(%u+)%]$")
  if not adm_type or not TYPES[adm_type] then return nil end

  return adm_type
end

--- 先頭 Para/Plain から [!TYPE] トークンと直後の改行を除去し、
--- 残った内容ブロックリストを返す。
local function strip_marker(bq, adm_type)
  local blocks = pandoc.List(bq.content)
  local first_block = blocks[1]
  local inlines = pandoc.List(first_block.content)

  -- [!TYPE] Str を除去
  inlines:remove(1)

  -- 直後の LineBreak / SoftBreak を除去
  if #inlines > 0 and (inlines[1].t == "LineBreak" or inlines[1].t == "SoftBreak") then
    inlines:remove(1)
  end

  -- 先頭ブロックが空になった場合は除去、そうでなければ更新
  if #inlines == 0 then
    blocks:remove(1)
  else
    blocks[1] = pandoc.Para(inlines)
  end

  return blocks
end

function BlockQuote(bq)
  local adm_type = detect_type(bq)
  if not adm_type then return nil end

  local info = TYPES[adm_type]
  local content = strip_marker(bq, adm_type)

  if FORMAT:match("html") then
    local title_span = pandoc.Span(
      { pandoc.Str(info.title) },
      pandoc.Attr("", { "admonition-title" }, {})
    )
    local title_para = pandoc.Para({ title_span })
    content:insert(1, title_para)
    return pandoc.Div(content, pandoc.Attr("", { "admonition", "admonition-" .. info.class }, {}))

  elseif FORMAT:match("docx") then
    local style_name = "Block Text " .. info.title
    local style_id = style_name:gsub(" ", "")
    local title_raw = string.format(
      '<w:p><w:pPr><w:pStyle w:val="%s"/></w:pPr>' ..
      '<w:r><w:rPr><w:b/><w:color w:val="%s"/></w:rPr>' ..
      '<w:t>%s</w:t></w:r></w:p>',
      style_id, info.color, info.title
    )
    content:insert(1, pandoc.RawBlock("openxml", title_raw))
    return pandoc.Div(content, pandoc.Attr("", {}, { { "custom-style", style_name } }))

  else
    return nil
  end
end
