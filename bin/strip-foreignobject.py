#!/usr/bin/env python3
"""
strip-foreignobject.py  —  draw.io SVG の foreignObject を決定的に除去します。

foreignObject 内 HTML からレイアウト情報を抽出し、
ok.drawio.svg 形式 (nested <g> + 複数行 <text>) に変換します。

Usage:
    python strip-foreignobject.py input.svg           # stdout に出力
    python strip-foreignobject.py a.svg b.svg ...     # 複数ファイルを stdout
    python strip-foreignobject.py input.svg --in-place  # 上書き
"""

import re
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# --------------------------------------------------
# 名前空間定数
# --------------------------------------------------
SVG_NS = "http://www.w3.org/2000/svg"
XHTML_NS = "http://www.w3.org/1999/xhtml"
SVG = "{%s}" % SVG_NS
XHTML = "{%s}" % XHTML_NS

# draw.io の mxConstants.LINE_HEIGHT に由来
LINE_HEIGHT = 1.2


# --------------------------------------------------
# 数値フォーマット
# --------------------------------------------------

def fmt_num(v):
    """浮動小数点数を末尾ゼロ除去で整形 (29.5 → '29.5', 30.0 → '30')"""
    if v == int(v):
        return str(int(v))
    s = "%.10f" % v
    s = s.rstrip("0").rstrip(".")
    return s


# --------------------------------------------------
# CSS / 色 ユーティリティ
# --------------------------------------------------

def parse_style(style_str):
    """CSS style 文字列 → {プロパティ: 値} 辞書"""
    result = {}
    for part in style_str.split(";"):
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            result[k.strip()] = v.strip()
    return result


def parse_px(val, default=0.0):
    """'12px' または '12' → float"""
    val = val.strip()
    if val.endswith("px"):
        try:
            return float(val[:-2])
        except ValueError:
            return default
    try:
        return float(val)
    except ValueError:
        return default


def hex_to_rgb(h):
    """'#rrggbb' → 'rgb(r, g, b)'"""
    h = h.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return "rgb(%d, %d, %d)" % (r, g, b)


def parse_color(col):
    """
    色文字列を (fill_attr, style_value_or_None) のタプルに変換。

    - light-dark(#A, #B) → ('#A', 'fill: light-dark(rgb(...), rgb(...));')
    - #rrggbb            → ('#rrggbb', None)
    """
    col = col.strip()
    m = re.match(
        r"light-dark\(\s*(#[0-9a-fA-F]{3,6})\s*,\s*(#[0-9a-fA-F]{3,6})\s*\)",
        col,
    )
    if m:
        ca, cb = m.group(1), m.group(2)
        return ca, "fill: light-dark(%s, %s);" % (hex_to_rgb(ca), hex_to_rgb(cb))
    if re.match(r"#[0-9a-fA-F]{3,6}$", col):
        return col, None
    # 未知の形式はそのまま返す
    return col, None


# --------------------------------------------------
# translate パース
# --------------------------------------------------

def parse_translate(transform_str):
    """'translate(-0.5 -0.5)' → (-0.5, -0.5)"""
    m = re.search(
        r"translate\(\s*([+-]?\d*\.?\d+)\s+([+-]?\d*\.?\d+)\s*\)",
        transform_str,
    )
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"translate\(\s*([+-]?\d*\.?\d+)\s*\)", transform_str)
    if m:
        return float(m.group(1)), 0.0
    return 0.0, 0.0


# --------------------------------------------------
# テキスト抽出 (foreignObject 内 HTML)
# --------------------------------------------------

def collect_segments(elem):
    """
    elem 配下から ('text', str) / ('br', None) のリストを生成。
    <b>/<i>/<span> 等のインライン書式は無視し、テキストのみ収集。
    """
    result = []
    if elem.text:
        result.append(("text", elem.text))
    for child in elem:
        local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if local == "br":
            result.append(("br", None))
        else:
            result.extend(collect_segments(child))
        if child.tail:
            result.append(("text", child.tail))
    return result


