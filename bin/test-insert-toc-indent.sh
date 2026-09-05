#!/bin/bash

set -eu

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
TOC_SCRIPT="$SCRIPT_DIR/pandoc-filters/insert-toc.sh"
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

mkdir -p "$tmp_dir/docs/child"
cat > "$tmp_dir/docs/index.md" <<'EOF'
# Root
EOF
cat > "$tmp_dir/docs/top.md" <<'EOF'
# Top
EOF
cat > "$tmp_dir/docs/child/index.md" <<'EOF'
# Child
EOF
cat > "$tmp_dir/docs/child/grandchild.md" <<'EOF'
# Grandchild
EOF

export PUB_MARKDOWN_MAIN_MDROOT="$tmp_dir/docs"
export DOCUMENT_LANG=ja
export DOCUMENT_DETAILS=false

run_toc() {
    local exclude_basedir="$1"
    PUB_MARKDOWN_TOC_OUTPUT_CACHE_DIR="$tmp_dir/cache" \
        "$TOC_SCRIPT" -1 "$tmp_dir/docs/index.md" ja "" "" "$exclude_basedir"
}

mkdir -p "$tmp_dir/cache"
exclude_output=$(run_toc true)
expected_exclude=$(cat <<'EOF'
- 📁 [child](child/index.md) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Child
    - 📄 [grandchild.md](child/grandchild.md) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Grandchild
- 📄 [top.md](top.md) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Top
EOF
)
if [[ "$exclude_output" != "$expected_exclude" ]]; then
    echo "Error: exclude-basedir=true indentation differed." >&2
    diff -u <(printf '%s\n' "$expected_exclude") <(printf '%s\n' "$exclude_output") >&2 || true
    exit 1
fi

include_output=$(run_toc false)
expected_include=$(cat <<'EOF'
- 📁 [docs](index.md) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Root
    - 📁 [child](child/index.md) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Child
        - 📄 [grandchild.md](child/grandchild.md) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Grandchild
    - 📄 [top.md](top.md) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Top
EOF
)
if [[ "$include_output" != "$expected_include" ]]; then
    echo "Error: exclude-basedir=false indentation differed." >&2
    diff -u <(printf '%s\n' "$expected_include") <(printf '%s\n' "$include_output") >&2 || true
    exit 1
fi

echo "insert-toc indentation tests passed."
