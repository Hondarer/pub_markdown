"""空白を含む一時ワークスペースと venv から make livedocs を実行する。"""

import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request


DOCSFW = Path(__file__).resolve().parents[1]
WORKSPACE = DOCSFW.parents[1]


class LivedocsPathSpacesTest(unittest.TestCase):
    def test_make_livedocs(self):
        with tempfile.TemporaryDirectory(prefix="livedocs space ") as temp:
            root = Path(temp)
            (root / "makefile").write_text(
                (WORKSPACE / "makefile").read_text(encoding="utf-8"),
                encoding="utf-8", newline="\n",
            )
            (root / "docs").mkdir()
            (root / "docs/README.md").write_text(
                "# Sample\n\nA page generated from a workspace with spaces.\n",
                encoding="utf-8",
            )
            (root / ".vscode").mkdir()
            (root / ".vscode/pub_markdown.config.yaml").write_text(
                "mdRoot: docs\npubRoot: pages\nlang: ja\ndetails: false\n",
                encoding="utf-8",
            )
            command = ["make", "--no-print-directory", "JOBS=1",
                 "MAKEFW_HOME=" + (WORKSPACE / "framework/makefw").as_posix(),
                 "LIVEDOCS_HOME=" + (DOCSFW / "livedocs").as_posix(),
                 "LIVEDOCS_VENV=" + (root / "venv space").as_posix()]
            result = subprocess.run(
                command + ["livedocs"],
                cwd=root, env=dict(os.environ), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace", timeout=480,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            html = root / "pages/livedocs/site/ja/index.html"
            self.assertTrue(html.is_file(), result.stdout)
            self.assertIn("A page generated from a workspace with spaces.", html.read_text(encoding="utf-8"))
            self.assertNotIn("Cannot find module", result.stdout)

            # 同じ空白入り venv から配信し、stopdocs がこの配信を識別して停止できるか確認する。
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            log_path = root / "serve log.txt"
            with log_path.open("w", encoding="utf-8") as log:
                server = subprocess.Popen(
                    command + ["servedocs", "LIVEDOCS_ADDR=127.0.0.1:" + str(port)],
                    cwd=root, env=dict(os.environ), stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                try:
                    deadline = time.monotonic() + 120
                    while time.monotonic() < deadline:
                        try:
                            with urllib.request.urlopen(
                                "http://127.0.0.1:" + str(port) + "/ja/", timeout=2,
                            ) as response:
                                page = response.read().decode("utf-8")
                            break
                        except (urllib.error.URLError, TimeoutError):
                            if server.poll() is not None:
                                self.fail(log_path.read_text(encoding="utf-8", errors="replace"))
                            time.sleep(0.25)
                    else:
                        self.fail(log_path.read_text(encoding="utf-8", errors="replace"))
                    self.assertIn("A page generated from a workspace with spaces.", page)
                finally:
                    stopped = subprocess.run(
                        command + ["stopdocs"], cwd=root, env=dict(os.environ),
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        encoding="utf-8", errors="replace", timeout=60,
                    )
                    try:
                        server.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        if os.name == "nt":
                            subprocess.run(
                                ["taskkill", "/PID", str(server.pid), "/T", "/F"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                            )
                        else:
                            server.kill()
                        server.wait(timeout=10)
                        self.fail("stopdocs did not stop the server: " + stopped.stdout)
                    self.assertEqual(stopped.returncode, 0, stopped.stdout)


if __name__ == "__main__":
    unittest.main()
