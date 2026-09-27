-- inline-code-style.lua
-- docx 出力時、インラインコード (Code) に専用文字スタイル InlineCode を割り当てる。
-- Pandoc docx writer はインラインコードもハイライトなしコードブロックの各行も
-- 同じ VerbatimChar を使うため、VerbatimChar に網かけを付けると両方に効いてしまう。
-- インラインコードだけを別スタイル InlineCode に振り替え、網かけを InlineCode のみに付ける。
-- 詳細: docs/docx-template-styles.md を参照。
function Code(el)
  if not (FORMAT and FORMAT:match("docx")) then
    return nil  -- HTML 等は変更しない (code クラスのまま素通し)
  end
  local t = el.text:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
  local xml = '<w:r><w:rPr><w:rStyle w:val="InlineCode"/></w:rPr>'
           .. '<w:t xml:space="preserve">' .. t .. '</w:t></w:r>'
  return pandoc.RawInline("openxml", xml)
end
