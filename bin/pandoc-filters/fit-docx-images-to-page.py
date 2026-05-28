#!/usr/bin/env python3
"""
fit-docx-images-to-page.py

Pandoc が生成した DOCX 内の画像をページ本文高さに収まるよう縮小する。

Pandoc の DOCX writer は画像幅をページ幅へ縮小するが、ページ高さは上限に
しない。縦長の PlantUML / Mermaid / SVG などがページからはみ出す場合に、
DOCX の DrawingML 寸法を後処理で補正する。

Usage:
    fit-docx-images-to-page.py <docx_path>
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

REGISTER_NAMESPACES = {
    "a": NS["a"],
    "w": NS["w"],
    "wp": NS["wp"],
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
}

for prefix, uri in REGISTER_NAMESPACES.items():
    ET.register_namespace(prefix, uri)


def register_document_namespaces(xml_bytes):
    for _event, namespace in ET.iterparse(BytesIO(xml_bytes), events=("start-ns",)):
        prefix, uri = namespace
        if prefix:
            ET.register_namespace(prefix, uri)


def qname(prefix, local_name):
    return f"{{{NS[prefix]}}}{local_name}"


def get_int_attr(element, namespace_prefix, name):
    value = element.get(qname(namespace_prefix, name))
    if value is None:
        value = element.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def find_section_properties(element):
    if element.tag == qname("w", "sectPr"):
        return element
    return element.find(".//w:sectPr", NS)


def available_height_emu(section_properties):
    page_size = section_properties.find("w:pgSz", NS)
    page_margin = section_properties.find("w:pgMar", NS)
    if page_size is None or page_margin is None:
        return None

    page_height = get_int_attr(page_size, "w", "h")
    margin_top = get_int_attr(page_margin, "w", "top")
    margin_bottom = get_int_attr(page_margin, "w", "bottom")
    if page_height is None or margin_top is None or margin_bottom is None:
        return None

    body_height = page_height - margin_top - margin_bottom
    if body_height <= 0:
        return None
    return body_height * EMU_PER_TWIP


def find_fallback_height_emu(body):
    for section_properties in body.findall(".//w:sectPr", NS):
        height = available_height_emu(section_properties)
        if height is not None:
            return height
    return None


def resize_drawing_container(container, max_height_emu):
    extent = container.find("wp:extent", NS)
    if extent is None:
        return 0

    old_cx = get_int_attr(extent, "wp", "cx")
    old_cy = get_int_attr(extent, "wp", "cy")
    if old_cx is None or old_cy is None or old_cx <= 0 or old_cy <= 0:
        return 0
    if old_cy <= max_height_emu:
        return 0

    scale = max_height_emu / old_cy
    new_cx = max(1, int(old_cx * scale))
    new_cy = max(1, int(max_height_emu))
    old_cx_text = str(old_cx)
    old_cy_text = str(old_cy)

    extent.set("cx", str(new_cx))
    extent.set("cy", str(new_cy))

    for shape_extent in container.findall(".//a:xfrm/a:ext", NS):
        if (shape_extent.get("cx") == old_cx_text
                and shape_extent.get("cy") == old_cy_text):
            shape_extent.set("cx", str(new_cx))
            shape_extent.set("cy", str(new_cy))

    return 1


def resize_images(element, max_height_emu):
    changed = 0
    for inline in element.findall(".//wp:inline", NS):
        changed += resize_drawing_container(inline, max_height_emu)
    for anchor in element.findall(".//wp:anchor", NS):
        changed += resize_drawing_container(anchor, max_height_emu)
    return changed


def process_document_xml(xml_bytes):
    register_document_namespaces(xml_bytes)
    root = ET.fromstring(xml_bytes)
    body = root.find("w:body", NS)
    if body is None:
        return None, 0

    if body.find(".//w:sectPr", NS) is None:
        print("Warning: section properties not found.", file=sys.stderr)
        return None, 0

    fallback_height = find_fallback_height_emu(body)
    if fallback_height is None:
        print("Warning: available page height could not be determined.", file=sys.stderr)
        return None, 0

    changed = 0
    section_elements = []

    for child in list(body):
        section_elements.append(child)
        section_properties = find_section_properties(child)
        if section_properties is None:
            continue

        max_height = available_height_emu(section_properties) or fallback_height
        for section_element in section_elements:
            changed += resize_images(section_element, max_height)
        section_elements = []

    if section_elements:
        for section_element in section_elements:
            changed += resize_images(section_element, fallback_height)

    if changed == 0:
        return None, 0

    return ET.tostring(root, encoding="utf-8", xml_declaration=True), changed


def rewrite_docx(docx_path, document_xml):
    tmp_path = docx_path + ".tmp"
    with zipfile.ZipFile(docx_path, "r") as source:
        infos = source.infolist()
        contents = {info.filename: source.read(info.filename) for info in infos}

    contents["word/document.xml"] = document_xml

    try:
        with zipfile.ZipFile(tmp_path, "w") as target:
            for info in infos:
                data = contents[info.filename]
                target.writestr(info, data)
        os.replace(tmp_path, docx_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def main():
    if len(sys.argv) != 2:
        print("Usage: fit-docx-images-to-page.py <docx_path>", file=sys.stderr)
        sys.exit(1)

    docx_path = sys.argv[1]
    if not os.path.isfile(docx_path):
        print(f"Error: file not found: {docx_path}", file=sys.stderr)
        sys.exit(1)

    with zipfile.ZipFile(docx_path, "r") as source:
        document_xml = source.read("word/document.xml")

    new_document_xml, changed = process_document_xml(document_xml)
    if new_document_xml is None:
        return

    rewrite_docx(docx_path, new_document_xml)
    print(f"Resized {changed} image(s) to fit page height.")


if __name__ == "__main__":
    main()
