function CodeBlock(elem)
  -- info-string が "言語:ファイル名" 形式かどうかチェック
  if #elem.classes >= 1 then
    local info = elem.classes[1]
    local lang, fname = info:match("^([^:]+):(.+)$")
    if lang and fname then
      -- (1) 元のクラス（"text:sample.txt" など）を言語部分だけに置き換え
      elem.classes[1] = lang

      -- (2) ファイル名を表示する「段落」を、属性付きで直接作成する
      local caption_para = pandoc.Div(
        { pandoc.Str(fname) },
        pandoc.Attr("", {}, {["custom-style"]="Source Code Caption"})
      )

      -- (3) コード本体(elem) → キャプション段落(caption_para) の順で返す
      return { elem, caption_para }
    end
  end

  -- info-string が "言語:ファイル名" 形式でない場合は何もしない
  return nil
end
