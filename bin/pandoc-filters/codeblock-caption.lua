-- caption-filter.lua
local pandoc = require("pandoc")

function CodeBlock(elem)
  -- (1) caption 属性があればそれをキャプションに
  local cap = elem.attributes["caption"]
  if cap then
    -- 属性を消す
    elem.attributes["caption"] = nil
    -- キャプション段落を作成
    local caption_para = pandoc.Div(
      { pandoc.Str(cap) },
      pandoc.Attr("", {}, { ["custom-style"] = "Source Code Caption" })
    )
    return { elem, caption_para }
  end

  -- (2) 続いて info-string (.lang:filename) フォーマットをチェック
  if #elem.classes >= 1 then
    local info = elem.classes[1]
    local lang, fname = info:match("^([^:]+):(.+)$")
    if lang and fname then
      -- 言語クラスだけ残す
      elem.classes[1] = lang
      -- ファイル名をキャプション段落に
      local caption_para = pandoc.Div(
        { pandoc.Str(fname) },
        pandoc.Attr("", {}, { ["custom-style"] = "Source Code Caption" })
      )
      return { elem, caption_para }
    end
  end

  -- (3) どちらにも該当しなければ何もしない
  return nil
end
