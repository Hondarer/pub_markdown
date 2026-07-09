local utils = require 'pandoc.utils'
local paths = require 'pandoc.path'
local mediabags = require 'pandoc.mediabag'
local root_dir = paths.directory(paths.directory(PANDOC_SCRIPT_FILE))

local search_paths = {
    package.path,
    paths.join({ root_dir, "modules", "LibDeflate", "?.lua" })
}
package.path = table.concat(search_paths, ";")

local libDeflate = require("LibDeflate")

local default_pu_config = {
    protocol = "https",
    host_name = "www.plantuml.com",
    port = "443",
    sub_url = "plantuml/",
    format = "svg",
    style = "<style>\n</style>"
}

local plantuml_config_keys = {
    protocol = true,
    host_name = true,
    port = true,
    sub_url = true,
    format = true,
    style = true
}

local function trim(text)
    return (text:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function unquote_yaml_scalar(value)
    local trimmed = trim(value:gsub("%s+#.*$", ""))
    local first = trimmed:sub(1, 1)
    local last = trimmed:sub(-1)
    if (first == '"' and last == '"') or (first == "'" and last == "'") then
        return trimmed:sub(2, -2)
    end
    return trimmed
end

local function read_text_file(path)
    if path == nil or path == "" then
        return nil
    end

    local f = io.open(path, "r")
    if not f then
        return nil
    end

    local content = f:read("*a")
    f:close()
    return content:gsub("\r\n", "\n"):gsub("\r", "\n")
end

local function count_indent(line)
    return #(line:match("^[ \t]*") or "")
end

local function split_lines(content)
    local lines = {}
    for line in (content .. "\n"):gmatch("([^\n]*)\n") do
        table.insert(lines, line)
    end
    return lines
end

local function parse_plantuml_yaml_section(content)
    local parsed = {}
    local lines = split_lines(content)
    local i = 1
    local in_plantuml_section = false

    while i <= #lines do
        local line = lines[i]

        if not in_plantuml_section then
            if line:match("^plantuml:%s*$") or line:match("^plantuml:%s*#") then
                in_plantuml_section = true
            end
            i = i + 1
        else
            if line:match("^%S") and not line:match("^%s*#") and not line:match("^%s*$") then
                break
            end

            local indent = count_indent(line)
            local key, raw_value = line:match("^%s*([%w_%-]+):%s*(.*)$")
            if key and plantuml_config_keys[key] then
                local block_indicator = trim(raw_value)
                if block_indicator == "|" or block_indicator == "|-" or block_indicator == "|+" then
                    local block_lines = {}
                    local block_indent = nil
                    i = i + 1

                    while i <= #lines do
                        local block_line = lines[i]
                        local current_indent = count_indent(block_line)
                        if block_line:match("^%S") then
                            break
                        end
                        if block_line:match("^%s*$") then
                            table.insert(block_lines, "")
                            i = i + 1
                        elseif current_indent <= indent then
                            break
                        else
                            block_indent = block_indent or current_indent
                            table.insert(block_lines, block_line:sub(block_indent + 1))
                            i = i + 1
                        end
                    end

                    parsed[key] = table.concat(block_lines, "\n")
                else
                    parsed[key] = unquote_yaml_scalar(raw_value)
                    i = i + 1
                end
            else
                i = i + 1
            end
        end
    end

    return parsed
end

local function load_plantuml_config()
    local config = {}
    for key, value in pairs(default_pu_config) do
        config[key] = value
    end

    local config_content = read_text_file(os.getenv("PUB_MARKDOWN_CONFIG_FILE"))
    if not config_content then
        return config
    end

    local parsed = parse_plantuml_yaml_section(config_content)
    for key in pairs(default_pu_config) do
        if parsed[key] ~= nil and parsed[key] ~= "" then
            config[key] = tostring(parsed[key])
        end
    end

    return config
end

local pu_config = load_plantuml_config()

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

-- バイナリ ファイルをアトミックにコピーする
-- dst が既存のとき Windows では rename が失敗するため、失敗時は tmp を削除して正常とみなす
local function copy_file(src, dst)
    local _src = utf8_to_active_cp(src)
    local fin = io.open(_src, "rb")
    if not fin then return false end
    local data = fin:read("*a")
    fin:close()
    local tmp = dst .. ".tmp." .. tostring(math.random(100000000, 999999999))
    local _tmp = utf8_to_active_cp(tmp)
    local fout = io.open(_tmp, "wb")
    if not fout then return false end
    fout:write(data)
    fout:close()
    local _dst = utf8_to_active_cp(dst)
    if not os.rename(_tmp, _dst) then
        -- Windows: dst が既存だと rename が失敗する。他プロセスが先に書き込み済み。
        os.remove(_tmp)
    end
    return true
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

local function move_root_processing_instructions_after_svg(content)
    local svg_start, svg_end = content:find("<svg[%s>][^>]*>")
    if not svg_start then
        return content
    end

    local prefix = content:sub(1, svg_start - 1)
    local moved_processing_instructions = {}
    local kept_prefix_parts = {}
    local pos = 1

    while pos <= #prefix do
        local pi_start, pi_end, target = prefix:find("<%?([%w_:%-%.]+)%s.-%?>", pos)
        if not pi_start then
            table.insert(kept_prefix_parts, prefix:sub(pos))
            break
        end

        table.insert(kept_prefix_parts, prefix:sub(pos, pi_start - 1))
        local processing_instruction = prefix:sub(pi_start, pi_end)
        if target:lower() == "xml" then
            table.insert(kept_prefix_parts, processing_instruction)
        else
            table.insert(moved_processing_instructions, processing_instruction)
        end
        pos = pi_end + 1
    end

    if #moved_processing_instructions == 0 then
        return content
    end

    local kept_prefix = table.concat(kept_prefix_parts)
    if not kept_prefix:match("<%?xml%s") then
        kept_prefix = ""
    end

    return kept_prefix
        .. content:sub(svg_start, svg_end)
        .. table.concat(moved_processing_instructions)
        .. content:sub(svg_end + 1)
end

-- NOTE: Microsoft Word では、最初のフォント以外は評価されない
local plantuml_svg_font_family = "\'Segoe UI\', Meiryo, \'Hiragino Sans\', \'Hiragino Kaku Gothic ProN\', sans-serif"

-- docx 出力時の SVG → PNG 変換 DPI
-- rsvg-convert.js の計算式: scale = max(dpiX, dpiY) * 1.5 / 96
-- DPI 120 → scale = 1.875 → 実効 180 DPI
-- 生成 PNG は rsvg-convert.js 内で sharp によるパレット減色再エンコードを行う
local RSVG_DPI_X = 120
local RSVG_DPI_Y = 120

--- SVG ファイルのルートタグから表示用の幅と高さ (px) を取得する。
--- width/height 属性を優先し、なければ viewBox から取得する。
local function get_svg_display_size(svg_path)
    local f = io.open(svg_path, "r")
    if not f then return nil, nil end
    local content = f:read(4096)
    f:close()
    if not content then return nil, nil end
    local tag_end = content:find(">", 1, true)
    if not tag_end then return nil, nil end
    local root_tag = content:sub(1, tag_end)
    local w = tonumber(root_tag:match('width="([%d%.]+)'))
    local h = tonumber(root_tag:match('height="([%d%.]+)'))
    if w and h then return w, h end
    local vb = root_tag:match('viewBox="([^"]+)"')
    if vb then
        local _, _, vw, vh = vb:match("([%-%d%.]+)%s+([%-%d%.]+)%s+([%d%.]+)%s+([%d%.]+)")
        return tonumber(vw), tonumber(vh)
    end
    return nil, nil
end

--- パッチ済み SVG を rsvg-convert で PNG に変換する。
--- 既に PNG が存在する場合はスキップする。
local function convert_svg_to_png(svg_path, png_path)
    if file_exists(png_path) then
        return true
    end

    local _svg_path = utf8_to_active_cp(svg_path)
    local _png_path = utf8_to_active_cp(png_path)

    local cmd
    if package.config:sub(1,1) == '\\' then -- Windows
        cmd = string.format(
            'type "%s" | "%s" --dpi-x %d --dpi-y %d -f png -a > "%s"',
            _svg_path, _root_dir .. "\\rsvg-convert.cmd",
            RSVG_DPI_X, RSVG_DPI_Y, _png_path)
    else
        cmd = string.format(
            'cat "%s" | "%s" --dpi-x %d --dpi-y %d -f png -a > "%s"',
            svg_path, root_dir .. "/rsvg-convert",
            RSVG_DPI_X, RSVG_DPI_Y, png_path)
    end

    local result = os.execute(cmd)
    if result ~= true then
        io.stderr:write("[plantuml] Error: rsvg-convert failed for " .. svg_path .. "\n")
        return false
    end
    return true
end

local function patch_svg_font_family(content)
    content = string.gsub(content, 'font%-family%s*=%s*"[^"]*"', 'font-family="' .. plantuml_svg_font_family .. '"')
    content = string.gsub(content, "font%-family%s*=%s*'[^']*'", 'font-family="' .. plantuml_svg_font_family .. '"')
    content = string.gsub(content, 'font%-family%s*:%s*&quot;.-&quot;', 'font-family: ' .. plantuml_svg_font_family)
    content = string.gsub(content, 'font%-family%s*:%s*"[^"]*"', 'font-family: "' .. plantuml_svg_font_family .. '"')
    content = string.gsub(content, "font%-family%s*:%s*'[^']*'", "font-family: '" .. plantuml_svg_font_family .. "'")
    content = string.gsub(content, 'font%-family%s*:%s*[^;&"\']+', 'font-family: ' .. plantuml_svg_font_family)
    return content
end

local function patch_svg_content(content)
    content = move_root_processing_instructions_after_svg(content)
    --return patch_svg_font_family(content)
    return content
end

local function patch_svg_file(path)
    local _path = utf8_to_active_cp(path)
    local f = io.open(_path, "r")
    if not f then
        return
    end

    local content = f:read("*a")
    f:close()

    local patched_content = patch_svg_content(content)
    if patched_content == content then
        return
    end

    f = io.open(_path, "w")
    if f then
        f:write(patched_content)
        f:close()
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
-- 並列実行時の競合を防ぐため、仮ファイル名に出力する
-- 成功時: true, 仮ファイルパス を返す (呼び出し元でアトミックにリネームすること)
-- 失敗時: false, エラーメッセージ を返す
local function convert_with_local_plantuml(puml_text, output_path, format)
    local temp_puml = create_temp_file()
    -- 仮ファイル名: 並列プロセス間で衝突しないようランダム値を付与
    local temp_output = output_path .. ".tmp." .. tostring(math.random(100000000, 999999999))
    local _temp_output = utf8_to_active_cp(temp_output)

    -- PlantUML ソースを一時ファイルに書き出し
    local f = io.open(temp_puml, "w")
    if not f then
        return false, "Cannot create temporary file"
    end
    f:write(puml_text)
    f:close()

    -- plantuml コマンドを実行（仮ファイル名に出力）
    local cmd
    local os_name = os.getenv("OS")

    if os_name and string.match(os_name:lower(), "windows") then
        cmd = string.format('cat "%s" | plantuml -t%s -pipe > "%s"', temp_puml, format, _temp_output)
    else
        cmd = string.format('cat "%s" | plantuml -t%s -pipe > "%s"', temp_puml, format, temp_output)
    end

    local result = os.execute(cmd)

    -- PlantUML ソース一時ファイルを削除
    os.remove(temp_puml)

    if result ~= true then
        os.remove(temp_output)
        return false, "plantuml command failed"
    end

    -- 出力ファイルが生成されたかチェック
    if not file_exists(temp_output) then
        return false, "Output file not generated"
    end

    return true, temp_output
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

            -- PlantUML の ~ エスケープを除去（~__attribute__~ 等の表現を正規化）
            if caption then
                caption = caption:gsub("~(.)", "%1")
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

            -- 共有 SVG キャッシュ: 出力バリアントをまたいだ重複 HTTP 取得を防ぐ
            local shared_cache_dir = os.getenv("PUB_MARKDOWN_PLANTUML_CACHE_DIR") or ""
            local shared_cache_path = (shared_cache_dir ~= "") and paths.join({shared_cache_dir, filename}) or ""
            local _fresh_generated = false

            if not file_exists(image_file_path) then
                if shared_cache_path ~= "" and file_exists(shared_cache_path) then
                    -- 共有キャッシュから resource_dir へコピーして再利用
                    if not file_exists(resource_dir) then
                        if package.config:sub(1,1) == '\\' then -- Windows
                            os.execute("mkdir \"" .. utf8_to_active_cp(string.gsub(resource_dir, "/", "\\")) .. "\" >nul 2>&1")
                        else -- Unix-like systems (Linux, macOS, etc.)
                            os.execute("mkdir -p " .. resource_dir)
                        end
                    end
                    copy_file(shared_cache_path, image_file_path)
                else
                    local local_success = false
                    local temp_output = nil

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

                        local temp_path
                        local_success, temp_path = convert_with_local_plantuml(resultString, image_file_path, pu_config.format)
                        if local_success then
                            temp_output = temp_path
                        else
                            io.stderr:write("[plantuml] Local conversion failed: " .. (temp_path or "unknown error") .. "\n")
                            return el
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

                        -- 仮ファイルに書き込む（並列実行時の競合を防ぐため）
                        local temp_path = image_file_path .. ".tmp." .. tostring(math.random(100000000, 999999999))
                        local _temp_path = utf8_to_active_cp(temp_path)
                        local fs, errorDisc, errorCode = io.open(_temp_path, "wb")

                        if errorCode == 2 then
                            -- Use platform-specific commands to create the directory
                            if package.config:sub(1,1) == '\\' then -- Windows
                                os.execute("mkdir \"" .. utf8_to_active_cp(string.gsub(resource_dir, "/", "\\")) .. "\"")
                            else -- Unix-like systems (Linux, macOS, etc.)
                                os.execute("mkdir -p " .. resource_dir)
                            end
                            fs = io.open(_temp_path, "wb")
                        end

                        fs:write(img)
                        fs:close()
                        temp_output = temp_path
                    end

                    -- pu_config.format が "svg" の場合は、
                    -- font-family を、Word で日本語フォントとして解釈されやすい "Segoe UI, メイリオ" に置換する。
                    -- (docx にインポートした際に MS ゴシック になってしまうことへの対応)
                    -- PlantUML v1.2026.0 以降の SVG 先頭処理命令は、Pandoc の docx 画像サイズ解析を妨げるため <svg> 開始タグの直後へ移動する。
                    -- フォント置換は仮ファイルに対して実施してからアトミックにリネームする
                    if temp_output and pu_config.format == "svg" then
                        patch_svg_file(temp_output)
                    end

                    -- 仮ファイルを最終ファイル名にアトミックにリネーム
                    -- 複数プロセスが同時に完了しても os.rename は上書きになるだけで内容は同一
                    if temp_output then
                        local _temp_output = utf8_to_active_cp(temp_output)
                        os.rename(_temp_output, _image_file_path)
                    end

                    _fresh_generated = true
                end
            end

            if pu_config.format == "svg" then
                patch_svg_file(image_file_path)
            end

            -- SVG パッチ適用後に共有キャッシュへ保存 (初回生成時のみ)
            if _fresh_generated and shared_cache_path ~= "" then
                copy_file(image_file_path, shared_cache_path)
            end

            -- docx 出力時かつ SVG フォーマットの場合: パッチ済み SVG を PNG に変換して、PNG パスに切り替える
            -- (Pandoc が SVG を検出して rsvg-convert で二重変換するのを防ぐ)
            local display_width, display_height
            if pu_config.format == "svg" and not string.match(FORMAT, "html") then
                local png_filename = string.format("puml_%s.png", utils.sha1(encoded_text))
                local png_file_path = paths.join({resource_dir, png_filename})
                display_width, display_height = get_svg_display_size(utf8_to_active_cp(image_file_path))
                if convert_svg_to_png(image_file_path, png_file_path) then
                    image_file_path = png_file_path
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
                if display_width and display_height then
                    return pandoc.Figure(pandoc.Image("plantuml", image_src, "",
                        pandoc.Attr("", {}, {{"width", tostring(display_width) .. "px"},
                                            {"height", tostring(display_height) .. "px"}})))
                end
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

            if display_width and display_height then
                return pandoc.Figure(pandoc.Image(caption, image_src, "",
                    pandoc.Attr("", {}, {{"width", tostring(display_width) .. "px"},
                                        {"height", tostring(display_height) .. "px"}})), caption_elements)
            end
            return pandoc.Figure(pandoc.Image(caption, image_src, ""), caption_elements)
        end
    }
}
