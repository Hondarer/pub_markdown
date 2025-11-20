-- links-to-docx.lua
function Link(el)
  -- README.md を index.md に置換 (ケース非依存、パス内またはファイル名単体)
  el.target = string.gsub(el.target, "/[Rr][Ee][Aa][Dd][Mm][Ee]%.md", "/index.md")
  el.target = string.gsub(el.target, "^[Rr][Ee][Aa][Dd][Mm][Ee]%.md", "index.md")
  el.target = string.gsub(el.target, "%.md", ".docx")
  el.target = string.gsub(el.target, "%.Rmd", ".docx")
  el.target = string.gsub(el.target, "%.Tmd", ".docx")
  el.target = string.gsub(el.target, "%.rst", ".docx")
  el.target = string.gsub(el.target, "%.yaml", ".docx")
  el.target = string.gsub(el.target, "%.json", ".docx")
  return el
end
