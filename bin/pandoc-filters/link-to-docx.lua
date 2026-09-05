-- link-to-docx.lua

local source = debug.getinfo(1, "S").source
local filter_path = source:sub(1, 1) == "@" and source:sub(2) or source
local filter_dir = filter_path:match("^(.*[/\\])") or ""
local common = dofile(filter_dir .. "link-common.lua")

function Link(el)
  return common.rewrite_link(el, ".docx")
end
