"""Pandoc の表とコード キャプションの段落内改行を確認する。"""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FILTERS = ROOT / "bin_internal/pandoc-filters"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


@unittest.skipUnless(shutil.which("pandoc"), "pandoc が必要です")
class CaptionLineBreakTest(unittest.TestCase):
    def check_captions(self, crossref):
        for kind in ("table", "code"):
            samples = []
            cases = []
            prefix = "Table" if kind == "table" else "CodeBlock"
            label_prefix = "tbl" if kind == "table" else "lst"
            block = (
                "| Item | Value |\n|---|---|\n| A | B |"
                if kind == "table" else "```text\nhello\n```"
            )
            for lines in (1, 2, 3):
                for labeled in (False, True):
                    name = f"{kind}-{lines}-{labeled}"
                    caption = "  \n".join(
                        f"{name} line {i + 1}" for i in range(lines)
                    )
                    if labeled:
                        caption += f" {{#{label_prefix}:{name}}}"
                    samples.append(f"{block}\n\n{prefix}: {caption}\n")
                    cases.append((name, lines, labeled))
            samples.append(block + "\n")

            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "captions.md"
                source.write_text("\n".join(samples), encoding="utf-8")
                for output_format in ("html", "docx"):
                    with self.subTest(kind=kind, crossref=crossref,
                                      output_format=output_format):
                        output = Path(directory) / f"captions.{output_format}"
                        command = [
                            "pandoc", str(source), "-f", "markdown+hard_line_breaks",
                            "-t", output_format, "-o", str(output),
                            "-M", f"docsfw-crossref={str(crossref).lower()}",
                            "--lua-filter", str(FILTERS / "codeblock-caption-line.lua"),
                            "--lua-filter", str(FILTERS / "codeblock-caption.lua"),
                        ]
                        if crossref:
                            command += ["--filter", "pandoc-crossref"]
                        command += ["--lua-filter", str(FILTERS / "listing-caption-style.lua")]
                        if output_format == "html":
                            command += ["--lua-filter", str(FILTERS / "table-caption-style.lua")]
                        result = subprocess.run(
                            command, capture_output=True, text=True, encoding="utf-8"
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stderr, "")
                        if output_format == "docx":
                            with zipfile.ZipFile(output) as archive:
                                document = ET.fromstring(archive.read("word/document.xml"))
                            captions = [
                                p for p in document.findall(".//w:p", NS)
                                if f"{kind}-" in "".join(p.itertext())
                            ]
                            self.assertEqual(len(captions), len(cases))
                        else:
                            html = output.read_text(encoding="utf-8")
                        for name, lines, labeled in cases:
                            if output_format == "docx":
                                matches = [p for p in captions if name in "".join(p.itertext())]
                                self.assertEqual(len(matches), 1)
                                text = "".join(matches[0].itertext())
                                breaks = len(matches[0].findall(".//w:br", NS))
                                self.assertEqual(
                                    bool(re.match(r"(?:Table|Listing) \d+: ", text)),
                                    crossref and labeled,
                                )
                                style = matches[0].find("./w:pPr/w:pStyle", NS)
                                self.assertEqual(
                                    style.get("{" + NS["w"] + "}val"),
                                    "TableCaption" if kind == "table" else "SourceCodeCaption",
                                )
                            else:
                                match = re.search(re.escape(name + " line 1") + r".*?</div>", html, re.S)
                                self.assertIsNotNone(match)
                                text = match.group()
                                breaks = text.count("<br />")
                            self.assertEqual(breaks, lines - 1, name)
                            for i in range(lines):
                                self.assertIn(f"{name} line {i + 1}", text)

    def test_without_crossref(self):
        self.check_captions(False)

    @unittest.skipUnless(shutil.which("pandoc-crossref"), "pandoc-crossref が必要です")
    def test_with_crossref(self):
        self.check_captions(True)


if __name__ == "__main__":
    unittest.main()
