#!/usr/bin/env python3
"""プレビュー サイトのアセットと mkdocs.yml を配置する。

配置するものを次に示します。

- ``@plantuml/core`` の JavaScript と WebAssembly (ブラウザー上の PlantUML 描画)
- ``mermaid`` の ``mermaid.min.js`` (ブラウザー上の Mermaid 描画)
- ``livedocs/assets/`` 配下の自前スクリプトとスタイル
- Doxygen 単一ページ リンク用の SVG と theme 上書き
- ``livedocs/mkdocs.yml.in`` から生成した ``pages/livedocs/mkdocs.yml``

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

from stage_livedocs import (  # noqa: E402
    DEFAULT_LIVEDOCS_VARIANT,
    parse_config,
    parse_livedocs_variant,
    write_if_changed,
)

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
    "docsfw-responsive-nav.js",
    "docsfw-svg-download.js",
    "docsfw-livedocs.css",
    "docsfw-pandoc-style.css",
    "docsfw-doxygen-link.css",
)

DOXYGEN_ICON_SRC = os.path.join(DOCSFW_DIR, "styles", "html", "docsfw-doxygen-icon.svg")


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


def vendor_doxygen_icon(assets_dir):
    """docsfw の Doxygen アイコン SVG をプレビュー資産へコピーする。"""
    if not os.path.isfile(DOXYGEN_ICON_SRC):
        print("Warning: Doxygen アイコンが見つかりません: {}".format(DOXYGEN_ICON_SRC))
        return 0
    dst = os.path.join(assets_dir, "docsfw-doxygen-icon.svg")
    return 1 if copy_if_changed(DOXYGEN_ICON_SRC, dst) else 0


def vendor_theme(livedocs_dir):
    """Material の custom_dir 上書きを ``pages/livedocs/theme/`` へコピーする。"""
    src_dir = os.path.join(MKDOCS_DIR, "theme")
    dst_dir = os.path.join(livedocs_dir, "theme")
    if not os.path.isdir(src_dir):
        return 0
    copied = 0
    for dirpath, _dirnames, filenames in os.walk(src_dir):
        rel_dir = os.path.relpath(dirpath, src_dir)
        for filename in filenames:
            src = os.path.join(dirpath, filename)
            if rel_dir == os.curdir:
                dst = os.path.join(dst_dir, filename)
            else:
                dst = os.path.join(dst_dir, rel_dir, filename)
            if copy_if_changed(src, dst):
                copied += 1
    return copied


def has_nav_files(docs_dir):
    """ステージング先に ``.nav.yml`` が 1 つでもあるかどうかを返す。"""
    for dirpath, _dirnames, filenames in os.walk(docs_dir):
        if ".nav.yml" in filenames:
            return True
    return False


def resolve_site_name(workspace, config_path):
    """``site_name`` に使う名前をワークスペース側の設定から解決する。

    ``.vscode/pub_markdown.config.yaml`` の ``siteName`` を優先し、
    未指定ならワークスペース フォルダー名を使う。
    """
    site_name = (parse_config(config_path).get("siteName") or "").strip()
    if site_name:
        return site_name
    return os.path.basename(os.path.normpath(workspace))


def generate_mkdocs_yml(livedocs_dir, nav_generated, variant=DEFAULT_LIVEDOCS_VARIANT,
                        site_name=""):
    """``mkdocs.yml.in`` から ``pages/livedocs/mkdocs.yml`` を生成する。"""
    lang, _details, variant_name = parse_livedocs_variant(variant)
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

    text = "\n".join(lines)
    text = text.replace("@LIVEDOCS_SITE_NAME@", site_name)
    text = text.replace("@LIVEDOCS_VARIANT@", variant_name)
    text = text.replace("@LIVEDOCS_THEME_LANGUAGE@", lang)
    return write_if_changed(os.path.join(livedocs_dir, "mkdocs.yml"), text)


def main(argv=None):
    parser = argparse.ArgumentParser(description="mkdocs プレビューのアセットと設定を配置する")
    parser.add_argument("--workspaceFolder", dest="workspace", required=True)
    parser.add_argument("--livedocsDir", dest="livedocs_dir", default=None,
                        help="既定は <workspaceFolder>/pages/livedocs")
    parser.add_argument("--configFile", dest="config", default=None,
                        help="既定は <workspaceFolder>/.vscode/pub_markdown.config.yaml")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--variant",
        default=DEFAULT_LIVEDOCS_VARIANT,
        help="ja / ja-details / en / en-details (default: ja-details)",
    )
    args = parser.parse_args(argv)

    workspace = os.path.abspath(args.workspace)
    livedocs_dir = os.path.abspath(args.livedocs_dir or os.path.join(workspace, "pages", "livedocs"))
    config_path = args.config or os.path.join(workspace, ".vscode", "pub_markdown.config.yaml")
    assets_dir = os.path.join(livedocs_dir, "src", "assets")

    try:
        _lang, _details, variant = parse_livedocs_variant(args.variant)
        resolved = resolve_node_components()
        copied = vendor_plantuml(assets_dir, resolved.get("paths", {}).get("plantumlCore", ""))
        copied += vendor_mermaid(assets_dir, resolved.get("paths", {}).get("mermaidJs", ""))
        copied += vendor_own_assets(assets_dir)
        copied += vendor_doxygen_icon(assets_dir)
        copied += vendor_theme(livedocs_dir)
    except (FileNotFoundError, ValueError) as error:
        print("Error: {}".format(error), file=sys.stderr)
        return 1

    nav_generated = has_nav_files(os.path.join(livedocs_dir, "src"))
    site_name = resolve_site_name(workspace, config_path)
    changed = generate_mkdocs_yml(livedocs_dir, nav_generated, variant=variant,
                                  site_name=site_name)

    if not args.quiet:
        print("vendored: {} assets, mkdocs.yml {}".format(copied, "updated" if changed else "unchanged"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
