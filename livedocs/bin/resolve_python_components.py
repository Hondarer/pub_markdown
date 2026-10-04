#!/usr/bin/env python3
"""既存 Python の依存を優先し、不足分を専用 venv へ導入する。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys


HOME = Path(__file__).resolve().parents[1]
MODULES = {
    "mkdocs": "mkdocs.config",
    "mkdocs-material": "material",
    "markdown-callouts": "markdown_callouts",
    "pymdown-extensions": "pymdownx.superfences",
    "mkdocs-awesome-nav": "mkdocs_awesome_nav",
    "watchdog": "watchdog.observers",
}

# 標準ライブラリだけで探索する。対象 Python に pip がなくても判定できる。
PROBE = r'''
import contextlib, importlib, importlib.metadata as metadata, importlib.util, json, sys
packages = {}
for name, module in json.loads(sys.argv[1]).items():
    entry = {"version": "", "error": ""}
    try:
        entry["version"] = metadata.version(name)
        with contextlib.redirect_stdout(sys.stderr):
            importlib.import_module(module)
    except Exception as error:
        entry["error"] = str(error)
    packages[name] = entry
print(json.dumps({
    "packages": packages,
    "base_prefix": sys.base_prefix,
    "version": list(sys.version_info[:3]),
    "executable": sys.executable,
    "pip": importlib.util.find_spec("pip") is not None,
}))
'''


def load_requirements(path):
    """管理対象の ==、>=、< 指定を読み込む。"""
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"([a-zA-Z0-9_-]+)((?:(?:==|>=|<)\d+(?:\.\d+)*(?:,|$))+)", line)
        if not match or match[1] in result:
            raise ValueError("Invalid dependency declaration: " + line)
        result[match[1]] = match[2]
    return result


def release_version(value):
    # 採用するのは安定版だけ。プレリリース、開発版、ローカル版は補完対象とする。
    if not re.fullmatch(r"\d+(?:\.\d+)*", value):
        return None
    parts = tuple(int(part) for part in value.split("."))
    while parts and parts[-1] == 0:
        parts = parts[:-1]
    return parts


def satisfies(version, specification):
    value = release_version(version)
    if value is None:
        return False
    for clause in specification.split(","):
        match = re.fullmatch(r"(==|>=|<)(\d+(?:\.\d+)*)", clause)
        if not match:
            raise ValueError("Unsupported version constraint: " + clause)
        bound = release_version(match[2])
        if match[1] == "==" and value != bound:
            return False
        if match[1] == ">=" and value < bound:
            return False
        if match[1] == "<" and value >= bound:
            return False
    return True


def probe(python):
    result = subprocess.run(
        [str(python), "-c", PROBE, json.dumps(MODULES)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8",
        errors="replace", check=True,
    )
    return json.loads(result.stdout)


def missing_packages(state, compatible):
    return [name for name, constraint in compatible.items()
            if state["packages"][name]["error"]
            or not satisfies(state["packages"][name]["version"], constraint)]


def venv_python(venv):
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def validate_declarations(compatible, pinned):
    if set(compatible) != set(MODULES) or set(pinned) != set(MODULES):
        raise ValueError("Dependency declarations must match MODULES")
    for name in MODULES:
        if not pinned[name].startswith("==") or not satisfies(pinned[name][2:], compatible[name]):
            raise ValueError("Pinned version is outside the accepted range: " + name)


def select_python(venv, ensure=False, base_python=None):
    base_python = base_python or sys.executable
    compatible = load_requirements(HOME / "requirements-compatible.txt")
    pinned = load_requirements(HOME / "requirements.txt")
    validate_declarations(compatible, pinned)
    system = probe(base_python)
    if not missing_packages(system, compatible):
        return system["executable"]

    python = venv_python(venv)
    local = None
    if python.is_file():
        try:
            local = probe(python)
        except (OSError, subprocess.CalledProcessError, ValueError):
            pass
    if local is not None and (
        os.path.normcase(local["base_prefix"]) != os.path.normcase(system["base_prefix"])
        or local["version"] != system["version"]
    ):
        raise RuntimeError("The livedocs venv belongs to another Python; recreate it: " + str(venv))

    if ensure:
        config = venv / "pyvenv.cfg"
        shares_system = config.is_file() and re.search(
            r"^include-system-site-packages\s*=\s*true\s*$",
            config.read_text(encoding="utf-8"), re.M | re.I,
        )
        if local is None or not shares_system:
            print("INFO: Preparing livedocs venv at " + str(venv), file=sys.stderr, flush=True)
            # 既存 venv のパッケージは保持し、システム側への参照を有効にする。
            # see: https://docs.python.org/3/library/venv.html
            subprocess.run([str(base_python), "-m", "venv", "--system-site-packages", str(venv)], check=True)
            local = probe(python)

    if local is None:
        raise RuntimeError("Python dependencies are missing; run make livedocs-venv")
    missing = missing_packages(local, compatible)
    if missing and ensure:
        if not local["pip"]:
            subprocess.run([str(python), "-m", "ensurepip", "--upgrade"], check=True, stdout=sys.stderr)
        command = [str(python), "-m", "pip", "install", "--no-user",
                   "--disable-pip-version-check", "-c", str(HOME / "requirements-compatible.txt")]
        # 同じ固定版が入っていても import に失敗する場合は再導入する。
        if any(local["packages"][name]["error"]
               and local["packages"][name]["version"] == pinned[name][2:] for name in missing):
            command.append("--force-reinstall")
        if len(missing) == len(MODULES):
            command.extend(["-r", str(HOME / "requirements.txt")])
        else:
            command.extend(name + pinned[name] for name in missing)
        print("INFO: Installing livedocs dependencies: " + ", ".join(missing), file=sys.stderr, flush=True)
        subprocess.run(command, check=True, stdout=sys.stderr)
        local = probe(python)
        missing = missing_packages(local, compatible)
    if missing:
        raise RuntimeError("Unresolved Python dependencies: " + ", ".join(missing))
    return str(python)


def cache_info(venv):
    """CI の環境と依存宣言からキャッシュの識別子を求める。"""
    # venv は移動できないため、配置先とベース Python の絶対パスも鍵へ含める。
    # see: https://docs.python.org/3/library/venv.html#how-venvs-work
    import importlib.metadata as metadata
    import platform

    distributions = sorted((item.metadata.get("Name", ""), item.version,
                            str(item.locate_file(""))) for item in metadata.distributions())
    identity = [sys.platform, platform.machine(), sys.version, sys.executable,
                sys.prefix, sys.base_prefix, str(venv), distributions]
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8"))
    for path in (HOME / "requirements.txt", HOME / "requirements-compatible.txt", Path(__file__)):
        digest.update(path.read_bytes())
    pip = subprocess.run([sys.executable, "-m", "pip", "cache", "dir"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         encoding="utf-8", errors="replace", check=False)
    return {"key": digest.hexdigest(), "pip-cache": pip.stdout.strip() if pip.returncode == 0 else ""}


def run_child(command, environment):
    """子プロセスの終了を待ち、Ctrl+C の終了処理は子プロセスに任せる。"""
    process = subprocess.Popen(command, env=environment)
    # Ctrl+C は子プロセスにも届く。subprocess.call は待機中の中断で子プロセスを kill し、
    # mkdocs serve などの終了処理を打ち切るため、待機中だけ親で無視する。
    # see: https://github.com/python/cpython/blob/main/Lib/subprocess.py
    # 無視の設定は exec 後も引き継がれるため、子プロセスの起動後に切り替える。
    # see: https://pubs.opengroup.org/onlinepubs/9799919799/functions/exec.html
    previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        code = process.wait()
    finally:
        signal.signal(signal.SIGINT, previous)
    # シグナルによる終了は、シェルと同じく 128 + シグナル番号で返す。
    return 128 - code if code < 0 else code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv", type=Path, default=HOME / ".venv")
    parser.add_argument("--ensure", action="store_true")
    parser.add_argument("--print-python", action="store_true")
    parser.add_argument("--cache-info", action="store_true", help="GitHub Actions の出力形式で鍵と pip キャッシュを表示する")
    execution = parser.add_mutually_exclusive_group()
    execution.add_argument("--run", nargs=argparse.REMAINDER, help="選択した Python でモジュールを実行する")
    execution.add_argument("--run-script", nargs=argparse.REMAINDER, help="選択した Python でスクリプトを実行する")
    args = parser.parse_args()
    try:
        if args.cache_info:
            for key, value in cache_info(args.venv.resolve()).items():
                print(key + "=" + value)
            return 0
        python = select_python(args.venv.resolve(), args.ensure)
        if args.print_python:
            print(python)
        if args.run or args.run_script:
            environment = os.environ.copy()
            # Python と Node.js のテストも発行処理と同じ環境を使う。
            environment["BIN_TEST_PYTHON"] = python
            command = [python, "-m"] + args.run if args.run else [python] + args.run_script
            return run_child(command, environment)
        return 0
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
