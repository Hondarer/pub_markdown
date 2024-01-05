-- links-to-html.lua
function Link(el)
  el.target = string.gsub(el.target, "%.md", ".html")
  el.target = string.gsub(el.target, "%.Rmd", ".html")
  el.target = string.gsub(el.target, "%.Tmd", ".html")
  el.target = string.gsub(el.target, "%.rst", ".html")
  el.target = string.gsub(el.target, "%.yaml", ".html")
  el.target = string.gsub(el.target, "%.json", ".html")
  return el
end
