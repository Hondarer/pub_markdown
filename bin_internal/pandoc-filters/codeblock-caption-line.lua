-- codeblock-caption-line.lua
--
-- コード ブロックまたは画像の直後に置かれた "CodeBlock: キャプション" / "Figure: キャプション"
-- 段落を、直前の要素のキャプションと identifier へ畳み込む。
--
-- 表の "Table:" と同じく、キャプションをフェンスや画像の属性の外に出すための記法である。
-- フェンスを ```mermaid のような素の形に保てるため、GitHub などの Web 表示でも
-- 図の描画やシンタックス ハイライトが機能する。
--
--     ```mermaid
--     sequenceDiagram
--         Alice->>John: Hello
--     ```
--
--     Figure: 接続シーケンス {#fig:seq-open}
--
-- 末尾の {#fig:xxx} / {#lst:xxx} は省略可能なラベルで、pandoc-crossref による
-- 採番と相互参照に用いる。
--
-- 図と判定する言語の一覧は ../diagram-languages.txt から読み込む。
--   - 図フェンス (plantuml / mermaid): "Figure:" を正とし、"CodeBlock:" も互換で受け付ける。
--   - 通常のコード ブロック: "CodeBlock:" を正とし、"Figure:" は警告のうえで受け付ける。
--   - 画像 1 個だけの段落: "Figure:" のみ受け付ける ("CodeBlock:" は通常の段落として残す)。
--   - キャプション行種別とラベル接頭辞の不一致 (Figure: と lst: 等) や、
--     画像属性ラベルと Figure: 行ラベルの重複時は警告を出力する。
--
-- キャプションの描画は後続のフィルターが担当する。
--   mermaid   -> mermaid.lua
--   plantuml  -> plantuml.lua
--   画像      -> Pandoc Figure (pandoc-crossref があれば採番・参照)
--   それ以外  -> codeblock-caption.lua (ラベル付きは pandoc-crossref)
--
-- 適用位置は plantuml.lua、mermaid.lua、codeblock-caption.lua のいずれよりも前。

local CODEBLOCK_PREFIX = "CodeBlock:"
local FIGURE_PREFIX = "Figure:"

-- キャプション行に由来する caption であることを示す内部用の印。
-- 廃止したフェンス属性 caption と区別するために用い、処理後に取り除く。
local SOURCE_MARK = "docsfw-caption-source"

--- スクリプト配置ディレクトリからの相対パスで図言語一覧を読み込む。
local function load_diagram_languages()
    local script_dir = PANDOC_SCRIPT_FILE:match("^(.*)[/\\][^/\\]+$") or "."
    local path = script_dir .. "/../diagram-languages.txt"
    local fh, err = io.open(path, "r")
    if not fh then
        error(string.format("[codeblock-caption-line] diagram-languages.txt を開けません (%s): %s", path, tostring(err)))
    end
    local langs = {}
    for line in fh:lines() do
        local stripped = line:gsub("#.*$", ""):match("^%s*(.-)%s*$")
        if stripped ~= "" then
            langs[stripped] = true
        end
    end
    fh:close()
    return langs
end

local DIAGRAM_LANGUAGES = load_diagram_languages()

--- 警告時に表示する入力ファイル名を得る。
local function input_file_name()
    if PANDOC_STATE and PANDOC_STATE.input_files and PANDOC_STATE.input_files[1] then
        return PANDOC_STATE.input_files[1]
    end
    return "(stdin)"
end

--- 警告メッセージを標準エラー出力へ出力する。
local function warn(fmt, ...)
    io.stderr:write(string.format("[codeblock-caption-line] %s: " .. fmt .. "\n", input_file_name(), ...))
end

--- インライン列を文字列化する。改行は "\n" として保持する。
local function inlines_to_text(inlines)
    local parts = {}
    for _, inline in ipairs(inlines) do
        if inline.t == "LineBreak" or inline.t == "SoftBreak" then
            table.insert(parts, "\n")
        else
            table.insert(parts, pandoc.utils.stringify(inline))
        end
    end
    return table.concat(parts)
end

--- キャプション本文から末尾のラベル {#lst:xxx} を切り出す。
--- 戻り値: キャプション本文, ラベル (ラベルがなければ nil)
local function split_label(text)
    local body, label = text:match("^(.-)%s*{#([^%s{}]+)}$")
    if label then
        return body, label
    end
    return text, nil
end

--- インライン列のコピーを作り、SoftBreak を LineBreak へ正規化する。
local function clone_inlines_with_linebreak(inlines)
    local out = pandoc.List({})
    for _, inline in ipairs(inlines) do
        if inline.t == "SoftBreak" then
            out:insert(pandoc.LineBreak())
        else
            out:insert(inline:clone())
        end
    end
    return out
end

--- インライン列の先頭プレフィックスと末尾ラベルを除去する (画像 Figure 用)。
local function extract_figure_inlines(para_inlines, prefix, label)
    local out = clone_inlines_with_linebreak(para_inlines)
    -- 先頭の空白類を除去
    while #out > 0 and (out[1].t == "Space" or out[1].t == "LineBreak") do
        table.remove(out, 1)
    end
    -- 先頭の Str からプレフィックスを除去
    if #out > 0 and out[1].t == "Str" and out[1].text:sub(1, #prefix) == prefix then
        local rest = out[1].text:sub(#prefix + 1)
        if rest == "" then
            table.remove(out, 1)
        else
            out[1] = pandoc.Str(rest)
        end
    end
    -- プレフィックス直後の空白を除去
    while #out > 0 and (out[1].t == "Space" or out[1].t == "LineBreak") do
        table.remove(out, 1)
    end
    -- 末尾の空白類を除去
    while #out > 0 and (out[#out].t == "Space" or out[#out].t == "LineBreak") do
        table.remove(out)
    end
    -- 末尾のラベル "{#label}" を除去
    if label and #out > 0 and out[#out].t == "Str" then
        local token = "{#" .. label .. "}"
        local text = out[#out].text
        if text == token then
            table.remove(out)
        elseif #text > #token and text:sub(-#token) == token then
            out[#out] = pandoc.Str(text:sub(1, #text - #token))
        end
        while #out > 0 and (out[#out].t == "Space" or out[#out].t == "LineBreak") do
            table.remove(out)
        end
    end
    return out
end

--- Para が "CodeBlock:" または "Figure:" 段落であれば、
--- (prefix_kind, prefix_str, body_text, para_inlines) を返す。該当しない場合は nil。
local function parse_caption_para(para)
    local text = inlines_to_text(para.content)
    text = text:match("^%s*(.-)%s*$")
    local kind, prefix
    if text:sub(1, #FIGURE_PREFIX) == FIGURE_PREFIX then
        kind, prefix = "Figure", FIGURE_PREFIX
    elseif text:sub(1, #CODEBLOCK_PREFIX) == CODEBLOCK_PREFIX then
        kind, prefix = "CodeBlock", CODEBLOCK_PREFIX
    else
        return nil
    end
    local body = text:sub(#prefix + 1):match("^%s*(.-)%s*$")
    if body == "" then
        return nil
    end
    return kind, prefix, body, para.content
end

--- 廃止したフェンス属性 caption を検出したことを警告する。
local function warn_obsolete_attribute(caption)
    warn("フェンス属性の caption ('%s') は廃止されました。ブロックの直後の 'CodeBlock:' または 'Figure:' 行へ移してください。", caption)
end

--- コードブロックが図言語 (plantuml / mermaid 等) かを判定する。
local function is_diagram_codeblock(code_block)
    for _, cls in ipairs(code_block.classes) do
        if DIAGRAM_LANGUAGES[cls] then
            return true
        end
    end
    return false
end

--- キャプション行種別とラベル接頭辞の整合性を確認し、不一致なら警告する。
local function check_label_prefix(kind, label, allow_fig_on_codeblock)
    if not label then
        return
    end
    local lprefix = label:match("^([^:]+):")
    if not lprefix then
        return
    end
    if kind == "Figure" and lprefix ~= "fig" then
        warn("'Figure:' 行に図以外のラベル接頭辞 '{#%s}' が指定されています。", label)
    elseif kind == "CodeBlock" and lprefix ~= "lst" and not (allow_fig_on_codeblock and lprefix == "fig") then
        warn("'CodeBlock:' 行にリスト以外のラベル接頭辞 '{#%s}' が指定されています。", label)
    end
end

--- コードブロックへキャプションとラベルを設定する。
local function apply_to_codeblock(code_block, kind, body)
    local caption, label = split_label(body)
    if caption == "" then
        -- ラベルのみの記載はキャプションとして扱わない
        return false
    end

    local is_diagram = is_diagram_codeblock(code_block)
    if kind == "Figure" and not is_diagram then
        warn("図以外のコード ブロックに対して 'Figure:' が使われています。通常コード ブロックには 'CodeBlock:' を使用してください。")
    end
    check_label_prefix(kind, label, is_diagram)

    if code_block.attributes["caption"] then
        warn_obsolete_attribute(code_block.attributes["caption"])
    end
    code_block.attributes["caption"] = caption
    -- 後段の掃除で、廃止した記法との区別に用いる
    code_block.attributes[SOURCE_MARK] = "line"

    if label then
        code_block.identifier = label
    end
    return true
end

--- ブロックが画像 1 個だけを含む段落 (または Figure) かを判定し、
--- 該当する場合は (kind_tag, img_elem, existing_fig_elem) を返す。
--- kind_tag: "figure" | "para"
local function extract_single_image(block)
    if block.t == "Para" and #block.content == 1 and block.content[1].t == "Image" then
        return "para", block.content[1], nil
    end
    if block.t == "Figure" and #block.content == 1 then
        local inner = block.content[1]
        if (inner.t == "Plain" or inner.t == "Para") and #inner.content == 1 and inner.content[1].t == "Image" then
            return "figure", inner.content[1], block
        end
    end
    return nil, nil, nil
end

--- 画像ブロック (Para[Image] または Figure) へ Figure: 行を適用する。
--- 戻り値: (consumed_bool, replacement_block_or_nil)
local function apply_to_image(block, kind, prefix, body, para_inlines)
    if kind ~= "Figure" then
        -- 画像の後の CodeBlock: は受け付けない
        return false, nil
    end
    local tag, img, existing_fig = extract_single_image(block)
    if not tag then
        return false, nil
    end

    local caption_text, label = split_label(body)
    if caption_text == "" then
        return false, nil
    end
    check_label_prefix(kind, label)

    local caption_inlines = extract_figure_inlines(para_inlines, prefix, label)
    if #caption_inlines == 0 then
        return false, nil
    end

    -- 代替テキストが空の場合はキャプション文字列を alt 属性へ設定する
    if #img.caption == 0 then
        img.caption = caption_inlines
    end

    local existing_id = ""
    if existing_fig and existing_fig.identifier ~= "" then
        existing_id = existing_fig.identifier
    elseif img.identifier ~= "" then
        existing_id = img.identifier
    end

    local final_id = existing_id
    if label then
        if existing_id ~= "" and existing_id ~= label then
            warn("画像の属性ラベル '{#%s}' と 'Figure:' 行のラベル '{#%s}' が競合しています。'Figure:' 行のラベルを採用します。",
                existing_id, label)
        end
        final_id = label
        img.identifier = ""
    end

    local attr
    if existing_fig then
        attr = pandoc.Attr(final_id, existing_fig.classes, existing_fig.attributes)
    else
        attr = pandoc.Attr(final_id)
    end
    local fig_caption = pandoc.Caption({ pandoc.Plain(caption_inlines) })
    local fig = pandoc.Figure(
        { pandoc.Plain({ img }) },
        fig_caption,
        attr
    )
    return true, fig
end

return {
    {
        Blocks = function(blocks)
            local result = pandoc.Blocks({})
            local index = 1
            while index <= #blocks do
                local current = blocks[index]
                local following = blocks[index + 1]

                local consumed = false
                if following ~= nil and following.t == "Para" then
                    local kind, prefix, body, para_inlines = parse_caption_para(following)
                    if kind ~= nil then
                        if current.t == "CodeBlock" then
                            consumed = apply_to_codeblock(current, kind, body)
                        else
                            local ok, replaced = apply_to_image(current, kind, prefix, body, para_inlines)
                            if ok then
                                current = replaced
                                consumed = true
                            end
                        end
                    end
                end

                result:insert(current)
                if consumed then
                    -- キャプション段落を取り込んだので、段落自体は出力しない
                    index = index + 2
                else
                    index = index + 1
                end
            end
            return result
        end
    },
    {
        -- キャプション行に由来しない caption 属性は廃止した記法のため、警告して破棄する
        CodeBlock = function(elem)
            if elem.attributes[SOURCE_MARK] then
                elem.attributes[SOURCE_MARK] = nil
                return elem
            end
            if elem.attributes["caption"] then
                warn_obsolete_attribute(elem.attributes["caption"])
                elem.attributes["caption"] = nil
                return elem
            end
            return nil
        end
    }
}
