local utils = require 'pandoc.utils'
local paths = require 'pandoc.path'
local mediabags = require 'pandoc.mediabag'
local root_dir = paths.directory(paths.directory(PANDOC_SCRIPT_FILE))

-- 一時ディレクトリを取得
function create_temp_file()
    -- OS 判定
    local os_name = os.getenv("OS")
    if not os_name or not string.match(os_name:lower(), "windows") then
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

-- コードページ変換 (for Windows)
function utf8_to_active_cp(text)
    -- OS 判定
    local os_name = os.getenv("OS")
    if not os_name or not string.match(os_name:lower(), "windows") then
        -- Linux
        return text
    end

    if not text or text == "" then
        return text
    end
    
    -- 一時ファイル名を得る
    local temp_file = create_temp_file()
    
    -- ファイルに書き込み
    local f = io.open(temp_file, "w")
    if not f then
        return text
    end
    f:write(text)
    f:close()

    -- PowerShell でファイル内容を現在のコードページに変換
    local handle = io.popen('powershell -Command "Write-Output(Get-Content -Path \'' .. temp_file .. '\' -Encoding UTF8 -Raw)"')

    local result = ""
    if handle then
        result = handle:read("*a")
        handle:close()
    end

    -- 一時ファイル削除
    os.remove(temp_file)
    
    if result == "" then
        return text
    end

    return result:gsub("\r?\n$", "")
end

local _root_dir = utf8_to_active_cp(root_dir)

local function file_exists(name)
    local _name = utf8_to_active_cp(name)

    local f = io.open(_name, "r")
    if f ~= nil then
        io.close(f)
        --io.stderr:write("[mermaid] skip " .. _name .. "\n")
        return true
    else
        --io.stderr:write("[mermaid] make " .. _name .. "\n")
        return false
    end
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

                if width and height then
                    -- ルート svg 要素のみ対象に style 属性を書き換え
                    patched_svg = patched_svg:gsub('(<svg[^>]-)style="([^"]*)"', function(svg_tag, style)
                        -- max-width を削除
                        style = style:gsub("max%-width:[^;]*;? ?", "")
                        -- width / height を削除
                        style = style:gsub("width:[^;]*;?", "")
                        style = style:gsub("height:[^;]*;?", "")
                        -- 末尾に width / height 追加
                        return string.format('%sstyle="width:%spx; height:%spx; %s"', svg_tag, width, height, style)
                    end, 1) -- 最初の svg タグのみ置換

                    -- svg タグの width / height 属性を上書きまたは追加 (ルート svg 要素のみ対象)
                    patched_svg = patched_svg
                        :gsub('(<svg[^>]*)%swidth="[^"]*"', '%1', 1)
                        :gsub('(<svg[^>]*)%sheight="[^"]*"', '%1', 1)
                        :gsub('(<svg)', '%1 width="' .. width .. 'px" height="' .. height .. 'px"', 1)
                end

                -- 上書き保存
                local f = io.open(_image_file_path, "w")
                if f then
                    f:write(patched_svg)
                    f:close()
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

            return pandoc.Figure(pandoc.Image(caption, image_src, ""), caption_elements)

        end
    }
}
