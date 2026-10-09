"""PlantUML のキャプションの優先順位を確認する。"""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FILTERS = ROOT / "bin_internal/pandoc-filters"


def plantuml_block(caption_line):
    lines = ["```plantuml", "@startuml 開始名"]
    if caption_line:
        lines.append("caption ソース内キャプション")
    lines += ["Alice->Bob : Hello", "@enduml", "```"]
    return "\n".join(lines)


@unittest.skipUnless(shutil.which("pandoc"), "pandoc が必要です")
class PlantUmlCaptionPriorityTest(unittest.TestCase):
    def figcaptions(self, markdown):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "plantuml.md"
            source.write_text(markdown, encoding="utf-8")
            result = subprocess.run(
                [
                    "pandoc", str(source), "-t", "html",
                    "--lua-filter", str(FILTERS / "codeblock-caption-line.lua"),
                    "--lua-filter", str(FILTERS / "plantuml.lua"),
                ],
                capture_output=True, text=True, encoding="utf-8",
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        return [
            re.sub(r"<[^>]+>", "", caption).strip()
            for caption in re.findall(r"<figcaption>(.*?)</figcaption>", result.stdout, re.S)
        ]

    def test_codeblock_line_overrides_source_caption(self):
        markdown = plantuml_block(True) + "\n\nCodeBlock: 行のキャプション\n"
        self.assertEqual(self.figcaptions(markdown), ["行のキャプション"])

    def test_source_caption_overrides_start_title(self):
        self.assertEqual(self.figcaptions(plantuml_block(True) + "\n"), ["ソース内キャプション"])

    def test_start_title_is_used_last(self):
        self.assertEqual(self.figcaptions(plantuml_block(False) + "\n"), ["開始名"])


if __name__ == "__main__":
    unittest.main()
