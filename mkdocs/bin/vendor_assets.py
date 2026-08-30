#!/usr/bin/env python3
"""プレビュー サイトのアセットと mkdocs.yml を配置する。

配置するものを次に示します。

- ``@plantuml/core`` の JavaScript と WebAssembly (ブラウザー上の PlantUML 描画)
- ``mermaid`` の ``mermaid.min.js`` (ブラウザー上の Mermaid 描画)
- ``mkdocs/assets/`` 配下の自前スクリプトとスタイル
- ``mkdocs/mkdocs.yml.in`` から生成した ``pages/preview/mkdocs.yml``

いずれも ``bin/resolve-node-components.js`` が解決したパスを参照します。
必須コンポーネントが無ければオンデマンドで導入します。

使用方法:

    python3 vendor_assets.py --workspaceFolder=/path/to/workspace
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage_preview_docs import write_if_changed  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

MKDOCS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCSFW_DIR = os.path.dirname(MKDOCS_DIR)
RESOLVE_SCRIPT = os.path.join(DOCSFW_DIR, "bin", "resolve-node-components.js")

# @plantuml/core から取り出すファイル。
# emoji.js と openiconic.js は plantuml.js が必要に応じて読み込むため同じ場所に置く。
PLANTUML_FILES = ("plantuml.js", "viz-global.js", "emoji.js", "openiconic.js", "LICENSE")

OWN_ASSETS = (
    "docsfw-plantuml.js",
    "docsfw-mermaid.js",
    "docsfw-mathjax.js",
    "docsfw-preview.css",
    "docsfw-pandoc-style.css",
)


def copy_if_changed(src, dst):
    """内容が変わったときだけコピーする。"""
    if os.path.isfile(dst):
        src_stat = os.stat(src)
        dst_stat = os.stat(dst)
        if src_stat.st_size == dst_stat.st_size and int(src_stat.st_mtime) == int(dst_stat.st_mtime):
            return False
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    shutil.copy2(src, dst)
    return True


def resolve_node_components():
    """必須 npm コンポーネントを解決し、欠けていれば導入する。"""
    result = subprocess.run(
        ["node", RESOLVE_SCRIPT, "--ensure"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "node component resolve failed"
        raise FileNotFoundError(message)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise FileNotFoundError("node component resolve の JSON を解釈できません: {}".format(error))


def vendor_plantuml(assets_dir, source_dir):
    """``@plantuml/core`` のファイルを配置する。"""
    if not source_dir or not os.path.isdir(source_dir):
        raise FileNotFoundError(
            "@plantuml/core が見つかりません。framework/docsfw/bin の node コンポーネントを解決してください"
        )

    target_dir = os.path.join(assets_dir, "plantuml")
    copied = 0
    for name in PLANTUML_FILES:
        src = os.path.join(source_dir, name)
        if not os.path.isfile(src):
            print("Warning: @plantuml/core に {} がありません".format(name))
            continue
        if copy_if_changed(src, os.path.join(target_dir, name)):
            copied += 1
    return copied


def vendor_mermaid(assets_dir, mermaid_js):
    """``mermaid.min.js`` を配置する。"""
    if mermaid_js and os.path.isfile(mermaid_js):
        dst = os.path.join(assets_dir, "mermaid", "mermaid.min.js")
        return 1 if copy_if_changed(mermaid_js, dst) else 0

    raise FileNotFoundError(
        "mermaid.min.js が見つかりません。framework/docsfw/bin の node コンポーネントを解決してください"
    )


def vendor_own_assets(assets_dir):
    """自前のスクリプトとスタイルを配置する。"""
    copied = 0
    for name in OWN_ASSETS:
        src = os.path.join(MKDOCS_DIR, "assets", name)
        if copy_if_changed(src, os.path.join(assets_dir, name)):
            copied += 1
    return copied


def has_nav_files(docs_dir):
    """ステージング先に ``.nav.yml`` が 1 つでもあるかどうかを返す。"""
    for dirpath, _dirnames, filenames in os.walk(docs_dir):
        if ".nav.yml" in filenames:
            return True
    return False


def generate_mkdocs_yml(preview_dir, nav_generated):
    """``mkdocs.yml.in`` から ``pages/preview/mkdocs.yml`` を生成する。"""
    template_path = os.path.join(MKDOCS_DIR, "mkdocs.yml.in")
    with open(template_path, "r", encoding="utf-8") as handle:
        template = handle.read()

    replacements = {
        "@AWESOME_NAV@": "  - awesome-nav" if nav_generated else "",
    }

    # 置換記号だけの行を差し替える。説明文の中に現れた記号は対象にしない。
    lines = []
    for line in template.split("\n"):
        if line.strip() in replacements:
            replaced = replacements[line.strip()]
            if replaced:
                lines.append(replaced)
        else:
            lines.append(line)

    return write_if_changed(os.path.join(preview_dir, "mkdocs.yml"), "\n".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description="mkdocs プレビューのアセットと設定を配置する")
    parser.add_argument("--workspaceFolder", dest="workspace", required=True)
    parser.add_argument("--previewDir", dest="preview_dir", default=None,
                        help="既定は <workspaceFolder>/pages/preview")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    workspace = os.path.abspath(args.workspace)
    preview_dir = os.path.abspath(args.preview_dir or os.path.join(workspace, "pages", "preview"))
    assets_dir = os.path.join(preview_dir, "src", "assets")

    try:
        resolved = resolve_node_components()
        copied = vendor_plantuml(assets_dir, resolved.get("paths", {}).get("plantumlCore", ""))
        copied += vendor_mermaid(assets_dir, resolved.get("paths", {}).get("mermaidJs", ""))
        copied += vendor_own_assets(assets_dir)
    except FileNotFoundError as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 1

    nav_generated = has_nav_files(os.path.join(preview_dir, "src"))
    changed = generate_mkdocs_yml(preview_dir, nav_generated)

    if not args.quiet:
        print("vendored: {} assets, mkdocs.yml {}".format(copied, "updated" if changed else "unchanged"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
