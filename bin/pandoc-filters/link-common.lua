-- link-common.lua
-- HTML と docx のリンク フィルターで共有するリンク解決処理。

local M = {}

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

local function basename(path)
  return path:match("([^/]+)$") or path
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

local function split_path(path)
  local parts = {}
  for part in normalize_path(path):gmatch("[^/]+") do
    table.insert(parts, part)
  end
  return parts
end

local function make_relative(path, base_dir)
  local target_parts = split_path(path)
  local base_parts = split_path(base_dir)
  local common = 0
  while target_parts[common + 1] ~= nil and target_parts[common + 1] == base_parts[common + 1] do
    common = common + 1
  end

  local relative_parts = {}
  for _ = common + 1, #base_parts do
    table.insert(relative_parts, "..")
  end
  for i = common + 1, #target_parts do
    table.insert(relative_parts, target_parts[i])
  end
  if #relative_parts == 0 then
    return "."
  end
  return table.concat(relative_parts, "/")
end

local function starts_with_path(path, prefix)
  return path == prefix or path:sub(1, #prefix + 1) == prefix .. "/"
end

local function parse_subfolder_entries()
  local entries = {}
  local raw = os.getenv("SUBFOLDER_DOCS_PATHS") or ""
  for line in raw:gmatch("[^\r\n]+") do
    local alias, _, root = line:match("^([^|]+)|([^|]+)|(.+)$")
    if alias ~= nil and root ~= nil then
      table.insert(entries, { alias = alias, root = normalize_path(root) })
    end
  end
  return entries
end

local main_mdroot = normalize_path(os.getenv("PUB_MARKDOWN_MAIN_MDROOT") or "")
local subfolder_entries = parse_subfolder_entries()

local function real_to_virtual_path(real_path)
  real_path = normalize_path(real_path)
  if main_mdroot == "" then
    return nil
  end
  for _, entry in ipairs(subfolder_entries) do
    if starts_with_path(real_path, entry.root) then
      local relative = real_path:sub(#entry.root + 1):gsub("^/", "")
      if relative == "" then
        return main_mdroot .. "/" .. entry.alias
      end
      return main_mdroot .. "/" .. entry.alias .. "/" .. relative
    end
  end
  if starts_with_path(real_path, main_mdroot) then
    return real_path
  end
  return nil
end

local function virtual_to_real_path(virtual_path)
  virtual_path = normalize_path(virtual_path)
  if main_mdroot == "" or not starts_with_path(virtual_path, main_mdroot) then
    return virtual_path
  end

  local relative = virtual_path:sub(#main_mdroot + 1):gsub("^/", "")
  for _, entry in ipairs(subfolder_entries) do
    if relative == entry.alias then
      return entry.root
    end
    if starts_with_path(relative, entry.alias) then
      local subfolder_relative = relative:sub(#entry.alias + 1):gsub("^/", "")
      return entry.root .. "/" .. subfolder_relative
    end
  end

  return virtual_path
end

local function find_same_dir_file(path, filename)
  local dir = dirname(path)
  local ok, entries = pcall(pandoc.system.list_directory, dir)
  if not ok then
    return nil
  end
  for _, candidate in ipairs(entries) do
    if candidate:lower() == filename then
      return dir .. "/" .. candidate
    end
  end
  return nil
end

local function resolve_document_file(path)
  if file_exists(path) then
    return path
  end
  -- TOC は README.md / SKILL.md の発行先を index.md として参照する。
  if basename(path):lower() == "index.md" then
    return find_same_dir_file(path, "index.md")
      or find_same_dir_file(path, "readme.md")
      or find_same_dir_file(path, "skill.md")
  end
  return nil
end

local function is_relative_local_path(path)
  return path ~= ""
    and path:sub(1, 1) ~= "/"
    and path:match("^[%a][%w+.-]*:") == nil
end

local function is_published_document(path)
  local lower_path = path:lower()
  return lower_path:match("%.md$") ~= nil
    or lower_path:match("%.yaml$") ~= nil
    or lower_path:match("%.json$") ~= nil
end

local function rewrite_document_path(target)
  local path, suffix = split_suffix(target)
  if not is_relative_local_path(path) or not is_published_document(path) then
    return target, false
  end

  local source_file = os.getenv("SOURCE_FILE")
  if source_file == nil or source_file == "" then
    return target, false
  end

  local source_virtual = real_to_virtual_path(source_file)
  if source_virtual == nil then
    return target, false
  end

  local real_target = resolve_document_file(normalize_path(dirname(source_file) .. "/" .. path))
  if real_target == nil then
    local virtual_target = normalize_path(dirname(source_virtual) .. "/" .. path)
    real_target = resolve_document_file(virtual_to_real_path(virtual_target))
    if real_target == nil then
      return target, false
    end
  end

  local target_virtual = real_to_virtual_path(real_target)
  if target_virtual == nil then
    return target, false
  end

  local target_name = basename(real_target):lower()
  if target_name == "readme.md" and not find_same_dir_file(real_target, "index.md") then
    target_virtual = dirname(target_virtual) .. "/index.md"
  elseif target_name == "skill.md"
    and not find_same_dir_file(real_target, "index.md")
    and not find_same_dir_file(real_target, "readme.md") then
    target_virtual = dirname(target_virtual) .. "/index.md"
  end

  return make_relative(target_virtual, dirname(source_virtual)) .. suffix, true
end

local function is_doxygen_relative_path(path)
  local rest = path
  while rest:sub(1, 3) == "../" do
    rest = rest:sub(4)
  end
  return rest:sub(1, 8) == "doxygen/"
end

local function unresolved_link(el)
  local inlines = {}
  for _, inline in ipairs(el.content) do
    table.insert(inlines, inline)
  end
  table.insert(inlines, pandoc.Space())
  table.insert(inlines, pandoc.Code(el.target))
  return inlines
end

function M.rewrite_link(el, extension)
  if el.target:match("^[%a][%w+.-]*:") ~= nil then
    return el
  end

  local path, _ = split_suffix(el.target)
  local rewritten, resolved = rewrite_document_path(el.target)
  if not resolved and is_relative_local_path(path) and not is_doxygen_relative_path(path) then
    return unresolved_link(el)
  end

  local rewritten_path, suffix = split_suffix(rewritten)
  el.target = string.gsub(rewritten_path, "%.[mM][dD]$", extension)
  el.target = string.gsub(el.target, "%.Rmd", extension)
  el.target = string.gsub(el.target, "%.Tmd", extension)
  el.target = string.gsub(el.target, "%.rst", extension)
  el.target = string.gsub(el.target, "%.yaml", extension)
  el.target = string.gsub(el.target, "%.json", extension)
  el.target = el.target .. suffix
  return el
end

return M
