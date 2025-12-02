-- links-to-html.lua

-- リンクがURLスキームを持つかチェック
local function hasScheme(url)
  return url:match("^%w+://") ~= nil or url:match("^mailto:") ~= nil
end

-- ファイルが存在するかチェック
local function fileExists(path)
  local file = io.open(path, "r")
  if file then
    file:close()
    return true
  end
  return false
end

-- 現在のファイルのディレクトリを取得
local function getCurrentDir()
  if PANDOC_STATE.input_files and #PANDOC_STATE.input_files > 0 then
    local input_file = PANDOC_STATE.input_files[1]
    return input_file:match("(.*/)")
  end
  return nil
end

function Link(el)
  local target = el.target

  -- URLスキームを持つ場合やアンカーの場合は、そのまま処理
  if hasScheme(target) or target:match("^#") then
    -- 通常のリンク処理を続ける
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

  -- ローカルファイルへのリンクの場合、ファイルの存在を確認
  local current_dir = getCurrentDir()
  if current_dir then
    local file_path = current_dir .. target
    -- アンカー部分を削除
    file_path = file_path:gsub("#.*$", "")

    if not fileExists(file_path) then
      -- ファイルが存在しない場合、プレーンテキストに変換
      if #el.content > 0 then
        return el.content
      else
        return pandoc.Str(target)
      end
    end
  end

  -- ファイルが存在する場合、通常のリンク処理を続ける
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
