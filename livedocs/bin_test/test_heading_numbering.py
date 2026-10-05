"""見出しのレベルと目次の深さが異なる場合も番号を一致させる。"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
from livedocs_heading_numbering_hook import on_page_content, alphabetic


def item(identifier, title, children=None):
    return SimpleNamespace(id=identifier, title=title, children=children or [])


class HeadingNumberingTest(unittest.TestCase):
    def test_skipped_levels_and_toc_depth(self):
        low = item("low", "<em>Lower</em>")
        second = item("second", "Second")
        page = SimpleNamespace(toc=SimpleNamespace(items=[item("title", "Title", [low]), second]))
        source = '<h1 id="title">Title</h1><h2 id="first">First</h2>'
        source += '<h4 id="low">Lower</h4><h5>Hidden from TOC</h5>'
        source += '<h2 id="second">Second</h2>'
        self.assertEqual(on_page_content(source, page, {}, None), source)
        self.assertEqual(low.title, '<span class="docsfw-toc-number">1.0.1</span> <em>Lower</em>')
        self.assertEqual(second.title, '<span class="docsfw-toc-number">2</span> Second')
        self.assertEqual(page.toc.items[0].title, "Title")
        on_page_content(source, page, {}, None)
        self.assertEqual(low.title.count("docsfw-toc-number"), 1)

    def test_parent_reset_and_overflow(self):
        entries = [item("alpha", "Alpha"), item("reset", "Reset"), item("numeric", "Numeric")]
        source = '<h1>Title</h1><h2>A</h2><h3>B</h3><h4>C</h4><h5>D</h5>'
        source += '<h6>Letter</h6>' * 26 + '<h6 id="alpha">Alpha</h6>'
        source += '<h2>E</h2><h6 id="reset">Reset</h6><h5 id="numeric">Numeric</h5>'
        on_page_content(source, SimpleNamespace(toc=SimpleNamespace(items=entries)), {}, None)
        self.assertEqual([x.title.split("</span>")[0].split(">")[-1] for x in entries],
                         ["(aa)", "(a)", "(1)"])
        self.assertEqual(alphabetic(26), "z")


if __name__ == "__main__":
    unittest.main()
