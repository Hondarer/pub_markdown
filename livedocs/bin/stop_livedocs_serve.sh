#!/bin/bash
# このワークスペースの mkdocs serve を停止する。
# ルート makefile の servedocs / stopdocs / cleandocs / cleanlivedocs から呼ぶ。
# make servedocs は起動前に --require-stopped 付きでこれを呼び、
# 先に動いていた serve が消えてからステージングする。
# stopdocs / clean は停止しきれなくても失敗しない。
#
# 対象は、動的発行の venv のパスをコマンドラインに含み、かつ引数が
# ちょうど serve であるプロセスとその子孫に限る。
# ポート番号や作業ディレクトリだけでは判定しない。
#
# Windows では SIGTERM がネイティブ子プロセスに届かず、親だけが先に死ぬと
# pages/livedocs のハンドルが残る。taskkill /T /F でツリーごと終了する。
# see: https://cygwin.com/cygwin-ug-net/proc.html
# see: https://learn.microsoft.com/windows-server/administration/windows-commands/taskkill

set -u

usage() {
    echo "Usage: $0 --venv <livedocs-venv-dir> [--require-stopped]" >&2
    exit 2
}

venv=""
require_stopped=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --venv)
            [ "$#" -ge 2 ] || usage
            venv=$2
            shift 2
            ;;
        --require-stopped)
            require_stopped=1
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            usage
            ;;
    esac
done

[ -n "$venv" ] || usage

# 末尾の区切りを除き、存在するなら絶対パスにする。存在しなくても文字列照合は行う。
venv=${venv%/}
venv=${venv%\\}
if [ -d "$venv" ]; then
    venv=$(cd "$venv" && pwd)
fi

is_windows_host() {
    case "$(uname -s 2>/dev/null)" in
        MINGW*|MSYS*|CYGWIN*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# venv パスの表記ゆれ (POSIX、Windows、mixed) を照合用に集める。
needles=()
add_needle() {
    local n="${1-}"
    local existing

    [ -n "$n" ] || return 0
    n=${n%/}
    n=${n%\\}
    [ -n "$n" ] || return 0
    for existing in "${needles[@]+"${needles[@]}"}"; do
        if [ "$existing" = "$n" ]; then
            return 0
        fi
    done
    needles+=("$n")
}

add_needle "$venv"
add_needle "${venv//\\//}"
add_needle "${venv//\//\\}"
if command -v cygpath >/dev/null 2>&1; then
    add_needle "$(cygpath -u "$venv" 2>/dev/null || true)"
    add_needle "$(cygpath -w "$venv" 2>/dev/null || true)"
    add_needle "$(cygpath -m "$venv" 2>/dev/null || true)"
fi

pid_alive() {
    kill -0 "$1" 2>/dev/null
}

win_pid_of() {
    local wp
    wp=$(tr -d '[:space:]' < "/proc/$1/winpid" 2>/dev/null || true)
    printf '%s\n' "${wp:-$1}"
}

ppid_of() {
    awk '/^PPid:/{print $2; exit}' "/proc/$1/status" 2>/dev/null
}

# /proc/<pid>/cmdline の NUL 区切り引数を見て、venv パスと serve サブコマンドを確認する。
# スクリプト名に serve が含まれていても、引数そのものが serve でなければ一致しない。
is_livedocs_serve() {
    local pid="$1"
    local arg
    local has_venv=0
    local has_serve=0
    local needle
    local cmdline="/proc/$pid/cmdline"

    [ -r "$cmdline" ] || return 1
    while IFS= read -r -d '' arg || [ -n "$arg" ]; do
        if [ "$arg" = "serve" ]; then
            has_serve=1
        fi
        if [ "$has_venv" -eq 0 ]; then
            for needle in "${needles[@]}"; do
                case "$arg" in
                    *"$needle"*)
                        has_venv=1
                        break
                        ;;
                esac
            done
        fi
        if [ "$has_venv" -eq 1 ] && [ "$has_serve" -eq 1 ]; then
            return 0
        fi
    done < "$cmdline"
    return 1
}

