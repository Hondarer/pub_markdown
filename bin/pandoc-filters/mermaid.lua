local utils = require 'pandoc.utils'
local paths = require 'pandoc.path'
local mediabags = require 'pandoc.mediabag'

local root_dir = paths.directory(paths.directory(PANDOC_SCRIPT_FILE))

local search_paths = {
    package.path,
    paths.join({ root_dir, "modules", "UTF8toSJIS", "?.lua" }),
}
package.path = table.concat(search_paths, ";")

local UTF8toSJIS = require("UTF8toSJIS")
local UTF8SJIS_table = root_dir .. "/modules/UTF8toSJIS/UTF8toSJIS.tbl"

local function file_exists(name)
    -- io.open は OS のデフォルトコードページ依存のため、日本語 OS では日本語のファイル名を渡す際に UTF-8 のファイル名を SJIS にする必要がある。
    -- この処理が 他の言語の場合に正しく動作するかは未検証(動かない可能性が非常に高い)。
    local fht = io.open(UTF8SJIS_table, "r")
    local name_sjis, name_sjis_length = UTF8toSJIS:UTF8_to_SJIS_str_cnv(fht, name)
    fht:close()

    local f = io.open(name_sjis, "r")
    if f ~= nil then
        io.close(f)
        --io.stderr:write("[mermaid] skip " .. name_sjis .. "\n")
        return true
    else
        --io.stderr:write("[mermaid] make " .. name_sjis .. "\n")
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
            local caption = nil
            if filename then
                -- ファイル名の拡張子を除去
                filename = filename:gsub("%.[mM][mM][dD]$", "")
                -- ファイル名を caption に
                caption = filename
            end

            ---------------------------------------------------------------------

            local resource_dir = PANDOC_STATE.resource_path[1] or ""

            local image_filename = string.format("mermaid_%s.svg", utils.sha1(el.text))
            local image_file_path = paths.join({resource_dir, image_filename})

            if not file_exists(image_file_path) then
                local mmd_filename = string.format("mermaid_%s.mmd", utils.sha1(el.text))
                local mmd_file_path = paths.join({resource_dir, mmd_filename})

                -- el.text を一時ファイルに保存
                local f = io.open(mmd_file_path, "w")
                f:write(el.text)
                f:close()

                -- root_dir .. "/node_modules/.bin/mmdc" を呼び出して mermaid-cli を実行し、image_file_path に出力する。
                -- NOTE: mmdc は -i や -o を クオートできないので、cd して実行
                os.execute(string.format("cd %s && \"%s\" -i %s -o %s", resource_dir, root_dir .. "\\node_modules\\.bin\\mmdc.cmd", mmd_filename, image_filename))

                -- 一時ファイル削除
                os.remove(mmd_file_path)

                -- TODO: svg にパッチが必要

                -- ルートの svg 要素の viewBox="-50 -10 485 259" を解釈して幅と高さを得る
                -- その内容で svg をパッチ
                -- style="width:535px; height:269px; background-color: white;"
                -- width="535px" height="269px"
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