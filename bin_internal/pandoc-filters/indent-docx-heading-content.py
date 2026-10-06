#!/usr/bin/env python3
"""
indent-docx-heading-content.py

Pandoc が生成した DOCX の本文を、直前の見出しと同じ位置まで字下げする。

見出しの字下げは docx テンプレートの見出しスタイル (段落番号を含む) が持つ。
本文の段落スタイルは見出しのレベルを区別できないため、見出しの字下げ位置を
本文の各段落の左インデントへ後処理で加算する。

- 段落: スタイル、段落番号、直接指定から求めた左インデントに加算する。
- 画像: 字下げ後の本文幅を超える場合は縦横比を保って縮小する。
- 表と表の表題: Word は中央揃えの表に左インデントを適用しないため、字下げしない。
- 水平線: 前後の字下げのうち浅い方で引く。上位の見出しの直前では字下げを戻す。

Usage:
    indent-docx-heading-content.py <docx_path>
"""

import os
import sys
import zipfile
from io import BytesIO
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

EMU_PER_TWIP = 635

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}

# 字下げしない段落スタイルの名前 (styleId ではなく w:name で判定する)。
EXCLUDED_STYLE_NAMES = {"Table Caption"}

# CT_PPrBase の子要素の順序。w:ind はこの一覧の末尾より後ろに置く。
PPR_ELEMENTS_BEFORE_IND = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr",
    "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap",
    "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing",
]


def register_document_namespaces(xml_bytes):
    for _event, namespace in ET.iterparse(BytesIO(xml_bytes), events=("start-ns",)):
        prefix, uri = namespace
        if prefix:
            ET.register_namespace(prefix, uri)


def qname(prefix, local_name):
    return f"{{{NS[prefix]}}}{local_name}"


def w_attr(element, name):
    if element is None:
        return None
    return element.get(qname("w", name))


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class Indent:
    """w:ind の左端に関わる値。None は未指定を表す。"""

    def __init__(self, element=None):
        self.left = to_int(w_attr(element, "left") or w_attr(element, "start"))
        self.hanging = to_int(w_attr(element, "hanging"))
        self.first_line = to_int(w_attr(element, "firstLine"))

    def merge(self, fallback):
        """未指定の値を fallback で補う。Word は w:ind の属性ごとに継承する。"""
        merged = Indent()
        for name in ("left", "hanging", "first_line"):
            value = getattr(self, name)
            setattr(merged, name, value if value is not None else getattr(fallback, name))
        return merged

    def first_line_position(self):
        position = self.left or 0
        if self.hanging is not None:
            return position - self.hanging
        return position + (self.first_line or 0)


class StyleSheet:
    """styles.xml と numbering.xml から、段落の字下げと見出しレベルを求める。"""

    def __init__(self, styles_xml, numbering_xml):
        self.styles = {}
        if styles_xml is not None:
            for style in ET.fromstring(styles_xml).findall("w:style", NS):
                self.styles[w_attr(style, "styleId")] = style
        self.nums = {}
        self.abstract_nums = {}
        if numbering_xml is not None:
            numbering = ET.fromstring(numbering_xml)
            for num in numbering.findall("w:num", NS):
                self.nums[w_attr(num, "numId")] = w_attr(num.find("w:abstractNumId", NS), "val")
            for abstract in numbering.findall("w:abstractNum", NS):
                self.abstract_nums[w_attr(abstract, "abstractNumId")] = abstract

    def style_chain(self, style_id):
        seen = set()
        while style_id in self.styles and style_id not in seen:
            seen.add(style_id)
            style = self.styles[style_id]
            yield style
            style_id = w_attr(style.find("w:basedOn", NS), "val")

    def style_name(self, style_id):
        style = self.styles.get(style_id)
        return w_attr(style.find("w:name", NS), "val") if style is not None else None

    def style_ppr_value(self, style_id, path):
        for style in self.style_chain(style_id):
            element = style.find("w:pPr/" + path, NS)
            if element is not None:
                return element
        return None

    def outline_level(self, ppr, style_id):
        element = ppr.find("w:outlineLvl", NS) if ppr is not None else None
        if element is None:
            element = self.style_ppr_value(style_id, "w:outlineLvl")
        level = to_int(w_attr(element, "val"))
        # 9 は本文を表す。
        return level if level is not None and level < 9 else None

    def numbering_indent(self, num_id, ilvl, depth=0):
        abstract = self.abstract_nums.get(self.nums.get(num_id))
        if abstract is None or depth > 4:
            return Indent()
        # 段落番号のスタイル定義を参照する定義は、参照先のスタイルの番号をたどる。
        link = w_attr(abstract.find("w:numStyleLink", NS), "val")
        if link is not None:
            linked = self.style_ppr_value(link, "w:numPr/w:numId")
            if linked is not None:
                return self.numbering_indent(w_attr(linked, "val"), ilvl, depth + 1)
            return Indent()
        for level in abstract.findall("w:lvl", NS):
            if w_attr(level, "ilvl") == ilvl:
                return Indent(level.find("w:pPr/w:ind", NS))
        return Indent()

    def effective_indent(self, ppr, style_id):
        """直接指定、段落番号、スタイルの優先順位で左端の字下げを求める。"""
        direct = Indent(ppr.find("w:ind", NS) if ppr is not None else None)
        num_pr = ppr.find("w:numPr", NS) if ppr is not None else None
        if num_pr is None:
            num_pr = self.style_ppr_value(style_id, "w:numPr")
        numbered = Indent()
        if num_pr is not None:
            num_id = w_attr(num_pr.find("w:numId", NS), "val")
            ilvl = w_attr(num_pr.find("w:ilvl", NS), "val") or "0"
            if num_id is None and style_id is not None:
                linked = self.style_ppr_value(style_id, "w:numPr/w:numId")
                num_id = w_attr(linked, "val")
            if num_id not in (None, "0"):
                numbered = self.numbering_indent(num_id, ilvl)
        styled = Indent(self.style_ppr_value(style_id, "w:ind"))
        return direct.merge(numbered).merge(styled)


