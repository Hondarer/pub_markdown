-- page-break-before-heading.lua
-- 見出し1~Nがページの指定位置(%)を超えた場所から始まる場合、直前に改ページを挿入
-- デフォルトは無効。メタデータで明示的に有効化した文書にのみ機能する。
--
-- 使用例 (ショートハンド):
--   pandoc input.md -o output.docx --lua-filter=page-break-before-heading.lua \
--     -M page-break-before-heading=true
--
-- 使用例 (個別設定、--metadata-file を使用):
--   # settings.yaml:
--   # page-break-before-heading:
--   #   enabled: true
--   #   threshold: 70
--   #   chars-per-page: 2000
--   #   heading-level-to: 2
--   pandoc input.md -o output.docx --lua-filter=page-break-before-heading.lua \
--     --metadata-file=settings.yaml
--
-- オプション (page-break-before-heading: 配下):
--   enabled           : フィルター有効フラグ (デフォルト: false)
--   threshold         : 改ページを挿入する閾値 [%] (デフォルト: 50)
--   chars-per-page    : 1ページあたりの推定文字数 (デフォルト: 1500)
--   heading-level-to  : 対象見出しレベルの上限 (デフォルト: 3、範囲は 1~N)
--   image-height-chars: 画像1枚あたりの推定文字数 (デフォルト: 300)
--   table-row-chars   : 表の1行あたりの推定文字数 (デフォルト: 80)

-- 設定値 (メタデータで上書き可能)
local CONFIG = {
  enabled = false,          -- フィルター有効フラグ (デフォルト: false)
  threshold = 50,           -- ページ位置の閾値 [%]
  chars_per_page = 1500,    -- 1ページあたりの推定文字数
  heading_level_to = 3,     -- 対象見出しレベルの上限 (1~この値)
  image_height_chars = 300, -- 画像1枚あたりの推定文字数 (約5行相当)
  table_row_chars = 80,     -- 表の1行あたりの推定文字数
}

-- 現在のページ内文字数カウンター
local current_page_chars = 0

-- 対象の見出しレベルか判定
local function is_target_level(level)
  return level >= 1 and level <= CONFIG.heading_level_to
end

-- 画像サイズキャッシュ (同じ画像を何度も読まないため)
local image_size_cache = {}

-- ページ高さの基準値 [px] (A4 縦、余白除く約250mm ≒ 945px @96dpi)
local PAGE_HEIGHT_PX = 945

-- 単位付き文字列をピクセルに変換 (近似)
local function parse_length_to_px(value)
  if not value then return nil end
  local num, unit = value:match("^([%d%.]+)%s*(%a*)%%?$")
  if not num then return nil end
  num = tonumber(num)
  if not num then return nil end

  unit = unit:lower()
  if unit == "px" or unit == "" then
    return num
  elseif unit == "pt" then
    return num * 1.333  -- 1pt ≒ 1.333px
  elseif unit == "cm" then
    return num * 37.8   -- 1cm ≒ 37.8px @96dpi
  elseif unit == "mm" then
    return num * 3.78   -- 1mm ≒ 3.78px @96dpi
  elseif unit == "in" then
    return num * 96     -- 1in = 96px @96dpi
  elseif value:match("%%$") then
    -- パーセント指定はページ高さに対する割合として扱う
    return PAGE_HEIGHT_PX * num / 100
  end
  return num  -- 単位不明の場合は数値をそのまま返す
end

-- PNG ファイルから高さを取得 (シグネチャ + IHDR チャンク)
local function get_png_height(path)
  local f = io.open(path, "rb")
  if not f then return nil end

  local header = f:read(24)
  f:close()

  if not header or #header < 24 then return nil end
  -- PNG シグネチャ確認
  if header:sub(1, 8) ~= "\137PNG\r\n\26\n" then return nil end
  -- IHDR チャンクの高さ (ビッグエンディアン、オフセット 20-23)
  local h1, h2, h3, h4 = header:byte(21, 24)
  return h1 * 16777216 + h2 * 65536 + h3 * 256 + h4
end

-- JPEG ファイルから高さを取得 (SOF0/SOF2 マーカー探索)
local function get_jpeg_height(path)
  local f = io.open(path, "rb")
  if not f then return nil end

  local data = f:read(65536)  -- 先頭64KBを読む
  f:close()

  if not data or #data < 2 then return nil end
  -- JPEG シグネチャ確認
  if data:sub(1, 2) ~= "\255\216" then return nil end

  local pos = 3
  while pos < #data - 8 do
    if data:byte(pos) ~= 0xFF then
      pos = pos + 1
    else
      local marker = data:byte(pos + 1)
      -- SOF0 (0xC0) または SOF2 (0xC2) を探す
      if marker == 0xC0 or marker == 0xC2 then
        local h1, h2 = data:byte(pos + 5, pos + 6)
        return h1 * 256 + h2
      elseif marker == 0xD9 then  -- EOI
        break
      elseif marker >= 0xC0 and marker <= 0xFE then
        -- セグメント長を読んでスキップ
        local len1, len2 = data:byte(pos + 2, pos + 3)
        if len1 and len2 then
          pos = pos + 2 + len1 * 256 + len2
        else
          break
        end
      else
        pos = pos + 1
      end
    end
  end
  return nil
