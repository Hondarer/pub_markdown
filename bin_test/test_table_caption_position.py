"""table_caption_position.prepare_for_pandoc の並べ替え、エスケープ、警告を検証する。"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin_internal"))

from table_caption_position import prepare_for_pandoc  # noqa: E402

TABLE = "| a |\n|---|\n| 1 |"


class PrepareForPandocTest(unittest.TestCase):
    def test_caption_moves_after_table(self):
        out, warnings = prepare_for_pandoc(f"Table: Cap\n\n{TABLE}\n")
        self.assertEqual(out, f"{TABLE}\n\nTable: Cap\n")
        self.assertEqual(warnings, [])

    def test_consecutive_tables_keep_attribution(self):
        out, warnings = prepare_for_pandoc(f"Table: A\n\n{TABLE}\n\nTable: B\n\n{TABLE}\n")
        self.assertEqual(out, f"{TABLE}\n\nTable: A\n\n{TABLE}\n\nTable: B\n")
        self.assertEqual(warnings, [])

    def test_indented_caption_in_list_item(self):
        out, warnings = prepare_for_pandoc("- x\n\n  Table: Cap\n\n  | a |\n  |---|\n  | 1 |\n")
        self.assertEqual(out, "- x\n\n  | a |\n  |---|\n  | 1 |\n\n  Table: Cap\n")
        self.assertEqual(warnings, [])

    def test_caption_without_table_is_escaped_with_line_number(self):
        out, warnings = prepare_for_pandoc("text\n\nTable: Lonely\n\nmore\n")
        self.assertEqual(out, "text\n\nTable\\: Lonely\n\nmore\n")
        self.assertEqual(len(warnings), 1)
        self.assertTrue(warnings[0].startswith("3 行目: 'Table:' 行の直後に表がありません"))

    def test_caption_after_table_is_escaped(self):
        out, warnings = prepare_for_pandoc(f"{TABLE}\n\nTable: Late\n")
        self.assertEqual(out, f"{TABLE}\n\nTable\\: Late\n")
        self.assertEqual(len(warnings), 1)
        self.assertTrue(warnings[0].startswith("5 行目:"))

    def test_colon_and_lowercase_table_next_to_table_are_escaped_silently(self):
        for head in (":", "table:"):
            with self.subTest(head=head):
                out, warnings = prepare_for_pandoc(f"{head} X\n\n{TABLE}\n")
                self.assertEqual(out, f"\\{head} X\n\n{TABLE}\n".replace("\\table:", "table\\:"))
                self.assertEqual(warnings, [])

    def test_non_tbl_label_warns_and_still_moves(self):
        out, warnings = prepare_for_pandoc(f"Table: Cap {{#fig:x}}\n\n{TABLE}\n")
        self.assertEqual(out, f"{TABLE}\n\nTable: Cap {{#fig:x}}\n")
        self.assertEqual(len(warnings), 1)
        self.assertIn("{#fig:x}", warnings[0])
        self.assertTrue(warnings[0].startswith("1 行目:"))

    def test_fence_and_html_comment_are_unchanged(self):
        text = f"```\nTable: Cap\n\n{TABLE}\n```\n\n<!--\nTable: Cap\n\n{TABLE}\n-->\n"
        out, warnings = prepare_for_pandoc(text)
        self.assertEqual(out, text)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