def paragraph_style(ppr):
    return w_attr(ppr.find("w:pStyle", NS), "val") if ppr is not None else None


def is_horizontal_rule(paragraph, ppr):
    """horizontal-rule.lua が出力する、下罫線だけを持つ空の段落か判定する。"""
    if ppr is None or ppr.find("w:pStyle", NS) is not None or ppr.find("w:pBdr/w:bottom", NS) is None:
        return False
    return all(child.tag == qname("w", "pPr") for child in paragraph)


def ensure_ppr(paragraph):
    ppr = paragraph.find("w:pPr", NS)
    if ppr is None:
        ppr = ET.Element(qname("w", "pPr"))
        paragraph.insert(0, ppr)
    return ppr


def ensure_ind(ppr):
    ind = ppr.find("w:ind", NS)
    if ind is not None:
        return ind
    ind = ET.Element(qname("w", "ind"))
    position = 0
    for index, child in enumerate(list(ppr)):
        if child.tag.split("}")[1] in PPR_ELEMENTS_BEFORE_IND:
            position = index + 1
    ppr.insert(position, ind)
    return ind


def indent_paragraph(paragraph, delta, sheet):
    ppr = ensure_ppr(paragraph)
    style_id = paragraph_style(ppr)
    current = sheet.effective_indent(ppr, style_id)
    ind = ensure_ind(ppr)
    if ind.get(qname("w", "start")) is not None:
        del ind.attrib[qname("w", "start")]
    ind.set(qname("w", "left"), str((current.left or 0) + delta))
    # 段落番号やスタイルの値を直接指定へ写し、ぶら下げと 1 行目の位置を保つ。
    if current.hanging is not None:
        ind.set(qname("w", "hanging"), str(current.hanging))
    elif current.first_line is not None:
        ind.set(qname("w", "firstLine"), str(current.first_line))


def shrink_images(paragraph, max_width_emu):
    changed = 0
    for container in paragraph.findall(".//wp:inline", NS) + paragraph.findall(".//wp:anchor", NS):
        extent = container.find("wp:extent", NS)
        if extent is None:
            continue
        old_cx = to_int(extent.get("cx"))
        old_cy = to_int(extent.get("cy"))
        if old_cx is None or old_cy is None or old_cx <= max_width_emu or old_cx <= 0:
            continue
        scale = max_width_emu / old_cx
        new_cx = max(1, int(max_width_emu))
        new_cy = max(1, int(old_cy * scale))
        for shape_extent in [extent] + container.findall(".//a:xfrm/a:ext", NS):
            if shape_extent.get("cx") == str(old_cx) and shape_extent.get("cy") == str(old_cy):
                shape_extent.set("cx", str(new_cx))
                shape_extent.set("cy", str(new_cy))
        changed += 1
    return changed


