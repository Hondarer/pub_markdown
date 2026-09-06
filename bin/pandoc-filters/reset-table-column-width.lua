-- Pandoc は表の区切り行 (ダッシュ) の長さの比率から列幅を計算し、
-- HTML では <colgroup><col style="width: NN%"></colgroup> として、
-- DOCX では各列の固定幅 (tblLayout=fixed) として出力する。
-- これは行の実効幅が既定の折り返し幅を超えたときに働く Pandoc 標準の
-- フォールバックで、Markdown 側で意図して指定したものではない。
-- MkDocs (python-markdown の tables 拡張) は列幅情報を一切出力せず、
-- ブラウザーの自動レイアウトに任せているため、同じ表でも Pandoc 発行側
-- だけ列幅の出方が変わってしまう。
-- 列幅を既定値に戻すことで、HTML はブラウザーの自動幅、DOCX は Word の
-- オートフィットに任せ、MkDocs 側と同じ「内容に応じた列幅」に揃える。
function Table(tbl)
    for i, colspec in ipairs(tbl.colspecs) do
        colspec[2] = pandoc.ColWidthDefault
    end
    return tbl
end
