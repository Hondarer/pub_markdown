-- links-to-docx.lua
local function file_exists(path)
  local file = io.open(path, "r")
  if file == nil then
    return false
  end
  file:close()
  return true
end

local function dirname(path)
  return path:match("^(.*)/[^/]*$") or "."
end

local function split_suffix(target)
  local path, suffix = target:match("^([^#?]*)(.*)$")
  return path or target, suffix or ""
end

local function normalize_path(path)
  local is_absolute = path:sub(1, 1) == "/"
  local parts = {}
  for part in path:gmatch("[^/]+") do
    if part == ".." then
      if #parts > 0 and parts[#parts] ~= ".." then
        table.remove(parts)
      elseif not is_absolute then
        table.insert(parts, part)
      end
    elseif part ~= "." and part ~= "" then
      table.insert(parts, part)
    end
  end
  local normalized = table.concat(parts, "/")
  if is_absolute then
    normalized = "/" .. normalized
  end
  return normalized
end

local function same_dir_has(path, filename)
  local dir = dirname(path)
  local ok, entries = pcall(pandoc.system.list_directory, dir)
  if not ok then
    return false
  end
  for _, candidate in ipairs(entries) do
    if candidate:lower() == filename then
      return true
    end
  end
  return false
end

local function rewrite_skill_index(target)
  local path, suffix = split_suffix(target)
  local lower_path = path:lower()
  if lower_path ~= "skill.md" and lower_path:match("/skill%.md$") == nil then
    return target
  end
  if path:match("^/") or path:match("^[%a][%w+.-]*:") then
    return target
  end

  local source_file = os.getenv("SOURCE_FILE")
  if source_file == nil or source_file == "" then
    return target
  end

  local resolved_path = normalize_path(dirname(source_file) .. "/" .. path)
  if not file_exists(resolved_path) then
    return target
  end
  if same_dir_has(resolved_path, "index.md") or same_dir_has(resolved_path, "readme.md") then
    return target
  end

  return path:gsub("([^/]+)$", "index.md") .. suffix
end

function Link(el)
  -- README.md を index.md に置換 (ケース非依存、パス内またはファイル名単体)
  el.target = string.gsub(el.target, "/[Rr][Ee][Aa][Dd][Mm][Ee]%.md", "/index.md")
  el.target = string.gsub(el.target, "^[Rr][Ee][Aa][Dd][Mm][Ee]%.md", "index.md")
  el.target = rewrite_skill_index(el.target)
  el.target = string.gsub(el.target, "%.md", ".docx")
  el.target = string.gsub(el.target, "%.Rmd", ".docx")
  el.target = string.gsub(el.target, "%.Tmd", ".docx")
  el.target = string.gsub(el.target, "%.rst", ".docx")
  el.target = string.gsub(el.target, "%.yaml", ".docx")
  el.target = string.gsub(el.target, "%.json", ".docx")
  return el
end
