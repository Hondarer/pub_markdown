"""Pandoc の通常・埋め込み HTML と採番後処理の局所テスト。"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORMATTER = ROOT / "bin_internal/format-section-numbers.sh"


def postprocess(path):
    path = Path(path)
    converted = subprocess.run([shutil.which("bash") or "bash", str(FORMATTER)],
                               input=path.read_bytes(), capture_output=True, check=True)
    path.write_bytes(converted.stdout)


def render(markdown, directory, template, embed=False):
    output = Path(directory) / (template + ("-embed" if embed else "") + ".html")
    # テンプレートのコンパイルも確認する。通信は局所テストの対象外。
    source = (ROOT / "styles/html" / template).read_text(encoding="utf-8")
    source = re.sub(r'<(?:script|link)\b[^>]*(?:src|href)=["\x27]https?:[^>]*>'
                    r'(?:\s*</script>)?', "", source)
    local_template = Path(directory) / template
    local_template.write_text(source, encoding="utf-8")
    args = ["pandoc", "-s", "-t", "html", "--wrap=none", "--toc", "--toc-depth=5",
            "--shift-heading-level-by=-1", "-N", "--template", str(local_template),
            "-M", "pagetitle=Heading test", "-o", str(output)]
    if embed:
        args.append("--embed-resources")
    subprocess.run(args, input=markdown, encoding="utf-8", check=True,
                   capture_output=True)
    return output


class HeadingNumberingTest(unittest.TestCase):
    def test_all_templates_and_embedded_output(self):
        markdown = (ROOT / "docs/sample/heading.md").read_text(encoding="utf-8")
        for template in ("html-template.html", "html-simple-template.html"):
            for embed in (False, True):
                with self.subTest(template=template, embed=embed), tempfile.TemporaryDirectory() as d:
                    output = render(markdown, d, template, embed)
                    before = output.read_text(encoding="utf-8")
                    expected = ["1", "1.1", "1.1.1", "(1)", "(a)",
                                "2", "2.1", "2.1.1", "(1)", "(a)",
                                "3", "3.1", "3.1.1", "(1)", "(a)",
                                "4", "5", "6", "6.1", "6.2", "6.3",
                                "6.3.1", "6.3.2", "6.3.3", "(1)", "(2)", "(3)",
                                "(a)", "(b)", "(c)"]
                    postprocess(output)
                    after = output.read_text(encoding="utf-8")
                    for cls in ("header-section-number", "toc-section-number"):
                        self.assertEqual(re.findall(f'<span class="{cls}">([^<]*)</span>', after),
                                         expected)
                    self.assertEqual(re.findall(r'(?:id|href)="[^"]*"', before),
                                     re.findall(r'(?:id|href)="[^"]*"', after))
                    postprocess(output)
                    self.assertEqual(re.findall(r'<span class="(?:header|toc)-section-number">([^<]*)</span>',
                                                output.read_text(encoding="utf-8")), expected * 2)

    def test_resets_skipped_levels_and_alphabetic_overflow(self):
        markdown = "# Title\n\n## A\n\n### B\n\n#### C\n\n##### D\n\n"
        markdown += "\n\n".join(f"###### Letter {i}" for i in range(1, 28))
        markdown += "\n\n##### E\n\n###### Restart\n\n## F\n\n###### Skip\n"
        with tempfile.TemporaryDirectory() as d:
            output = render(markdown, d, "html-simple-template.html")
            postprocess(output)
            numbers = re.findall(r'<span class="header-section-number">([^<]*)</span>',
                                 output.read_text(encoding="utf-8"))
            self.assertEqual(numbers[29:31], ["(z)", "(aa)"])
            self.assertEqual(numbers[-5:], ["(aa)", "(2)", "(a)", "2", "(a)"])


if __name__ == "__main__":
    unittest.main()
