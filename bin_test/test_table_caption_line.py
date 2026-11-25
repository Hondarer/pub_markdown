"""前処理 table-caption-preprocess.py と Pandoc の table_captions による Table: (表の直前に置くキャプション) の取り込みを検証する。"""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FILTER_DIR = ROOT / "bin_internal" / "pandoc-filters"
CAPTION_LINE = FILTER_DIR / "codeblock-caption-line.lua"
PREPROCESS = ROOT / "bin_internal" / "table-caption-preprocess.py"
TABLE_STYLE = FILTER_DIR / "table-caption-style.lua"
TEMPLATE = ROOT / "styles" / "docx" / "docx-template.dotx"
HAS_CROSSREF = shutil.which("pandoc-crossref") is not None

TABLE = "| a |\n|---|\n| 1 |\n"
WARNING = "'Table:' 行の直後に表がありません。表のキャプションは、空行を挟んで表の直前に記述してください。"


def run_pandoc(markdown, output_format="native", crossref=False, style=False, extra_args=()):
    """実際の発行と同じく、前処理を通してから Pandoc (table_captions 有効) へ渡す。"""
    pre = subprocess.run(
        ["python3", str(PREPROCESS), "t.md"],
        input=markdown.encode("utf-8"),
        capture_output=True,
    )
    command = [
        "pandoc",
        "-f",
        "markdown+hard_line_breaks",
        "-t",
        output_format,
        "--lua-filter",
        str(CAPTION_LINE),
    ]
    if crossref:
        command.extend(["-F", "pandoc-crossref"])
    if style:
        command.extend(["--lua-filter", str(TABLE_STYLE)])
    command.extend(extra_args)
    res = subprocess.run(
        command,
        input=pre.stdout,
        capture_output=True,
    )
    return subprocess.CompletedProcess(
        res.args,
        res.returncode,
        stdout=res.stdout.decode("utf-8"),
        stderr=pre.stderr.decode("utf-8") + res.stderr.decode("utf-8"),
    )


