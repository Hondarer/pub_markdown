-- コマンドラインからメタデータを与えると上書きになる。
-- この lua フィルタは、ドキュメントにメタデータが設定されていない場合に限り値を補完する。

function Meta(meta)
    -- date メタデータがない場合
    if not meta.date then
        -- 環境変数 DOCUMENT_DATE を取得
        local document_date = os.getenv("DOCUMENT_DATE")
        if document_date and document_date ~= "" then
            meta.date = document_date
        else
            -- 環境変数が未設定、または空白の場合、何もしない
        end
    end
    
    -- author メタデータがない場合
    if not meta.author then
        -- 環境変数 DOCUMENT_AUTHOR を取得
        local document_author = os.getenv("DOCUMENT_AUTHOR")
        if document_author and document_author ~= "" then
            -- 改行で分割してリスト形式に変換
            local authors = {}
            for line in document_author:gmatch("[^\r\n]+") do
                -- 空行をスキップ
                if line:match("%S") then
                    table.insert(authors, line)
                end
            end
            
            -- authorsが空でない場合のみ設定
            if #authors > 0 then
                -- 出力形式を判定 (docx 以外かどうか)
                local output_format = FORMAT or ""
                
                if output_format ~= "docx" and #authors >= 2 then
                    -- docx 以外で著者が 2 人以上の場合、最初の著者 + "et al."
                    meta.author = authors[1] .. " et al."
                else
                    -- docx 形式または著者が 1 人の場合、元の著者を維持
                    meta.author = authors
                end
            end
        else
            -- 環境変数が未設定、または空白の場合、何もしない
        end
    end
    
    return meta
end
