-- links-to-html.lua
function Link(el)
  el.target = string.gsub(el.target, "%.md", ".docx")
  el.target = string.gsub(el.target, "%.Rmd", ".docx")
  el.target = string.gsub(el.target, "%.Tmd", ".docx")
  el.target = string.gsub(el.target, "%.rst", ".docx")
  el.target = string.gsub(el.target, "%.yaml", ".docx")
  el.target = string.gsub(el.target, "%.json", ".docx")
  return el
end