@unittest.skipUnless(shutil.which("pandoc"), "pandoc が必要です")
class TableCaptionLineTest(unittest.TestCase):
    def assert_ok(self, res):
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_caption_before_table_becomes_table_caption(self):
        res = run_pandoc(f"Table: Preceding\n\n{TABLE}")
        self.assert_ok(res)
        self.assertEqual(res.stderr, "")
        self.assertIn('(Caption Nothing [ Plain [ Str "Preceding" ] ])', res.stdout)
        self.assertNotIn("Para", res.stdout)

    def test_consecutive_tables_each_get_the_preceding_caption(self):
        res = run_pandoc(f"Table: First\n\n{TABLE}\nTable: Second\n\n{TABLE.replace('1', '2')}")
        self.assert_ok(res)
        self.assertEqual(res.stderr, "")
        self.assertEqual(res.stdout.count("(Caption Nothing [ Plain"), 2)
        self.assertLess(res.stdout.index('Str "First"'), res.stdout.index('Str "1"'))
        self.assertLess(res.stdout.index('Str "1"'), res.stdout.index('Str "Second"'))
        self.assertLess(res.stdout.index('Str "Second"'), res.stdout.index('Str "2"'))
        self.assertEqual(res.stdout.count("Para"), 0)

    def test_caption_after_table_warns_and_stays_paragraph(self):
        res = run_pandoc(f"{TABLE}\nTable: Late {{#tbl:late}}\n")
        self.assert_ok(res)
        self.assertIn(WARNING, res.stderr)
        self.assertIn("(Caption Nothing [])", res.stdout)
        self.assertIn("Para", res.stdout)
        self.assertIn('Str "Table:"', res.stdout)
        self.assertIn("t.md: 5 行目:", res.stderr)
        self.assertNotIn('"tbl:late"', res.stdout.replace('Str "{#tbl:late}"', ""))

    def test_caption_without_blank_line_is_not_a_caption(self):
        res = run_pandoc(f"Table: NoBlank\n{TABLE}")
        self.assert_ok(res)
        # 空行がないと pandoc は表として解釈せず、全体が 1 つの段落になる。
        # 前処理はキャプションにしない Table: として警告を出す。
        self.assertIn("'Table:' 行の直後に表がありません", res.stderr)
        self.assertNotIn("Caption", res.stdout)
        self.assertNotIn("Table", res.stdout.replace('Str "Table:"', ""))
        self.assertIn("Para", res.stdout)

    def test_caption_in_blockquote_attaches_to_the_following_table_only(self):
        # 1 つ目の表にキャプションがなく、2 つ目の表の前に Table: がある。
        # 前処理がなければ、Pandoc は Table: を 1 つ目の表のキャプションにする。
        quoted = "> | a |\n> |---|\n> | 1 |\n"
        quoted2 = "> | b |\n> |---|\n> | 2 |\n"
        res = run_pandoc(f"{quoted}>\n> Table: Second\n>\n{quoted2}")
        self.assert_ok(res)
        self.assertEqual(res.stderr, "")
        self.assertEqual(res.stdout.count("(Caption Nothing [ Plain"), 1)
        self.assertEqual(res.stdout.count("(Caption Nothing [])"), 1)
        self.assertLess(res.stdout.index('Str "1"'), res.stdout.index('Str "Second"'))
        self.assertLess(res.stdout.index('Str "Second"'), res.stdout.index('Str "2"'))
        self.assertNotIn('Str "Table:"', res.stdout)

    def test_caption_in_blockquote_without_table_warns_and_stays_paragraph(self):
        res = run_pandoc("> Table: Lonely\n>\n> text\n")
        self.assert_ok(res)
        self.assertIn(WARNING, res.stderr)
        self.assertIn("t.md: 1 行目:", res.stderr)
        self.assertNotIn("Caption", res.stdout)

    def test_label_becomes_table_identifier(self):
        res = run_pandoc(f"Table: Labeled {{#tbl:sample}}\n\n{TABLE}")
        self.assert_ok(res)
        self.assertEqual(res.stderr, "")
        self.assertIn('( "tbl:sample" , [] , [] )', res.stdout)
        self.assertNotIn("{#tbl:sample}", res.stdout)

    def test_non_tbl_label_prefix_warns_and_is_used(self):
        res = run_pandoc(f"Table: Other {{#fig:wrong}}\n\n{TABLE}")
        self.assert_ok(res)
        self.assertIn("'Table:' 行に表以外のラベル接頭辞 '{#fig:wrong}' が指定されています", res.stderr)
        self.assertIn('( "fig:wrong" , [] , [] )', res.stdout)

    def test_multiline_caption_keeps_line_break(self):
        res = run_pandoc(f"Table: Line1\n2nd\n\n{TABLE}")
        self.assert_ok(res)
        self.assertEqual(res.stderr, "")
        self.assertRegex(res.stdout, r'Str "Line1"\s*,\s*LineBreak\s*,\s*Str "2nd"')

    def test_caption_inside_list_item(self):
        md = "- 項目\n\n    Table: Nested\n\n    | a |\n    |---|\n    | 1 |\n"
        res = run_pandoc(md)
        self.assert_ok(res)
        self.assertEqual(res.stderr, "")
        self.assertIn("BulletList", res.stdout)
        self.assertEqual(res.stdout.count("(Caption Nothing [ Plain"), 1)
        self.assertNotIn('Str "Table:"', res.stdout)

    def test_preceding_caption_keeps_tight_list(self):
        # 子項目の直後の表に前置きの Table: を付けても、リストは詰めた表示 (Plain) のままになる。
        base = "- 親\n  - 子\n\n  | a |\n  |---|\n  | 1 |\n"
        with_caption = "- 親\n  - 子\n\n  Table: Cap\n\n  | a |\n  |---|\n  | 1 |\n"
        for md in (base, with_caption):
            with self.subTest(md=md):
                res = run_pandoc(md)
                self.assert_ok(res)
                self.assertEqual(res.stderr, "")
                self.assertNotIn("Para", res.stdout)
                self.assertIn("Plain", res.stdout)
        self.assertIn("(Caption Nothing [ Plain", run_pandoc(with_caption).stdout)

    def test_indent_mismatch_in_list_item_warns(self):
        md = "- 項目\n\n    Table: Mismatch\n\n| a |\n|---|\n| 1 |\n"
        res = run_pandoc(md)
        self.assert_ok(res)
        self.assertIn(WARNING, res.stderr)
        self.assertIn("(Caption Nothing [])", res.stdout)

    def test_leading_colon_and_lowercase_table_are_not_captions(self):
        for prefix in (": Colon", "table: Lower"):
            with self.subTest(prefix=prefix):
                res = run_pandoc(f"{prefix}\n\n{TABLE}")
                self.assert_ok(res)
                self.assertEqual(res.stderr, "")
                self.assertIn("(Caption Nothing [])", res.stdout)
                self.assertIn("Para", res.stdout)

        res = run_pandoc(f"{TABLE}\n: LateColon\n")
        self.assert_ok(res)
        self.assertIn("(Caption Nothing [])", res.stdout)
        self.assertIn('Str "LateColon"', res.stdout)
        self.assertEqual(res.stdout.count("(Caption Nothing [ Plain"), 0)

    @unittest.skipUnless(HAS_CROSSREF, "pandoc-crossref が必要です")
    def test_crossref_numbers_table_and_resolves_reference(self):
        md = f"Table: Numbered {{#tbl:x}}\n\n{TABLE}\n[@tbl:x] ref.\n"
        res = run_pandoc(md, output_format="html", crossref=True, style=True)
        self.assert_ok(res)
        self.assertEqual(res.stderr, "")
        self.assertRegex(
            res.stdout,
            r'docsfw-table-caption[^>]*>\s*(?:<p>)?\s*Table 1: Numbered\s*(?:</p>)?\s*</div>\s*<table',
        )
        self.assertIn('id="tbl:x"', res.stdout)
        self.assertRegex(res.stdout, r"<p>tbl\.(?:&nbsp;|\xa0)1 ref\.</p>")

    @unittest.skipUnless(HAS_CROSSREF, "pandoc-crossref が必要です")
    def test_docx_caption_paragraph_precedes_table(self):
        md = f"Table: DocxTable {{#tbl:d}}\n\n{TABLE}\n"
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "out.docx"
            # 実際の発行と同じく、docx では table-caption-style.lua を使わず、既定の表キャプションを使う。
            res = run_pandoc(
                md,
                output_format="docx",
                crossref=True,
                extra_args=("--reference-doc", str(TEMPLATE), "-o", str(docx)),
            )
            self.assert_ok(res)
            with zipfile.ZipFile(docx) as archive:
                document = archive.read("word/document.xml").decode("utf-8")
        caption = re.search(r'<w:pStyle w:val="TableCaption"\s*/>', document)
        self.assertIsNotNone(caption, "TableCaption スタイルの段落がありません")
        table = document.find("<w:tbl>")
        self.assertGreaterEqual(table, 0)
        self.assertLess(caption.start(), table)
        self.assertEqual(len(re.findall(r'w:val="TableCaption"', document)), 1)
        self.assertIn("Table 1: DocxTable", document)


if __name__ == "__main__":
    unittest.main()
