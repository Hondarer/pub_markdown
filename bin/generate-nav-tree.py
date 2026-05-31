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
    - Children are sorted: files and subdirs mixed alphabetically by name.

Usage: python3 generate-nav-tree.py <html-root>
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
# Utilities
# ---------------------------------------------------------------------------

def extract_title(path):
    """Extract the page title from <title>...</title> (reads first 8 KB)."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            head = fh.read(8192)
        m = re.search(r'<title[^>]*>(.*?)</title>', head, re.IGNORECASE | re.DOTALL)
        if m:
            text = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            text = (text
                    .replace('&amp;', '&')
                    .replace('&lt;', '<')
                    .replace('&gt;', '>')
                    .replace('&quot;', '"')
                    .replace('&#39;', "'"))
            return text
    except Exception:
        pass
    # Fallback: use stem of filename
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

    children = [all_items[k] for k in sorted(all_items.keys(), key=str.lower)]

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
    if len(sys.argv) < 2:
        sys.stderr.write('Usage: python3 generate-nav-tree.py <html-root>\n')
        sys.exit(1)

    html_root = sys.argv[1]
    if not os.path.isdir(html_root):
        sys.stderr.write(f'Error: not a directory: {html_root}\n')
        sys.exit(1)

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
