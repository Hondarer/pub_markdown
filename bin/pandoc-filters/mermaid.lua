local utils = require 'pandoc.utils'
local paths = require 'pandoc.path'
local mediabags = require 'pandoc.mediabag'
local root_dir = paths.directory(paths.directory(PANDOC_SCRIPT_FILE))

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

local function is_html_format()
    return FORMAT and FORMAT:match("html")
end

local function escape_html(text)
    text = text:gsub("&", "&amp;")
    text = text:gsub("<", "&lt;")
    text = text:gsub(">", "&gt;")
    text = text:gsub('"', "&quot;")
    return text
end

local function caption_to_html(caption)
    caption = caption:gsub("\\n", "\n")
    local lines = {}
    for line in caption:gmatch("[^\n]+") do
        table.insert(lines, escape_html(line))
    end
    return table.concat(lines, "<br />")
end

local function mermaid_html_block(text, caption)
    local pre = '<pre class="mermaid">' .. escape_html(text) .. '</pre>'
    if caption == nil then
        return pandoc.RawBlock("html", pre)
    end
    return pandoc.RawBlock("html",
        '<figure class="mermaid-figure">' .. pre .. '<figcaption>' ..
        caption_to_html(caption) .. '</figcaption></figure>')
end

-- NOTE: Microsoft Word では、最初のフォント以外は評価されない
local mermaid_svg_font_family = "\'Segoe UI\', Meiryo, \'Hiragino Sans\', \'Hiragino Kaku Gothic ProN\', sans-serif"

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
        io.stderr:write("[mermaid] Error: rsvg-convert failed for " .. svg_path .. "\n")
        return false
    end
    return true
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
            if lang ~= "mermaid" then
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

            if is_html_format() then
                return mermaid_html_block(el.text, caption)
            end

            ---------------------------------------------------------------------

            local MMDC_CMD
            -- Use platform-specific commands to create the directory
            if package.config:sub(1,1) == '\\' then -- Windows
                MMDC_CMD = "\\node_modules\\.bin\\mmdc.cmd"
            else -- Unix-like systems (Linux, macOS, etc.)
                MMDC_CMD = "/mmdc-wrapper.sh"
            end

            local resource_dir = PANDOC_STATE.resource_path[1] or ""
            local _resource_dir = utf8_to_active_cp(resource_dir)

            local image_filename = string.format("mermaid_%s.svg", utils.sha1(el.text))
            local _image_filename = utf8_to_active_cp(image_filename)
            local image_file_path = paths.join({resource_dir, image_filename})
            local _image_file_path = utf8_to_active_cp(image_file_path)

            if not file_exists(image_file_path) then
                local mmd_filename = string.format("mermaid_%s.mmd", utils.sha1(el.text))
                local _mmd_filename = utf8_to_active_cp(mmd_filename)
                local mmd_file_path = paths.join({resource_dir, mmd_filename})
                local _mmd_file_path = utf8_to_active_cp(mmd_file_path)

                -- el.text を一時ファイルに保存
                local f = io.open(_mmd_file_path, "w")
                f:write(el.text)
                f:close()

                -- root_dir .. "/node_modules/.bin/mmdc" を呼び出して mermaid-cli を実行し、image_file_path に出力する。
                -- NOTE: mmdc は -i や -o を クオートできないので、cd して実行
                --
                -- 以下はフィルタする
                -- Generating single mermaid chart
                -- -ms-high-contrast-adjust is in the process of being deprecated. Please see https://blogs.windows.com/msedgedev/2024/04/29/deprecating-ms-high-contrast/ for tips on updating to the new Forced Colors Mode standard.
                -- [@zenuml/core] Store is a function and is not initiated in 1 second.
                --io.stderr:write(string.format("cd \"%s\" && \"%s\" -i %s -o %s -b transparent | grep -v -E \"Generating|deprecated|Store is a function\"\n", _resource_dir, _root_dir .. MMDC_CMD, _mmd_filename, _image_filename))
                os.execute(string.format("cd \"%s\" && \"%s\" -i %s -o %s -b transparent | grep -v -E \"Generating|deprecated|Store is a function\"", _resource_dir, _root_dir .. MMDC_CMD, _mmd_filename, _image_filename))

                -- mmd ファイル削除
                os.remove(_mmd_file_path)

                -- svg にパッチをする
                -- Mermaid からはサイズ指定が 100% で 出力されるので、svg の viewBox を取得して width / height を上書きする。
                -- before sample
                -- <svg aria-roledescription="sequence" role="graphics-document document" viewBox="-50 -10 485 259" style="max-width: 485px; background-color: white;" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns="http://www.w3.org/2000/svg" width="100%" id="my-svg">
                -- after sample
                -- <svg width="485px" height="259px" aria-roledescription="sequence" role="graphics-document document" viewBox="-50 -10 485 259" style="width:535px; height:269px; background-color: white;" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns="http://www.w3.org/2000/svg" width="100%" id="my-svg">

                -- svg を読み込む
                local svg_content = ""
                do
                    local f = io.open(_image_file_path, "r")
                    if not f then
                        io.stderr:write("[mermaid] Error: SVG file was not generated: " .. image_file_path .. "\n")
                        return el
                    end
                    svg_content = f:read("*a")
                    f:close()
                end

                -- viewBox から幅と高さを得る
                local width, height
                do
                    local viewBox = svg_content:match('viewBox="([^"]+)"')
                    if viewBox then
                        local _, _, w, h = viewBox:match("([%-%d%.]+) ([%-%d%.]+) ([%d%.]+) ([%d%.]+)")
                        width = w
                        height = h
                    end
                end

                -- style 属性から max-width を削除し、width / height を追加または上書き
                local patched_svg = svg_content

                -- PlantUML に対する mermaid svg の倍率
                -- ※ mermaid svg のほうが、やや大きいため
                local multiply_svg = 0.875

                if width and height then
                    -- ルート svg 開始タグを抽出し、その中だけを書き換える
                    -- (ネストされた svg 要素を誤って変更しないための安全策)
                    local root_tag_end_pos = patched_svg:find(">", 1, true)
                    if root_tag_end_pos then
                        local root_tag = patched_svg:sub(1, root_tag_end_pos)
                        local rest = patched_svg:sub(root_tag_end_pos + 1)

                        -- style 属性から max-width を削除し、width / height を追加または上書き
                        root_tag = root_tag:gsub('style="([^"]*)"', function(style)
                            style = style:gsub("max%-width:[^;]*;? ?", "")
                            style = style:gsub("width:[^;]*;?", "")
                            style = style:gsub("height:[^;]*;?", "")
                            return string.format('style="width:%spx; height:%spx; %s"',
                                width * multiply_svg, height * multiply_svg, style)
                        end)

                        -- width / height 属性を削除して新しい値を追加
                        root_tag = root_tag:gsub('%swidth="[^"]*"', '')
                        root_tag = root_tag:gsub('%sheight="[^"]*"', '')
                        root_tag = root_tag:gsub('^<svg',
                            '<svg width="' .. width * multiply_svg .. 'px" height="' .. height * multiply_svg .. 'px"')

                        patched_svg = root_tag .. rest
                    end
                end

                -- font-family:"trebuchet ms",verdana,arial,sans-serif; (デフォルトの場合のフォント名) を、
                -- Word で日本語フォントとして解釈されやすいフォントスタックに置換する。
                -- (docx にインポートした際に MS ゴシック になってしまうことへの対応)
                --patched_svg = string.gsub(patched_svg, 'font%-family:"trebuchet ms",verdana,arial,sans%-serif;', 'font-family:' .. mermaid_svg_font_family .. ';')

                -- 上書き保存
                local f = io.open(_image_file_path, "w")
                if f then
                    f:write(patched_svg)
                    f:close()
                end
            end

            -- docx 出力時: パッチ済み SVG を PNG に変換して、PNG パスに切り替える
            -- (Pandoc が SVG を検出して rsvg-convert で二重変換するのを防ぐ)
            local display_width, display_height
            if not is_html_format() then
                local png_filename = string.format("mermaid_%s.png", utils.sha1(el.text))
                local png_file_path = paths.join({resource_dir, png_filename})
                display_width, display_height = get_svg_display_size(utf8_to_active_cp(image_file_path))
                if convert_svg_to_png(image_file_path, png_file_path) then
                    image_file_path = png_file_path
                end
            end

            local image_src = image_file_path

            -- output relative
            if PANDOC_STATE.output_file ~= nil then
                if is_html_format() then
                    local output_dir = paths.directory(PANDOC_STATE.output_file)
                    image_src = paths.make_relative(image_file_path, output_dir)
                else
                    image_src = paths.make_relative(image_file_path, resource_dir)
                end
            end

            -- replace tag
            if caption == nil then
                if display_width and display_height then
                    return pandoc.Figure(pandoc.Image("mermaid", image_src, "",
                        pandoc.Attr("", {}, {{"width", tostring(display_width) .. "px"},
                                            {"height", tostring(display_height) .. "px"}})))
                end
                return pandoc.Figure(pandoc.Image("mermaid", image_src, ""))
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
