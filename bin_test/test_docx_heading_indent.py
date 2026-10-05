"""docx の見出し配下の字下げ後処理を、実テンプレートで生成した docx で検証する。"""

import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin_internal/pandoc-filters/indent-docx-heading-content.py"
TEMPLATE = ROOT / "styles/docx/docx-template.dotx"
IMAGE = ROOT / "docs/sample/images/docx-category.png"

# テンプレートの見出し 4 / 5 (Markdown の H5 / H6) は 7.5mm / 15mm 字下げする。
H5_INDENT = 425
H6_INDENT = 851

MARKDOWN = f"""# Title

## Chapter

#### Item

Under item.

##### Level five

Body five.

- bullet

```c
int x;
```

| a | b |
|---|---|
| 1 | 2 |

Table: caption five

![figure]({IMAGE.as_posix()})

> quote

###### Level six

Body six.

#### Next item

Back to item.
"""


def paragraphs(document):
    """(段落スタイル, w:ind の属性, テキスト) を本文の順に返す。"""
    result = []
    for match in re.finditer(r"<w:p>.*?</w:p>|<w:p .*?</w:p>|<w:tbl>.*?</w:tbl>", document, re.S):
        block = match.group(0)
        if block.startswith("<w:tbl>"):
            result.append(("TABLE", re.search(r"<w:tblPr>.*?</w:tblPr>", block, re.S).group(0), ""))
            continue
        style = re.search(r'<w:pStyle w:val="([^"]*)"', block)
        ind = re.search(r"<w:ind ([^/]*)/>", block)
        text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", block))
        result.append((style.group(1) if style else "", ind.group(1).strip() if ind else "", text))
    return result


class DocxHeadingIndentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        docx = Path(cls.temporary.name) / "out.docx"
        subprocess.run(["pandoc", "-f", "markdown", "-t", "docx", "--shift-heading-level-by=-1",
                        "--reference-doc", str(TEMPLATE), "-o", str(docx)],
                       input=MARKDOWN, encoding="utf-8", check=True, capture_output=True)
        with zipfile.ZipFile(docx) as source:
            cls.before = source.read("word/document.xml").decode("utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), str(docx)], capture_output=True,
                                encoding="utf-8", check=True)
        cls.stdout = result.stdout
        with zipfile.ZipFile(docx) as source:
            cls.after = source.read("word/document.xml").decode("utf-8")
        page = re.search(r'<w:pgSz [^>]*w:w="(\d+)"', cls.after)
        margin = re.search(r'<w:pgMar [^>]*w:left="(\d+)"[^>]*w:right="(\d+)"', cls.after) or \
            re.search(r'<w:pgMar [^>]*w:right="(\d+)"[^>]*w:left="(\d+)"', cls.after)
        cls.text_width = int(page.group(1)) - int(margin.group(1)) - int(margin.group(2))
        cls.blocks = paragraphs(cls.after)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def block(self, text):
        return next(block for block in self.blocks if block[2] == text)

    def test_body_follows_the_preceding_heading_indent(self):
        self.assertEqual(self.block("Under item.")[1], "")
        self.assertEqual(self.block("Body five.")[1], f'w:left="{H5_INDENT}"')
        self.assertEqual(self.block("Body six.")[1], f'w:left="{H6_INDENT}"')
        # 上位の見出しへ戻ると字下げしない。
        self.assertEqual(self.block("Back to item.")[1], "")

    def test_headings_keep_the_template_indent(self):
        for text in ("Level five", "Level six", "Next item"):
            self.assertEqual(self.block(text)[1], "")

    def test_list_code_and_quote_add_to_their_own_indent(self):
        self.assertEqual(self.block("bullet")[1], f'w:left="{720 + H5_INDENT}" w:hanging="360"')
        self.assertEqual(self.block("int x;")[1], f'w:left="{H5_INDENT}"')
        quote = self.block("quote")[1]
        self.assertRegex(quote, r'^w:left="\d+"$')
        self.assertGreater(int(re.search(r'\d+', quote).group(0)), H5_INDENT)

    def test_tables_and_table_captions_are_not_indented(self):
        caption = next(block for block in self.blocks if block[2].endswith("caption five"))
        self.assertEqual(caption[1], "")
        table = next(block for block in self.blocks if block[0] == "TABLE")
        self.assertNotIn("tblInd", table[1])
        self.assertEqual(self.before.count("<w:tbl>"), self.after.count("<w:tbl>"))

    def test_images_fit_the_indented_width(self):
        before = int(re.search(r'<wp:extent cx="(\d+)"', self.before).group(1))
        after = int(re.search(r'<wp:extent cx="(\d+)"', self.after).group(1))
        limit = (self.text_width - H5_INDENT) * 635
        self.assertGreater(before, limit)
        self.assertEqual(after, limit)
        self.assertIn("resized 1 image(s)", self.stdout)


if __name__ == "__main__":
    unittest.main()
