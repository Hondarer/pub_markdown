#!/usr/bin/env python3
"""プレビュー サイトのアセットと mkdocs.yml を配置する。

配置するものを次に示します。

- ``@plantuml/core`` の JavaScript と WebAssembly (ブラウザー上の PlantUML 描画)
- ``mermaid`` の ``mermaid.min.js`` (ブラウザー上の Mermaid 描画)
- ``livedocs/assets/`` 配下の自前スクリプトとスタイル
- Doxygen と Git の単一ページ リンク用 SVG、favicon、および theme 上書き
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

OWN_ASSETS = (
    "docsfw-diagrams.js",
    "docsfw-diagrams.css",
    "docsfw-mathjax.js",
    "docsfw-responsive-nav.js",
    "docsfw-svg-download.js",
    "docsfw-collapsible-list.js",
    "docsfw-collapsible-list.css",
    "docsfw-code-expander.js",
    "docsfw-code-expander.css",
    "docsfw-livedocs.css",
    "docsfw-pandoc-style.css",
    "docsfw-header-links.css",
    "docsfw-header-meta.css",
)

# ヘッダーの単一ページ リンクで使うアイコン。静的発行と同じく、provider 設定を
# 切り替えても参照が切れないように 4 種すべてを常時配置する。
HEADER_ICONS = (
    "docsfw-doxygen-icon.svg",
    "docsfw-git-icon.svg",
    "docsfw-github-icon.svg",
    "docsfw-gitlab-icon.svg",
    "docsfw-gitbucket-icon.svg",
)

FAVICON_ICONS = (
    "docsfw-mkdocs-favicon.svg",
)

STYLES_HTML_DIR = os.path.join(DOCSFW_DIR, "styles", "html")


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

    subprocess.run(
        ["node", os.path.join(DOCSFW_DIR, "bin", "build-browser-assets.js"), source_dir, assets_dir],
        check=True,
    )
    return 1


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
        shared = os.path.join(DOCSFW_DIR, "styles", "browser", name)
        src = shared if os.path.isfile(shared) else os.path.join(MKDOCS_DIR, "assets", name)
        if copy_if_changed(src, os.path.join(assets_dir, name)):
            copied += 1
    return copied


def vendor_header_icons(assets_dir):
    """ヘッダーの単一ページ リンクで使うアイコン SVG をプレビュー資産へコピーする。"""
    copied = 0
    for name in HEADER_ICONS:
        src = os.path.join(STYLES_HTML_DIR, name)
        if not os.path.isfile(src):
            print("Warning: アイコンが見つかりません: {}".format(src))
            continue
        if copy_if_changed(src, os.path.join(assets_dir, name)):
            copied += 1
    return copied


def vendor_favicon_icons(assets_dir):
    """動的発行の favicon SVG をプレビュー資産へコピーする。"""
    copied = 0
    for name in FAVICON_ICONS:
        src = os.path.join(STYLES_HTML_DIR, name)
        if not os.path.isfile(src):
            print("Warning: favicon が見つかりません: {}".format(src))
            continue
        if copy_if_changed(src, os.path.join(assets_dir, name)):
            copied += 1
    return copied


def vendor_theme(livedocs_dir):
    """Material の custom_dir 上書きを ``pages/livedocs/theme/`` へコピーする。

    正本から消えた上書きは、コピー先からも取り除きます。上書きを外したときに
    古い partial が残ると、Material 標準へ戻らないためです。
    """
    src_dir = os.path.join(MKDOCS_DIR, "theme")
    dst_dir = os.path.join(livedocs_dir, "theme")
    if not os.path.isdir(src_dir):
        return 0
    copied = 0
    keep = set()
    for dirpath, _dirnames, filenames in os.walk(src_dir):
        rel_dir = os.path.relpath(dirpath, src_dir)
        for filename in filenames:
            src = os.path.join(dirpath, filename)
            if rel_dir == os.curdir:
                relative = filename
            else:
                relative = os.path.join(rel_dir, filename)
            keep.add(os.path.normcase(relative))
            if copy_if_changed(src, os.path.join(dst_dir, relative)):
                copied += 1
    remove_stale_theme(dst_dir, keep)
    return copied


def remove_stale_theme(dst_dir, keep):
    """正本に無いファイルと、空になったディレクトリをコピー先から取り除く。"""
    if not os.path.isdir(dst_dir):
        return
    for dirpath, _dirnames, filenames in os.walk(dst_dir, topdown=False):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            relative = os.path.relpath(path, dst_dir)
            if os.path.normcase(relative) not in keep:
                os.remove(path)
        if dirpath != dst_dir and not os.listdir(dirpath):
            os.rmdir(dirpath)


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


def resolve_hooks_dir(livedocs_dir):
    """``hooks:`` に書く ``livedocs/bin`` の位置を ``mkdocs.yml`` から見て求める。

    mkdocs は ``hooks`` を設定ファイルのディレクトリ基準で解決する。
    docsfw の実際の配置 (``MKDOCS_DIR``) から求めるため、docsfw の位置と
    ``--livedocsDir`` の指定にそのまま追随する。
    """
    hooks_dir = os.path.join(MKDOCS_DIR, "bin")
    try:
        hooks_ref = os.path.relpath(hooks_dir, livedocs_dir)
    except ValueError:
        # Windows で livedocs_dir と docsfw が別ドライブにある場合は相対化できない
        hooks_ref = hooks_dir
    return hooks_ref.replace(os.sep, "/")


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
    text = text.replace("@LIVEDOCS_HOOKS_DIR@", resolve_hooks_dir(livedocs_dir))
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
        copied += vendor_header_icons(assets_dir)
        copied += vendor_favicon_icons(assets_dir)
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
