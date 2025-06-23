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
                meta.author = authors
            end
        else
            -- 環境変数が未設定、または空白の場合、何もしない
        end
    end
    
    return meta
end
