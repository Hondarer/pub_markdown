"""空白を含む配置先から発行スクリプトと Mermaid ラッパーを起動する。"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile


DOCSFW = Path(__file__).resolve().parents[1]


class PathSpacesTest(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "[Linux] chrome-wrapper の代替 Chromium 探索は Linux 用")
    def test_chrome_fallback_preserves_paths(self):
        with tempfile.TemporaryDirectory(prefix="chrome space ") as temp:
            root = Path(temp)
            tools = root / "tools space"
            tools.mkdir()
            missing = root / "cache space/linux-100.0.0.0/chrome-linux64/chrome"
            chrome = root / "cache space/linux-101.0.0.0/chrome-linux64/chrome"
            chrome.parent.mkdir(parents=True)
            chrome.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n', encoding="utf-8")
            chrome.chmod(0o755)
            node = tools / "node"
            node.write_text('#!/bin/bash\nprintf "%s\\n" "$MISSING_CHROME"\n', encoding="utf-8")
            node.chmod(0o755)
            report = root / "browser executable.txt"
            env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"],
                       MISSING_CHROME=str(missing), DOCSFW_BROWSER_EXECUTABLE_REPORT_FILE=str(report))
            result = subprocess.run(
                ["bash", str(DOCSFW / "bin_internal/chrome-wrapper.sh"), "argument space"],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                encoding="utf-8", timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "--no-sandbox\nargument space\n")
            self.assertEqual(report.read_text(encoding="utf-8").strip(), str(chrome))

    def test_mermaid_wrapper_preserves_paths(self):
        with tempfile.TemporaryDirectory(prefix="mmdc space ") as temp:
            root = Path(temp)
            runtime = root / "runtime space"
            runtime.mkdir()
            shutil.copy(DOCSFW / "bin_internal/mmdc-wrapper.sh", runtime)
            (runtime / "mmdc-reuse.js").touch()
            tools = root / "tools space"
            tools.mkdir()
            node = tools / "node"
            with open(node, "w", encoding="utf-8", newline="\n") as handle:
                handle.write('#!/bin/bash\n[ -f "$1" ] || exit 2\nshift\nprintf "%s\\n" "$@"\n')
            node.chmod(0o755)
            ws = root / "browser ws.txt"
            ws.touch()
            # Git Bash の PATH は POSIX 形式。変換は Bash 内で行う。
            env = dict(os.environ, PUB_MARKDOWN_BROWSER_WS_FILE=ws.as_posix())
            result = subprocess.run(
                ["bash", "-c", 'PATH="$(cygpath -u "$1" 2>/dev/null || printf "%s" "$1"):$PATH"; shift; exec bash "$@"',
                 "test", str(tools), str(runtime / "mmdc-wrapper.sh"),
                 "-i", "input space.mmd", "-o", "output space.svg"],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace", timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(result.stdout, "-i\ninput space.mmd\n-o\noutput space.svg\n")

    def test_publish_html_in_workspace_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="docs space ") as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            (root / "docs/sample.md").write_text(
                "# Sample\n\nThis page uses a workspace with spaces.\n", encoding="utf-8"
            )
            (root / ".vscode").mkdir()
            (root / ".vscode/pub_markdown.config.yaml").write_text(
                "mdRoot: docs\npubRoot: pages\ndocxOutput: false\nlang: ja\ndetails: false\n",
                encoding="utf-8",
            )
            workspace = DOCSFW.parents[1]
            with open(root / "makefile", "w", encoding="utf-8", newline="\n") as handle:
                handle.write((workspace / "makefile").read_text(encoding="utf-8"))
            (root / "framework/docsfw").mkdir(parents=True)
            skills = root / "app/general/bin_internal/sync-skills.sh"
            skills.parent.mkdir(parents=True)
            with open(skills, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("#!/bin/bash\nexit 0\n")
            (root / "tmp space").mkdir()
            env = dict(os.environ, PUB_MARKDOWN_BROWSER_REUSE="off", TMPDIR=(root / "tmp space").as_posix())
            result = subprocess.run(
                ["make", "--no-print-directory", "docs", "JOBS=1",
                 "MAKEFW_HOME=" + (workspace / "framework/makefw").as_posix(),
                 "TESTFW_HOME=" + (workspace / "framework/testfw").as_posix(),
                 "DOCSFW_SCRIPT=" + (DOCSFW / "bin/pub_markdown.sh").as_posix(),
                 "EXTRACT_DOCS_WARNINGS=" + (DOCSFW / "bin_internal/extract_docs_warnings.sh").as_posix()],
                cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace", timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertNotIn("No such file or directory", result.stdout)
            self.assertNotIn("too many arguments", result.stdout)
            output = root / "pages/ja/html/sample.html"
            self.assertTrue(output.is_file(), result.stdout)
            self.assertIn("This page uses a workspace with spaces.", output.read_text(encoding="utf-8"))
            self.assertFalse((root / "docs.warn").exists(), result.stdout)
            self.assertEqual(list((root / "tmp space").glob("*.pipe")), [])

    def test_publish_diagrams_and_docx_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="diagram docs space ") as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            (root / "tmp space").mkdir()
            (root / "docs/sample.md").write_text('''# Sample diagrams

```plantuml
@startuml
Alice -> Bob: Hello
@enduml
```

```mermaid
graph TD
    A --> B
```
''', encoding="utf-8")
            (root / ".vscode").mkdir()
            (root / ".vscode/pub_markdown.config.yaml").write_text(
                "mdRoot: docs\npubRoot: pages\ndocxOutput: true\nlang: ja\ndetails: false\n",
                encoding="utf-8",
            )
            env = dict(os.environ, PUB_MARKDOWN_BROWSER_REUSE="off", TMPDIR=(root / "tmp space").as_posix())
            result = subprocess.run(
                ["bash", str(DOCSFW / "bin/pub_markdown.sh"), "--workspaceFolder=" + root.as_posix()],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace", timeout=180,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertNotIn("SVG file was not generated", result.stdout)
            self.assertNotIn("Cannot find module", result.stdout)
            self.assertNotIn("No such file or directory", result.stdout)
            html = root / "pages/ja/html/sample.html"
            self.assertTrue(html.is_file(), result.stdout)
            rendered = html.read_text(encoding="utf-8")
            self.assertIn("docsfw-plantuml", rendered)
            self.assertIn("docsfw-mermaid", rendered)
            docx = root / "pages/ja/docx/sample.docx"
            self.assertTrue(docx.is_file(), result.stdout)
            with zipfile.ZipFile(docx) as archive:
                media = [name for name in archive.namelist() if name.startswith("word/media/")]
            self.assertGreaterEqual(len(media), 2, result.stdout)


if __name__ == "__main__":
    unittest.main()
