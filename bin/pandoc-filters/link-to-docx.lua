-- links-to-html.lua
function Link(el)
  el.target = string.gsub(el.target, "%.md", ".docx")
  el.target = string.gsub(el.target, "%.Rmd", ".docx")
  el.target = string.gsub(el.target, "%.Tmd", ".docx")
  el.target = string.gsub(el.target, "%.rst", ".docx")
  return el
end
