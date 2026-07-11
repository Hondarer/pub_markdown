#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source "${SCRIPT_DIR}/pub-markdown-skip.sh"

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

write_fixture() {
    local name="$1"
    local content="$2"
    printf '%s' "$content" > "${tmp_dir}/${name}"
}

expect_skip() {
    local name="$1"
    if ! is_pub_markdown_skip "${tmp_dir}/${name}"; then
        printf 'Expected skip: %s\n' "$name" >&2
        exit 1
    fi
}

expect_include() {
    local name="$1"
    if is_pub_markdown_skip "${tmp_dir}/${name}"; then
        printf 'Expected include: %s\n' "$name" >&2
        exit 1
    fi
}

write_fixture true.md $'---\npub_markdown.skip: true\n---\n# Hidden\n'
write_fixture quoted.md $'---\npub_markdown.skip: "TRUE" # generated only\n---\n# Hidden\n'
write_fixture false.md $'---\npub_markdown.skip: false\n---\n# Visible\n'
write_fixture missing.md '# Visible\n'
write_fixture unclosed.md $'---\npub_markdown.skip: true\n# Visible\n'
write_fixture markdown.markdown $'---\npub_markdown.skip: true\n---\n# Hidden\n'

expect_skip true.md
expect_skip quoted.md
expect_include false.md
expect_include missing.md
expect_include unclosed.md
expect_skip markdown.markdown

printf 'pub-markdown-skip tests passed\n'
