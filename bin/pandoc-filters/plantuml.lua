local utils = require 'pandoc.utils'
local paths = require 'pandoc.path'
local mediabags = require 'pandoc.mediabag'
local root_dir = paths.directory(paths.directory(PANDOC_SCRIPT_FILE))

local search_paths = {
    package.path,
    paths.join({ root_dir, "modules", "LibDeflate", "?.lua" }),
    paths.join({ root_dir, "config", "?.lua" })
}
package.path = table.concat(search_paths, ";")

local libDeflate = require("LibDeflate")

-- load plantuml server configurations
local config_loaded, pu_config = pcall(function() return (require "config-plantuml").config() end)
if not config_loaded then
    io.stderr:write("use default settings ...\n")
    pu_config = { protocol = "http", host_name = "localhost", port = 8080 , sub_url = "", format = "png" }
end

pu_config.protocol = pu_config.protocol or "http"
pu_config.host_name = pu_config.host_name or "localhost"
pu_config.port = pu_config.port or "8080"
pu_config.sub_url = pu_config.sub_url or ""
pu_config.format = pu_config.format or "png"
pu_config.style = pu_config.style or ""

-- @type number -> string
local function encode6(b)
    if b < 10 then
        return utf8.char(b + 48)
    end

    b = b - 10
    if b < 26 then
        return utf8.char(b + 65)
    end

    b = b - 26
    if b < 26 then
        return utf8.char(b + 97)
    end

    b = b - 26
    if b == 0 then
        return "-"
    elseif b == 1 then
        return "_"
    else
        return "?"
    end
end

-- @type char -> char -> char -> string
local function append3(c1, c2, c3)
    local b1 = c1 >> 2
    local b2 = ((c1 & 0x03) << 4) | (c2 >> 4)
    local b3 = ((c2 & 0x0f) << 2) | (c3 >> 6)
    local b4 = c3 & 0x3f

    return table.concat({
        encode6(b1 & 0x3f), encode6(b2 & 0x3f), encode6(b3 & 0x3f), encode6(b4), 
    })
end

-- @type string -> string
local function encode(text)
    local ctext = libDeflate:CompressDeflate(text, {level = 9})
    local len = ctext:len()
    local buf = {}

    for i = 1, len, 3 do
        if i + 1 > len then
            table.insert(buf, append3(string.byte(ctext, i), 0, 0))
        elseif i + 2 > len then
            table.insert(buf, append3(string.byte(ctext, i), string.byte(ctext, i+1), 0))
        else 
            table.insert(buf, append3(string.byte(ctext, i), string.byte(ctext, i+1), string.byte(ctext, i+2)))
        end
    end

    return table.concat(buf)
end

-- OS 判定関数
local function is_windows()
    local os_name = os.getenv("OS")
    return os_name and string.match(os_name:lower(), "windows")
end

-- 一時ディレクトリを取得
function create_temp_file()
    if not is_windows() then
        -- Linux
        return os.tmpname()
    end

    -- Windows
    local temp_dir = os.getenv("TEMP") or os.getenv("TMP") or os.getenv("USERPROFILE") or "."
    
    -- 一意なファイル名を生成
    local timestamp = os.time()
    local random_num = math.random(1000, 9999)
    local temp_file = temp_dir .. "\\pandoc_temp_" .. timestamp .. "_" .. random_num .. ".txt"
    
    --io.stderr:write("DBG_TEMP_FILE: " .. temp_file .. "\n")
    return temp_file
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

local _root_dir = utf8_to_active_cp(root_dir)

local function file_exists(name)
    local _name = utf8_to_active_cp(name)

    local f = io.open(_name, "r")
    if f ~= nil then
        io.close(f)
        --io.stderr:write("exists " .. _name .. "\n")
        return true
    else
        --io.stderr:write("not exists " .. _name .. "\n")
        return false
    end
end

-- PATH に plantuml コマンドがあるかチェック
local function check_local_plantuml()
    local os_name = os.getenv("OS")
    local cmd
    if os_name and string.match(os_name:lower(), "windows") then
        cmd = "where plantuml >nul 2>&1"
    else
        cmd = "which plantuml >/dev/null 2>&1"
    end
    
    local result = os.execute(cmd)
    return result == true
end

