#!/usr/bin/env python3
"""本文の見出しレベルに基づき、ページ内目次へ番号を挿入する。"""

from html.parser import HTMLParser
import re


def alphabetic(number):
    """CSS lower-alpha と同じ a … z, aa … の番号を返す。"""
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(97 + remainder) + letters
    return letters


class HeadingNumbers(HTMLParser):
    def __init__(self):
        super().__init__()
        self.counts = [0] * 5
        self.numbers = {}

    def handle_starttag(self, tag, attrs):
        if tag not in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return
        level = int(tag[1])
        if level == 1:
            self.counts = [0] * 5
            return
        index = level - 2
        self.counts[index] += 1
        self.counts[index + 1:] = [0] * (4 - index)
        if level <= 4:
            number = ".".join(map(str, self.counts[:index + 1]))
        elif level == 5:
            number = f"({self.counts[index]})"
        else:
            number = f"({alphabetic(self.counts[index])})"
        identifier = dict(attrs).get("id")
        if identifier:
            self.numbers[identifier] = number


def on_page_content(html, page, config, files):
    parser = HeadingNumbers()
    parser.feed(html)

    def annotate(items):
        for item in items:
            # 再実行しても番号を重複させない。
            title = re.sub(r'^<span class="docsfw-toc-number">[^<]*</span> ',
                           "", item.title)
            number = parser.numbers.get(item.id)
            item.title = (f'<span class="docsfw-toc-number">{number}</span> {title}'
                          if number else title)
            annotate(item.children)

    annotate(page.toc.items)
    return html
