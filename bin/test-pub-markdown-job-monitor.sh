#!/usr/bin/env bash

set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
eval "$(awk '/^monitor_file_jobs_once\(\)/,/^}/; /^wait_for_parallel_slot\(\)/,/^}/' "${SCRIPT_DIR}/pub_markdown_core.sh")"

is_windows_host() {
    return 1
}

tmp_dir=$(mktemp -d)
cleanup() {
    for pid in "${_file_pids[@]:-}"; do
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done
    rm -rf "$tmp_dir"
}
trap cleanup EXIT

MAX_PARALLEL=2
_file_job_timeout_sec=1
_running_count=0
_file_pids=()
_file_names=()
_file_status_files=()
_file_slot_released=()
_file_heartbeat_sigs=()
_file_last_progress=()
_file_timeout_reported=()

start_stalled_job() {
    local name="$1"
    local status_file="${tmp_dir}/${name}.status"
    (
        trap 'echo 143 > "$status_file"; exit 143' TERM
        touch "${status_file}.hb"
        printf 'test phase\n' > "${status_file}.phase"
        while :; do
            read -r -t 10 _unused || true
        done
    ) &
    _file_pids+=("$!")
    _file_names+=("$name")
    _file_status_files+=("$status_file")
    _file_slot_released+=(false)
    _file_heartbeat_sigs+=("")
    _file_last_progress+=("$SECONDS")
    _file_timeout_reported+=(false)
    (( _running_count++ ))
}

start_stalled_job first.md
start_stalled_job second.md
start_time=$SECONDS
wait_for_parallel_slot
elapsed=$((SECONDS - start_time))

if (( _running_count >= MAX_PARALLEL )); then
    echo 'Error: stalled jobs did not release a parallel slot.' >&2
    exit 1
fi
if (( elapsed > 5 )); then
    echo "Error: watchdog took too long: ${elapsed}s" >&2
    exit 1
fi

while (( _running_count > 0 )); do
    monitor_file_jobs_once
    sleep 0.1
done

for status_file in "${_file_status_files[@]}"; do
    if [[ ! -s "$status_file" ]]; then
        echo "Error: missing status after timeout: $status_file" >&2
        exit 1
    fi
done

printf 'pub-markdown job monitor tests passed\n'
