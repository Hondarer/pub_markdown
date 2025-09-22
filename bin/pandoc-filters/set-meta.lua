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
                
                if output_format ~= "docx" then
                    -- docx 以外の場合、人数に応じて形式を変更
                    if #authors == 1 then
                        -- 1人の場合: {登録者}
                        meta.author = authors[1]
                    elseif #authors == 2 then
                        -- 2人の場合: {登録者}, {編集者}
                        meta.author = authors[1] .. ", " .. authors[2]
                    else
                        -- 3人以上の場合: {登録者}, {最終編集者} et al.
                        meta.author = authors[1] .. ", " .. authors[#authors] .. " et al."
                    end
                else
                    -- docx 形式の場合、元の著者リストを維持
                    meta.author = authors
                end
            end
        else
            -- 環境変数が未設定、または空白の場合、何もしない
        end
    end

    -- 目次に対する処理
    if FORMAT == "docx" then
        -- docx 出力の場合
        if meta.toc and meta.toc == true then
            -- meta.toc が true の場合、目次の見出しを "目次" に設定
            meta["toc-title"] = pandoc.MetaString("目次")
        end
    else
        -- docx 以外の場合、meta.toc を取り除く
        -- (html の場合、この属性が存在すると目次出力が不正になってしまう)
        meta.toc = nil
    end

    return meta
end