list_serve_pids() {
    local dir pid
    for dir in /proc/[0-9]*; do
        [ -d "$dir" ] || continue
        pid=${dir#/proc/}
        [ "$pid" = "$$" ] && continue
        if is_livedocs_serve "$pid"; then
            printf '%s\n' "$pid"
        fi
    done
}

# 指定 PID の子孫を PPid で辿る。プロセス グループ全体へは送らない。
# make servedocs は端末とグループを共有するため。
list_descendants() {
    local root="$1"
    local dir pid ppid
    for dir in /proc/[0-9]*; do
        [ -d "$dir" ] || continue
        pid=${dir#/proc/}
        [ "$pid" = "$root" ] && continue
        ppid=$(ppid_of "$pid") || continue
        if [ "$ppid" = "$root" ]; then
            printf '%s\n' "$pid"
            list_descendants "$pid"
        fi
    done
}

unique_pids() {
    awk 'NF && !seen[$0]++'
}

collect_tree_pids() {
    local root="$1"
    printf '%s\n' "$root"
    list_descendants "$root"
}

taskkill_tree() {
    local pid="$1"
    local winpid

    command -v taskkill.exe >/dev/null 2>&1 || return 0
    pid_alive "$pid" || return 0
    winpid=$(win_pid_of "$pid")
    # MSYS2_ARG_CONV_EXCL は /PID がパス変換されるのを防ぐ。
    # see: https://www.msys2.org/docs/filesystem-paths/
    MSYS2_ARG_CONV_EXCL='*' taskkill.exe /PID "$winpid" /T /F >/dev/null 2>&1 || true
}

term_then_kill() {
    local pid
    for pid in "$@"; do
        pid_alive "$pid" || continue
        kill -TERM "$pid" 2>/dev/null || true
    done
}

kill_remaining() {
    local pid
    for pid in "$@"; do
        pid_alive "$pid" || continue
        kill -KILL "$pid" 2>/dev/null || true
    done
}

wait_until_gone() {
    local remaining
    local try
    local pid

    try=0
    while [ "$try" -lt 20 ]; do
        remaining=0
        for pid in "$@"; do
            if pid_alive "$pid"; then
                remaining=1
                break
            fi
        done
        if [ "$remaining" -eq 0 ]; then
            return 0
        fi
        sleep 0.2
        try=$((try + 1))
    done
    return 1
}

if [ ! -d /proc ]; then
    printf 'WARNING: /proc が無いため mkdocs serve を停止できません\n' >&2
    if [ "$require_stopped" -eq 1 ]; then
        exit 1
    fi
    exit 0
fi

mapfile -t serve_pids < <(list_serve_pids | unique_pids)
if [ "${#serve_pids[@]}" -eq 0 ]; then
    exit 0
fi

tree_pids=()
for pid in "${serve_pids[@]}"; do
    printf 'INFO: Stopping livedocs mkdocs serve (pid %s)\n' "$pid"
    while IFS= read -r child; do
        [ -n "$child" ] || continue
        tree_pids+=("$child")
    done < <(collect_tree_pids "$pid" | unique_pids)
done

if [ "${#tree_pids[@]}" -eq 0 ]; then
    exit 0
fi

mapfile -t tree_pids < <(printf '%s\n' "${tree_pids[@]}" | unique_pids)

if is_windows_host; then
    for pid in "${serve_pids[@]}"; do
        taskkill_tree "$pid"
    done
else
    term_then_kill "${tree_pids[@]}"
    if ! wait_until_gone "${tree_pids[@]}"; then
        kill_remaining "${tree_pids[@]}"
    fi
fi

if ! wait_until_gone "${tree_pids[@]}"; then
    for pid in "${tree_pids[@]}"; do
        if pid_alive "$pid"; then
            printf 'WARNING: livedocs mkdocs serve が残っています (pid %s)\n' "$pid" >&2
        fi
    done
fi

# Windows のハンドル解放遅延に備える。
sleep 0.5

# 停止対象の PID だけでなく、いまも serve と判定できるプロセスが残っていないか確認する。
mapfile -t leftover_pids < <(list_serve_pids | unique_pids)
if [ "${#leftover_pids[@]}" -gt 0 ]; then
    for pid in "${leftover_pids[@]}"; do
        printf 'WARNING: livedocs mkdocs serve が残っています (pid %s)\n' "$pid" >&2
    done
    if [ "$require_stopped" -eq 1 ]; then
        printf 'ERROR: 既存の mkdocs serve を止めきれなかったため、動的発行の配信を起動しません\n' >&2
        exit 1
    fi
fi

exit 0
