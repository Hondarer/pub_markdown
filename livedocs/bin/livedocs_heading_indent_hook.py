#!/usr/bin/env python3
"""Markdown の H5 以降の見出しと配下の本文を字下げするクラスを付ける。

静的発行の heading-content-indent.lua と同じ構造を出力する。
見出しに docsfw-heading-indent-N クラスを付け、次の見出しまでの本文を同じクラスの
div で囲む。N は H5 が 1、H6 が 2 で、CSS が 1 段ごとに 7.5mm を字下げする。
見出しは div の外に残し、CSS カウンターと目次の参照先を変えない。
水平線は区切りのため、前後の字下げのうち浅い方で引く。文書の末尾は字下げ 0 とみなす。
"""

import re
import xml.etree.ElementTree as etree

from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

FIRST_INDENTED_LEVEL = 5
HEADING = re.compile(r"h([1-6])")


def indent_class(depth):
    return f"docsfw-heading-indent-{depth}"


def heading_depth(element):
    match = HEADING.fullmatch(element.tag) if isinstance(element.tag, str) else None
    if match is None:
        return None
    return max(0, int(match.group(1)) - FIRST_INDENTED_LEVEL + 1)


class HeadingIndentTreeprocessor(Treeprocessor):
    def run(self, root):
        children = list(root)
        depth = 0
        wrapper = None

        def wrap(child, child_depth, current):
            if current is None:
                current = etree.Element("div", {"class": indent_class(child_depth)})
                root.insert(list(root).index(child), current)
            root.remove(child)
            current.append(child)
            return current

        for index, child in enumerate(children):
            level_depth = heading_depth(child)
            if level_depth is not None:
                depth = level_depth
                wrapper = None
                if depth:
                    classes = child.get("class", "").split()
                    if indent_class(depth) not in classes:
                        child.set("class", " ".join(classes + [indent_class(depth)]))
                continue
            if child.tag == "hr":
                # 水平線は前後の字下げのうち浅い方で引く。
                following = children[index + 1] if index + 1 < len(children) else None
                next_depth = 0 if following is None else heading_depth(following)
                if next_depth is not None and next_depth < depth:
                    wrapper = None
                    if next_depth:
                        wrap(child, next_depth, None)
                    continue
            if not depth:
                continue
            wrapper = wrap(child, depth, wrapper)


class HeadingIndentExtension(Extension):
    def extendMarkdown(self, md):
        # 見出しの id を付ける toc (優先度 5) より後に、ほかの拡張が作った要素も囲む。
        md.treeprocessors.register(HeadingIndentTreeprocessor(md), "docsfw_heading_indent", 4)


def on_config(config):
    # 同じ設定で on_config が再実行されても、拡張を重複して登録しない。
    if not any(isinstance(item, HeadingIndentExtension) for item in config.markdown_extensions):
        config.markdown_extensions.append(HeadingIndentExtension())
    return config
