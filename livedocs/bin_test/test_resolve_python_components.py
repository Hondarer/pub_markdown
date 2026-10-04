"""Python の採用条件と、不足時だけ venv へ導入する動作を検証する。"""

import copy
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


BIN = Path(__file__).resolve().parents[1] / "bin"
sys.path.insert(0, str(BIN))
import resolve_python_components as resolver  # noqa: E402


class ResolverTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="python components space ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.venv = self.root / "venv space"
        self.pinned = resolver.load_requirements(resolver.HOME / "requirements.txt")
        self.compatible = resolver.load_requirements(resolver.HOME / "requirements-compatible.txt")
        self.complete = {
            "packages": {name: {"version": value[2:], "error": ""}
                         for name, value in self.pinned.items()},
            "base_prefix": "/python base", "version": [3, 14, 3],
            "executable": "/python base/python", "pip": True,
        }

    def missing(self, *names):
        state = copy.deepcopy(self.complete)
        for name in names:
            state["packages"][name] = {"version": "", "error": "not installed"}
        return state

    def existing_venv(self, shares_system=True):
        python = resolver.venv_python(self.venv)
        python.parent.mkdir(parents=True)
        python.touch()
        (self.venv / "pyvenv.cfg").write_text(
            "include-system-site-packages = " + str(shares_system).lower() + "\n",
            encoding="utf-8",
        )
        return python

    def test_current_pins_are_inside_ranges(self):
        resolver.validate_declarations(self.compatible, self.pinned)

    def test_compatible_system_does_not_create_venv_or_run_pip(self):
        with patch.object(resolver, "probe", return_value=self.complete), patch.object(
            resolver.subprocess, "run"
        ) as run:
            self.assertEqual(resolver.select_python(self.venv, ensure=True), self.complete["executable"])
        run.assert_not_called()
        self.assertFalse(self.venv.exists())

    def test_system_is_preferred_even_if_old_local_environment_exists(self):
        self.existing_venv()
        with patch.object(resolver, "probe", return_value=self.complete) as probe:
            self.assertEqual(resolver.select_python(self.venv), self.complete["executable"])
        probe.assert_called_once()

    def test_one_missing_package_installs_only_its_pin(self):
        python = self.existing_venv()
        incomplete = self.missing("watchdog")
        with patch.object(resolver, "probe", side_effect=[incomplete, incomplete, self.complete]), patch.object(
            resolver.subprocess, "run"
        ) as run:
            self.assertEqual(resolver.select_python(self.venv, ensure=True), str(python))
        command = run.call_args.args[0]
        self.assertEqual(command[:4], [str(python), "-m", "pip", "install"])
        self.assertEqual(command[-1], "watchdog==6.0.0")
        self.assertIn("--no-user", command)
        self.assertIn(str(resolver.HOME / "requirements-compatible.txt"), command)
        self.assertNotIn("-r", command)
        run.assert_called_once()

    def test_all_missing_packages_create_shared_venv_and_install_all_pins(self):
        incomplete = self.missing(*resolver.MODULES)
        with patch.object(resolver, "probe", side_effect=[incomplete, incomplete, self.complete]), patch.object(
            resolver.subprocess, "run"
        ) as run:
            resolver.select_python(self.venv, ensure=True, base_python="system python")
        create, install = [item.args[0] for item in run.call_args_list]
        self.assertEqual(create, ["system python", "-m", "venv", "--system-site-packages", str(self.venv)])
        self.assertEqual(install[-2:], ["-r", str(resolver.HOME / "requirements.txt")])

    def test_ready_local_environment_needs_no_install(self):
        python = self.existing_venv()
        with patch.object(resolver, "probe", side_effect=[self.missing("watchdog"), self.complete]), patch.object(
            resolver.subprocess, "run"
        ) as run:
            self.assertEqual(resolver.select_python(self.venv, ensure=True), str(python))
        run.assert_not_called()

    def test_old_isolated_venv_is_enabled_without_clearing_packages(self):
        self.existing_venv(shares_system=False)
        with patch.object(resolver, "probe", side_effect=[self.missing("watchdog"), self.complete, self.complete]), patch.object(
            resolver.subprocess, "run"
        ) as run:
            resolver.select_python(self.venv, ensure=True)
        self.assertIn("--system-site-packages", run.call_args.args[0])
        self.assertNotIn("--clear", run.call_args.args[0])
        run.assert_called_once()

    def test_material_other_version_is_not_adopted(self):
        incompatible = copy.deepcopy(self.complete)
        incompatible["packages"]["mkdocs-material"]["version"] = "9.7.8"
        self.assertEqual(resolver.missing_packages(incompatible, self.compatible), ["mkdocs-material"])

    def test_compatible_newer_versions_are_adopted(self):
        newer = copy.deepcopy(self.complete)
        newer["packages"]["mkdocs"]["version"] = "1.7.0"
        newer["packages"]["watchdog"]["version"] = "6.1.0"
        self.assertEqual(resolver.missing_packages(newer, self.compatible), [])

    def test_version_boundaries_and_non_stable_versions(self):
        for version, expected in [("1.6.0", False), ("1.6.1", True), ("1.6.1.0", True),
                                  ("1.9.9", True), ("2.0", False), ("2.0.0rc1", False),
                                  ("1.6.1.dev1", False), ("1.6.1+local", False)]:
            with self.subTest(version=version):
                self.assertEqual(resolver.satisfies(version, ">=1.6.1,<2.0.0"), expected)

    def test_out_of_range_package_is_replaced_with_pin(self):
        self.existing_venv()
        old = copy.deepcopy(self.complete)
        old["packages"]["mkdocs"]["version"] = "1.5.0"
        with patch.object(resolver, "probe", side_effect=[old, old, self.complete]), patch.object(
            resolver.subprocess, "run"
        ) as run:
            resolver.select_python(self.venv, ensure=True)
        self.assertEqual(run.call_args.args[0][-1], "mkdocs==1.6.1")

    def test_same_version_with_broken_import_is_reinstalled(self):
        self.existing_venv()
        broken = copy.deepcopy(self.complete)
        broken["packages"]["watchdog"]["error"] = "missing submodule"
        with patch.object(resolver, "probe", side_effect=[broken, broken, self.complete]), patch.object(
            resolver.subprocess, "run"
        ) as run:
            resolver.select_python(self.venv, ensure=True)
        self.assertIn("--force-reinstall", run.call_args.args[0])

    def test_venv_without_pip_bootstraps_it_only_when_installing(self):
        self.existing_venv()
        incomplete = self.missing("watchdog")
        incomplete["pip"] = False
        with patch.object(resolver, "probe", side_effect=[incomplete, incomplete, self.complete]), patch.object(
            resolver.subprocess, "run"
        ) as run:
            resolver.select_python(self.venv, ensure=True)
        self.assertEqual(run.call_args_list[0].args[0][1:], ["-m", "ensurepip", "--upgrade"])

    def test_unresolved_dependencies_after_install_fail(self):
        self.existing_venv()
        incomplete = self.missing("watchdog")
        with patch.object(resolver, "probe", return_value=incomplete), patch.object(resolver.subprocess, "run"):
            with self.assertRaisesRegex(RuntimeError, "Unresolved.*watchdog"):
                resolver.select_python(self.venv, ensure=True)

    def test_failed_pip_install_propagates(self):
        self.existing_venv()
        with patch.object(resolver, "probe", return_value=self.missing("watchdog")), patch.object(
            resolver.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "pip")
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                resolver.select_python(self.venv, ensure=True)

    def test_read_only_selection_never_installs(self):
        with patch.object(resolver, "probe", return_value=self.missing("watchdog")), patch.object(
            resolver.subprocess, "run"
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "make livedocs-venv"):
                resolver.select_python(self.venv)
        run.assert_not_called()

    def test_venv_from_another_python_is_not_overwritten(self):
        self.existing_venv()
        foreign = copy.deepcopy(self.complete)
        foreign["base_prefix"] = "/another python"
        with patch.object(resolver, "probe", side_effect=[self.missing("watchdog"), foreign]), patch.object(
            resolver.subprocess, "run"
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "another Python"):
                resolver.select_python(self.venv, ensure=True)
        run.assert_not_called()

    def test_real_probe_checks_metadata_and_importability(self):
        module = self.root / "resolver_fixture.py"
        module.write_text("raise RuntimeError('fixture import failure')\n", encoding="utf-8")
        info = self.root / "resolver_fixture-1.0.0.dist-info"
        info.mkdir()
        (info / "METADATA").write_text("Name: resolver-fixture\nVersion: 1.0.0\n", encoding="utf-8")
        with patch.object(resolver, "MODULES", {"resolver-fixture": "resolver_fixture"}), patch.dict(
            os.environ, {"PYTHONPATH": str(self.root)}
        ):
            result = resolver.probe(sys.executable)
        self.assertEqual(result["packages"]["resolver-fixture"]["version"], "1.0.0")
        self.assertIn("fixture import failure", result["packages"]["resolver-fixture"]["error"])

    def test_cli_uses_complete_system_environment_without_creating_venv(self):
        # 実パッケージの有無によらず、空白入りパスに読み込める配布物を用意する。
        for name, imported in resolver.MODULES.items():
            parts = imported.split(".")
            package = self.root / parts[0]
            package.mkdir(exist_ok=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            if len(parts) > 1:
                (package / (parts[1] + ".py")).write_text("", encoding="utf-8")
            info = self.root / (name.replace("-", "_") + "-" + self.pinned[name][2:] + ".dist-info")
            info.mkdir()
            (info / "METADATA").write_text(
                "Name: " + name + "\nVersion: " + self.pinned[name][2:] + "\n", encoding="utf-8",
            )
        (self.root / "selected_fixture.py").write_text(
            "import os, sys; print(sys.executable); print(os.environ['PYTHON']); raise SystemExit(7)\n",
            encoding="utf-8",
        )
        environment = dict(os.environ, PYTHONPATH=str(self.root))
        command = [sys.executable, str(BIN / "resolve_python_components.py"), "--venv", str(self.venv)]
        result = subprocess.run(command + ["--ensure", "--print-python"], env=environment,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        selected = result.stdout.strip()
        self.assertEqual(Path(selected), Path(sys.executable))
        self.assertFalse(self.venv.exists())
        result = subprocess.run(command + ["--run", "selected_fixture"], env=environment,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [selected, selected])
        result = subprocess.run(command + ["--run-script", str(self.root / "selected_fixture.py")],
                                env=environment, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [selected, selected])

    def test_cache_identity_changes_with_venv_location_or_requirements(self):
        home = self.root / "declarations"
        home.mkdir()
        for filename in ("requirements.txt", "requirements-compatible.txt"):
            (home / filename).write_bytes((resolver.HOME / filename).read_bytes())
        pip = subprocess.CompletedProcess([], 0, stdout="/pip cache\n", stderr="")
        with patch.object(resolver, "HOME", home), patch("importlib.metadata.distributions", return_value=[]), patch.object(
            resolver.subprocess, "run", return_value=pip
        ):
            first = resolver.cache_info(self.venv)
            self.assertEqual(first, resolver.cache_info(self.venv))
            self.assertNotEqual(first["key"], resolver.cache_info(self.root / "moved venv")["key"])
            with (home / "requirements-compatible.txt").open("a", encoding="utf-8") as handle:
                handle.write("# changed declaration\n")
            self.assertNotEqual(first["key"], resolver.cache_info(self.venv)["key"])
        self.assertEqual(first["pip-cache"], "/pip cache")
        self.assertFalse(self.venv.exists())

    def test_child_handles_interrupt_while_parent_waits(self):
        # 子プロセスの起動後だけ Ctrl+C を無視し、待機後に元の設定へ戻す。
        observed = []

        class Child:
            def __init__(self, command, env):
                observed.append(signal.getsignal(signal.SIGINT))

            def wait(self):
                observed.append(signal.getsignal(signal.SIGINT))
                return -signal.SIGINT

        previous = signal.getsignal(signal.SIGINT)
        with patch.object(resolver.subprocess, "Popen", Child):
            code = resolver.run_child(["child"], {})
        self.assertEqual(observed, [previous, signal.SIG_IGN])
        self.assertEqual(signal.getsignal(signal.SIGINT), previous)
        self.assertEqual(code, 128 + signal.SIGINT)


if __name__ == "__main__":
    unittest.main()
