local utils = require 'pandoc.utils'
local paths = require 'pandoc.path'
local mediabags = require 'pandoc.mediabag'

local root_dir = paths.directory(paths.directory(PANDOC_SCRIPT_FILE))

local search_paths = {
    package.path,
    paths.join({ root_dir, "modules", "LibDeflate", "?.lua" }),
    paths.join({ root_dir, "modules", "UTF8toSJIS", "?.lua" }),
    paths.join({ root_dir, "config", "?.lua" })
}
package.path = table.concat(search_paths, ";")

local libDeflate = require("LibDeflate")

local UTF8toSJIS = require("UTF8toSJIS")
local UTF8SJIS_table = root_dir .. "/modules/UTF8toSJIS/UTF8toSJIS.tbl"

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

local function file_exists(name)
    -- io.open は OS のデフォルトコードページ依存のため、日本語 OS では日本語のファイル名を渡す際に UTF-8 のファイル名を SJIS にする必要がある。
    -- この処理が 他の言語の場合に正しく動作するかは未検証(動かない可能性が非常に高い)。
    local fht = io.open(UTF8SJIS_table, "r")
    local name_sjis, name_sjis_length = UTF8toSJIS:UTF8_to_SJIS_str_cnv(fht, name)
    fht:close()

    local f = io.open(name_sjis, "r")
    if f ~= nil then
        io.close(f)
        --io.stderr:write("[plantuml] skip " .. name_sjis .. "\n")
        return true
    else
        --io.stderr:write("[plantuml] make " .. name_sjis .. "\n")
        return false
    end
end

return {
    {
        CodeBlock = function(el) 
            if el.classes[1] ~= "plantuml" then
                return el
            end

            ---------------------------------------------------------------------

            -- 改行ごとに分割
            local lines = {}
            for line in el.text:gmatch("[^\n]+") do
                table.insert(lines, line)
            end

            -- "caption キャプション" の行を削除
            local filteredLines = {}
            local captionPattern = "^%s*[Cc][Aa][Pp][Tt][Ii][Oo][Nn]%s*(.-)%s*$"
            local caption = nil
            for _, line in ipairs(lines) do
                if not line:match(captionPattern) then
                    table.insert(filteredLines, line)
                else
                    -- キャプションの部分を得る
                    caption = line:match(captionPattern)
                end
            end

            -- キャプションを取り除いた文字列を組み立て
            local resultString = table.concat(filteredLines, "\n")

            ---------------------------------------------------------------------

            local encoded_text = encode(resultString)

            local resource_dir = PANDOC_STATE.resource_path[1] or ""

            local filename = string.format("%s.%s", utils.sha1(encoded_text), pu_config.format)
            local image_file_path = paths.join({resource_dir, filename})

            if not file_exists(image_file_path) then

                local url = string.format("%s://%s:%s/%s%s/%s", pu_config.protocol, pu_config.host_name, pu_config.port, pu_config.sub_url, pu_config.format, encoded_text)
                local mt, img = mediabags.fetch(url)

                if mt == nil or img == nil then
                    -- TODO: error checking...
                    print("Error fetching image from " .. url)
                    return
                end
            
                -- write to file

                -- io.open は OS のデフォルトコードページ依存のため、日本語 OS では日本語のファイル名を渡す際に UTF-8 のファイル名を SJIS にする必要がある。
                -- この処理が 他の言語の場合に正しく動作するかは未検証(動かない可能性が非常に高い)。
                local fht = io.open(UTF8SJIS_table, "r")
                local image_file_path_sjis, image_file_path_sjis_length = UTF8toSJIS:UTF8_to_SJIS_str_cnv(fht, image_file_path)
                fht:close()
                local fs, errorDisc, errorCode = io.open(image_file_path_sjis, "wb")

                if errorCode == 2 then
                    -- Use platform-specific commands to create the directory
                    if package.config:sub(1,1) == '\\' then -- Windows
                        os.execute("mkdir " .. string.gsub(resource_dir, "/", "\\"))
                    else -- Unix-like systems (Linux, macOS, etc.)
                        os.execute("mkdir " .. resource_dir)
                    end
                    fs = io.open(image_file_path, "wb")
                end

                -- pu_config.format が "svg" の場合は、
                -- font-family="sans-serif" (デフォルトの場合のフォント名) を、font-family="メイリオ, Helvetica Neue, Helvetica, Arial, sans-serif" に置換する。
                -- (docx にインポートした際に MS ゴシック になってしまうことへの対応)
                if pu_config.format == "svg" then
                    img = string.gsub(img, 'font%-family="sans%-serif"', 'font-family="メイリオ, Helvetica Neue, Helvetica, Arial, sans-serif"')
                end
            
                fs:write(img)
                fs:close()
            end
            
            local image_src = image_file_path

            if PANDOC_STATE.output_file ~= nil then
                if string.match(FORMAT, "html") then 
                    local output_dir = paths.directory(PANDOC_STATE.output_file)

                    -- output relative
                    image_src = paths.make_relative(image_file_path, output_dir)
                end
            end

            -- replace tag
            if caption == nil then
                return pandoc.Figure(pandoc.Image("test", image_src, ""))
            end
            return pandoc.Figure(pandoc.Image("test", image_src, ""), {pandoc.Str(caption)})

        end
    }
}