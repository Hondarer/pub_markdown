"""text_style_jp の表のキャプション位置の規則 (table-caption-position) と --migrate-table-caption を検証する。"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin_internal"))

from table_caption_position import relocate_table_captions  # noqa: E402

CLI = ROOT / "bin" / "text_style_jp.py"
TABLE_A = "| a |\n|---|\n| 1 |\n"
TABLE_B = "| b |\n|---|\n| 2 |\n"


def run_cli(*args, stdin=None):
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        input=stdin, capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT),
    )


class TempFileCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def write(self, name, text):
        path = self.tmp / name
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def in_place(self, name, text, *args):
        path = self.write(name, text)
        result = run_cli("--in-place", *args, str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        return path.read_text(encoding="utf-8")


class DefaultRuleTest(TempFileCase):
    def test_trailing_caption_moves_before_table_in_place(self):
        out = self.in_place("a.md", f"# T\n\n{TABLE_A}\nTable: 後置き\n\n本文\n")
        self.assertEqual(out, f"# T\n\nTable: 後置き\n\n{TABLE_A}\n本文\n")

    def test_trailing_caption_moves_before_table_on_stdout(self):
        path = self.write("a.md", f"{TABLE_A}\nTable: 後置き\n")
        result = run_cli(str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"Table: 後置き\n\n{TABLE_A}")

    def test_multiline_caption(self):
        out = self.in_place("a.md", f"{TABLE_A}\nTable: 一行目\n二行目\n\n本文\n")
        # 複数行のキャプションの行末には、整形が強制改行 (半角空白 2 個) を付与する。
        self.assertEqual(out, f"Table: 一行目  \n二行目\n\n{TABLE_A}\n本文\n")

    def test_indented_in_list_item_keeps_indent(self):
        text = "- 項目\n\n    | a |\n    |---|\n    | 1 |\n\n    Table: 後置き\n\n- 次\n"
        out = self.in_place("a.md", text)
        self.assertEqual(out, "- 項目\n\n    Table: 後置き\n\n    | a |\n    |---|\n    | 1 |\n\n- 次\n")

    def test_leading_captions_with_consecutive_tables_unchanged(self):
        text = f"Table: A\n\n{TABLE_A}\nTable: B\n\n{TABLE_B}"
        self.assertEqual(self.in_place("a.md", text), text)
        self.assertEqual(run_cli("--check", str(self.tmp / "a.md")).returncode, 0)

    def test_caption_with_different_indent_not_moved(self):
        text = f"{TABLE_A}\n    Table: 字下げが違う\n"
        self.assertEqual(self.in_place("a.md", text), text)

    def test_example_inside_fence_not_moved(self):
        text = f"```markdown\n{TABLE_A}\nTable: 例\n```\n"
        self.assertEqual(self.in_place("a.md", text), text)

    def test_dry_run_reports_rule_without_unattributed_change(self):
        path = self.write("a.md", f"# T\n\n{TABLE_A}\nTable: 後置き\n\n本文\n")
        result = run_cli("--dry-run", str(path))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("table-caption-position", result.stdout)
        self.assertIn("Table: 後置き", result.stdout)
        self.assertIn("3 行目の表の直前へ移動", result.stdout)
        self.assertNotIn("unattributed-change", result.stdout)
        self.assertIn("1 problem found", result.stdout)

    def test_dry_run_clean_file_returns_zero(self):
        path = self.write("a.md", f"Table: 前置き\n\n{TABLE_A}")
        result = run_cli("--dry-run", str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("table-caption-position", result.stdout)

    def test_check_exit_code(self):
        bad = self.write("bad.md", f"{TABLE_A}\nTable: 後置き\n")
        good = self.write("good.md", f"Table: 前置き\n\n{TABLE_A}")
        self.assertEqual(run_cli("--check", str(bad)).returncode, 1)
        self.assertEqual(run_cli("--check", str(good)).returncode, 0)


class MigrateRuleTest(TempFileCase):
    OLD = f"{TABLE_A}\nTable: A\n\n{TABLE_B}\nTable: B\n"

    def test_migrate_moves_each_caption_before_its_table(self):
        out = self.in_place("a.md", self.OLD, "--migrate-table-caption")
        self.assertEqual(out, f"Table: A\n\n{TABLE_A}\nTable: B\n\n{TABLE_B}")

    def test_migrate_does_not_apply_other_styling(self):
        text = f"第3章\n\n{TABLE_A}\nTable: A\n"
        out = self.in_place("a.md", text, "--migrate-table-caption")
        self.assertEqual(out, f"第3章\n\nTable: A\n\n{TABLE_A}")
        self.assertNotIn("第 3 章", out)

    def test_migrate_dry_run_reports_only_caption_rule(self):
        path = self.write("a.md", f"第3章\n\n{TABLE_A}\nTable: A\n")
        result = run_cli("--dry-run", "--migrate-table-caption", str(path))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("table-caption-position", result.stdout)
        self.assertNotIn("fullwidth-halfwidth-space", result.stdout)
        self.assertNotIn("unattributed-change", result.stdout)

    def test_migrate_check_exit_code(self):
        bad = self.write("bad.md", f"{TABLE_A}\nTable: A\n")
        good = self.write("good.md", f"Table: A\n\n{TABLE_A}")
        self.assertEqual(run_cli("--check", "--migrate-table-caption", str(bad)).returncode, 1)
        self.assertEqual(run_cli("--check", "--migrate-table-caption", str(good)).returncode, 0)


DOXY_TABLE = " * | a |\n * |---|\n * | 1 |\n"


class DoxygenTest(TempFileCase):
    def test_trailing_caption_moves_and_prefix_is_kept(self):
        text = f"/**\n * @brief 概要\n *\n{DOXY_TABLE} *\n * Table: 後置き\n */\nint f(void);\n"
        out = self.in_place("a.h", text)
        self.assertEqual(
            out, f"/**\n * @brief 概要\n *\n * Table: 後置き\n *\n{DOXY_TABLE} */\nint f(void);\n")

    def test_dry_run_reports_rule(self):
        text = f"/**\n * @brief 概要\n *\n{DOXY_TABLE} *\n * Table: 後置き\n */\nint f(void);\n"
        path = self.write("a.h", text)
        result = run_cli("--dry-run", str(path))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("table-caption-position", result.stdout)
        self.assertNotIn("unattributed-change", result.stdout)

    def test_inside_code_command_not_moved(self):
        text = f"/**\n * @code\n{DOXY_TABLE} *\n * Table: 例\n * @endcode\n */\nint f(void);\n"
        self.assertEqual(self.in_place("a.h", text), text)


class ModuleTest(unittest.TestCase):
    def test_default_returns_one_based_line_numbers(self):
        text = f"# T\n\n{TABLE_A}\nTable: 一\n二\n\n本文"
        out, moves = relocate_table_captions(text, "markdown")
        self.assertEqual(out, f"# T\n\nTable: 一\n二\n\n{TABLE_A}\n本文")
        self.assertEqual(moves, [(7, 3, 8)])

    def test_unsupported_mode_unchanged(self):
        text = f"{TABLE_A}\nTable: x\n"
        self.assertEqual(relocate_table_captions(text, "python"), (text, []))

    def test_default_keeps_caption_between_tables(self):
        text = f"Table: A\n\n{TABLE_A}\nTable: B\n\n{TABLE_B}"
        self.assertEqual(relocate_table_captions(text, "markdown"), (text, []))

    def test_migrate_moves_caption_between_tables(self):
        text = f"{TABLE_A}\nTable: A\n\n{TABLE_B}\nTable: B\n"
        out, moves = relocate_table_captions(text, "markdown", migrate=True)
        self.assertEqual(out, f"Table: A\n\n{TABLE_A}\nTable: B\n\n{TABLE_B}")
        self.assertEqual(moves, [(5, 1, 5), (11, 7, 11)])

    def test_doxygen_mode_line_numbers(self):
        text = f"/**\n *\n{DOXY_TABLE} *\n * Table: x\n */\n"
        out, moves = relocate_table_captions(text, "c")
        self.assertEqual(moves, [(7, 3, 7)])

    def test_doxygen_structural_commands_stay_in_place(self):
        text = (
            "/**\n"
            " *  @par            見出し\n"
            " *  @parblock\n"
            " *  | a |\n"
            " *  |---|\n"
            " *  | 1 |\n"
            " *\n"
            " *  Table: x\n"
            " *  @endparblock\n"
            " */\n"
        )
        out, moves = relocate_table_captions(text, "c", migrate=True)
        self.assertEqual(
            out,
            "/**\n"
            " *  @par            見出し\n"
            " *  @parblock\n"
            " *  Table: x\n"
            " *\n"
            " *  | a |\n"
            " *  |---|\n"
            " *  | 1 |\n"
            " *  @endparblock\n"
            " */\n",
        )
        self.assertEqual(moves, [(8, 4, 8)])


if __name__ == "__main__":
    unittest.main()
