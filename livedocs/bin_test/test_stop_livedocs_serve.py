"""設定ファイルによる配信停止と、別ワークスペースの除外を検証する。"""

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest


STOP = Path(__file__).resolve().parents[1] / "bin/stop_livedocs_serve.sh"


class StopServeTest(unittest.TestCase):
    def start_server(self, arguments):
        # 実際に配信せず、コマンドラインと子孫の停止だけを検証する。
        command = ["bash", "-c", '"$@" & wait', "fixture", sys.executable, "-c",
                   "import time; print('ready', flush=True); time.sleep(120)"] + arguments
        server = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  start_new_session=os.name != "nt",
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.addCleanup(self.cleanup_server, server)
        self.assertEqual(server.stdout.readline().strip(), "ready")
        return server

    @staticmethod
    def cleanup_server(server):
        if server.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(server.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                os.killpg(server.pid, signal.SIGTERM)
            server.wait(timeout=10)
        server.stdout.close()
        server.stderr.close()

    def stop(self, *arguments):
        result = subprocess.run(["bash", str(STOP)] + list(arguments), capture_output=True,
                                text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_stops_only_matching_mkdocs_serve_configuration(self):
        self.assertIsNotNone(shutil.which("bash"), "bash is required")
        with tempfile.TemporaryDirectory(prefix="serve config space ") as temporary:
            root = Path(temporary)
            config = (root / "workspace/mkdocs.yml").as_posix()
            other = (root / "workspace-other/mkdocs.yml").as_posix()
            venv = (root / "shared venv").as_posix()
            # 同じ venv 印を持つ配信でも、明示された別の設定ファイルは停止しない。
            target = self.start_server([venv, "-m", "mkdocs", "serve", "--config-file", config])
            neighbor = self.start_server([venv, "-m", "mkdocs", "serve", "--config-file=" + other])
            builder = self.start_server(["-m", "mkdocs", "build", "--config-file", config])
            unrelated = self.start_server(["serve", "--config-file", config])
            self.stop("--venv", venv, "--config", config, "--require-stopped")
            target.wait(timeout=10)
            self.assertIsNone(neighbor.poll())
            self.assertIsNone(builder.poll())
            self.assertIsNone(unrelated.poll())
            # 後処理も、実装と同じ停止処理で子孫まで停止する。
            self.stop("--config", other)
            neighbor.wait(timeout=10)

    def test_stops_legacy_venv_server_without_config_argument(self):
        with tempfile.TemporaryDirectory(prefix="legacy serve space ") as temporary:
            venv = (Path(temporary) / "venv").as_posix()
            server = self.start_server([venv + "/bin/mkdocs", "serve"])
            self.stop("--venv", venv, "--config", temporary + "/mkdocs.yml", "--require-stopped")
            server.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
