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
    depth = 0,                  -- 現在のディレクトリのみ
    exclude = {},               -- 除外なし
    basedir = "",               -- 起点ディレクトリ指定なし（現在のディレクトリ）
    ["exclude-basedir"] = false -- 基準ディレクトリを除外しない
}

-- パラメータパース
-- クォート除去関数
-- 注意: スマートクォート（" "）にも対応しています。
-- 一部のエディタは自動的に通常のダブルクォート " を スマートクォートに変換するため、
-- この対応が必要です。トラブルシューティング時は、以下のデバッグ行のコメントを外してください。
local function unquote(str)
    --debug_print("unquote input:", str, "length:", #str)

    -- 通常のクォート（ASCII）
    if (str:sub(1, 1) == '"' and str:sub(-1) == '"') or
       (str:sub(1, 1) == "'" and str:sub(-1) == "'") then
        local result = str:sub(2, -2)
        --debug_print("unquote result (ASCII quote):", result)
        return result
    end

    -- スマートクォート（UTF-8バイト列）
    -- " (U+201C) = E2 80 9C (左ダブルクォーテーションマーク)
    -- " (U+201D) = E2 80 9D (右ダブルクォーテーションマーク)
    if #str >= 6 then
        local first3 = str:sub(1, 3)
        local last3 = str:sub(-3)
        if first3 == "\xE2\x80\x9C" and last3 == "\xE2\x80\x9D" then
            local result = str:sub(4, -4)
            --debug_print("unquote result (smart quote):", result)
            return result
        end
    end

    --debug_print("unquote result (not quoted):", str)
    return str
end

local function parse_toc_params(params_str)
    --debug_print("Parsing params:", params_str)
    local params = {exclude = {}}

    -- key=value パターンのパース（ハイフンも許可）
    for key, value in params_str:gmatch('([%w-_]+)=([^%s]+)') do
        --debug_print("Found param:", key, "=", value)
        if key == "exclude" then
            -- exclude パラメータは配列に追加
            if type(params.exclude) ~= "table" then
                params.exclude = {}
            end
            local unquoted = unquote(value)
            --debug_print("Unquoted value:", value, "->", unquoted)
            table.insert(params.exclude, unquoted)
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

    --debug_print("Final params - depth:", result.depth)
    --debug_print("Final exclude count:", #result.exclude)
    --for i, ex in ipairs(result.exclude) do
    --    debug_print("Final exclude", i .. ":", ex)
    --end

    return result
end

-- Windows における git-bash 探索処理関数
local function find_bash_path()
    if is_windows() then
        -- git.exe のパスを取得
        local git_path = nil
        local ok, output = pcall(pandoc.pipe, "where", {"git"}, "")
        if ok and output and output ~= "" then
            output = active_cp_to_utf8(output)
            git_path = output:gsub("[\r\n]+$", ""):match("([^\r\n]+)")
        end
        --debug_print("git_path:", git_path)

        if git_path then
            -- git.exe のパスから bash.exe のパスを生成
            local bash_path

            if git_path:match("\\mingw64\\bin\\git%.exe$") then
                -- /mingw64/bin/git.exe → /usr/bin/bash.exe
                bash_path = git_path:gsub("\\mingw64\\bin\\git%.exe$", "\\bin\\bash.exe")
            elseif git_path:match("\\cmd\\git%.exe$") then
                -- /cmd/git.exe → /bin/bash.exe
                bash_path = git_path:gsub("\\cmd\\git%.exe$", "\\bin\\bash.exe")
            elseif git_path:match("\\bin\\git%.exe$") then
                -- /bin/git.exe → /bin/bash.exe
                bash_path = git_path:gsub("\\bin\\git%.exe$", "\\bin\\bash.exe")
            end

            if bash_path then
                return bash_path
            end
        end

        return nil -- bash が見つからない
    else
        -- Linux/Unix では bash のパスを返す
        local ok, output = pcall(pandoc.pipe, "which", {"bash"}, "")
        if ok and output and output ~= "" then
            return output:gsub("[\r\n]+$", "")
        end
        return "/bin/bash" -- デフォルト
    end
end

function get_filter_path()
    local info = debug.getinfo(1, "S")
    if info and info.source then
        local source = info.source
        -- "@" プレフィックスを除去
        if source:sub(1, 1) == "@" then
            source = source:sub(2)
        end
        -- source からファイル名を取り除き、ディレクトリパスのみを返す
        local dir_path = source:match("(.+)[/\\][^/\\]+$")
        return dir_path or source
    end
    return nil
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
    
    --io.stderr:write("    > process_toc (This may take several minutes.)")
    --io.stderr:flush()

    -- bash パスを探索
    local bash_path = find_bash_path()
    if not bash_path then
        debug_print("Error: bash executable not found. Please ensure Git for Windows is installed or bash is available in PATH.")
        return {}
    end
    --debug_print("bash_path:", bash_path)

    -- insert-toc.sh に移譲
    -- params と current_file を引数として渡す
    local script_path = "'" .. get_filter_path() .. "/insert-toc.sh" .. "'"

    -- basedir が指定されている場合、current_file を調整
    local adjusted_current_file = current_file or ""
    if params.basedir and params.basedir ~= "" then
        -- current_file のディレクトリを取得
        local current_dir = adjusted_current_file:match("(.+)[/\\][^/\\]+$") or "."
        -- basedir を結合（ダミーファイル名を付与してディレクトリを指定）
        adjusted_current_file = current_dir .. "/" .. params.basedir .. "/.toc-dummy.md"
    end

    -- 引数を構築
    local args = {
        tostring(params.depth),
        adjusted_current_file,
        os.getenv("DOCUMENT_LANG") or "ja"
    }

    -- exclude パラメータは配列なので、カンマ区切りで結合
    if params.exclude and #params.exclude > 0 then
        table.insert(args, table.concat(params.exclude, ","))
    else
        table.insert(args, "")
    end

    -- basedir パラメータを追加（リンク生成用）
    table.insert(args, params.basedir or "")

    -- exclude-basedir パラメータを追加
    table.insert(args, tostring(params["exclude-basedir"] or false))

    -- bash コマンドを構築
    local command = script_path
    for _, arg in ipairs(args) do
        -- 引数をクォートで囲む
        command = command .. " '" .. arg:gsub("'", "'\"'\"'") .. "'"
    end

    --debug_print("bash command:", command)
    local proc_ok, proc_output = pcall(pandoc.pipe, utf8_to_active_cp(bash_path), {"-c", command}, "")
    if proc_ok and proc_output then
        --debug_print("insert-toc.sh execute successful:\n", proc_output)
    else
        debug_print("Error: insert-toc.sh execute failed")
        return {}
    end

    -- proc_output は Markdown として評価できる文字列が返却される
    return proc_output
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
                elseif element.t == "Quoted" then
                    -- Quoted ノードの処理（例: basedir="doxybook/calc"）
                    table.insert(params_parts, '"')
                    -- Quoted ノードの中身を展開
                    if element.content then
                        for _, quoted_elem in ipairs(element.content) do
                            if quoted_elem.t == "Str" then
                                local quoted_str = quoted_elem.text or quoted_elem.c
                                if quoted_str then
                                    table.insert(params_parts, quoted_str)
                                end
                            elseif quoted_elem.t == "Space" then
                                table.insert(params_parts, " ")
                            end
                        end
                    end
                    table.insert(params_parts, '"')
                end
            end
            
            local params_str = table.concat(params_parts, ""):gsub("^%s+", ""):gsub("%s+$", "")
            --debug_print("Para params:", params_str or "(empty)")
            
            local current_file = active_cp_to_utf8(os.getenv("SOURCE_FILE"))
            local markdown_content = process_toc_command(params_str, current_file)
            
            if markdown_content then
                -- Markdown 文字列を Pandoc AST に変換
                --debug_print("Generated markdown content:", markdown_content)

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
            local current_file = active_cp_to_utf8(os.getenv("SOURCE_FILE"))
            local markdown_content = process_toc_command(params_str, current_file)
            
            if markdown_content then
                -- Markdown 文字列を Pandoc AST に変換
                --debug_print("Generated markdown content:", markdown_content)

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
