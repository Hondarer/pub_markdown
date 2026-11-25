"""table_caption_position.prepare_for_pandoc の並べ替え、エスケープ、警告を検証する。"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin_internal"))

from table_caption_position import prepare_for_pandoc, relocate_table_captions  # noqa: E402

TABLE = "| a |\n|---|\n| 1 |"
QTABLE = "> | a |\n> |---|\n> | 1 |"
QTABLE2 = "> | b |\n> |---|\n> | 2 |"


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


class BlockquoteTest(unittest.TestCase):
    """ブロック引用の中では、引用の深さが同じ行だけを Table: 段落と表の組として扱う。"""

    def test_caption_before_second_table_moves_after_it(self):
        out, warnings = prepare_for_pandoc(f"{QTABLE}\n>\n> Table: B\n>\n{QTABLE2}\n")
        self.assertEqual(out, f"{QTABLE}\n>\n{QTABLE2}\n>\n> Table: B\n")
        self.assertEqual(warnings, [])

    def test_consecutive_tables_keep_attribution(self):
        text = f"> Table: A\n>\n{QTABLE}\n>\n> Table: B\n>\n{QTABLE2}\n"
        out, warnings = prepare_for_pandoc(text)
        self.assertEqual(out, f"{QTABLE}\n>\n> Table: A\n>\n{QTABLE2}\n>\n> Table: B\n")
        self.assertEqual(warnings, [])

    def test_caption_without_following_table_is_escaped_with_line_number(self):
        out, warnings = prepare_for_pandoc(f"{QTABLE}\n>\n> Table: Late\n")
        self.assertEqual(out, f"{QTABLE}\n>\n> Table\\: Late\n")
        self.assertEqual(len(warnings), 1)
        self.assertTrue(warnings[0].startswith("5 行目: 'Table:' 行の直後に表がありません"))

    def test_different_depth_is_not_paired(self):
        text = "> Table: Cap\n>\n> > | a |\n> > |---|\n> > | 1 |\n"
        out, warnings = prepare_for_pandoc(text)
        self.assertEqual(out, text.replace("Table:", "Table\\:"))
        self.assertEqual(len(warnings), 1)
        _out, moves = relocate_table_captions(text.replace("Cap\n>\n> > ", "Cap\n\n> > "), "markdown", migrate=True)
        self.assertEqual(moves, [])

    def test_lazy_continuation_line_is_not_paired(self):
        text = f"> Table: Cap\nlazy\n>\n{QTABLE}\n"
        out, warnings = prepare_for_pandoc(text)
        self.assertEqual(out, text.replace("Table:", "Table\\:"))
        self.assertEqual(len(warnings), 1)

    def test_blank_line_without_prefix_ends_the_quote(self):
        text = f"> Table: Cap\n\n{QTABLE}\n"
        out, warnings = prepare_for_pandoc(text)
        self.assertEqual(out, text.replace("Table:", "Table\\:"))
        self.assertEqual(len(warnings), 1)

    def test_caption_after_alert_marker_without_blank_line_is_not_a_caption(self):
        text = f"> [!NOTE]\n> Table: Cap\n>\n{QTABLE}\n"
        out, warnings = prepare_for_pandoc(text)
        self.assertEqual(out, text)
        self.assertEqual(warnings, [])

    def test_caption_after_alert_marker_with_blank_line_moves(self):
        out, warnings = prepare_for_pandoc(f"> [!NOTE]\n>\n> Table: Cap\n>\n{QTABLE}\n")
        self.assertEqual(out, f"> [!NOTE]\n>\n{QTABLE}\n>\n> Table: Cap\n")
        self.assertEqual(warnings, [])

    def test_fence_inside_blockquote_is_unchanged(self):
        text = f"> ```\n> Table: Cap\n>\n{QTABLE}\n> ```\n"
        out, warnings = prepare_for_pandoc(text)
        self.assertEqual(out, text)
        self.assertEqual(warnings, [])

    def test_quote_without_space_after_marker(self):
        out, warnings = prepare_for_pandoc(">Table: Cap\n>\n>| a |\n>|---|\n>| 1 |\n")
        self.assertEqual(out, ">| a |\n>|---|\n>| 1 |\n>\n>Table: Cap\n")
        self.assertEqual(warnings, [])

    def test_colon_next_to_quoted_table_is_escaped_keeping_prefix(self):
        out, warnings = prepare_for_pandoc(f"> : X\n>\n{QTABLE}\n")
        self.assertEqual(out, f"> \\: X\n>\n{QTABLE}\n")
        self.assertEqual(warnings, [])

    def test_relocate_moves_trailing_caption_before_quoted_table(self):
        out, moves = relocate_table_captions(f"{QTABLE}\n>\n> Table: Cap\n", "markdown")
        self.assertEqual(out, f"> Table: Cap\n>\n{QTABLE}\n")
        self.assertEqual(moves, [(5, 1, 5)])

    def test_relocate_keeps_leading_captions_between_quoted_tables(self):
        text = f"> Table: A\n>\n{QTABLE}\n>\n> Table: B\n>\n{QTABLE2}\n"
        self.assertEqual(relocate_table_captions(text, "markdown"), (text, []))

    def test_relocate_does_not_pair_quoted_caption_with_unquoted_table(self):
        text = f"{TABLE}\n\n> Table: Cap\n"
        self.assertEqual(relocate_table_captions(text, "markdown", migrate=True), (text, []))


class DoxygenDeepTableTest(unittest.TestCase):
    """C/C++ の Doxygen コメントでは、表が Table: より深い場合も組として扱う。"""

    DEEP = " *      | a |\n *      |---|\n *      | 1 |\n"
    SHALLOW = " *  Table: 後置き\n"

    def wrap(self, body):
        return f"/**\n * @brief 概要\n *\n{body} */\nint f(void);\n"

    def test_shallow_trailing_caption_moves_before_deep_table(self):
        text = self.wrap(f" * @param x 説明\n *\n{self.DEEP} *\n{self.SHALLOW}")
        out, moves = relocate_table_captions(text, "cpp")
        self.assertEqual(out, self.wrap(f" * @param x 説明\n *\n{self.SHALLOW} *\n{self.DEEP}"))
        self.assertEqual(len(moves), 1)

    def test_c_mode_behaves_like_cpp(self):
        text = self.wrap(f" *\n{self.DEEP} *\n{self.SHALLOW}")
        self.assertEqual(relocate_table_captions(text, "c")[0], self.wrap(f" *\n{self.SHALLOW} *\n{self.DEEP}"))

    def test_deep_table_under_list_item(self):
        text = self.wrap(f" * - 項目\n *\n{self.DEEP} *\n{self.SHALLOW}")
        out, _moves = relocate_table_captions(text, "cpp")
        self.assertEqual(out, self.wrap(f" * - 項目\n *\n{self.SHALLOW} *\n{self.DEEP}"))

    def test_deeper_caption_than_table_is_not_moved(self):
        text = self.wrap(f" *  | a |\n *  |---|\n *  | 1 |\n *\n *      Table: 深い\n")
        self.assertEqual(relocate_table_captions(text, "cpp", migrate=True), (text, []))

    def test_leading_shallow_caption_with_deep_table_is_unchanged(self):
        text = self.wrap(f"{self.SHALLOW} *\n{self.DEEP}")
        self.assertEqual(relocate_table_captions(text, "cpp"), (text, []))

    def test_leading_shallow_caption_between_deep_tables_is_unchanged(self):
        text = self.wrap(f"{self.DEEP} *\n{self.SHALLOW} *\n{self.DEEP.replace('a', 'b')}")
        self.assertEqual(relocate_table_captions(text, "cpp"), (text, []))

    def test_markdown_mode_keeps_different_indent_unpaired(self):
        text = "      | a |\n      |---|\n      | 1 |\n\n  Table: 後置き\n"
        self.assertEqual(relocate_table_captions(text, "markdown", migrate=True), (text, []))


if __name__ == "__main__":
    unittest.main()