end

-- SVG ファイルから高さを取得 (width/height 属性または viewBox から)
local function get_svg_height(path)
  local f = io.open(path, "r")
  if not f then return nil end

  -- 先頭部分のみ読む (通常 <svg> タグは先頭付近にある)
  local content = f:read(4096)
  f:close()

  if not content then return nil end

  -- <svg> タグを探す
  local svg_tag = content:match("<svg[^>]*>")
  if not svg_tag then return nil end

  -- height 属性を探す (優先)
  local height_attr = svg_tag:match('height%s*=%s*["\']([^"\']+)["\']')
  if height_attr then
    local height_px = parse_length_to_px(height_attr)
    if height_px then return height_px end
  end

  -- viewBox から取得 (viewBox="minX minY width height")
  local viewbox = svg_tag:match('viewBox%s*=%s*["\']([^"\']+)["\']')
  if viewbox then
    local _, _, _, vb_height = viewbox:match("([%d%.%-]+)%s+([%d%.%-]+)%s+([%d%.%-]+)%s+([%d%.%-]+)")
    if vb_height then
      return tonumber(vb_height)
    end
  end

  return nil
end

-- 画像ファイルから高さを取得
local function get_image_height_from_file(src)
  -- URL はスキップ
  if src:match("^https?://") then return nil end

  -- キャッシュ確認
  if image_size_cache[src] then
    return image_size_cache[src]
  end

  local height = nil
  local ext = src:lower():match("%.([^%.]+)$")

  if ext == "png" then
    height = get_png_height(src)
  elseif ext == "jpg" or ext == "jpeg" then
    height = get_jpeg_height(src)
  elseif ext == "svg" then
    height = get_svg_height(src)
  end

  -- キャッシュに保存 (nil でも保存して再試行を防ぐ)
  image_size_cache[src] = height or false
  return height
end

-- 画像の高さを推定して文字数換算で返す
-- 優先順位: 1. Markdown属性 height → 2. Markdown属性 width から推定 → 3. 実ファイル → 4. 固定値
local function estimate_image_chars(img)
  local attr = img.attr or {}
  local attributes = attr.attributes or {}

  -- 属性を取得 (Pandoc の attr 構造に対応)
  local height_attr = nil
  local width_attr = nil
  for _, pair in ipairs(attributes) do
    if pair[1] == "height" then
      height_attr = pair[2]
    elseif pair[1] == "width" then
      width_attr = pair[2]
    end
  end

  local height_px = nil

  -- 1. height 属性があればそれを使用
  if height_attr then
    height_px = parse_length_to_px(height_attr)
  end

  -- 2. width のみ指定されている場合、アスペクト比 16:9 を仮定
  if not height_px and width_attr then
    local width_px = parse_length_to_px(width_attr)
    if width_px then
      height_px = width_px * 9 / 16
    end
  end

  -- 3. 実ファイルから取得を試みる
  if not height_px and img.src then
    height_px = get_image_height_from_file(img.src)
  end

  -- 4. フォールバック: 固定値
  if not height_px then
    return CONFIG.image_height_chars
  end

  -- 高さ [px] を文字数に換算
  -- 基準: ページ高さ (945px) = chars_per_page 文字
  local chars = height_px / PAGE_HEIGHT_PX * CONFIG.chars_per_page
  return math.max(chars, 50)  -- 最低50文字相当
end

-- インライン要素の文字数を計算
local function count_inline_chars(elem)
  local count = 0
  if elem.t == "Str" then
    count = utf8.len(elem.text) or #elem.text
  elseif elem.t == "Image" then
    count = estimate_image_chars(elem)
  elseif elem.content then
    for _, child in ipairs(elem.content) do
      count = count + count_inline_chars(child)
    end
  elseif elem.c then
    if type(elem.c) == "table" then
      for _, child in ipairs(elem.c) do
        if type(child) == "table" then
          count = count + count_inline_chars(child)
        end
      end
    end
  end
  return count
end

-- 表の行数をカウント
local function count_table_rows(tbl)
  local rows = 0
  -- ヘッダー行
  if tbl.head and tbl.head.rows then
    rows = rows + #tbl.head.rows
  end
  -- ボディ行
  if tbl.bodies then
    for _, body in ipairs(tbl.bodies) do
      if body.body then
        rows = rows + #body.body
      end
    end
  end
  -- フッター行
  if tbl.foot and tbl.foot.rows then
    rows = rows + #tbl.foot.rows
  end
  -- 最低1行 + ヘッダー余白
  return math.max(rows, 1) + 1
