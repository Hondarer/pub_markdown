#!/usr/bin/env python3
"""プレビュー バリアント名の分解テスト。"""

import os
import sys
import unittest

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
sys.path.insert(0, BIN_DIR)

from lang_details_filter import filter_lang_details  # noqa: E402
from stage_preview_docs import parse_preview_variant  # noqa: E402


SAMPLE = """
<!--ja:-->
japanese
<!--:ja-->
<!--en:-->
english
<!--:en-->
neutral
<!--details:-->
detail-only
<!--:details-->
"""


class ParsePreviewVariantTest(unittest.TestCase):
    def test_four_variants(self):
        self.assertEqual(parse_preview_variant("ja"), ("ja", False, "ja"))
        self.assertEqual(parse_preview_variant("ja-details"), ("ja", True, "ja-details"))
        self.assertEqual(parse_preview_variant("en"), ("en", False, "en"))
        self.assertEqual(parse_preview_variant("en-details"), ("en", True, "en-details"))

    def test_default_and_blank(self):
        self.assertEqual(parse_preview_variant(None), ("ja", True, "ja-details"))
        self.assertEqual(parse_preview_variant(""), ("ja", True, "ja-details"))
        self.assertEqual(parse_preview_variant("  ja-details  "), ("ja", True, "ja-details"))

    def test_rejects_unknown(self):
        with self.assertRaises(ValueError):
            parse_preview_variant("fr")
        with self.assertRaises(ValueError):
            parse_preview_variant("ja-detail")


class VariantFilterTest(unittest.TestCase):
    def test_ja_details_keeps_details_and_japanese(self):
        lang, details, _name = parse_preview_variant("ja-details")
        text = filter_lang_details(SAMPLE, lang, details)
        self.assertIn("japanese", text)
        self.assertIn("neutral", text)
        self.assertIn("detail-only", text)
        self.assertNotIn("english", text)

    def test_ja_drops_details(self):
        lang, details, _name = parse_preview_variant("ja")
        text = filter_lang_details(SAMPLE, lang, details)
        self.assertIn("japanese", text)
        self.assertNotIn("detail-only", text)
        self.assertNotIn("english", text)

    def test_en_details_keeps_english(self):
        lang, details, _name = parse_preview_variant("en-details")
        text = filter_lang_details(SAMPLE, lang, details)
        self.assertIn("english", text)
        self.assertIn("detail-only", text)
        self.assertNotIn("japanese", text)


if __name__ == "__main__":
    unittest.main()
