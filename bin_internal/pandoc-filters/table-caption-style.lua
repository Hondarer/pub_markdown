-- table-caption-style.lua
--
-- 表のキャプションを table の外へ出し、表の前に本文幅で表示できるようにする。
-- Table: 段落は前処理 (table-caption-preprocess.py) が表の後ろへ並べ替え、
-- Pandoc の table_captions 拡張が表のキャプションとして取り込む。
-- pandoc-crossref が採番したキャプションもそのまま出すため、この
-- フィルターは pandoc-crossref より後に適用する。

function Table(elem)
    if elem.caption == nil or elem.caption.long == nil or #elem.caption.long == 0 then
        return nil
    end

    local caption = pandoc.utils.blocks_to_inlines(elem.caption.long)
    local caption_div = pandoc.Div(
        { pandoc.Plain(caption) },
        pandoc.Attr("", { "docsfw-caption", "docsfw-table-caption" })
    )
    elem.caption = pandoc.Caption()

    return { caption_div, elem }
end
