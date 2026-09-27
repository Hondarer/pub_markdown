-- horizontal-rule.lua
-- docx 出力時に Pandoc 既定の VML ベース水平線を
-- Word の段落下罫線（AutoFormat の --- 相当）に置き換える。

function HorizontalRule()
  if FORMAT == "docx" then
    return pandoc.RawBlock(
      "openxml",
      '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="auto"/></w:pBdr></w:pPr></w:p>'
    )
  end
  return nil
end
