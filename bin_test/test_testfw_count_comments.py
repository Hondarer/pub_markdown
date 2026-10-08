"""期待確認の回数指定がコメント不足の誤診断を起こさないことを検証する。"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin_internal"))
from text_style_jp_frontends import style_by_mode
from text_style_jp_engine import DiagnosticCollector


class CountCommentsTest(unittest.TestCase):
    def test_counted_comments_satisfy_required_comment_diagnostics(self):
        source = '''TEST_P(Suite, Case) {
    EXPECT_CALL(mock, Run()).Times(3); // [Pre-Assert確認_正常系 回数=PARAM * (2+3)] - 呼ばれること。
    EXPECT_CALL(mock, Stop()).Times(0); // [Pre-Assert確認_異常系 回数=2*3+1] - 呼ばれないこと。
    EXPECT_EQ(1, actual); // [確認_正常系 回数=PARAM*2*3] - 値が一致すること。
    ASSERT_FALSE(error); // [確認_異常系 回数=0] - エラーがないこと。
    ASSERT_NE(nullptr, state); // [状態確認] - 準備できること。
}
'''
        collector = DiagnosticCollector()
        style_by_mode(source, "cpp", collector=collector)
        self.assertEqual([f.rule for f in collector.findings if f.rule.startswith("test-comment-")], [])


if __name__ == "__main__":
    unittest.main()
