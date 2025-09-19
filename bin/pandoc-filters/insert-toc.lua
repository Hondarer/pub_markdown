-- Pandoc Markdown インデックス挿入 Lua フィルタ
-- \toc コマンドを指定された階層以下の Markdown ファイルから自動生成したインデックスに置換

local paths = require 'pandoc.path'

-- OS 判定関数
local function is_windows()
    local os_name = os.getenv("OS")
    return os_name and string.match(os_name:lower(), "windows")
end

-- コードページ変換のスキップ判定
local function needs_conversion(text)
  -- 空や ASCII のみならそのまま返す
  return text and text ~= "" and text:match("[\128-\255]") ~= nil
end

-- UTF-8 -> 現在のアクティブコードページ (Windows)
local function utf8_to_active_cp(text)
    if (not is_windows()) or (not needs_conversion(text)) then
        return text
    end
    local ps = table.concat({
        "$ErrorActionPreference='Stop'",
        "[Console]::InputEncoding  = [System.Text.Encoding]::UTF8",
        "[Console]::OutputEncoding = [System.Text.Encoding]::Default",
        "$in = [Console]::In.ReadToEnd()",
        "[Console]::Out.Write($in)",
        "[Console]::InputEncoding  = [System.Text.Encoding]::Default",
        "[Console]::OutputEncoding = [System.Text.Encoding]::Default"
    }, "; ")
    local ok, out = pcall(pandoc.pipe, "powershell", {
        "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-Command", ps
    }, text)
    if ok and out and out ~= "" then
        -- 末尾の改行を削る
        return (out:gsub("[\r\n]+$", ""))
    end
    return text
end

-- 現在のアクティブコードページ -> UTF-8 (Windows)
local function active_cp_to_utf8(text)
    if (not is_windows()) or (not needs_conversion(text)) then
        return text
    end
    local ps = table.concat({
        "$ErrorActionPreference='Stop'",
        "[Console]::InputEncoding  = [System.Text.Encoding]::Default",
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8",
        "$in = [Console]::In.ReadToEnd()",
        "[Console]::Out.Write($in)",
        "[Console]::InputEncoding  = [System.Text.Encoding]::Default",
        "[Console]::OutputEncoding = [System.Text.Encoding]::Default"
    }, "; ")
    local ok, out = pcall(pandoc.pipe, "powershell", {
        "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-Command", ps
    }, text)
    if ok and out and out ~= "" then
        -- 末尾の改行を削る
        return (out:gsub("[\r\n]+$", ""))
    end
    return text
end

-- デバッグ出力関数
local function debug_print(...)
    local debug_msg = "[insert-toc DEBUG] "
    for i, v in ipairs({...}) do
        if i > 1 then debug_msg = debug_msg .. " " end
        debug_msg = debug_msg .. tostring(v)
    end
    -- ここまで UTF-8 ベースで処理しているので、出力直前で Windows ならコードページ変換する
    debug_msg = utf8_to_active_cp(debug_msg) .. "\n"
    
    io.stderr:write(debug_msg)
    io.stderr:flush()
end

-- デフォルト設定
local defaults = {
    depth = 0,        -- 現在のディレクトリのみ
    sort = "name",    -- ファイル名順
    format = "ul",    -- 番号なしリスト
    exclude = {}      -- 除外なし
}

-- パス操作ユーティリティ
local function normalize_path(path)
    -- Windows と Unix 両対応
    return path:gsub("\\", "/")
end

local function split_path(path)
    local parts = {}
    for part in normalize_path(path):gmatch("[^/]+") do
        table.insert(parts, part)
    end
    return parts
end