end

-- Figure 内の画像の合計文字数を計算
local function count_figure_chars(fig)
  local count = 0
  if fig.content then
    for _, block in ipairs(fig.content) do
      if block.t == "Plain" or block.t == "Para" then
        for _, inline in ipairs(block.content or {}) do
          if inline.t == "Image" then
            count = count + estimate_image_chars(inline)
          end
        end
      end
    end
  end
  -- 画像がなければ固定値
  if count == 0 then
    count = CONFIG.image_height_chars
  end
  return count
end

-- ブロック全体の文字数を計算 (図・表対応)
local function count_block_chars(block)
  local count = 0

  if block.t == "Para" or block.t == "Plain" then
    for _, inline in ipairs(block.content or {}) do
      count = count + count_inline_chars(inline)
    end
    count = count + 20  -- 段落間余白

  elseif block.t == "CodeBlock" then
    local lines = 1
    for _ in block.text:gmatch("\n") do
      lines = lines + 1
    end
    count = lines * 40  -- 1行あたり約40文字相当

  elseif block.t == "Header" then
    for _, inline in ipairs(block.content or {}) do
      count = count + count_inline_chars(inline)
    end
    count = count + 50  -- 見出し余白

  elseif block.t == "Table" then
    local rows = count_table_rows(block)
    count = rows * CONFIG.table_row_chars

  elseif block.t == "Figure" then
    count = count_figure_chars(block) + 30  -- キャプション余白

  elseif block.t == "RawBlock" then
    -- Raw ブロック (HTML の img タグなど) は中程度のサイズと仮定
    if block.text:match("<img") or block.text:match("<figure") then
      count = CONFIG.image_height_chars
    else
      count = 50
    end

  elseif block.t == "BulletList" or block.t == "OrderedList" then
    for _, item in ipairs(block.content or {}) do
      for _, b in ipairs(item) do
        count = count + count_block_chars(b)
      end
    end
    count = count + 20  -- リスト余白

  elseif block.t == "BlockQuote" then
    for _, b in ipairs(block.content or {}) do
      count = count + count_block_chars(b)
    end
    count = count + 30  -- 引用余白

  elseif block.t == "Div" then
    for _, b in ipairs(block.content or {}) do
      count = count + count_block_chars(b)
    end
  end

  return count
end

-- DOCX 用の改ページ RawBlock を生成
local function make_page_break()
  local ooxml = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
  return pandoc.RawBlock("openxml", ooxml)
end

-- メタデータから設定を読み込み
function Meta(meta)
  local pbh = meta["page-break-before-heading"]
  if pbh == nil then return meta end

  if pbh.t == "MetaBool" then
    CONFIG.enabled = pbh.c

  elseif pbh.t == "MetaMap" then
    local m = pbh.c
    local function read_bool(key)
      if m[key] == nil then return nil end
      if m[key].t == "MetaBool" then return m[key].c end
      local s = pandoc.utils.stringify(m[key]):lower()
      return s ~= "false" and s ~= "0" and s ~= "no"
    end
    local function read_num(key)
      if m[key] == nil then return nil end
      return tonumber(pandoc.utils.stringify(m[key]))
    end

    local en = read_bool("enabled")
    if en ~= nil then CONFIG.enabled = en end
    CONFIG.threshold          = read_num("threshold") or CONFIG.threshold
    CONFIG.chars_per_page     = read_num("chars-per-page") or CONFIG.chars_per_page
    CONFIG.image_height_chars = read_num("image-height-chars") or CONFIG.image_height_chars
    CONFIG.table_row_chars    = read_num("table-row-chars") or CONFIG.table_row_chars
    local lvl = read_num("heading-level-to")
    if lvl and lvl >= 1 then CONFIG.heading_level_to = lvl end

  else
    -- 文字列フォールバック (-M page-break-before-heading=true 等)
    local s = pandoc.utils.stringify(pbh):lower()
    CONFIG.enabled = s ~= "false" and s ~= "0" and s ~= "no"
  end

  return meta
end

-- ブロックリストを処理
function Blocks(blocks)
  if not CONFIG.enabled then return blocks end
  local result = {}
  current_page_chars = 0

  for _, block in ipairs(blocks) do
    local block_chars = count_block_chars(block)

    if block.t == "Header" and is_target_level(block.level) then
      -- 現在のページ位置を計算 [%]
      local page_position = (current_page_chars % CONFIG.chars_per_page) / CONFIG.chars_per_page * 100

      if page_position >= CONFIG.threshold then
        -- 閾値を超えていたら改ページを挿入
        table.insert(result, make_page_break())
        current_page_chars = 0  -- 新しいページからカウント開始
      end
    end

    table.insert(result, block)
    current_page_chars = current_page_chars + block_chars
  end

  return result
end

-- フィルターの実行順序を指定
return {
  {Meta = Meta},
  {Blocks = Blocks},
}
