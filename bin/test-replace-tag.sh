#!/bin/bash

set -eu

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

cat > "$tmp_dir/input.md" <<'EOF'
# Title

<!--details:-->
details only
<!--:details-->

<!--ja:-->
Japanese only
<!--:ja-->

```text
<!--details:-->
code block
<!--:details-->
```
EOF

expected_false=$(cat <<'EOF'
# Title


Japanese only

```text
<!--details:-->
code block
<!--:details-->
```
EOF
)
actual_false=$("$SCRIPT_DIR/replace-tag.sh" --lang=ja --details=false < "$tmp_dir/input.md")
if [[ "$actual_false" != "$expected_false" ]]; then
    echo "Error: details=false output differed." >&2
    exit 1
fi

expected_true=$(cat <<'EOF'
# Title

details only

Japanese only

```text
<!--details:-->
code block
<!--:details-->
```
EOF
)
actual_true=$("$SCRIPT_DIR/replace-tag.sh" --lang=ja --details=true < "$tmp_dir/input.md")
if [[ "$actual_true" != "$expected_true" ]]; then
    echo "Error: details=true output differed." >&2
    exit 1
fi

empty_output=$(printf '' | "$SCRIPT_DIR/replace-tag.sh" --lang=ja --details=false)
if [[ -n "$empty_output" ]]; then
    echo "Error: empty input output differed." >&2
    exit 1
fi

echo "replace-tag tests passed."
