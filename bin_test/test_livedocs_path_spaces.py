"""空白を含む一時ワークスペースと venv から make livedocs を実行する。"""

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request


DOCSFW = Path(__file__).resolve().parents[1]
WORKSPACE = DOCSFW.parents[1]

# resolve_python_components は livedocs/bin にあり、このテストと同じディレクトリではないため、
# sys.path へ追加して読み込む。
sys.path.insert(0, str(DOCSFW / "livedocs" / "bin"))

import resolve_python_components  # noqa: E402


def packages_outside_compatible_range(python):
    """``python`` が採用範囲 (requirements-compatible.txt) を満たさないパッケージ名の一覧を返す。

    livedocs の Python の選択 (resolve_python_components.py) と同じ判定を使う。
    """
    compatible = resolve_python_components.load_requirements(
        DOCSFW / "livedocs" / "requirements-compatible.txt"
    )
    state = resolve_python_components.probe(python)
    return resolve_python_components.missing_packages(state, compatible)


class LivedocsPathSpacesTest(unittest.TestCase):
    def test_make_livedocs(self):
        self.run_make_livedocs()

    def test_make_livedocs_with_complete_system_environment(self):
        # 前提: テストを実行する Python が livedocs の採用範囲を満たし、システム環境だけで
        # livedocs を実行できること。満たさない Python では venv が作られるため、スキップする。
        # make bin-test は resolve_python_components.py --run-script で採用範囲を満たす
        # Python を選んで起動するため、通常の経路ではスキップしない。
        missing = packages_outside_compatible_range(sys.executable)
        if missing:
            self.skipTest(
                "テストを実行する Python が livedocs の採用範囲を満たしません: " + ", ".join(missing)
            )
        self.run_make_livedocs(system_python=sys.executable)

    def run_make_livedocs(self, system_python=None):
        with tempfile.TemporaryDirectory(prefix="livedocs space ") as temp:
            root = Path(temp)
            with open(root / "makefile", "w", encoding="utf-8", newline="\n") as handle:
                handle.write((WORKSPACE / "makefile").read_text(encoding="utf-8"))
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
            if system_python:
                command.append("LIVEDOCS_SYSTEM_PYTHON=" + Path(system_python).as_posix())
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
            if system_python:
                self.assertFalse((root / "venv space").exists(), result.stdout)

            # 選択した Python から配信し、stopdocs が空白入り設定パスで停止できるか確認する。
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
