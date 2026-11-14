"""Pandoc フィルター codeblock-caption-line.lua の Figure: / CodeBlock: 動作を検証する。"""

from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
FILTER = ROOT / "bin_internal" / "pandoc-filters" / "codeblock-caption-line.lua"
CODEBLOCK_CAPTION = ROOT / "bin_internal" / "pandoc-filters" / "codeblock-caption.lua"


def run_pandoc(markdown, output_format="html", extra_filters=()):
    command = [
        "pandoc",
        "-f",
        "markdown+hard_line_breaks",
        "-t",
        output_format,
        "--lua-filter",
        str(FILTER),
    ]
    for flt in extra_filters:
        command.extend(["--lua-filter", str(flt)])
    return subprocess.run(
        command,
        input=markdown,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@unittest.skipUnless(shutil.which("pandoc"), "pandoc が必要です")
class FigureCaptionLineTest(unittest.TestCase):
    def test_diagram_fence_accepts_figure_without_warning(self):
        md = "```mermaid\nsequenceDiagram\n    Alice->>John: Hello\n```\n\nFigure: Sequence diagram {#fig:seq}\n"
        res = run_pandoc(md, output_format="native")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stderr, "")
        self.assertIn('"fig:seq"', res.stdout)
        self.assertIn('"caption"', res.stdout)
        self.assertIn("Sequence diagram", res.stdout)

    def test_diagram_fence_with_codeblock_warns_and_leaves_normal_paragraph(self):
        md = "```plantuml\n@startuml\nA -> B\n@enduml\n```\n\nCodeBlock: Compat diagram {#fig:compat}\n"
        res = run_pandoc(md, output_format="html")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("図のコード ブロックに対して 'CodeBlock:' が使われています", res.stderr)
        self.assertNotIn("ラベル接頭辞", res.stderr)
        self.assertIn("<p>CodeBlock: Compat diagram {#fig:compat}</p>", res.stdout)
        self.assertNotIn("<figcaption>", res.stdout)

    def test_normal_codeblock_with_figure_warns_and_leaves_normal_paragraph(self):
        md = "```c\nint x = 0;\n```\n\nFigure: C code {#lst:c}\n"
        res = run_pandoc(md, output_format="html", extra_filters=(CODEBLOCK_CAPTION,))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("図以外のコード ブロックに対して 'Figure:' が使われています", res.stderr)
        self.assertNotIn("ラベル接頭辞", res.stderr)
        self.assertIn("<p>Figure: C code {#lst:c}</p>", res.stdout)
        self.assertNotIn("Source Code Caption", res.stdout)

    def test_diagram_fence_with_lst_label_warns(self):
        md = "```mermaid\nsequenceDiagram\n    Alice->>John: Hello\n```\n\nFigure: Sequence {#lst:wrong}\n"
        res = run_pandoc(md, output_format="native")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("'Figure:' 行に図以外のラベル接頭辞 '{#lst:wrong}' が指定されています", res.stderr)
        self.assertIn('"lst:wrong"', res.stdout)

    def test_normal_codeblock_with_fig_label_warns(self):
        md = "```c\nint x = 0;\n```\n\nCodeBlock: C コード {#fig:wrong}\n"
        res = run_pandoc(md, output_format="native")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("'CodeBlock:' 行にリスト以外のラベル接頭辞 '{#fig:wrong}' が指定されています", res.stderr)
        self.assertIn('"fig:wrong"', res.stdout)

    def test_image_with_alt_prefers_figure_caption_and_preserves_alt(self):
        md = "![構成図の概要](images/arch.png)\n\nFigure: システム構成  \n2 行目 {#fig:arch}\n"
        res = run_pandoc(md, output_format="html")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stderr, "")
        self.assertIn('<figure id="fig:arch">', res.stdout)
        self.assertIn('alt="構成図の概要"', res.stdout)
        self.assertIn("<figcaption>システム構成<br />\n2 行目</figcaption>", res.stdout)

    def test_image_without_alt_fills_alt_from_figure_caption(self):
        md = "![](images/empty.png)\n\nFigure: 空代替の図 {#fig:empty}\n"
        res = run_pandoc(md, output_format="html")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stderr, "")
        self.assertIn('<figure id="fig:empty">', res.stdout)
        self.assertIn('alt="空代替の図"', res.stdout)
        self.assertIn("空代替の図</figcaption>", res.stdout)

    def test_image_label_conflict_prefers_figure_line_and_warns(self):
        md = "![代替](x.png){#fig:a}\n\nFigure: 題名 {#fig:b}\n"
        res = run_pandoc(md, output_format="html")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("競合しています", res.stderr)
        self.assertIn('<figure id="fig:b">', res.stdout)
        self.assertNotIn("fig:a", res.stdout)

    def test_image_with_codeblock_line_leaves_normal_paragraph(self):
        md = "![代替](x.png)\n\nCodeBlock: 無視される段落\n"
        res = run_pandoc(md, output_format="html")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stderr, "")
        self.assertIn("<p>CodeBlock: 無視される段落</p>", res.stdout)
        self.assertIn("代替</figcaption>", res.stdout)


if __name__ == "__main__":
    unittest.main()
