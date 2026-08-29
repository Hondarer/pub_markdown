#!/usr/bin/env python3
"""プレビュー サイトのアセットと mkdocs.yml を配置する。

配置するものを次に示します。

- ``@plantuml/core`` の JavaScript と WebAssembly (ブラウザー上の PlantUML 描画)
- ``mermaid`` の ``mermaid.min.js`` (ブラウザー上の Mermaid 描画)
- ``mkdocs/assets/`` 配下の自前スクリプトとスタイル
- ``mkdocs/mkdocs.yml.in`` から生成した ``pages/preview/mkdocs.yml``

いずれも docsfw の ``bin/node_modules`` を参照します。
``npm ci`` が済んでいない場合はエラーを返します。

使用方法:

    python3 vendor_assets.py --workspaceFolder=/path/to/workspace
"""

import argparse
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage_preview_docs import write_if_changed  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

MKDOCS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCSFW_DIR = os.path.dirname(MKDOCS_DIR)
NODE_MODULES = os.path.join(DOCSFW_DIR, "bin", "node_modules")

# @plantuml/core から取り出すファイル。
# emoji.js と openiconic.js は plantuml.js が必要に応じて読み込むため同じ場所に置く。
PLANTUML_FILES = ("plantuml.js", "viz-global.js", "emoji.js", "openiconic.js", "LICENSE")

MERMAID_CANDIDATES = (
    os.path.join("mermaid", "dist", "mermaid.min.js"),
    os.path.join("@mermaid-js", "mermaid-cli", "node_modules", "mermaid", "dist", "mermaid.min.js"),
)

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


def vendor_plantuml(assets_dir):
    """``@plantuml/core`` のファイルを配置する。"""
    source_dir = os.path.join(NODE_MODULES, "@plantuml", "core")
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(
            "@plantuml/core が見つかりません。framework/docsfw/bin で npm ci を実行してください: {}".format(source_dir)
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


def vendor_mermaid(assets_dir):
    """``mermaid.min.js`` を配置する。"""
    for candidate in MERMAID_CANDIDATES:
        src = os.path.join(NODE_MODULES, candidate)
        if os.path.isfile(src):
            dst = os.path.join(assets_dir, "mermaid", "mermaid.min.js")
            return 1 if copy_if_changed(src, dst) else 0

    raise FileNotFoundError(
        "mermaid.min.js が見つかりません。framework/docsfw/bin で npm ci を実行してください"
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
        copied = vendor_plantuml(assets_dir)
        copied += vendor_mermaid(assets_dir)
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
