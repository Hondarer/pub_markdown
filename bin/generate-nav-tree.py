#!/usr/bin/env python3
"""
generate-nav-tree.py

Walks a pub_markdown HTML output directory, extracts page titles, builds a
navigation tree, and writes nav-tree.js to the html root.

The output file sets:
    window.__DOCSFW_NAV__  - tree object used by docsfw-nav.js

Tree node format:
    { "title": str, "url": str|null, "children": [...] }

    - A directory is represented by its index.html (url = "dir/index.html").
      If no index.html exists, url is null.
    - Leaf pages have no "children" key (or children=[]).
    - Children are sorted: files and subdirs mixed alphabetically by name,
      unless the corresponding source directory provides a publocal.yaml with
      an explicit "order" list (listed entries first, the rest by name).

Usage: python3 generate-nav-tree.py <html-root> [<source-md-root> [alias=dir ...]]

  <source-md-root> is the Markdown source root (mdRoot). When given, each
  output directory's child order can be overridden by a publocal.yaml placed
  in the corresponding source directory. When omitted, the legacy name order
  is used (backward compatible).

  Each trailing "alias=dir" is a mergeSubfolderDocs mapping: output paths under
  "<alias>/..." resolve to the real source directory "<dir>/..." for the
  purpose of locating publocal.yaml.
"""

import sys
import os
import json
import re

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Non-HTML assets to ignore when walking
SKIP_NAMES = {
    'search-index.js', 'nav-tree.js', 'minisearch.min.js',
    'docsfw-search.js', 'docsfw-nav.js', 'docsfw-tokenize.js', 'docsfw-ui.css',
    'html-style.css', 'mermaid.min.js',
}

# ---------------------------------------------------------------------------
# Source-directory ordering (publocal.yaml)
# ---------------------------------------------------------------------------

# Markdown source root passed as the optional 2nd CLI argument. None => legacy
# name ordering (backward compatible).
SRC_ROOT = None

# mergeSubfolderDocs mapping: alias -> real source directory. Output directories
# under "<alias>/..." map to "<real>/..." instead of "<SRC_ROOT>/<alias>/...".
MERGE_MAP = {}

# Cache: source directory -> { normalized_name: order_index }
_order_cache = {}


def resolve_src_dir(prefix):
    """Map an output-relative directory *prefix* to its source directory.

    Honors mergeSubfolderDocs aliases (longest alias match wins). Returns None
    when no source root is configured.
    """
    if SRC_ROOT is None:
        return None
    p = prefix.strip('/')
    if not p:
        return SRC_ROOT

    best = None  # (alias_stripped, real_dir)
    for alias, real in MERGE_MAP.items():
        a = alias.strip('/')
        if a and (p == a or p.startswith(a + '/')):
            if best is None or len(a) > len(best[0]):
                best = (a, real)
    if best is not None:
        a, real = best
        rest = p[len(a):].lstrip('/')
        return os.path.join(real, rest.replace('/', os.sep)) if rest else real

    return os.path.join(SRC_ROOT, p.replace('/', os.sep))


def normalize_order_name(name):
    """Normalize an order entry or an item name to a comparison key.

    Strips a known document/output extension and a trailing slash, then
    lowercases. So 'overview.md', 'overview.html' and 'overview/' all compare
    equal to the directory/file stem 'overview'.
    """
    base = name.rstrip('/')
    lower = base.lower()
    for ext in ('.md', '.markdown', '.html'):
        if lower.endswith(ext):
            base = base[:-len(ext)]
            break
    return base.lower()


def load_order(src_dir):
    """Return { normalized_name: index } from publocal.yaml in *src_dir*.

    Returns an empty dict when there is no publocal.yaml or no 'order' list.
    Results are cached per directory. The parser is intentionally minimal
    (matching the awk-level YAML handling used elsewhere in docsfw): it reads a
    top-level 'order:' key followed by '- item' list entries.
    """
    if src_dir in _order_cache:
        return _order_cache[src_dir]

    result = {}
    path = os.path.join(src_dir, 'publocal.yaml')
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            in_order = False
            idx = 0
            for raw in fh:
                line = raw.rstrip('\r\n')
                if re.match(r'^order:\s*$', line):
                    in_order = True
                    continue
                if not in_order:
                    continue
                m = re.match(r'^\s*-\s*(.*)$', line)
                if m:
                    name = re.sub(r'\s+#.*$', '', m.group(1)).strip()
                    if len(name) >= 2 and name[0] == name[-1] and name[0] in '"\'':
                        name = name[1:-1]
                    key = normalize_order_name(name)
                    if key and key not in result:
                        result[key] = idx
                        idx += 1
                elif re.match(r'^\S', line):
                    # A new top-level key terminates the order block.
                    in_order = False
    except (OSError, IOError):
        pass

    _order_cache[src_dir] = result
    return result


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def extract_title(path):
    """Extract the page title from HTML (reads first 8 KB).

    Priority:
      1. <meta name="docsfw-nav-title" content="..."> — short-title for nav/toc
      2. <title>...</title> — document title
      3. filename stem — fallback
    """
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            head = fh.read(8192)

        def unescape(text):
            return (text
                    .replace('&amp;', '&')
                    .replace('&lt;', '<')
                    .replace('&gt;', '>')
                    .replace('&quot;', '"')
                    .replace('&#39;', "'"))

        # 1. docsfw-nav-title meta タグを優先して採用する
        m = re.search(
            r'<meta\s[^>]*name=["\']docsfw-nav-title["\'][^>]*content=["\']([^"\']*)["\']',
            head, re.IGNORECASE)
        if not m:
            # content が name より先に来る形式にも対応
            m = re.search(
                r'<meta\s[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']docsfw-nav-title["\']',
                head, re.IGNORECASE)
        if m:
            nav_title = unescape(m.group(1)).strip()
            if nav_title:
                return nav_title

        # 2. <title> タグ
        m = re.search(r'<title[^>]*>(.*?)</title>', head, re.IGNORECASE | re.DOTALL)
        if m:
            text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            return unescape(text)
    except Exception:
        pass
    # 3. Fallback: use stem of filename
    return os.path.splitext(os.path.basename(path))[0]


