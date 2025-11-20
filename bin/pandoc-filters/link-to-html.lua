-- links-to-html.lua
function Link(el)
  -- README.md を index.md に置換 (ケース非依存、パス内またはファイル名単体)
  el.target = string.gsub(el.target, "/[Rr][Ee][Aa][Dd][Mm][Ee]%.md", "/index.md")
  el.target = string.gsub(el.target, "^[Rr][Ee][Aa][Dd][Mm][Ee]%.md", "index.md")
  el.target = string.gsub(el.target, "%.md", ".html")
  el.target = string.gsub(el.target, "%.Rmd", ".html")
  el.target = string.gsub(el.target, "%.Tmd", ".html")
  el.target = string.gsub(el.target, "%.rst", ".html")
  el.target = string.gsub(el.target, "%.yaml", ".html")
  el.target = string.gsub(el.target, "%.json", ".html")
  return el
end
