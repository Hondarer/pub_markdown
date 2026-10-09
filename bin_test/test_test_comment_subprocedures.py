"""サブ手順の範囲も Assert・モック期待のコメント検査に含める。"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin_internal"))
from text_style_jp_engine import DiagnosticCollector
from text_style_jp_frontends import _find_cpp_test_comment_findings


class SubprocedureCommentTest(unittest.TestCase):
    def findings(self, text):
        collector = DiagnosticCollector()
        _find_cpp_test_comment_findings(text, collector)
        return collector.findings

    def test_assert_inside_class_method_is_checked(self):
        source = '''class Fixture {
    // [サブ手順 名前=Fixture.Check]
    void Check() { EXPECT_EQ(1, actual); }
    // [サブ手順終了]
};
'''
        self.assertEqual([f.rule for f in self.findings(source)], ["test-comment-assertion-check"])

    def test_annotated_assert_and_expectation_pass(self):
        source = '''// [サブ手順 名前=Helper.Check]
void Check() {
    ASSERT_NE(nullptr, p); // [状態確認] - 準備できたこと。
    EXPECT_EQ(1, actual); // [確認_正常系 回数=2] - 値が 1 であること。
    EXPECT_CALL(mock, Run()).WillOnce(Return(0)); // [Pre-Assert確認_正常系] - 呼ばれること。
    // [Pre-Assert手順] - 0 を返す。
}
// [サブ手順終了]
'''
        self.assertEqual(self.findings(source), [])

    def test_literals_and_block_comments_do_not_open_ranges(self):
        for prefix in ['const char *s = "// [サブ手順 名前=Fake]";\n',
                       'const char *s = R"x(// [サブ手順 名前=Fake]\n)x";\n',
                       '/* // [サブ手順 名前=Fake] */\n']:
            with self.subTest(prefix=prefix):
                self.assertEqual(self.findings(prefix + 'void f() { EXPECT_EQ(1, actual); }\n// [サブ手順終了]\n'), [])

    def test_definition_end_excludes_other_helpers(self):
        source = '''// [サブ手順 名前=A]
void a() { EXPECT_EQ(1, actual); // [確認_正常系] - 値が 1 であること。
}
// [サブ手順終了]
void b() { EXPECT_EQ(2, actual); }
'''
        self.assertEqual(self.findings(source), [])

    def test_region_inside_test_is_checked_once(self):
        source = '''TEST(Suite, Case) {
    // [サブ手順 名前=Region]
    EXPECT_EQ(1, actual);
    // [サブ手順終了]
}
'''
        self.assertEqual([f.rule for f in self.findings(source)], ["test-comment-assertion-check"])


if __name__ == '__main__':
    unittest.main()