def extract_lines(inner_div):
    """
    innermost div (書式 div) から行リストを抽出。
    <br/> で分割し、各行を strip。末尾の空行は除去。
    """
    segments = collect_segments(inner_div)
    lines = []
    current = ""
    for kind, val in segments:
        if kind == "br":
            lines.append(current.strip())
            current = ""
        else:
            current += val
    lines.append(current.strip())

    # 末尾の空行を除去
    while lines and lines[-1] == "":
        lines.pop()

    return lines if lines else [""]


# --------------------------------------------------
# foreignObject データ抽出
# --------------------------------------------------

def parse_foreignobject(fo_elem, tx, ty):
    """
    foreignObject ET 要素からレイアウトデータを抽出して辞書で返す。
    失敗時は None を返す。

    返す辞書のキー:
        M, W, T, tx, ty, S, font_family, color, h_align, v_align, lines
    """
    # 外側 div (配置: display:flex / align-items / justify-content / width / padding-top / margin-left)
    outer_div = None
    for child in fo_elem:
        if child.tag == XHTML + "div":
            outer_div = child
            break
    if outer_div is None:
        sys.stderr.write("警告: foreignObject に外側 div が見つかりません\n")
        return None

    outer_style = parse_style(outer_div.get("style", ""))
    W = parse_px(outer_style.get("width", "0px"))
    T = parse_px(outer_style.get("padding-top", "0px"))
    M = parse_px(outer_style.get("margin-left", "0px"))

    def normalize_align(v):
        # "unsafe center" → "center" など
        return v.replace("unsafe ", "").strip()

    v_align = normalize_align(outer_style.get("align-items", "center"))
    h_align = normalize_align(outer_style.get("justify-content", "center"))

    # 中間 div
    middle_div = None
    for child in outer_div:
        if child.tag == XHTML + "div":
            middle_div = child
            break
    if middle_div is None:
        sys.stderr.write("警告: foreignObject に中間 div が見つかりません\n")
        return None

    # 内側 div (書式: font-size / font-family / color / line-height)
    inner_div = None
    for child in middle_div:
        if child.tag == XHTML + "div":
            inner_div = child
            break
    if inner_div is None:
        sys.stderr.write("警告: foreignObject に内側 div が見つかりません\n")
        return None

    inner_style = parse_style(inner_div.get("style", ""))
    S = parse_px(inner_style.get("font-size", "12px"))
    font_family = inner_style.get("font-family", "Helvetica")
    color = inner_style.get("color", "#000000")

    lines = extract_lines(inner_div)

    return {
        "M": M,
        "W": W,
        "T": T,
        "tx": tx,
        "ty": ty,
        "S": S,
        "font_family": font_family,
        "color": color,
        "h_align": h_align,
        "v_align": v_align,
        "lines": lines,
    }


# --------------------------------------------------
# ジオメトリ計算
# --------------------------------------------------

def compute_geometry(M, W, T, tx, ty, S, n, v_align, h_align):
    """
    text-anchor="middle" の x と各行ベースライン y のリストを返す。

    定数 LINE_HEIGHT = 1.2 は mxConstants 由来。
    ng.drawio.svg ↔ ok.drawio.svg ペアで完全検証済み:
        M=1, W=58, T=15, tx=ty=-0.5, S=12, n=2 → x=29.5, ys=[12.5, 26.5]
    """
    line_h = round(S * LINE_HEIGHT)
    text_h = n * line_h

    # 水平位置
    if h_align in ("flex-start", "start"):
        x = M + tx
    elif h_align in ("flex-end", "end"):
        x = M + W + tx
    else:
        # center (drawio 既定)
        x = M + W / 2 + tx

    # テキスト ブロック上端
    center_y = T + ty
    if v_align in ("flex-start", "start", "top"):
        top = center_y
    elif v_align in ("flex-end", "end", "bottom"):
        top = center_y - text_h
    else:
        # center (drawio 既定)
        top = center_y - text_h / 2

    # 各行ベースライン y (ascent = font-size S)
    ys = [top + i * line_h + S for i in range(n)]
    return x, ys


