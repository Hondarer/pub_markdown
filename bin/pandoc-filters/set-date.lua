function Meta(meta)
    -- date メタデータがない場合
    if not meta.date then
      -- 環境変数 EXEC_DATE を取得
      local exec_date = os.getenv("EXEC_DATE")
      if exec_date then
        meta.date = exec_date
      else
        -- 環境変数が未設定の場合、警告メッセージを出力
        io.stderr:write("Warning: EXEC_DATE environment variable is not set.\n")
        -- 必要に応じてデフォルト値を設定
        meta.date = "Unknown Date"
      end
    end
    return meta
  end
  