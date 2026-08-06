-- codeblock-caption-line.lua
--
-- コードブロックの直後に置かれた "CodeBlock: キャプション" 段落を、
-- 直前のコードブロックの caption 属性と identifier へ畳み込む。
--
-- 表の "Table:" と同じく、キャプションをフェンスの外に出すための記法である。
-- フェンスを ```mermaid のような素の形に保てるため、GitHub などの Web 表示でも
-- 図の描画やシンタックス ハイライトが機能する。
--
--     ```mermaid
--     sequenceDiagram
--         Alice->>John: Hello
--     ```
--
--     CodeBlock: 接続シーケンス {#fig:seq-open}
--
-- 末尾の {#fig:xxx} / {#lst:xxx} は省略可能なラベルで、pandoc-crossref による
-- 採番と相互参照に用いる。
--
-- 言語による区別は行わず、すべてのコードブロックを同じ記法で扱う。
-- キャプションの描画は後続のフィルターが担当する。
--   mermaid   -> mermaid.lua
--   plantuml  -> plantuml.lua
--   それ以外  -> codeblock-caption.lua (ラベル付きは pandoc-crossref)
--
-- 適用位置は plantuml.lua、mermaid.lua、codeblock-caption.lua のいずれよりも前。

local CAPTION_PREFIX = "CodeBlock:"

-- "CodeBlock:" 行に由来する caption であることを示す内部用の印。
-- 廃止したフェンス属性 caption と区別するために用い、処理後に取り除く。
local SOURCE_MARK = "docsfw-caption-source"

--- 警告時に表示する入力ファイル名を得る。
local function input_file_name()
    if PANDOC_STATE and PANDOC_STATE.input_files and PANDOC_STATE.input_files[1] then
        return PANDOC_STATE.input_files[1]
    end
    return "(stdin)"
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

--- Para が "CodeBlock:" 段落であればキャプション本文を返す。
--- 該当しない場合は nil を返す。
local function caption_line_body(para)
    local text = inlines_to_text(para.content)
    -- 先頭と末尾の空白を除去してから接頭辞を判定する
    text = text:match("^%s*(.-)%s*$")
    if text:sub(1, #CAPTION_PREFIX) ~= CAPTION_PREFIX then
        return nil
    end
    local body = text:sub(#CAPTION_PREFIX + 1):match("^%s*(.-)%s*$")
    if body == "" then
        return nil
    end
    return body
end

--- 廃止したフェンス属性 caption を検出したことを警告する。
local function warn_obsolete_attribute(caption)
    io.stderr:write(string.format(
        "[codeblock-caption-line] %s: フェンス属性の caption ('%s') は廃止されました。" ..
        "コード ブロックの直後の 'CodeBlock:' 行へ移してください。\n",
        input_file_name(), caption))
end

--- コードブロックへキャプションとラベルを設定する。
local function apply_caption(code_block, body)
    local caption, label = split_label(body)
    if caption == "" then
        -- ラベルのみの記載はキャプションとして扱わない
        return false
    end

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

return {
    {
        Blocks = function(blocks)
            local result = pandoc.Blocks({})
            local index = 1
            while index <= #blocks do
                local current = blocks[index]
                local following = blocks[index + 1]

                local consumed = false
                if current.t == "CodeBlock" and following ~= nil and following.t == "Para" then
                    local body = caption_line_body(following)
                    if body ~= nil then
                        consumed = apply_caption(current, body)
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
        -- "CodeBlock:" 行に由来しない caption 属性は廃止した記法のため、警告して破棄する
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