# --------------------------------------------------
# SVG 置換テキスト生成
# --------------------------------------------------

def generate_replacement(indent, data, x, ys):
    """
    foreignObject を置き換える <g> + <text> ブロックを生成する。

    indent: 開始タグのインデント文字列 (スペース)。
    """
    fill_attr, style_val = parse_color(data["color"])

    # text-anchor
    h_align = data["h_align"]
    if h_align in ("start", "flex-start"):
        anchor = "start"
    elif h_align in ("end", "flex-end"):
        anchor = "end"
    else:
        anchor = "middle"

    # font-family: CSS 内のダブルクォートを XML エスケープ
    ff_escaped = data["font_family"].replace('"', "&quot;")

    # <g> 属性
    g_attrs = 'fill="%s" font-family="%s" text-anchor="%s" font-size="%spx"' % (
        fill_attr,
        ff_escaped,
        anchor,
        fmt_num(data["S"]),
    )
    if style_val:
        g_attrs += ' style="%s"' % style_val

    # <text> 行群
    lines_xml = ""
    for line, y in zip(data["lines"], ys):
        line_esc = (
            line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        lines_xml += "%s    <text x=\"%s\" y=\"%s\">%s</text>\n" % (
            indent,
            fmt_num(x),
            fmt_num(y),
            line_esc,
        )

    # 先頭インデントなし: text[i:block_start] がすでに \n + indent を含む
    result = "<g %s>\n" % g_attrs
    result += lines_xml
    result += "%s</g>" % indent
    return result


# --------------------------------------------------
# テキスト上での <g>...</g> ブロック境界検索
# --------------------------------------------------

_GTAG_RE = re.compile(r"<(/?)g([^>]*)>", re.DOTALL)


def find_close_g(text, start):
    """
    start の位置 (開始 <g...> の直後) から、対応する </g> の直後位置を返す。
    depth=1 の状態から開始し、対応する </g> で depth=0 になったときの位置。
    """
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        m = _GTAG_RE.search(text, i)
        if not m:
            break
        is_closing = m.group(1) == "/"
        # attrs の末尾が "/" なら自己終了タグ (<g .../>)
        attrs = m.group(2)
        is_self_closing = attrs.rstrip().endswith("/")

        if is_closing:
            depth -= 1
        elif not is_self_closing:
            depth += 1

        if depth == 0:
            return m.end()
        i = m.end()
    return len(text)


# --------------------------------------------------
# ブロック内 ET 解析
# --------------------------------------------------

def parse_fo_from_block(block_text, tx, ty):
    """
    translate-g ブロック (生テキスト) を ET で解析し、
    foreignObject データを抽出して返す。失敗時は例外を送出。
    """
    # ET で解析するために SVG 名前空間をルートに宣言してラップ
    wrapped = (
        '<_root xmlns="http://www.w3.org/2000/svg"'
        ' xmlns:xlink="http://www.w3.org/1999/xlink">'
        + block_text
        + "</_root>"
    )
    try:
        root = ET.fromstring(wrapped)
    except ET.ParseError as e:
        raise ValueError("XML 解析エラー: %s" % e)

    # <g transform="translate(...)"> の直下を探す
    translate_g = root.find(SVG + "g")
    if translate_g is None:
        translate_g = root

    switch_elem = translate_g.find(SVG + "switch")
    if switch_elem is None:
        raise ValueError("<switch> が見つかりません")

    fo_elem = switch_elem.find(SVG + "foreignObject")
    if fo_elem is None:
        raise ValueError("<foreignObject> が見つかりません")

    return parse_foreignobject(fo_elem, tx, ty)


# --------------------------------------------------
# フッター switch 除去
# --------------------------------------------------

_FOOTER_SWITCH_RE = re.compile(
    r"\s*<switch>"
    r"\s*<g\s[^>]*requiredFeatures="
    r'"http://www\.w3\.org/TR/SVG11/feature#Extensibility"[^>]*/>'
    r"\s*<a\s[^>]*drawio\.com[^>]*>.*?</a>"
    r"\s*</switch>",
    re.DOTALL,
)


def remove_footer_switch(text):
    """フッターの <switch>...</switch> (drawio.com リンク) を除去する。"""
    return _FOOTER_SWITCH_RE.sub("", text)


# --------------------------------------------------
# メイン変換
# --------------------------------------------------

_TRANSLATE_G_RE = re.compile(
    r'<g\s+transform\s*=\s*"translate\(([^)]+)\)"([^>]*)>',
    re.DOTALL,
)


def process_svg(text):
    """
    SVG テキストを変換して foreignObject を除去した SVG テキストを返す。
    foreignObject を持たない要素はすべて原文を温存する。
    """
    result = []
    i = 0
    replaced = 0

    while i < len(text):
        m = _TRANSLATE_G_RE.search(text, i)
        if not m:
            result.append(text[i:])
            break

        translate_str = m.group(1)
        tx, ty = parse_translate("translate(%s)" % translate_str)

        block_start = m.start()
        block_end = find_close_g(text, m.end())
        block_text = text[block_start:block_end]

        if "<foreignObject" not in block_text:
            # foreignObject なし → 温存して次へ
            result.append(text[i : m.end()])
            i = m.end()
            continue

        # データ抽出
        try:
            data = parse_fo_from_block(block_text, tx, ty)
        except Exception as e:
            sys.stderr.write(
                "警告: foreignObject の解析に失敗しました (%s) — ブロックを温存します\n" % e
            )
            result.append(text[i : m.end()])
            i = m.end()
            continue

        if data is None:
            result.append(text[i : m.end()])
            i = m.end()
            continue

        # ジオメトリ計算
        x, ys = compute_geometry(
            data["M"],
            data["W"],
            data["T"],
            data["tx"],
            data["ty"],
            data["S"],
            len(data["lines"]),
            data["v_align"],
            data["h_align"],
        )

        # インデント検出 (block_start より前の行頭から)
        line_start = text.rfind("\n", 0, block_start)
        if line_start == -1:
            indent = ""
        else:
            raw_indent = text[line_start + 1 : block_start]
            indent = " " * (len(raw_indent) - len(raw_indent.lstrip()))

        # 置換テキスト生成
        replacement = generate_replacement(indent, data, x, ys)

        result.append(text[i:block_start])
        result.append(replacement)
        i = block_end
        replaced += 1

    output = "".join(result)

    if replaced > 0:
        output = remove_footer_switch(output)
        sys.stderr.write("情報: %d 個の foreignObject を変換しました\n" % replaced)
    else:
        sys.stderr.write("情報: foreignObject は見つかりませんでした (変換不要)\n")

    return output


# --------------------------------------------------
# CLI エントリ ポイント
# --------------------------------------------------

def main():
    args = sys.argv[1:]
    in_place = "--in-place" in args
    files = [a for a in args if not a.startswith("--")]

    if not files:
        sys.stderr.write(
            "使用方法: strip-foreignobject.py <input.svg> [--in-place]\n"
        )
        sys.exit(1)

    for path in files:
        with open(path, encoding="utf-8") as f:
            text = f.read()

        out = process_svg(text)

        if in_place:
            with open(path, "w", encoding="utf-8") as f:
                f.write(out)
            sys.stderr.write("書き込み: %s\n" % path)
        else:
            sys.stdout.write(out)


if __name__ == "__main__":
    main()
