#!/usr/bin/env bash

set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
eval "$(awk '/^mermaid_job_key_is_active\(\)/,/^}/; /^select_next_pending_file\(\)/,/^}/; /^mermaid_job_key_for_file\(\)/,/^}/' "${SCRIPT_DIR}/pub_markdown_core.sh")"

tmp_dir=$(mktemp -d)
cleanup() {
    rm -rf "$tmp_dir"
}
trap cleanup EXIT

workspaceFolder="${tmp_dir}/workspace"
mdRoot="docs"
pubRoot="pages"
docxOutput=true
mergeSubfolderDocs=""
mkdir -p "${workspaceFolder}/docs/sample"

real_to_virtual_path() {
    printf '%s\n' "$1"
}

mermaid_file="${workspaceFolder}/docs/sample/mermaid.md"
plain_file="${workspaceFolder}/docs/sample/plain.md"
printf '%s\n' '```mermaid' 'sequenceDiagram' '```' > "$mermaid_file"
printf '%s\n' '# Plain' > "$plain_file"

mermaid_key=$(mermaid_job_key_for_file "$mermaid_file")
plain_key=$(mermaid_job_key_for_file "$plain_file")
expected_key="${workspaceFolder}/pages/html/sample"
if [[ "$mermaid_key" != "$expected_key" ]]; then
    echo "Error: unexpected Mermaid key: $mermaid_key" >&2
    exit 1
fi
if [[ -n "$plain_key" ]]; then
    echo "Error: plain Markdown received a Mermaid key: $plain_key" >&2
    exit 1
fi
docxOutput=false
if [[ -n "$(mermaid_job_key_for_file "$mermaid_file")" ]]; then
    echo "Error: HTML-only Markdown received a Mermaid key" >&2
    exit 1
fi
docxOutput=true

MAX_PARALLEL=2
_running_count=1
_file_pids=(101)
_file_slot_released=(false)
_file_mermaid_keys=("$mermaid_key")
_pending_files=(
    "${workspaceFolder}/docs/sample/mermaid-second.md"
    "${workspaceFolder}/docs/other/mermaid.md"
    "${workspaceFolder}/docs/sample/plain.md"
)
_pending_mermaid_keys=(
    "$mermaid_key"
    "${workspaceFolder}/pages/html/other"
    ""
)

select_next_pending_file
if [[ "$_selected_pending_index" != "1" ]]; then
    echo "Error: scheduler did not select a different Mermaid key: $_selected_pending_index" >&2
    exit 1
fi

_file_pids+=(102)
_file_slot_released+=(false)
_file_mermaid_keys+=("${workspaceFolder}/pages/html/other")
_running_count=2
_pending_files=(
    "${workspaceFolder}/docs/sample/mermaid-second.md"
    "${workspaceFolder}/docs/sample/plain.md"
)
_pending_mermaid_keys=("$mermaid_key" "")
select_next_pending_file
if [[ "$_selected_pending_index" != "-1" ]]; then
    echo "Error: scheduler selected a conflicting Markdown job: $_selected_pending_index" >&2
    exit 1
fi

_file_slot_released[0]=true
_running_count=1
select_next_pending_file
if [[ "$_selected_pending_index" != "0" ]]; then
    echo "Error: scheduler did not select the released Mermaid key: $_selected_pending_index" >&2
    exit 1
fi

printf 'pub-markdown Mermaid scheduling tests passed\n'