def text_width_twip(body):
    section = body.find("w:sectPr", NS)
    if section is None:
        sections = body.findall(".//w:sectPr", NS)
        section = sections[-1] if sections else None
    page_size = section.find("w:pgSz", NS) if section is not None else None
    margin = section.find("w:pgMar", NS) if section is not None else None
    width = to_int(w_attr(page_size, "w"))
    left = to_int(w_attr(margin, "left"))
    right = to_int(w_attr(margin, "right"))
    if width is None or left is None or right is None:
        return None
    return width - left - right


class Indenter:
    def __init__(self, sheet, text_width):
        self.sheet = sheet
        self.text_width = text_width
        self.delta = 0
        self.paragraphs = 0
        self.images = 0

    def process_blocks(self, container):
        children = [child for child in container
                    if child.tag in (qname("w", "p"), qname("w", "tbl"), qname("w", "sdt"))]
        for index, child in enumerate(children):
            if child.tag == qname("w", "p"):
                following = children[index + 1] if index + 1 < len(children) else None
                self.process_paragraph(child, following)
            elif child.tag == qname("w", "sdt"):
                content = child.find("w:sdtContent", NS)
                if content is not None:
                    self.process_blocks(content)
            # 表 (w:tbl) は字下げしない。

    def heading_indent(self, paragraph):
        """見出しの段落なら 1 行目の位置を返し、見出しでなければ None を返す。"""
        if paragraph is None or paragraph.tag != qname("w", "p"):
            return None
        ppr = paragraph.find("w:pPr", NS)
        style_id = paragraph_style(ppr)
        if self.sheet.outline_level(ppr, style_id) is None:
            return None
        return max(0, self.sheet.effective_indent(ppr, style_id).first_line_position())

    def process_paragraph(self, paragraph, following):
        heading = self.heading_indent(paragraph)
        if heading is not None:
            # 以降の本文は、この見出しの 1 行目の位置まで字下げする。
            self.delta = heading
            return
        ppr = paragraph.find("w:pPr", NS)
        style_id = paragraph_style(ppr)
        if self.delta <= 0 or self.sheet.style_name(style_id) in EXCLUDED_STYLE_NAMES:
            return
        if is_horizontal_rule(paragraph, ppr):
            # 水平線は前後の字下げのうち浅い方で引く。文書の末尾は字下げ 0 とみなす。
            next_indent = 0 if following is None else self.heading_indent(following)
            delta = self.delta if next_indent is None else min(self.delta, next_indent)
            if delta > 0:
                indent_paragraph(paragraph, delta, self.sheet)
                self.paragraphs += 1
            return
        indent_paragraph(paragraph, self.delta, self.sheet)
        self.paragraphs += 1
        if self.text_width is not None:
            self.images += shrink_images(paragraph, (self.text_width - self.delta) * EMU_PER_TWIP)


def process_docx_parts(document_xml, styles_xml, numbering_xml):
    register_document_namespaces(document_xml)
    root = ET.fromstring(document_xml)
    body = root.find("w:body", NS)
    if body is None:
        return None, 0, 0
    indenter = Indenter(StyleSheet(styles_xml, numbering_xml), text_width_twip(body))
    indenter.process_blocks(body)
    if indenter.paragraphs == 0:
        return None, 0, 0
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), indenter.paragraphs, indenter.images


def rewrite_docx(docx_path, document_xml):
    tmp_path = docx_path + ".tmp"
    with zipfile.ZipFile(docx_path, "r") as source:
        infos = source.infolist()
        contents = {info.filename: source.read(info.filename) for info in infos}

    contents["word/document.xml"] = document_xml

    try:
        with zipfile.ZipFile(tmp_path, "w") as target:
            for info in infos:
                target.writestr(info, contents[info.filename])
        os.replace(tmp_path, docx_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def main():
    if len(sys.argv) != 2:
        print("Usage: indent-docx-heading-content.py <docx_path>", file=sys.stderr)
        sys.exit(1)

    docx_path = sys.argv[1]
    if not os.path.isfile(docx_path):
        print(f"Error: file not found: {docx_path}", file=sys.stderr)
        sys.exit(1)

    with zipfile.ZipFile(docx_path, "r") as source:
        names = set(source.namelist())
        document_xml = source.read("word/document.xml")
        styles_xml = source.read("word/styles.xml") if "word/styles.xml" in names else None
        numbering_xml = source.read("word/numbering.xml") if "word/numbering.xml" in names else None

    new_document_xml, paragraphs, images = process_docx_parts(document_xml, styles_xml, numbering_xml)
    if new_document_xml is None:
        return

    rewrite_docx(docx_path, new_document_xml)
    print(f"Indented {paragraphs} paragraph(s) under headings; resized {images} image(s).")


if __name__ == "__main__":
    main()