def collect_pages(html_root):
    """
    Walk html_root and return {rel_path: title} for every HTML page.
    rel_path uses POSIX separators (/).
    """
    pages = {}
    for dirpath, dirnames, filenames in os.walk(html_root):
        dirnames.sort()
        for fname in sorted(filenames):
            if not fname.endswith('.html'):
                continue
            if fname in SKIP_NAMES:
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, html_root).replace(os.sep, '/')
            pages[rel_path] = extract_title(abs_path)
    return pages


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------

def build_tree(pages, prefix=''):
    """
    Recursively build a tree node for the directory at *prefix*.

    prefix: POSIX path ending with '/', or '' for root.
    """
    # Determine index URL and title for this directory
    index_url = prefix + 'index.html'
    if index_url in pages:
        dir_title = pages[index_url]
    else:
        index_url = None
        # Use the last component of the prefix as the fallback title
        dir_title = prefix.rstrip('/').split('/')[-1] if prefix else ''

    # Collect direct children: files (non-index) and immediate subdirs
    direct_files = {}   # fname -> (rel_path, title)
    direct_dirs  = {}   # dirname -> True  (deduplicated)

    for rel_path in sorted(pages.keys()):
        if prefix and not rel_path.startswith(prefix):
            continue
        rest = rel_path[len(prefix):]
        if not rest:
            continue
        slash = rest.find('/')
        if slash == -1:
            # Direct file in this directory
            if rest != 'index.html':
                direct_files[rest] = (rel_path, pages[rel_path])
        else:
            # In a subdirectory
            subdir = rest[:slash]
            direct_dirs[subdir] = True

    # Build child nodes, mixed alphabetically by name
    all_items = {}  # name -> node (for sorting)

    for fname, (rel_path, title) in direct_files.items():
        all_items[fname] = {'title': title, 'url': rel_path}

    for subdir in direct_dirs:
        sub_node = build_tree(pages, prefix + subdir + '/')
        all_items[subdir] = sub_node

    # Determine child order. By default it is the case-insensitive name order.
    # When a source publocal.yaml exists for this directory, listed entries come
    # first in that order; the rest follow by name.
    order_map = {}
    src_dir = resolve_src_dir(prefix)
    if src_dir is not None:
        order_map = load_order(src_dir)

    def child_sort_key(name):
        idx = order_map.get(normalize_order_name(name), len(order_map))
        return (idx, name.lower())

    children = [all_items[k] for k in sorted(all_items.keys(), key=child_sort_key)]

    node = {
        'title':    dir_title,
        'url':      index_url,
        'path':     prefix,     # directory path for ancestry check (e.g. "calc/doxybook2_public/")
        'children': children,
    }
    return node


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global SRC_ROOT

    if len(sys.argv) < 2:
        sys.stderr.write('Usage: python3 generate-nav-tree.py <html-root> [<source-md-root>]\n')
        sys.exit(1)

    html_root = sys.argv[1]
    if not os.path.isdir(html_root):
        sys.stderr.write(f'Error: not a directory: {html_root}\n')
        sys.exit(1)

    # Optional source mdRoot: enables publocal.yaml order overrides.
    if len(sys.argv) >= 3 and sys.argv[2]:
        if os.path.isdir(sys.argv[2]):
            SRC_ROOT = sys.argv[2]
        else:
            sys.stderr.write(f'  Warning: source md-root not found, using name order: {sys.argv[2]}\n')

    # Optional mergeSubfolderDocs mapping: each remaining arg is "alias=real-dir".
    for arg in sys.argv[3:]:
        if '=' in arg:
            alias, real = arg.split('=', 1)
            if alias and real:
                MERGE_MAP[alias] = real

    sys.stdout.write(f'  Collecting pages from {html_root}...\n')
    pages = collect_pages(html_root)
    sys.stdout.write(f'  Found {len(pages)} pages\n')

    tree = build_tree(pages, prefix='')

    nav_js = (
        '/* docsfw nav-tree.js - auto-generated by generate-nav-tree.py, do not edit */\n'
        f'window.__DOCSFW_NAV__ = {json.dumps(tree, ensure_ascii=False)};\n'
    )

    out_path = os.path.join(html_root, 'nav-tree.js')
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(nav_js)

    kb = len(nav_js.encode('utf-8')) / 1024
    sys.stdout.write(f'  Written: nav-tree.js ({kb:.0f} KB)\n')


if __name__ == '__main__':
    main()