-- ローカルの plantuml コマンドを使用して変換
local function convert_with_local_plantuml(puml_text, output_path, format)
    local temp_puml = create_temp_file()
    local _output_path = utf8_to_active_cp(output_path)
    
    -- PlantUML ソースを一時ファイルに書き出し
    local f = io.open(temp_puml, "w")
    if not f then
        return false, "Cannot create temporary file"
    end
    f:write(puml_text)
    f:close()
    
    -- plantuml コマンドを実行
    local cmd
    local os_name = os.getenv("OS")
    
    if os_name and string.match(os_name:lower(), "windows") then
        cmd = string.format('cat "%s" | plantuml -t%s -pipe > "%s"', temp_puml, format, _output_path)
    else
        cmd = string.format('cat "%s" | plantuml -t%s -pipe > "%s"', temp_puml, format, output_path)
    end
    
    local result = os.execute(cmd)
    
    -- 一時ファイルを削除
    os.remove(temp_puml)
    
    if result ~= true then
        return false, "plantuml command failed"
    end
    
    -- 出力ファイルが生成されたかチェック
    if not file_exists(output_path) then
        return false, "Output file not generated"
    end
    
    return true, nil
end

return {
    {
        CodeBlock = function(el) 

            ---------------------------------------------------------------------

            -- コードブロックの種別とファイル名を取得
            local code_class = el.classes[1] or ""
            local lang, filename = code_class:match("^([^:]+):(.+)$")
            if not lang then
                lang = code_class
            end
            -- コード種別判定
            if lang ~= "plantuml" then
                return el
            end

            ---------------------------------------------------------------------

            -- caption 属性があれば優先してキャプションに
            local caption = el.attributes["caption"]
            if caption then
                -- 属性を消す
                el.attributes["caption"] = nil
            elseif filename then
                -- 属性がない場合は従来どおりファイル名をキャプションに
                -- ファイル名の拡張子を除去
                filename = filename:gsub("%.[mM][mM][dD]$", "")
                -- ファイル名を caption に
                caption = filename
            end

            ---------------------------------------------------------------------

            -- 改行ごとに分割
            local lines = {}
            for line in el.text:gmatch("[^\n]+") do
                table.insert(lines, line)
            end

            -- "caption キャプション" の行を削除
            local removeCaptionLines = {}
            local captionPattern = "^%s*[Cc][Aa][Pp][Tt][Ii][Oo][Nn]%s*(.-)%s*$"
            for _, line in ipairs(lines) do
                if not line:match(captionPattern) then
                    table.insert(removeCaptionLines, line)
                else
                    -- キャプションの部分を得る
                    caption = line:match(captionPattern)
                end
            end

            -- @startjson, @startyaml に caption が付与できなかったので、caption がなくても対応できるようにする
            if caption == nil then
                local umlPattern = "^@startuml%s*(.+)%s*$"
                local mindmapPattern = "^@startmindmap%s*(.+)%s*$"
                local jsonPattern = "^@startjson%s*(.+)%s*$"
                local yamlPattern = "^@startyaml%s*(.+)%s*$"
                for _, line in ipairs(lines) do
                    if line:match(umlPattern) then
                        -- キャプションの部分を得る
                        caption = line:match(umlPattern)
                        break
                    end
                    if line:match(mindmapPattern) then
                        -- キャプションの部分を得る
                        caption = line:match(mindmapPattern)
                        break
                    end
                    if line:match(jsonPattern) then
                        -- キャプションの部分を得る
                        caption = line:match(jsonPattern)
                        break
                    end
                    if line:match(yamlPattern) then
                        -- キャプションの部分を得る
                        caption = line:match(yamlPattern)
                        break
                    end
                end
            end

            -- "skinparam backgroundColor " の処理
            local hasBackgroundColor = false
            for i, line in ipairs(removeCaptionLines) do
                if line:match("^skinparam backgroundColor ") then
                    hasBackgroundColor = true
                    removeCaptionLines[i] = "skinparam backgroundColor transparent" -- 置換
                end
            end

            if not hasBackgroundColor then
                -- @startuml, @startmindmap, @startjson, @startyaml の後に スタイル設定と "skinparam backgroundColor transparent" を挿入
                local insertIndex = 1
                for i, line in ipairs(removeCaptionLines) do
                    if line:match("^@startuml") or line:match("^@startmindmap") or line:match("^@startjson") or line:match("^@startyaml") then
                        insertIndex = i + 1 -- 該当行の次の行に挿入する
                        break
                    end
                end

                if pu_config.style ~= "" then
                    table.insert(removeCaptionLines, insertIndex, "\n" .. pu_config.style:gsub("\n$", ""))
                end

                table.insert(removeCaptionLines, insertIndex + 1, "skinparam backgroundColor transparent")
            end

            -- 文字列を再度組み立て
            local resultString = table.concat(removeCaptionLines, "\n")

            ---------------------------------------------------------------------

            local encoded_text = encode(resultString)

            local resource_dir = PANDOC_STATE.resource_path[1] or ""
            local _resource_dir = utf8_to_active_cp(resource_dir)

            local filename = string.format("puml_%s.%s", utils.sha1(encoded_text), pu_config.format)
            local image_file_path = paths.join({resource_dir, filename})
            local _image_file_path = utf8_to_active_cp(image_file_path)

            if not file_exists(image_file_path) then
                local local_success=false
                -- plantuml コマンドに PATH が通っているかチェック
                if check_local_plantuml() then
                    -- ローカルの plantuml コマンドで変換
                    --io.stderr:write("[plantuml] Using local plantuml command\n")
                    
                    -- 出力ディレクトリが存在しない場合は作成
                    -- ※ Windows の場合は、file_exists では既存ディレクトリの不存在チェックができないので、nul にリダイレクト
                    if not file_exists(resource_dir) then
                        if package.config:sub(1,1) == '\\' then -- Windows
                            os.execute("mkdir \"" .. utf8_to_active_cp(string.gsub(resource_dir, "/", "\\")) .. "\" >nul 2>&1")
                        else -- Unix-like systems (Linux, macOS, etc.)
                            os.execute("mkdir -p " .. resource_dir)
                        end
                    end
                    
                    local_success, error_msg = convert_with_local_plantuml(resultString, image_file_path, pu_config.format)
                    if not local_success then
                        io.stderr:write("[plantuml] Local conversion failed: " .. (error_msg or "unknown error") .. ", falling back to server\n")
                        -- ローカル変換に失敗した場合はサーバー変換にフォールバック
                    end
                end

                if not local_success then
                    -- サーバーを使用した変換
                    --io.stderr:write("[plantuml] Using server conversion\n")
                    local url = string.format("%s://%s:%s/%s%s/", pu_config.protocol, pu_config.host_name, pu_config.port, pu_config.sub_url, pu_config.format)
                    local mt, img = mediabags.fetch(url .. encoded_text)

                    if mt == nil or img == nil or (not img:match("^<svg") and not img:match("><svg")) then
                        io.stderr:write("Error: fetching image from " .. url .. "\n")
                        return el
                    end

                    -- write to file
                    local fs, errorDisc, errorCode = io.open(_image_file_path, "wb")

                    if errorCode == 2 then
                        -- Use platform-specific commands to create the directory
                        if package.config:sub(1,1) == '\\' then -- Windows
                            os.execute("mkdir \"" .. utf8_to_active_cp(string.gsub(resource_dir, "/", "\\")) .. "\"")
                        else -- Unix-like systems (Linux, macOS, etc.)
                            os.execute("mkdir -p " .. resource_dir)
                        end
                        fs = io.open(_image_file_path, "wb")
                    end

                    fs:write(img)
                    fs:close()
                end

                -- pu_config.format が "svg" の場合は、
                -- font-family="sans-serif" (デフォルトの場合のフォント名) を、font-family="メイリオ, Helvetica Neue, Helvetica, Arial, sans-serif" に置換する。
                -- (docx にインポートした際に MS ゴシック になってしまうことへの対応)
                if pu_config.format == "svg" then
                    local f = io.open(_image_file_path, "r")
                    if f then
                        local content = f:read("*a")
                        f:close()
                        content = string.gsub(content, 'font%-family="sans%-serif"', 'font-family="メイリオ, Helvetica Neue, Helvetica, Arial, sans-serif"')
                        f = io.open(_image_file_path, "w")
                        if f then
                            f:write(content)
                            f:close()
                        end
                    end
                end
            end
            
            local image_src = image_file_path

            -- output relative
            if PANDOC_STATE.output_file ~= nil then
                if string.match(FORMAT, "html") then 
                    local output_dir = paths.directory(PANDOC_STATE.output_file)
                    image_src = paths.make_relative(image_file_path, output_dir)
                else
                    image_src = paths.make_relative(image_file_path, resource_dir)
                end
            end

            -- replace tag
            if caption == nil then
                return pandoc.Figure(pandoc.Image("plantuml", image_src, ""))
            end

            -- TODO: caption に '\n' が含まれる場合の改行処理。構文的には問題なく html では動作するが、docx writer 経由で不要な改行が挿入され期待通り改行されない。要調査。
            caption = caption:gsub("\\n", "\n")
            local caption_elements = {}
            for line in caption:gmatch("[^\n]+") do
                --io.stderr:write("[plantuml] captionline: '" .. line .. "'\n")
                table.insert(caption_elements, pandoc.Str(line))
                table.insert(caption_elements, pandoc.LineBreak())
            end
            -- Remove the last LineBreak
            table.remove(caption_elements)

            return pandoc.Figure(pandoc.Image(caption, image_src, ""), caption_elements)
        end
    }
}