local function get_directory_name(path)
    local parts = split_path(path)
    return parts[#parts] or path
end

local function path_join(...)
    local parts = {...}
    return table.concat(parts, "/"):gsub("/+", "/")
end

-- base_path から target_path への相対パスを計算
local function get_relative_path(base_path, target_path)
    local base_normalized = normalize_path(base_path)
    local target_normalized = normalize_path(target_path)
    
    -- base_path が "." の場合、"./" プレフィックスを除去
    if base_normalized == "." then
        if target_normalized:sub(1, 2) == "./" then
            return target_normalized:sub(3)
        end
        return target_normalized
    end
    
    -- target_path が base_path から始まる場合
    local base_prefix = base_normalized .. "/"
    if target_normalized:sub(1, #base_prefix) == base_prefix then
        return target_normalized:sub(#base_prefix + 1)
    end
    
    -- "./" プレフィックスを除去
    if target_normalized:sub(1, 2) == "./" then
        target_normalized = target_normalized:sub(3)
    end
    
    return target_normalized
end

local function is_markdown_file(filename)
    local ext = filename:match("%.([^.]+)$")
    return ext and (ext:lower() == "md" or ext:lower() == "markdown")
end

-- ディレクトリ内のファイルとフォルダを取得 (OS コマンド経由)
-- dir_path は UTF-8
local function get_files_in_directory(dir_path)
    --debug_print("get_files_in_directory:", dir_path)
    local files = {}
    
    -- 正規化されたパス
    local normalized_dir = normalize_path(dir_path)
    --debug_print("Normalized dir:", normalized_dir)
    --debug_print("Is Windows:", is_windows())
    
    -- Markdown ファイルを取得
    local md_command
    if is_windows() then
        local cmd_dir = utf8_to_active_cp(normalized_dir:gsub("/", "\\"))
        md_command = string.format('dir /b "%s\\*.md" "%s\\*.markdown" 2>nul', cmd_dir, cmd_dir)
        --debug_print("MD command:", active_cp_to_utf8(md_command))
    else
        md_command = string.format('find "%s" -maxdepth 1 -name "*.md" -o -name "*.markdown" 2>/dev/null', normalized_dir)
        --debug_print("MD command:", md_command)
    end
    
    local handle = io.popen(md_command)
    if handle then
        --debug_print("Executing MD command...")
        for filename in handle:lines() do

            -- Windows 環境では得られる文字列を UTF-8 に
            filename = active_cp_to_utf8(filename)
            --debug_print("Found MD file:", filename)

            -- ファイル名のみを抽出
            local name = filename:match("[^/\\]+$") or filename
            --debug_print("name:", name)

            if is_markdown_file(name) then
                local file_entry = {
                    name = name,
                    path = path_join(dir_path, name)
                }
                --debug_print("Added file:", file_entry.name, "->", file_entry.path)
                table.insert(files, file_entry)
            end
        end
        handle:close()
    else
        --debug_print("Failed to open MD command handle")
    end
    
    -- ディレクトリを取得
    local dir_command
    if is_windows() then
        local cmd_dir = utf8_to_active_cp(normalized_dir:gsub("/", "\\"))
        dir_command = string.format('dir /b /ad "%s" 2>nul', cmd_dir)
        --debug_print("Dir command:", active_cp_to_utf8(dir_command))
    else
        dir_command = string.format('find "%s" -maxdepth 1 -type d ! -name "." 2>/dev/null', normalized_dir)
        --debug_print("Dir command:", dir_command)
    end
    
    local handle = io.popen(dir_command)
    if handle then
        --debug_print("Executing Dir command...")
        for dirname in handle:lines() do

            -- Windows 環境では得られる文字列を UTF-8 に
            dirname = active_cp_to_utf8(dirname)
            --debug_print("Found directory:", dirname)

            -- ディレクトリ名のみを抽出
            local name = dirname:match("[^/\\]+$") or dirname

            if name ~= "." and name ~= ".." then
                local dir_entry = {
                    name = name,
                    path = path_join(dir_path, name),
                    is_directory = true
                }
                --debug_print("Added directory:", dir_entry.name, "->", dir_entry.path)
                table.insert(files, dir_entry)
            end
        end
        handle:close()
    else
        --debug_print("Failed to open Dir command handle")
    end
    
    --debug_print("Total entries found:", #files)
    return files
end

-- ファイル内容からタイトルを抽出
local function extract_title_from_file(file_path)
    -- Windows 環境ではファイルパスを現在のコードページに変換
    local file = io.open(utf8_to_active_cp(file_path), "r")
    if not file then return nil end
    
    local in_frontmatter = false
    local frontmatter_count = 0
    
    for line in file:lines() do
        line = line:gsub("^%s+", ""):gsub("%s+$", "")  -- trim
        
        -- YAML フロントマターの処理
        if line:match("^%-%-%-") then
            frontmatter_count = frontmatter_count + 1
            if frontmatter_count == 1 then
                in_frontmatter = true
            elseif frontmatter_count == 2 then
                in_frontmatter = false
            end
        elseif not in_frontmatter and not line:match("^$") then
            local title = line:match("^#%s+(.+)")
            if title then
                file:close()
                --debug_print("extract_title_from_file:", title)
                return title
            elseif not line:match("^#") then
                -- # でない行が見つかったら検索終了
                break
            end
        end
    end
    
    file:close()
    return nil
end

-- 大文字小文字を無視したファイル検索
local function find_case_insensitive_file(dir_path, target_filename)
    --debug_print("find_case_insensitive_file:", dir_path)
    local files = get_files_in_directory(dir_path)
    for _, file in ipairs(files) do
        --debug_print("file:", file.path)
        if not file.is_directory and file.name:lower() == target_filename:lower() then
            return file.path
        end
    end
    return nil
end

-- フォルダの表示情報を取得
local function get_folder_display_info(folder_path)
    local index_files = {"index.md", "index.markdown"}
    
    for _, filename in ipairs(index_files) do
        local index_path = find_case_insensitive_file(folder_path, filename)
        if index_path then
            local title = extract_title_from_file(index_path)
            return {
                display_name = title or get_directory_name(folder_path),
                link_target = index_path,
                has_link = true
            }
        end
    end
    
    return {
        display_name = get_directory_name(folder_path),
        link_target = nil,
        has_link = false
    }
end

-- 除外パターンマッチング
local function glob_to_pattern(glob)
    -- Lua パターンで特別な意味を持つ文字をエスケープ
    local pattern = globTotal
    pattern = pattern:gsub("%-", "%%-")  -- ハイフンをエスケープ
    pattern = pattern:gsub("%.", "%%.")  -- ドットをエスケープ
    pattern = pattern:gsub("%+", "%%+")  -- プラスをエスケープ
    pattern = pattern:gsub("%^", "%%^")  -- ハットをエスケープ
    pattern = pattern:gsub("%$", "%%$")  -- ドルをエスケープ
    pattern = pattern:gsub("%(", "%%(")  -- 左括弧をエスケープ
    pattern = pattern:gsub("%)", "%%)")  -- 右括弧をエスケープ
    pattern = pattern:gsub("%[", "%%[")  -- 左角括弧をエスケープ
    pattern = pattern:gsub("%]", "%%]")  -- 右角括弧をエスケープ
    -- glob パターンを Lua パターンに変換
    pattern = pattern:gsub("%*", ".*"):gsub("%?", ".")
    return pattern
end

local function matches_exclude_pattern(file_path, exclude_patterns)
    local normalized_path = normalize_path(file_path)
    
    for _, pattern in ipairs(exclude_patterns) do
        local lua_pattern = glob_to_pattern(pattern)
        if normalized_path:match(lua_pattern) or normalized_path:match("/" .. lua_pattern .. "$") then
            return true
        end
        
        -- ファイル名のみでもマッチを試す
        local filename = file_path:match("[^/\\]+$")
        if filename and filename:match(lua_pattern) then
            return true
        end
    end
    
    return false
end

-- ファイル収集
local function collect_markdown_files(base_path, max_depth, exclude_patterns)
    --debug_print("collect_markdown_files called - base_path:", base_path, "max_depth:", max_depth)
    local all_files = {}
    local all_folders = {}
    
    -- dir_path は UTF-8
    local function scan_directory(dir_path, current_depth)

        io.stderr:write(".")
        io.stderr:flush()

        --debug_print("scan_directory:", dir_path, "depth:", current_depth, "max_depth:", max_depth)
        if max_depth ~= -1 and current_depth > max_depth then
            --debug_print("Skipping directory - depth exceeded:", current_depth, ">", max_depth)
            return
        end
        
        local files = get_files_in_directory(dir_path)
        --debug_print("scan_directory got", #files, "entries from get_files_in_directory")
        
        for _, file in ipairs(files) do
            --debug_print("Processing entry:", file.name, "is_directory:", file.is_directory or false, "path:", file.path)
            if file.is_directory then
                local excluded = matches_exclude_pattern(file.path, exclude_patterns)
                --debug_print("Directory", file.name, "excluded:", excluded)
                if not excluded then
                    -- ディレクトリが表示対象の深度内にある場合のみ追加
                    if max_depth == -1 or current_depth < max_depth then
                        --debug_print("Adding folder:", file.path, "at depth:", current_depth)
                        table.insert(all_folders, {
                            path = file.path,
                            depth = current_depth
                        })
                    end
                    -- 子ディレクトリを再帰的にスキャン（深度チェックは関数開始時に行われる）
                    scan_directory(file.path, current_depth + 1)
                else
                    --debug_print("Excluding folder:", file.path)
                end
            else
                local excluded = matches_exclude_pattern(file.path, exclude_patterns)
                --debug_print("File", file.name, "excluded:", excluded)
                if not excluded then
                    local title = extract_title_from_file(file.path)
                    if title == nil then
                        title = file.name:gsub("%.md$", ""):gsub("%.markdown$", "")
                        --title = active_cp_to_utf8(file.name)
                    end
                    --debug_print("Adding file:", file.path, "title:", title, "at depth:", current_depth)
                    table.insert(all_files, {
                        path = file.path,
                        name = file.name,
                        title = title,
                        depth = current_depth
                    })
                else
                    --debug_print("Excluding file:", file.path)
                end
            end
        end
    end
    
    scan_directory(base_path, 0)
    
    --debug_print("collect_markdown_files returning:", #all_files, "files,", #all_folders, "folders")
    return all_files, all_folders
end

-- ソート機能
local function sort_files(files, sort_method)
    if sort_method == "title" then
        table.sort(files, function(a, b)
            return a.title:lower() < b.title:lower()
        end)
    else -- "name"
        table.sort(files, function(a, b)
            return a.name:lower() < b.name:lower()
        end)
    end
end

-- フォルダのタイトルファイルかどうかをチェック
local function is_folder_title_file(file_path)
    local dir_path = file_path:match("(.+)/[^/]+$")
    if not dir_path then
        return false
    end
    
    local filename = file_path:match("[^/]+$")
    if not filename then
        return false
    end
    
    -- index.md または index.markdown かチェック
    local is_index_file = (filename:lower() == "index.md" or filename:lower() == "index.markdown")
    if not is_index_file then
        return false
    end
    
    -- そのフォルダの情報を取得してリンクターゲットと一致するかチェック
    local folder_info = get_folder_display_info(dir_path)
    return folder_info.has_link and normalize_path(folder_info.link_target) == normalize_path(file_path)
end

-- Markdown ファイルが含まれているかチェック（フォルダタイトルファイル除外後の状態で）
local function has_markdown_files_recursive(node)
    -- 現在のノードにMarkdownファイルがあるかチェック（フォルダタイトルファイル以外）
    if node.entry and not node.entry.is_directory then
        -- このファイルがフォルダのタイトルファイルでない場合はカウント
        if not is_folder_title_file(node.entry.path) then
            return true
        end
    end
    
    -- 子ノードを再帰的にチェック
    for _, child_node in pairs(node.children) do
        if has_markdown_files_recursive(child_node) then
            return true
        end
    end
    
    return false
end

-- 階層ツリー構造の構築
local function build_tree_structure(files, folders, base_path)
    local tree = {}
    
    -- パスを基にツリー構造を構築
    local function add_to_tree(path, entry)
        local normalized_path = normalize_path(path)
        local base_normalized = normalize_path(base_path)
        
        -- ベースパスからの相対パスを取得
        local relative_path = normalized_path:gsub("^" .. base_normalized .. "/", "")
        if relative_path == normalized_path then
            relative_path = normalized_path:gsub("^" .. base_normalized .. "$", "")
        end
        
        if relative_path == "" or relative_path == "." then
            -- ベースディレクトリのエントリはスキップ
            return
        end
        
        local parts = split_path(relative_path)
        local current_node = tree
        
        -- パスの各部分を辿ってツリー構造に追加
        for i, part in ipairs(parts) do
            if not current_node[part] then
                current_node[part] = {
                    children = {},
                    entry = nil,
                    is_folder = false
                }
            end
            
            if i == #parts then
                -- 最終パート（実際のエントリ）
                current_node[part].entry = entry
                current_node[part].is_folder = entry.is_directory or false
            end
            
            current_node = current_node[part].children
        end
    end
    
    -- フォルダを追加
    for _, folder in ipairs(folders) do
        local entry = {
            path = folder.path,
            depth = folder.depth,
            is_directory = true
        }
        add_to_tree(folder.path, entry)
    end
    
    -- ファイルを追加（フォルダのタイトルファイルは除外）
    for _, file in ipairs(files) do
        if not is_folder_title_file(file.path) then
            add_to_tree(file.path, file)
        else
            --debug_print("Skipping folder title file:", file.path)
        end
    end
    
    -- Markdownファイルを含まないフォルダを削除（タイトルファイル除外後の判定）
    local function prune_empty_folders(node_tree)
        local to_remove = {}
        
        for name, node in pairs(node_tree) do
            -- 子ノードを先に処理
            prune_empty_folders(node.children)
            
            -- フォルダで実質的なMarkdownファイルが含まれていない場合は削除対象
            -- ただし、フォルダタイトルファイルしか含まれない場合は、そのフォルダは表示する
            if node.entry and node.entry.is_directory then
                local has_title_file = false
                local has_other_files = has_markdown_files_recursive(node)
                
                -- このフォルダにタイトルファイルがあるかチェック
                local folder_info = get_folder_display_info(node.entry.path)
                has_title_file = folder_info.has_link
                
                -- タイトルファイルも他のファイルも含まれていない場合のみ削除
                if not has_title_file and not has_other_files then
                    table.insert(to_remove, name)
                end
            end
        end
        
        -- 削除対象のノードを削除
        for _, name in ipairs(to_remove) do
            node_tree[name] = nil
        end
    end
    
    prune_empty_folders(tree)
    
    return tree
end

-- インデックス生成
local function generate_index_list(files, folders, base_path, format_type)
    local lines = {}
    local tree = build_tree_structure(files, folders, base_path)
    
    -- ツリーを再帰的に処理してリストを生成
    local function process_node(node, name, depth, parent_path)

        io.stderr:write(".")
        io.stderr:flush()

        local indent = string.rep("  ", depth)
        local list_marker = format_type == "ol" and "1. " or "- "
        
        if node.entry then
            local line = indent .. list_marker
            
            if node.entry.is_directory then
                -- フォルダエントリの処理
                local folder_info = get_folder_display_info(node.entry.path)
                if folder_info.has_link then
                    local relative_path = get_relative_path(base_path, folder_info.link_target)
                    line = line .. "[" .. folder_info.display_name .. "](" .. relative_path .. ")"
                else
                    line = line .. folder_info.display_name
                end
            else
                -- ファイルエントリの処理
                local relative_path = get_relative_path(base_path, node.entry.path)
                line = line .. "[" .. node.entry.title .. "](" .. relative_path .. ")"
            end
            
            table.insert(lines, line)
        end
        
        -- 子ノードを処理（アルファベット順）
        local sorted_children = {}
        for child_name, child_node in pairs(node.children) do
            table.insert(sorted_children, {name = child_name, node = child_node})
        end
        
        table.sort(sorted_children, function(a, b)
            return a.name:lower() < b.name:lower()
        end)
        
        for _, child in ipairs(sorted_children) do
            local child_path = parent_path and (parent_path .. "/" .. child.name) or child.name
            process_node(child.node, child.name, depth + (node.entry and 1 or 0), child_path)
        end
    end
    
    -- ルートレベルから処理開始
    local sorted_root = {}
    for name, node in pairs(tree) do
        table.insert(sorted_root, {name = name, node = node})
    end
    
    table.sort(sorted_root, function(a, b)
        return a.name:lower() < b.name:lower()
    end)
    
    for _, root in ipairs(sorted_root) do
        process_node(root.node, root.name, 0, root.name)
    end
    
    return lines
end

-- パラメータパース
local function unquote(str)
    return str:gsub('^"([^"]*)"$', "%1"):gsub("^'([^']*)'$", "%1")
end

local function parse_toc_params(params_str)
    --debug_print("Parsing params:", params_str)
    local params = {exclude = {}}
    
    -- key=value パターンのパース
    for key, value in params_str:gmatch('(%w+)=([^%s]+)') do
        --debug_print("Found param:", key, "=", value)
        if key == "exclude" then
            -- exclude パラメータは配列に追加
            if type(params.exclude) ~= "table" then
                params.exclude = {}
            end
            table.insert(params.exclude, unquote(value))
        else
            params[key] = unquote(value)
        end
    end
    
    -- デフォルト値とマージ
    local result = {}
    for k, v in pairs(defaults) do
        if k == "exclude" then
            -- exclude は特別処理（配列をコピー）
            result[k] = {}
            if type(v) == "table" then
                for _, item in ipairs(v) do
                    table.insert(result[k], item)
                end
            end
        else
            result[k] = params[k] or v
        end
    end
    
    -- exclude パラメータを追加
    if params.exclude and type(params.exclude) == "table" then
        for _, item in ipairs(params.exclude) do
            table.insert(result.exclude, item)
        end
    end
    
    -- depth の正規化
    if params.depth then
        local depth = tonumber(params.depth)
        if depth and depth >= -1 then
            result.depth = depth
        end
    end
    
    --debug_print("Final params - depth:", result.depth, "sort:", result.sort, "format:", result.format)
    --debug_print("Final exclude count:", #result.exclude)
    --for i, ex in ipairs(result.exclude) do
    --    debug_print("Final exclude", i .. ":", ex)
    --end
    
    return result
end

-- メイン処理
local function process_toc_command(params_str, current_file)
    --debug_print("=== process_toc_command START ===")
    --debug_print("Raw params:", params_str or "(empty)")
    --debug_print("Current file:", current_file or "(none)")

    local params = parse_toc_params(params_str or "")
    --debug_print("Parsed depth:", params.depth)
    --debug_print("Parsed sort:", params.sort)
    --debug_print("Parsed format:", params.format)
    --debug_print("Parsed exclude count:", #params.exclude)
    
    -- 基準ディレクトリを取得
    local base_path = "."
    if current_file and current_file ~= "" and current_file ~= "-" then
        base_path = current_file:match("(.+)/[^/]+$") or "."
        --debug_print("Base path from current_file:", base_path)
    else
        --debug_print("Base path defaulted to current directory:", base_path)
    end
    --debug_print("Final base path:", base_path)
    
    -- 自身を除外リストに追加
    --if current_file and current_file ~= "-" and current_file ~= "-" and current_file:match("%.m[da][r]*[k]*[d]*o*w*n*$") then
    --    local current_filename = current_file:match("[^/\\]+$")
    --    --debug_print("Excluding current file:", current_filename)
    --    table.insert(params.exclude, current_filename)
    --end
    
    --debug_print("Final exclude count:", #params.exclude)
    for i, pattern in ipairs(params.exclude) do
        --debug_print("Exclude", i .. ":", pattern)
    end
    
    io.stderr:write("    > process_toc (This may take several minutes.) collect")
    io.stderr:flush()

    local files, folders = collect_markdown_files(base_path, params.depth, params.exclude)
    --debug_print("Found", #files, "files and", #folders, "folders")

    io.stderr:write(" -> sort")
    io.stderr:flush()
    
    sort_files(files, params.sort)

    for _, folder in ipairs(folders) do
        table.sort(folder, function(a, b)
            return a.path < b.path
        end)
    end
    
    io.stderr:write(" -> generate")
    io.stderr:flush()

    local index_lines = generate_index_list(files, folders, base_path, params.format)
    --debug_print("Generated", #index_lines, "index lines")
    --debug_print("=== process_toc_command END ===")

    io.stderr:write(" -> done.\n")
    io.stderr:flush()

    return index_lines
end

-- Pandoc フィルタのメイン関数

-- Para 要素内の \toc 処理（オプション付きの場合）
function Para(elem)
    --debug_print("Para function called with", #elem.content, "elements")
    
    -- Para の最初の要素が RawInline で \toc から始まるかチェック
    if #elem.content > 0 and elem.content[1].t == "RawInline" then
        local raw_inline = elem.content[1]
        --debug_print("RawInline found, format:", raw_inline.format, "text:", raw_inline.text)
        
        if raw_inline.format == "tex" and raw_inline.text:match("^\\toc") then
            --debug_print("Found \\toc in RawInline")
            
            -- RawInline には "\\toc " が含まれ、パラメータは後続の Str 要素に含まれる
            local params_parts = {}
            for i = 2, #elem.content do
                local element = elem.content[i]
                --debug_print("Processing element", i, ":", element.t)
                
                if element.t == "Str" then
                    -- Pandoc 3.x API では .text を使用
                    local str_content = element.text or element.c
                    if str_content then
                        table.insert(params_parts, str_content)
                    end
                elseif element.t == "Space" then
                    table.insert(params_parts, " ")
                end
            end
            
            local params_str = table.concat(params_parts, ""):gsub("^%s+", ""):gsub("%s+$", "")
            --debug_print("Para params:", params_str or "(empty)")
            
            local current_file = os.getenv("SOURCE_FILE")
            local index_lines = process_toc_command(params_str, current_file)
            
            if #index_lines > 0 then
                --debug_print("Returning BulletList from Para with", #index_lines, "lines")
                -- Markdown 文字列を Pandoc AST に変換
                local markdown_content = table.concat(index_lines, "\n")
                --debug_print("Generated markdown content:", utf8_to_active_cp(markdown_content))

                --local f = io.open("insert-toc.log", "w")
                --if f then
                --    f:write(markdown_content)
                --    f:close()
                --end

                -- pandoc.read を使って Markdown を AST に変換
                local doc = pandoc.read(markdown_content, "markdown")
                if doc and doc.blocks and #doc.blocks > 0 then
                    --debug_print("Successfully parsed markdown to AST")
                    return doc.blocks[1]  -- 最初のブロック（リスト）を返す
                else
                    debug_print("Failed to parse markdown")
                end
            else
                --debug_print("Returning empty Para from Para")
                return pandoc.Para({})
            end
        end
    end
    
    return elem
end

-- RawBlock での \toc 処理
-- Pandoc の Markdown パーサは、入力中の \toc のような バックスラッシュ始まりの制御シーケンス を、
-- LaTeX のコマンドとして解釈します。そのため AST では RawBlock として
-- {"t":"RawBlock","c":["tex","\\toc"]}
-- が生成されます。
function RawBlock(elem)
    --debug_print("RawBlock function called, format:", elem.format, "text:", elem.text)
    if elem.text:match("^\\toc") then
        --debug_print("Found \\toc in RawBlock:", elem.text)
        local params_str = elem.text:match("^\\toc%s*(.*)$")
        if params_str then
            --debug_print("RawBlock params:", params_str or "(empty)")
            local current_file = os.getenv("SOURCE_FILE")
            local index_lines = process_toc_command(params_str, current_file)
            
            if #index_lines > 0 then
                --debug_print("Returning BulletList from RawBlock with", #index_lines, "lines")
                -- Markdown 文字列を Pandoc AST に変換
                local markdown_content = table.concat(index_lines, "\n")
                --debug_print("Generated markdown content:", utf8_to_active_cp(markdown_content))

                --local f = io.open("insert-toc.log", "w")
                --if f then
                --    f:write(markdown_content)
                --    f:close()
                --end

                -- pandoc.read を使って Markdown を AST に変換
                local doc = pandoc.read(markdown_content, "markdown")
                if doc and doc.blocks and #doc.blocks > 0 then
                    --debug_print("Successfully parsed markdown to AST")
                    return doc.blocks[1]  -- 最初のブロック（リスト）を返す
                else
                    --debug_print("Failed to parse markdown, falling back to manual construction")
                    -- フォールバック: 手動でリスト項目を構築
                    local list_items = {}
                    for _, line in ipairs(index_lines) do
                        local content_text = line:gsub("^%s*[-*]%s*", ""):gsub("^%s*%d+%.%s*", "")
                        -- リンクパターンを解析
                        local link_text, link_url = content_text:match("%[(.-)%]%((.-)%)")
                        if link_text and link_url then
                            table.insert(list_items, {pandoc.Plain({pandoc.Link(link_text, link_url)})})
                        else
                            table.insert(list_items, {pandoc.Plain({pandoc.Str(content_text)})})
                        end
                    end
                    return pandoc.BulletList(list_items)
                end
            else
                --debug_print("Returning empty Para from RawBlock")
                return pandoc.Para({})
            end
        end
    end
    
    return elem
end
