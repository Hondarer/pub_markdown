function Meta(meta)
    -- date メタデータがない場合
    if not meta.date then
      -- 環境変数 EXEC_DATE を取得
      local exec_date = os.getenv("EXEC_DATE")
      if exec_date then
        meta.date = exec_date
      else
        -- 環境変数が未設定の場合、何もしない
      end
    end
    return meta
  end
  