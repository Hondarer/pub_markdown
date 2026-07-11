#!/bin/bash
#set -x

SCRIPT_DIR=$(cd $(dirname "$0"); pwd)
HOME_DIR=$(cd $SCRIPT_DIR; cd ..; pwd) # bin フォルダーの上位が home
PATH=$SCRIPT_DIR:$PATH # 優先的に bin フォルダーを選択させる
cd $HOME_DIR

source "${SCRIPT_DIR}/pub-markdown-skip.sh"

# short-title 解決ヘルパーを読み込む
source "${SCRIPT_DIR}/extract-short-title.sh"

# 並列ジョブ内では stdout / stderr を一時ファイルへ集約するため、
# 進捗ログだけは元の stderr を保持した FD 3 へ直接出力する。
exec 3>&2

# PUB_MARKDOWN_PROGRESS_LOG=1 のときだけ、長時間処理の進行状況を stderr に出力する。
# _pm_heartbeat_file が設定されている場合 (.md 処理サブシェル内) は、
# 出力設定にかかわらずハートビート ファイルを touch し、親の無進捗監視に進捗を伝える。
progress_log() {
    if [[ -n "${_pm_heartbeat_file:-}" ]]; then
        touch "$_pm_heartbeat_file" 2>/dev/null
    fi
    [[ "${PUB_MARKDOWN_PROGRESS_LOG:-0}" == "1" ]] || return 0
    printf '[pub_markdown %s] %s\n' "$(date '+%H:%M:%S')" "$*" >&3
}

set_job_phase() {
    local phase="$1"
    [[ -n "${_pm_phase_file:-}" ]] || return 0
    printf '%s\n' "$phase" > "$_pm_phase_file"
    if [[ -n "${_pm_heartbeat_file:-}" ]]; then
        touch "$_pm_heartbeat_file" 2>/dev/null
    fi
}

# publocal.yaml / pubpart.yaml / pubchild.yaml の defaults: ブロックを抽出し、
# pandoc の --metadata-file に渡せる素の YAML を out_tmp に書き出す。
# defaults: が無い、または中身が無い場合は何も書かず 1 を返す。
# 値の解釈 (コメント、クォート、型) は pandoc 側の YAML パーサーに委ねる。
extract_defaults_block() {
    local yaml_file="$1"
    local out_tmp="$2"
    local line
    local content
    local in_defaults=0
    local base_indent=-1
    local indent
    local wrote=0

    [[ -f "$yaml_file" ]] || return 1

    : > "$out_tmp"
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        if [[ $in_defaults -eq 0 ]]; then
            if [[ "$line" =~ ^defaults:[[:space:]]*$ ]]; then
                in_defaults=1
            fi
            continue
        fi
        # 空行・コメント行は読み飛ばす (ブロックの区切りとはしない)
        if [[ "$line" =~ ^[[:space:]]*$ ]] || [[ "$line" =~ ^[[:space:]]*# ]]; then
            continue
        fi
        # 行頭が非空白なら次のトップレベル キー。defaults ブロックは終了。
        if [[ "$line" =~ ^[^[:space:]] ]]; then
            break
        fi
        content="${line#"${line%%[![:space:]]*}"}"
        indent=$(( ${#line} - ${#content} ))
        if [[ $base_indent -lt 0 ]]; then
            base_indent=$indent
        fi
        # 基準より浅いインデントはブロック外とみなす
        if [[ $indent -lt $base_indent ]]; then
            break
        fi
        # 基準インデントぶんだけ除去 (相対ネストは保持) して書き出す
        printf '%s\n' "${line:$base_indent}" >> "$out_tmp"
        wrote=1
    done < "$yaml_file"

    if [[ $wrote -eq 1 ]]; then
        return 0
    fi
    : > "$out_tmp"
    return 1
}

# ファイルが属するソース ルート (defaults 走査の上端境界) を出力する。
# mergeSubfolderDocs のサブフォルダー配下ならその docs ルート、
# そうでなければ主 mdRoot を返す。
resolve_source_root_for_file() {
    local file="$1"
    local entry
    if [[ -n "$mergeSubfolderDocs" ]]; then
        for entry in "${subfolder_mdroot_paths[@]}"; do
            parse_subfolder_mdroot_entry "$entry"
            if [[ "$file" == "${subfolder_mdroot}/"* ]]; then
                printf '%s\n' "$subfolder_mdroot"
                return 0
            fi
        done
    fi
    printf '%s\n' "${PUB_MARKDOWN_MAIN_MDROOT}"
}

# ファイルの所属ディレクトリからソース ルートまでを遡り、各階層の
# publocal / pubpart / pubchild の defaults: を pandoc の --metadata-file 群として構築する。
# 優先順位 (低 -> 高): 遠い階層 -> 近い階層、同一階層では child -> part -> local。
# pandoc は後に指定した --metadata-file を優先し、ドキュメント自身の YAML / -M が
# すべてに勝つため、ドキュメントに指定があればデフォルトは適用されない。
# 結果: グローバル配列 defaults_metadata_file_args と defaults_metadata_tmpfiles を設定する。
build_defaults_metadata_args() {
    local file="$1"
    defaults_metadata_file_args=()
    defaults_metadata_tmpfiles=()

    local src_root
    src_root=$(resolve_source_root_for_file "$file")

    local file_dir
    file_dir=$(dirname "$file")

    # file_dir から src_root まで遡ったディレクトリを近い順に集める
    local -a dirs_near_to_far=()
    local d="$file_dir"
    while :; do
        dirs_near_to_far+=("$d")
        [[ "$d" == "$src_root" ]] && break
        local parent
        parent=$(dirname "$d")
        [[ "$parent" == "$d" ]] && break   # ファイルシステム ルートに到達
        d="$parent"
    done

    # 遠い階層 -> 近い階層の順に処理し、--metadata-file を後勝ちで積む
    local i dir magic tmp
    local -a magic_order
    for (( i=${#dirs_near_to_far[@]}-1; i>=0; i-- )); do
        dir="${dirs_near_to_far[i]}"
        if [[ $i -eq 0 ]]; then
            # ファイルの居るディレクトリ自身: part (自階層に効く) -> local (最優先)
            magic_order=("pubpart.yaml" "publocal.yaml")
        else
            # 祖先ディレクトリ: child (配下のみ) -> part の順 (part が優先)
            magic_order=("pubchild.yaml" "pubpart.yaml")
        fi
        for magic in "${magic_order[@]}"; do
            tmp=$(mktemp)
            if extract_defaults_block "${dir}/${magic}" "$tmp"; then
                defaults_metadata_file_args+=(--metadata-file "$tmp")
                defaults_metadata_tmpfiles+=("$tmp")
            else
                rm -f "$tmp"
            fi
        done
    done
}

is_windows_host() {
    case "$(uname -s 2>/dev/null)" in
        MINGW*|MSYS*|CYGWIN*) return 0 ;;
        *) return 1 ;;
    esac
}

# MSYS2 (Cygwin) の PID は Windows ネイティブの PID と一致しない場合があるため、
# taskkill.exe へ渡す前に /proc/<pid>/winpid で Windows PID に変換する。
# 変換できない場合は入力の PID をそのまま返す。
# see: https://cygwin.com/cygwin-ug-net/proc.html
win_pid_of() {
    local wp
    wp=$(cat "/proc/$1/winpid" 2>/dev/null)
    echo "${wp:-$1}"
}

append_unique_pid() {
    local pid="$1"
    local existing
    [[ -n "$pid" ]] || return 0
    for existing in "${_cleanup_pids[@]}"; do
        [[ "$existing" == "$pid" ]] && return 0
    done
    _cleanup_pids+=("$pid")
}

terminate_managed_pids() {
    local pid

    [[ ${#_cleanup_pids[@]} -gt 0 ]] || return 0

    if is_windows_host && command -v taskkill.exe >/dev/null 2>&1; then
        # Windows: SIGTERM は native プロセスに届かず、MSYS サブシェルに送ると
        # 親だけが先に死んで native の子 (pandoc.exe、powershell.exe など) が孤児化する。
        # 孤児は継承した stdout/stderr のパイプ ハンドルを保持し続け、
        # スクリプト終了後も呼び出し元 (make やコンソール) に制御が戻らなくなるため、
        # プロセス ツリーが健在なうちに taskkill /T /F で子孫ごと強制終了する。
        # kill -0 による生存確認は PID 再利用による誤爆の防止。
        for pid in "${_cleanup_pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                MSYS2_ARG_CONV_EXCL='*' taskkill.exe /PID "$(win_pid_of "$pid")" /T /F >/dev/null 2>&1 || true
            fi
        done
    else
        for pid in "${_cleanup_pids[@]}"; do
            kill "$pid" 2>/dev/null || true
        done

        # SIGTERM 送信後、猶予時間を置いてから残存プロセスを強制終了する。
        # browser.close() のタイムアウト (5 秒) に余裕を持たせ 6 秒待機してから SIGKILL。
        sleep 6

        for pid in "${_cleanup_pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        done
    fi

    # force kill 後のゾンビを reap する。
    # kill -0 が非ゼロを返すプロセス (終了確認済み) のみ wait してリープする。
    # kill -0 が 0 を返すまま (強制終了できなかったケース) はスキップし、
    # bash 自身の終了時に OS が回収する。
    for pid in "${_cleanup_pids[@]}"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            wait "$pid" 2>/dev/null || true
        fi
    done
}

# 終了時に実行する共通クリーンアップ処理
cleanup_resources() {
    if [[ "${CLEANUP_DONE:-0}" == "1" ]]; then
        return 0
    fi
    CLEANUP_DONE=1

    _cleanup_pids=()

    # 共有ブラウザー サーバーを停止
    if [[ -n "${BROWSER_SERVER_PID:-}" ]]; then
        append_unique_pid "$BROWSER_SERVER_PID"
    fi

    # Markdown ファイル単位の並列ジョブを停止
    if declare -p _file_pids >/dev/null 2>&1; then
        for _pid in "${_file_pids[@]}"; do
            append_unique_pid "$_pid"
        done
    fi

    # そのほかのバックグラウンド ジョブを停止
    local _bg_jobs
    _bg_jobs=$(jobs -rp 2>/dev/null)
    if [[ -n "$_bg_jobs" ]]; then
        for _pid in $_bg_jobs; do
            append_unique_pid "$_pid"
        done
    fi

    terminate_managed_pids

    if [[ -n "${PUB_MARKDOWN_BROWSER_WS_FILE:-}" ]]; then
        rm -f "$PUB_MARKDOWN_BROWSER_WS_FILE" 2>/dev/null
    fi
    if [[ -n "${BROWSER_SERVER_LOG:-}" ]]; then
        rm -f "$BROWSER_SERVER_LOG" 2>/dev/null
    fi
    if [[ -n "${OUTPUT_LOCK:-}" ]]; then
        rm -rf "${OUTPUT_LOCK}.lck" 2>/dev/null
    fi
    if [[ -n "${_PM_STATUS_DIR:-}" ]]; then
        rm -rf "${_PM_STATUS_DIR}" 2>/dev/null
    fi
    if [[ -n "${PUB_MARKDOWN_TOC_OUTPUT_CACHE_DIR:-}" ]]; then
        rm -rf "$PUB_MARKDOWN_TOC_OUTPUT_CACHE_DIR" 2>/dev/null
    fi
    if [[ -n "${PUB_MARKDOWN_PLANTUML_CACHE_DIR:-}" ]]; then
        rm -rf "$PUB_MARKDOWN_PLANTUML_CACHE_DIR" 2>/dev/null
    fi
}

# Ctrl+C (SIGINT) や SIGTERM を捕まえて実行する処理
cleanup_on_signal() {
    #echo >&2 "スクリプトが中断されました。"
    CLEANUP_FORCE_WINDOWS_TREE=1
    cleanup_resources
    printf "\e[0m" # 文字色を通常に設定
    exit 1
}

# 途中終了を含むすべての終了経路でリソースを解放する
cleanup_on_exit() {
    local exit_status=$?
    cleanup_resources
    exit "$exit_status"
}

# SIGINT (Ctrl+C)、SIGTERM (kill コマンドなど)、通常終了を捕捉
trap 'cleanup_on_signal' INT TERM
trap 'cleanup_on_exit' EXIT

#-------------------------------------------------------------------
# マルチ プラットフォーム対応
#-------------------------------------------------------------------

LINUX=0
WSL=0

if [[ "$(uname -s)" == "Linux" ]]; then
    LINUX=1
    # WSL 環境かどうかを判定
    if grep -qi microsoft /proc/version 2>/dev/null || uname -r | grep -qi microsoft 2>/dev/null; then
        WSL=1
    fi
fi

if [ $LINUX -eq 1 ]; then
    chmod +x "${SCRIPT_DIR}/replace-tag.sh"
    chmod +x "${SCRIPT_DIR}/mmdc-wrapper.sh"
    chmod +x "${SCRIPT_DIR}/chrome-wrapper.sh"
    chmod +x "${SCRIPT_DIR}/pandoc-filters/insert-toc.sh"
    WIDDERSHINS="${SCRIPT_DIR}/node_modules/.bin/widdershins"

    if [ $WSL -eq 1 ]; then
        # NOTE: WSL2 では 127.0.0.1 のネットワーク分離問題があるため、
        # PUPPETEER_EXECUTABLE_PATH に Windows 側の Edge を指定しても、
        # WSL2 から Edge (127.0.0.1 で LISTEN) にアクセスできない。
        # そのため、PUPPETEER_EXECUTABLE_PATH は設定せず、
        # Puppeteer が自動的にダウンロードする Linux 版 Chromium を使用する。
        :
    fi
else
    WIDDERSHINS="${SCRIPT_DIR}/node_modules/.bin/widdershins.cmd"
    # レジストリから Microsoft Edge のパスを取得
    EDGE_REG_PATH=$(
        reg query "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\msedge.exe" /v Path 2>/dev/null \
            | tr -d '\r' \
            | sed -n 's/^[[:space:]]*Path[[:space:]]\+REG_SZ[[:space:]]\+//p'
    )
    if [ -n "$EDGE_REG_PATH" ]; then
        EDGE_PATH="${EDGE_REG_PATH}/msedge.exe"
    else
        # フォールバック: 環境変数から取得を試みる
        EDGE_PATH="${ProgramW6432} (x86)/Microsoft/Edge/Application/msedge.exe"
    fi
    if [ -f "$EDGE_PATH" ]; then
        export PUPPETEER_EXECUTABLE_PATH="$EDGE_PATH"
        export PUPPETEER_SKIP_DOWNLOAD=1
        #echo "PUPPETEER_EXECUTABLE_PATH=\"${PUPPETEER_EXECUTABLE_PATH}\""
        #echo "PUPPETEER_SKIP_DOWNLOAD=1"
    else
        echo "Error: Microsoft Edge not found at $EDGE_PATH"
        exit 1
    fi
fi

# Pandoc が ${SCRIPT_DIR} にある または PATH が通っていれば
# PANDOC に Pandoc のパスを設定
if [ -x "${SCRIPT_DIR}/pandoc" ] || [ -x "${SCRIPT_DIR}/pandoc.exe" ]; then
    PANDOC="${SCRIPT_DIR}/pandoc"
elif command -v pandoc >/dev/null 2>&1 || command -v pandoc.exe >/dev/null 2>&1; then
    PANDOC="pandoc"
else
    echo "Error: pandoc not found."
    exit 1
fi

# pandoc-crossref が ${SCRIPT_DIR} にある または PATH が通っていれば
# pandoc_crossref_args に "-F {pandoc-crossref のパス}" を設定
if [ -x "${SCRIPT_DIR}/pandoc-crossref" ] || [ -x "${SCRIPT_DIR}/pandoc-crossref.exe" ]; then
    pandoc_crossref_args=(-F "${SCRIPT_DIR}/pandoc-crossref")
elif command -v pandoc-crossref >/dev/null 2>&1 || command -v pandoc-crossref.exe >/dev/null 2>&1; then
    pandoc_crossref_args=(-F pandoc-crossref)
else
    pandoc_crossref_args=()
fi

# セットアップ完了スタンプ。package.json / package-lock.json のハッシュを記録し、
# npm ci とブラウザーのインストールがすべて成功したときのみ書き込む。
# node_modules 内に置くことで、npm ci で node_modules が再生成された際に
# スタンプも消え、再セットアップが強制されて整合する。
# package-lock.json を利用して固定バージョンでセットアップするため、npm install ではなく npm ci。
SETUP_STAMP_FILE="${SCRIPT_DIR}/node_modules/.docsfw-setup.stamp"

compute_setup_hash() {
    cat "${SCRIPT_DIR}/package.json" "${SCRIPT_DIR}/package-lock.json" 2>/dev/null \
        | sha256sum | awk '{print $1}'
}

setup_stamp_valid() {
    [[ -f "$SETUP_STAMP_FILE" ]] || return 1
    local expected current
    expected=$(compute_setup_hash)
    current=$(cat "$SETUP_STAMP_FILE" 2>/dev/null)
    [[ -n "$expected" && "$expected" == "$current" ]]
}

if ! setup_stamp_valid; then
    echo "Installing node.js modules..."
    setup_ok=true
    (
        cd "${SCRIPT_DIR}" || exit 1
        export PUPPETEER_SKIP_DOWNLOAD=1
        npm ci || exit 1
        unset PUPPETEER_SKIP_DOWNLOAD
        # Windows では Edge を PUPPETEER_EXECUTABLE_PATH に指定するため、
        # Puppeteer 用 chrome / chrome-headless-shell のダウンロードは不要。
        # Linux / WSL のみ Puppeteer がダウンロードする Chromium を導入する。
        if [ -z "${PUPPETEER_EXECUTABLE_PATH:-}" ]; then
            npx puppeteer browsers install chrome || exit 1
            npx puppeteer browsers install chrome-headless-shell || exit 1
        fi
    ) || setup_ok=false

    if [[ "$setup_ok" == "true" ]]; then
        compute_setup_hash > "$SETUP_STAMP_FILE"
        progress_log "セットアップ完了スタンプを書き込みました: ${SETUP_STAMP_FILE}"
    else
        echo "Error: node.js modules / browser setup failed." >&2
        rm -f "$SETUP_STAMP_FILE"
        exit 1
    fi
fi

# node.js の警告を非表示にする
export NODE_NO_WARNINGS=1

#-------------------------------------------------------------------
# 共有ブラウザー インスタンスの起動設定
#-------------------------------------------------------------------

BROWSER_SERVER_PID=""
BROWSER_SERVER_LOG=""
export PUB_MARKDOWN_TOC_OUTPUT_CACHE_DIR="$(mktemp -d)"
# Windows (MSYS2) では mktemp が POSIX パスを返すが、
# pandoc.exe (Win32) の Lua が環境変数のパスを解決できないため
# cygpath -m で Windows ネイティブ形式 (ドライブレター + 順スラッシュ) に変換する
_pm_plantuml_cache_tmp="$(mktemp -d)"
if is_windows_host && command -v cygpath >/dev/null 2>&1; then
    export PUB_MARKDOWN_PLANTUML_CACHE_DIR="$(cygpath -m "$_pm_plantuml_cache_tmp")"
else
    export PUB_MARKDOWN_PLANTUML_CACHE_DIR="$_pm_plantuml_cache_tmp"
fi
unset _pm_plantuml_cache_tmp

PUB_MARKDOWN_BROWSER_REUSE="${PUB_MARKDOWN_BROWSER_REUSE:-auto}"
PUB_MARKDOWN_BROWSER_START_TIMEOUT_SEC="${PUB_MARKDOWN_BROWSER_START_TIMEOUT_SEC:-120}"
if ! [[ "$PUB_MARKDOWN_BROWSER_START_TIMEOUT_SEC" =~ ^[0-9]+$ ]] || [[ "$PUB_MARKDOWN_BROWSER_START_TIMEOUT_SEC" -lt 1 ]]; then
    PUB_MARKDOWN_BROWSER_START_TIMEOUT_SEC=120
fi
export PUB_MARKDOWN_BROWSER_START_TIMEOUT_SEC

summarize_browser_server_log() {
    local log_file="$1"
    if [[ ! -s "$log_file" ]]; then
        echo "(no browser-server diagnostics)"
        return 0
    fi

    tail -n 20 "$log_file" \
        | tr '\n' ' ' \
        | sed -e 's/[[:space:]][[:space:]]*/ /g' -e 's/^ //' -e 's/ $//'
}

start_shared_browser_server() {
    # ポーリングは 1 秒/tick のため、タイムアウト秒数をそのまま tick 数とする
    local timeout_ticks=$(( PUB_MARKDOWN_BROWSER_START_TIMEOUT_SEC * 1 ))
    local exit_status=0
    local reason=""

    export PUB_MARKDOWN_BROWSER_WS_FILE="/tmp/pub_markdown_browser_ws_$$"
    BROWSER_SERVER_LOG=$(mktemp)
    rm -f "$PUB_MARKDOWN_BROWSER_WS_FILE"

    # NOTE: browser-server.js は prepare_puppeteer_env.sh を source せず、
    #       chrome-wrapper.sh を直接 executablePath に指定する。
    #       これにより二重ラップを避けながら DevTools readiness 待機を適用する。
    #       フォールバック時 (rsvg-convert 単体実行) は従来通り chrome-wrapper.sh が使われる。
    echo -n "Starting shared browser..."
    node "${SCRIPT_DIR}/browser-server.js" "$PUB_MARKDOWN_BROWSER_WS_FILE" >"$BROWSER_SERVER_LOG" 2>&1 &
    BROWSER_SERVER_PID=$!
    progress_log "共有ブラウザ起動待機を開始しました pid=${BROWSER_SERVER_PID} timeout=${PUB_MARKDOWN_BROWSER_START_TIMEOUT_SEC}s"

    for _i in $(seq 1 "$timeout_ticks"); do
        if [[ -s "$PUB_MARKDOWN_BROWSER_WS_FILE" ]]; then
            echo " done."
            progress_log "共有ブラウザ起動待機を終了しました result=ready"
            return 0
        fi
        if ! jobs -pr | grep -qx "$BROWSER_SERVER_PID"; then
            wait "$BROWSER_SERVER_PID" 2>/dev/null
            exit_status=$?
            reason="exit=${exit_status}"
            break
        fi
        sleep 1
        if (( _i % 10 == 0 )); then
            echo -n "."
        fi
    done

    if [[ -z "$reason" ]]; then
        reason="timeout=${PUB_MARKDOWN_BROWSER_START_TIMEOUT_SEC}s"
        kill "$BROWSER_SERVER_PID" 2>/dev/null
        wait "$BROWSER_SERVER_PID" 2>/dev/null
    fi

    echo " fallback."
    echo "Warning: Shared browser server failed to start (${reason}). Falling back to per-process browser instances."
    echo "Warning: browser-server diagnostics: $(summarize_browser_server_log "$BROWSER_SERVER_LOG")"
    BROWSER_SERVER_PID=""
    rm -f "$PUB_MARKDOWN_BROWSER_WS_FILE" "$BROWSER_SERVER_LOG" 2>/dev/null
    BROWSER_SERVER_LOG=""
    export -n PUB_MARKDOWN_BROWSER_WS_FILE
    progress_log "共有ブラウザ起動待機を終了しました result=fallback ${reason}"
    return 1
}

markdown_needs_shared_browser() {
    local file="$1"
    [[ "$file" == *.md ]] || return 1
    grep -Eiq '(^```[[:space:]]*\{?\.?mermaid\b|^```[[:space:]]*mermaid\b)' "$file" && return 0
    grep -Fqi '.svg' "$file"
}

should_start_shared_browser() {
    local file

    case "$PUB_MARKDOWN_BROWSER_REUSE" in
        always)
            return 0
            ;;
        off|false|0|no)
            return 1
            ;;
        auto|"")
            ;;
        *)
            echo "Warning: Unknown PUB_MARKDOWN_BROWSER_REUSE=${PUB_MARKDOWN_BROWSER_REUSE}; using auto."
            ;;
    esac

    [[ "$docxOutput" == "true" ]] || return 1
    for file in "${files[@]}"; do
        if markdown_needs_shared_browser "$file"; then
            return 0
        fi
    done
    return 1
}

encode_docx_download_name_from_title() {
    python3 -c '
import re
import sys
import urllib.parse

sys.stdin.reconfigure(encoding="utf-8")
stem = sys.stdin.read()
stem = re.sub(r"[<>:\"/\\\\|?*\x00-\x1f\x7f]", "_", stem)
stem = stem.rstrip(" .")
if not stem:
    stem = "index"
if re.match(r"(?i)^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", stem):
    stem += "_"
sys.stdout.write(urllib.parse.quote(stem + ".docx", safe=""))
'
}

extract_frontmatter_value() {
    local file="$1"
    local key="$2"
    awk -v key="$key" '
        NR==1 { if ($0 !~ /^---[[:space:]]*$/) exit; next }
        /^---[[:space:]]*$/ { exit }
        $0 ~ "^" key ":[[:space:]]*" {
            line=$0
            sub(/\r$/, "", line)
            sub("^" key ":[[:space:]]*", "", line)
            sub(/[[:space:]]+$/, "", line)
            gsub(/^"|"$/, "", line)
            print line
            exit
        }
    ' "$file"
}

relative_url_from_output() {
    local output_html="$1"
    local workspace_root="$2"
    local target_ws_rel="$3"
    python3 -c '
import os
import sys

output_html, workspace_root, target_ws_rel = sys.argv[1:4]
output_dir = os.path.dirname(os.path.abspath(output_html))
target = target_ws_rel.replace("\\", "/")
if "://" in target or target.startswith("/"):
    print(target)
else:
    target_abs = os.path.abspath(os.path.join(workspace_root, target))
    print(os.path.relpath(target_abs, output_dir).replace("\\", "/"))
' "$output_html" "$workspace_root" "$target_ws_rel"
}

build_doxygen_link_metadata_args() {
    local source_file="$1"
    local output_html="$2"
    local icon_url="$3"

    doxygen_link_metadata_args=()
    if [[ "$doxygenLinkEnable" != "true" ]]; then
        return
    fi

    local doxygen_page_url
    doxygen_page_url=$(extract_frontmatter_value "$source_file" "doxygen-page-url")
    if [[ -z "$doxygen_page_url" ]]; then
        return
    fi

    local doxygen_url
    doxygen_url=$(relative_url_from_output "$output_html" "$workspaceFolder" "$doxygen_page_url")
    doxygen_link_metadata_args=(
        --metadata "doxygen-url=${doxygen_url}"
        --metadata "doxygen-icon=${icon_url}"
    )
}

resolve_git_link_target() {
    local source_file="$1"
    local git_link_target="$source_file"
    local git_origin_hint

    # doxyfw 生成 md は先頭フロントマターに git-origin (元ソースの workspace 相対パス) を持つ。
    # ヒントがあり実体が存在すれば、md 自身ではなく元ソースに対して Git リンクを解決する。
    git_origin_hint=$(extract_frontmatter_value "$source_file" "git-origin")
    if [[ -n "$git_origin_hint" && -f "${workspaceFolder}/${git_origin_hint}" ]]; then
        git_link_target="${workspaceFolder}/${git_origin_hint}"
    fi

    printf '%s\n' "$git_link_target"
}

build_git_link_metadata_args() {
    local source_file="$1"
    local output_html="$2"
    local icon_base="$3"

    git_link_metadata_args=()
    if [[ "$gitLinkEnable" != "true" ]]; then
        return
    fi

    local git_link_target git_link_result git_link_url git_link_provider
    git_link_target=$(resolve_git_link_target "$source_file")
    git_link_result=$(sh "${SCRIPT_DIR}/get_file_git_url.sh" "$git_link_target")
    if [[ -n "$git_link_result" ]]; then
        git_link_url="${git_link_result%%$'\t'*}"
        git_link_provider="${git_link_result##*$'\t'}"
    else
        local doxygen_page_url
        doxygen_page_url=$(extract_frontmatter_value "$source_file" "doxygen-page-url")
        if [[ -z "$doxygen_page_url" ]]; then
            return
        fi

        git_link_url=$(relative_url_from_output "$output_html" "$workspaceFolder" "$doxygen_page_url")
        git_link_provider=$(sh "${SCRIPT_DIR}/get_file_git_url.sh" --provider "$git_link_target")
        if [[ -z "$git_link_provider" ]]; then
            git_link_provider="git"
        fi
    fi

    case "$git_link_provider" in
        github|gitlab|gitbucket)
            ;;
        *)
            git_link_provider="git"
            ;;
    esac

    git_link_metadata_args=(
        --metadata "git-url=${git_link_url}"
        --metadata "git-icon=${icon_base}docsfw-${git_link_provider}-icon.svg"
    )
}

#-------------------------------------------------------------------

#-------------------------------------------------------------------
# 並列処理設定
#-------------------------------------------------------------------

# 並列処理の最大ジョブ数
# 環境変数 PUB_MARKDOWN_PARALLEL で上書き可能 (例: PUB_MARKDOWN_PARALLEL=2 pub_markdown_core.sh ...)
# CPU コア数の 1.5 倍を基準とし、端数は切り捨てる
# 上限は 6 に制限する
_nproc=$(nproc 2>/dev/null || echo 4)
_parallel_default=$(( _nproc * 3 / 2 ))
MAX_PARALLEL=${PUB_MARKDOWN_PARALLEL:-$(( _parallel_default > 6 ? 6 : _parallel_default ))}

# 並列出力の排他制御用ロック ベース パス
# flock (Linux 専用) の代わりに mkdir アトミック ロックを使用することで
# MSYS2 (Windows) 環境でも動作する
OUTPUT_LOCK=$(mktemp -u)
_PM_STATUS_DIR=$(mktemp -d)
_running_count=0
_wait_p_supported=false
if help wait 2>/dev/null | grep -q -- '-p VARNAME'; then
    _wait_p_supported=true
fi

# 実行中のバックグラウンド ジョブ数が MAX_PARALLEL に達している場合、
# 1 つ完了するまで待機する関数
wait_for_parallel_slot() {
    local _waited_pid
    while (( _running_count >= MAX_PARALLEL )); do
        if [[ "$_wait_p_supported" == "true" ]]; then
            # wait -p で収集した PID を識別し、ファイル処理ジョブのみカウントする。
            # BROWSER_SERVER_PID が先に終了した場合に wait -n でそれを収集してしまうと
            # _running_count が不正にデクリメントされ MAX_PARALLEL を超えて起動するため除外する。
            _waited_pid=""
            wait -p _waited_pid -n 2>/dev/null || true
            if [[ -n "$_waited_pid" && "$_waited_pid" != "${BROWSER_SERVER_PID:-}" ]]; then
                if (( _running_count > 0 )); then
                    (( _running_count-- ))
                fi
            fi
        else
            # Bash 4.x には wait -p がないため PID 識別なしで待つ。
            # 非対応環境で wait -p を実行すると _running_count が減らず、
            # このループが進行不能になる。
            wait -n 2>/dev/null || true
            if (( _running_count > 0 )); then
                (( _running_count-- ))
            fi
        fi
    done
}

#-------------------------------------------------------------------

# パスを絶対パスに変換する関数
resolve_path() {
    local input_path="$1"
    local resolved_path=""

    # 絶対パスの判定 (Linux/Unix および Windows Git Bash 対応)
    if [[ "$input_path" == /* || "$input_path" =~ ^[a-zA-Z]:\\ ]]; then
        # 絶対パスの場合はそのまま使用
        resolved_path="$input_path"
    else
        # 相対パスの場合はワークスペース フォルダーからの絶対パスを作成
        local workspace_resolved_path="$(realpath "$workspaceFolder/$input_path" 2>/dev/null)"
        if [[ -e "$workspace_resolved_path" ]]; then
            resolved_path="$workspace_resolved_path"
        else
            # ワークスペース フォルダーに存在しない場合は pub_markdown のホーム ディレクトリを使用
            resolved_path="$(realpath "$HOME_DIR/$input_path")"
        fi
    fi

    echo "$resolved_path"
}

#-------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspaceFolder=*)
            workspaceFolder="${1#*=}"
            workspaceFolder="${workspaceFolder//\\/\/}"
            #echo workspaceFolder=${workspaceFolder}
            shift
        ;;
        --relativeFile=*)
            relativeFile="${1#*=}"
            relativeFile="${relativeFile//\\/\/}"
            #echo relativeFile=${relativeFile}
            shift
        ;;
        --configFile=*)
            configFile="${1#*=}"
            configFile="${configFile//\\/\/}"
            #echo configFile=${configFile}
            shift
        ;;
        --details=*)
            details="${1#*=}"
            #echo details=${details}
            shift
        ;;
        --lang=*)
            lang="${1#*=}"
            lang="${lang//,/ }"  # カンマをスペースに変換
            #echo lang=${lang}
            shift
        ;;
        --docxOutput=*)
            docxOutput="${1#*=}"
            #echo docxOutput=${docxOutput}
            shift
        ;;
        --htmlSelfContainOutput=*)
            htmlSelfContainOutput="${1#*=}"
            #echo htmlSelfContainOutput=${htmlSelfContainOutput}
            shift
        ;;
        *)
            shift
        ;;
    esac
done
#echo ""

# 定義ファイルのデフォルト パス
if [[ -z "$configFile" ]]; then
    configFile="${workspaceFolder}/.vscode/pub_markdown.config.yaml"
else
    configFile=$(resolve_path "$configFile")
fi
export PUB_MARKDOWN_CONFIG_FILE="$configFile"

#-------------------------------------------------------------------

# キーを指定して値を取得する関数
parse_yaml() {
  local yaml="$1"
  local key="$2"
  local value=$(echo "$yaml" | awk -v k="$key" 'BEGIN {FS=":"} $1 == k {sub(/[ \t]*#.*$/, "", $2); sub(/^[ \t]+/, "", $2); print $2}')
  echo "$value"
}

find_mermaid_js() {
    local candidate
    for candidate in \
        "${SCRIPT_DIR}/node_modules/mermaid/dist/mermaid.min.js" \
        "${SCRIPT_DIR}/node_modules/@mermaid-js/mermaid-cli/node_modules/mermaid/dist/mermaid.min.js"; do
        if [[ -f "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

if [ -f "$configFile" ]; then

    # ファイルの内容を読み込む
    config_content=$(tr -d '\r' < "$configFile")

    # キーを指定して値を取得する
    mdRoot=$(parse_yaml "$config_content" "mdRoot")
    pubRoot=$(parse_yaml "$config_content" "pubRoot")
    if [[ "$details" == "" ]]; then
        details=$(parse_yaml "$config_content" "details")
    fi
    if [[ "$lang" == "" ]]; then
        lang=$(parse_yaml "$config_content" "lang")
        lang="${lang//,/ }"  # カンマをスペースに変換
    fi
    htmlStyleSheet=$(parse_yaml "$config_content" "htmlStyleSheet")
    htmlTemplate=$(parse_yaml "$config_content" "htmlTemplate")
    htmlSelfContainTemplate=$(parse_yaml "$config_content" "htmlSelfContainTemplate")
    if [[ "$htmlSelfContainOutput" == "" ]]; then
        htmlSelfContainOutput=$(parse_yaml "$config_content" "htmlSelfContainOutput")
    fi
    htmlTocEnable=$(parse_yaml "$config_content" "htmlTocEnable")
    htmlTocDepth=$(parse_yaml "$config_content" "htmlTocDepth")
    docxTemplate=$(parse_yaml "$config_content" "docxTemplate")
    if [[ "$docxOutput" == "" ]]; then
        docxOutput=$(parse_yaml "$config_content" "docxOutput")
    fi
    autoSetDate=$(parse_yaml "$config_content" "autoSetDate")
    autoSetAuthor=$(parse_yaml "$config_content" "autoSetAuthor")
    mergeSubfolderDocs=$(parse_yaml "$config_content" "mergeSubfolderDocs")
    htmlNavigationLinkEnable=$(parse_yaml "$config_content" "htmlNavigationLinkEnable")
    mathLatexEnable=$(parse_yaml "$config_content" "mathLatexEnable")
    gitLinkEnable=$(parse_yaml "$config_content" "gitLinkEnable")
    doxygenLinkEnable=$(parse_yaml "$config_content" "doxygenLinkEnable")
fi

gitLinkConfigFile="${workspaceFolder}/.vscode/git_link.yaml"
if [ -f "$gitLinkConfigFile" ]; then
    git_link_config_content=$(tr -d '\r' < "$gitLinkConfigFile")
    gitLinkHostProvider=$(parse_yaml "$git_link_config_content" "gitLinkHostProvider")
fi

# 設定ファイルに mdRoot が指定されなかった場合の値を "docs" にする
if [[ "$mdRoot" == "" ]]; then
    mdRoot="docs"
fi
export PUB_MARKDOWN_MAIN_MDROOT="${workspaceFolder}/${mdRoot}"

# 設定ファイルに pubRoot が指定されなかった場合の値を "pages" にする
if [[ "$pubRoot" == "" ]]; then
    pubRoot="pages"
fi

# 設定ファイルに details が指定されなかった場合の値を "false" にする
if [[ "$details" == "" ]]; then
    details="false"
fi

# 設定ファイルに lang が指定されなかった場合の値を "ja en" にする
if [[ "$lang" == "" ]]; then
    lang="ja en"
fi

# 設定ファイルに htmlTocEnable が指定されなかった場合の値を true にする
if [[ "$htmlTocEnable" == "" ]]; then
    htmlTocEnable="true"
fi

# 設定ファイルに htmlTocDepth が指定されなかった場合の値を 3 にする
if [[ "$htmlTocDepth" == "" ]]; then
    htmlTocDepth="3"
fi

# toc 関連オプションの組み立て
html_toc_args=()
if [[ "$htmlTocEnable" == "true" ]]; then
    html_toc_args=(--toc "--toc-depth=${htmlTocDepth}")
fi

# 設定ファイルに mathLatexEnable が指定されなかった場合の値を true にする
if [[ "$mathLatexEnable" == "" ]]; then
    mathLatexEnable="true"
fi

# markExtension: Pandoc 入力拡張。==text== を <mark> / docx 黄色ハイライトとして認識させる (HTML/docx 共通)
markExtension="+mark"

# 数式サポート (LaTeX 書式) 関連オプションの組み立て
# mathExtension: Pandoc 入力拡張。\[...\] \(...\) 書式の LaTeX 数式を認識させる (HTML/docx 共通)
# math_jax_args: MathJax によるブラウザー レンダリングを指定する Pandoc オプション (HTML のみ)
math_jax_args=()
if [[ "$mathLatexEnable" == "true" ]]; then
    mathExtension="+tex_math_single_backslash"
    math_jax_args=(--mathjax)
fi

# 設定ファイルに autoSetDate が指定されなかった場合の値を true にする
if [[ "$autoSetDate" == "" ]]; then
    autoSetDate="true"
fi

# 設定ファイルに autoSetAuthor が指定されなかった場合の値を true にする
if [[ "$autoSetAuthor" == "" ]]; then
    autoSetAuthor="true"
fi

# 設定ファイルに htmlNavigationLinkEnable (ナビゲーション リンク) が指定されなかった場合の値を true にする
if [[ "$htmlNavigationLinkEnable" == "" ]]; then
    htmlNavigationLinkEnable="true"
fi

# 設定ファイルに htmlSearchEnable (全文検索・グローバル ナビゲーション) が指定されなかった場合の値を true にする
if [[ "$htmlSearchEnable" == "" ]]; then
    htmlSearchEnable="true"
fi

# 設定ファイルに htmlNavTreeEnable (全体ナビゲーション ツリー) が指定されなかった場合の値を true にする
if [[ "$htmlNavTreeEnable" == "" ]]; then
    htmlNavTreeEnable="true"
fi

# 設定ファイルに gitLinkEnable (Git 単一ページ リンク) が指定されなかった場合の値を true にする
# (Git URL を解決できなくても doxygen-page-url があれば Doxygen HTML へフォールバックする)
if [[ "$gitLinkEnable" == "" ]]; then
    gitLinkEnable="true"
fi
# 設定ファイルに doxygenLinkEnable (Doxygen 単一ページ リンク) が指定されなかった場合の値を true にする
if [[ "$doxygenLinkEnable" == "" ]]; then
    doxygenLinkEnable="true"
fi

# 自己ホスト用 host=provider マッピングを get_file_git_url.sh へ環境変数で渡す
export GIT_LINK_HOST_PROVIDER="$gitLinkHostProvider"

#-------------------------------------------------------------------

# 設定ファイルに htmlStyleSheet が指定されなかった場合の値を "$HOME_DIR/bin/styles/html/html-style.css" にする
if [[ "$htmlStyleSheet" == "" ]]; then
    htmlStyleSheet="$HOME_DIR/styles/html/html-style.css"
else
    htmlStyleSheet=$(resolve_path ${htmlStyleSheet})
fi
if [[ ! -e "$htmlStyleSheet" ]]; then
    echo "Error: Html style sheets file does not exist: $htmlStyleSheet"
    exit 1
fi

# 設定ファイルに htmlTemplate が指定されなかった場合の値を "$HOME_DIR/bin/styles/html/html-template.html" にする
if [[ "$htmlTemplate" == "" ]]; then
    htmlTemplate="$HOME_DIR/styles/html/html-template.html"
else
    htmlTemplate=$(resolve_path ${htmlTemplate})
fi
if [[ ! -e "$htmlTemplate" ]]; then
    echo "Error: Html template file does not exist: $htmlTemplate"
    exit 1
fi

# 設定ファイルに htmlSelfContainTemplate が指定されなかった場合の値を htmlTemplate にする
if [[ "$htmlSelfContainTemplate" == "" ]]; then
    # 未指定であれば、htmlTemplate と同じでよいだろうという考え
    htmlSelfContainTemplate="${htmlTemplate}"
else
    htmlSelfContainTemplate=$(resolve_path ${htmlSelfContainTemplate})
fi
if [[ ! -e "$htmlSelfContainTemplate" ]]; then
    echo "Error: Html (self-contain) template file does not exist: $htmlSelfContainTemplate"
    exit 1
fi

# 設定ファイルに htmlSelfContainOutput が指定されなかった場合の値を false にする
if [[ "$htmlSelfContainOutput" == "" ]]; then
    htmlSelfContainOutput="false"
fi

mermaidScript=$(find_mermaid_js)
if [[ "$mermaidScript" == "" ]]; then
    echo "Error: Mermaid browser bundle does not exist. Please run npm ci in ${SCRIPT_DIR}."
    exit 1
fi

# 検索・ナビゲーション用アセットのパス解決
# MiniSearch UMD ブラウザー バンドル (npm ci で node_modules/minisearch/dist/umd/ 以下に配置)
miniSearchScript=""
for _ms_candidate in \
    "${SCRIPT_DIR}/node_modules/minisearch/dist/umd/index.min.js" \
    "${SCRIPT_DIR}/node_modules/minisearch/dist/umd/index.js"; do
    if [[ -f "$_ms_candidate" ]]; then
        miniSearchScript="$_ms_candidate"
        break
    fi
done

htmlSearchUiCss="${HOME_DIR}/styles/html/docsfw-ui.css"
htmlSearchScript="${HOME_DIR}/styles/html/docsfw-search.js"
htmlNavScript="${HOME_DIR}/styles/html/docsfw-nav.js"
htmlWordIconSvg="${HOME_DIR}/styles/html/docsfw-word-icon.svg"
htmlDetailsIconSvg="${HOME_DIR}/styles/html/docsfw-details-icon.svg"
htmlOverviewIconSvg="${HOME_DIR}/styles/html/docsfw-overview-icon.svg"
htmlDoxygenIconSvg="${HOME_DIR}/styles/html/docsfw-doxygen-icon.svg"
# Git 単一ページ リンク用 プロバイダ別アイコン (github / gitlab / gitbucket / gitea は git にフォールバック)
htmlGitIconSvgs=(
    "${HOME_DIR}/styles/html/docsfw-github-icon.svg"
    "${HOME_DIR}/styles/html/docsfw-gitlab-icon.svg"
    "${HOME_DIR}/styles/html/docsfw-gitbucket-icon.svg"
    "${HOME_DIR}/styles/html/docsfw-git-icon.svg"
)
htmlTokenizeScript="${SCRIPT_DIR}/docsfw-tokenize.js"
htmlBuildSearchScript="${SCRIPT_DIR}/build-search-index.mjs"
htmlNavTreeScript="${SCRIPT_DIR}/generate-nav-tree.py"

if [[ "$htmlSearchEnable" == "true" || "$htmlNavTreeEnable" == "true" ]]; then
    if [[ "$miniSearchScript" == "" ]]; then
        echo "Warning: MiniSearch bundle not found. Please run npm ci in ${SCRIPT_DIR}."
        echo "         Disabling htmlSearchEnable and htmlNavTreeEnable."
        htmlSearchEnable="false"
        htmlNavTreeEnable="false"
    fi
fi

# 設定ファイルに docxTemplate が指定されなかった場合の値を "$HOME_DIR/styles/docx/docx-template.dotx" にする
if [[ "$docxTemplate" == "" ]]; then
    docxTemplate="$HOME_DIR/styles/docx/docx-template.dotx"
else
    docxTemplate=$(resolve_path ${docxTemplate})
fi
if [[ ! -e "$docxTemplate" ]]; then
    echo "Error: Docx template file does not exist: $docxTemplate"
    exit 1
fi

# 設定ファイルに docxOutput が指定されなかった場合の値を false にする
if [[ "$docxOutput" == "" ]]; then
    docxOutput="false"
fi

# Adjust output directories based on the `details` flag
# details can be "true", "false", or "both"
if [[ "$details" == "both" ]]; then
    details_suffixes=("" "-details")
elif [[ "$details" == "true" ]]; then
    details_suffixes=("-details")
else
    details_suffixes=("")
fi

#-------------------------------------------------------------------
# 追加ドキュメント サブフォルダー機能
#-------------------------------------------------------------------

# mergeSubfolderDocs の path 部分で使用する環境変数を展開する関数
# 対応形式: $VAR / ${VAR}
expand_subfolder_path_env_vars() {
    local input_path="$1"
    local rest="$input_path"
    local expanded_path=""
    local prefix
    local var_name

    while [[ "$rest" == *'$'* ]]; do
        prefix="${rest%%\$*}"
        expanded_path+="$prefix"
        rest="${rest#*\$}"

        if [[ "$rest" =~ ^\{([A-Za-z_][A-Za-z0-9_]*)\}(.*)$ ]]; then
            var_name="${BASH_REMATCH[1]}"
            rest="${BASH_REMATCH[2]}"
        elif [[ "$rest" =~ ^([A-Za-z_][A-Za-z0-9_]*)(.*)$ ]]; then
            var_name="${BASH_REMATCH[1]}"
            rest="${BASH_REMATCH[2]}"
        else
            expanded_path+='$'
            continue
        fi

        if [[ -z "${!var_name+x}" ]]; then
            echo "Error: mergeSubfolderDocs path references undefined environment variable: ${var_name} (${input_path})" >&2
            return 1
        fi

        expanded_path+="${!var_name}"
    done

    expanded_path+="$rest"
    echo "$expanded_path"
}

# mergeSubfolderDocs の path をワークスペース相対パスへ正規化する関数
normalize_subfolder_path() {
    local input_path="$1"
    local normalized_path
    local workspace_abs_path
    local subfolder_abs_path

    normalized_path=$(expand_subfolder_path_env_vars "$input_path") || return 1
    normalized_path="${normalized_path//\\/\/}"

    while [[ "$normalized_path" == */ && "$normalized_path" != "/" ]]; do
        normalized_path="${normalized_path%/}"
    done

    if [[ "$normalized_path" == /* || "$normalized_path" =~ ^[a-zA-Z]:/ ]]; then
        workspace_abs_path="$(realpath "$workspaceFolder" 2>/dev/null || echo "$workspaceFolder")"
        subfolder_abs_path="$(realpath "$normalized_path" 2>/dev/null || echo "$normalized_path")"
        workspace_abs_path="${workspace_abs_path//\\/\/}"
        subfolder_abs_path="${subfolder_abs_path//\\/\/}"

        if [[ "$subfolder_abs_path" == "$workspace_abs_path" ]]; then
            echo "Error: mergeSubfolderDocs path must point below workspaceFolder, not workspaceFolder itself: ${input_path}" >&2
            return 1
        fi
        if [[ "$subfolder_abs_path" != "${workspace_abs_path}/"* ]]; then
            echo "Error: mergeSubfolderDocs path must be inside workspaceFolder: ${input_path}" >&2
            return 1
        fi

        normalized_path="${subfolder_abs_path#${workspace_abs_path}/}"
    fi

    echo "$normalized_path"
}

# 追加ドキュメント サブフォルダー設定 1 件を解析する関数
# 引数: $1=設定 (例: "docsfw=framework/docsfw/docs")
# 戻り値: グローバル変数 subfolder_alias / subfolder_path
parse_subfolder_spec() {
    local subfolder_spec="$1"

    if [[ "$subfolder_spec" != *=* ]]; then
        echo "Error: mergeSubfolderDocs entries must use alias=path: $subfolder_spec"
        return 1
    fi

    subfolder_alias="${subfolder_spec%%=*}"
    subfolder_path="${subfolder_spec#*=}"
    subfolder_path=$(normalize_subfolder_path "$subfolder_path") || return 1

    while [[ "$subfolder_alias" == */ && "$subfolder_alias" != "/" ]]; do
        subfolder_alias="${subfolder_alias%/}"
    done
    while [[ "$subfolder_path" == */ && "$subfolder_path" != "/" ]]; do
        subfolder_path="${subfolder_path%/}"
    done

    if [[ -z "$subfolder_alias" || -z "$subfolder_path" ]]; then
        echo "Error: mergeSubfolderDocs entries must use non-empty alias and path: $subfolder_spec"
        return 1
    fi
}

# subfolder_paths の要素を解析する関数
# 形式: "alias|path"
parse_subfolder_path_entry() {
    local entry="$1"
    subfolder_alias="${entry%%|*}"
    subfolder_path="${entry#*|}"
}

# subfolder_mdroot_paths の要素を解析する関数
# 形式: "alias|path|mdRoot 絶対パス"
parse_subfolder_mdroot_entry() {
    local entry="$1"
    local rest

    subfolder_alias="${entry%%|*}"
    rest="${entry#*|}"
    subfolder_path="${rest%%|*}"
    subfolder_mdroot="${rest#*|}"
}

# 設定ファイルで指定された追加ドキュメント サブフォルダーのパス リストを設定する関数
# 引数: $1=スペース区切りの一覧 (例: "doxyfw=framework/doxyfw/docs docsfw=framework/docsfw/docs")
# 戻り値: グローバル配列 subfolder_paths に "alias|path" を設定
set_subfolder_paths() {
    local subfolder_list="$1"
    local -a subfolder_specs=()
    local spec
    subfolder_paths=()

    if [[ -z "$subfolder_list" ]]; then
        return 0
    fi

    # スペース区切りで配列に変換し、alias/path 形式へ正規化
    read -ra subfolder_specs <<< "$subfolder_list"
    for spec in "${subfolder_specs[@]}"; do
        parse_subfolder_spec "$spec" || return 1
        subfolder_paths+=("${subfolder_alias}|${subfolder_path}")
    done
}

# mergeSubfolderDocs で指定された追加ドキュメント サブフォルダーを検出する関数
# 戻り値: グローバル配列 subfolder_mdroot_paths に "alias|path|ドキュメント ルート絶対パス" を設定
detect_subfolder_docs() {
    subfolder_mdroot_paths=()

    for entry in "${subfolder_paths[@]}"; do
        parse_subfolder_path_entry "$entry"
        local subfolder_mdroot_path="${workspaceFolder}/${subfolder_path}"
        if [[ ! -d "$subfolder_mdroot_path" ]]; then
            echo "Warning: mergeSubfolderDocs path does not exist or is not a directory; skipping: ${subfolder_path}"
            continue
        fi
        if [[ "${subfolder_path##*/}" != "$mdRoot" && -d "${subfolder_mdroot_path}/${mdRoot}" ]]; then
            echo "Error: mergeSubfolderDocs path must point to the document root itself, not its parent directory: ${subfolder_path}"
            return 1
        fi
        subfolder_mdroot_paths+=("${subfolder_alias}|${subfolder_path}|${subfolder_mdroot_path}")
    done
}

# 実パスを仮想パス (mdRoot 基準) に変換する関数
# 引数: $1=実パス (絶対パス)
# 戻り値: 標準出力に仮想パスを出力
real_to_virtual_path() {
    local real_path="$1"

    # 追加ドキュメント サブフォルダーのパスかチェック
    for entry in "${subfolder_mdroot_paths[@]}"; do
        parse_subfolder_mdroot_entry "$entry"

        if [[ "$real_path" == "${subfolder_mdroot}/"* ]]; then
            # 追加ドキュメント サブフォルダー配下のファイル
            local relative="${real_path#${subfolder_mdroot}/}"
            echo "${workspaceFolder}/${mdRoot}/${subfolder_alias}/${relative}"
            return 0
        elif [[ "$real_path" == "${subfolder_mdroot}" ]]; then
            # 追加ドキュメント サブフォルダー自体
            echo "${workspaceFolder}/${mdRoot}/${subfolder_alias}"
            return 0
        fi
    done

    # メイン mdRoot のファイル (変換不要)
    echo "$real_path"
}

# 仮想パスを実パスに変換する関数
# 引数: $1=仮想パス (絶対パス)
# 戻り値: 標準出力に実パスを出力
virtual_to_real_path() {
    local virtual_path="$1"
    local mdroot_prefix="${workspaceFolder}/${mdRoot}/"

    # mdRoot 配下のパスかチェック
    if [[ "$virtual_path" != "${mdroot_prefix}"* && "$virtual_path" != "${workspaceFolder}/${mdRoot}" ]]; then
        echo "$virtual_path"
        return 0
    fi

    local relative="${virtual_path#${mdroot_prefix}}"

    # 追加ドキュメント サブフォルダー名で始まるかチェック
    for entry in "${subfolder_mdroot_paths[@]}"; do
        parse_subfolder_mdroot_entry "$entry"

        if [[ "$relative" == "${subfolder_alias}/"* ]]; then
            # 追加ドキュメント サブフォルダーへのパスに変換
            local subfolder_relative="${relative#${subfolder_alias}/}"
            echo "${subfolder_mdroot}/${subfolder_relative}"
            return 0
        elif [[ "$relative" == "${subfolder_alias}" ]]; then
            # 追加ドキュメント サブフォルダー自体
            echo "${subfolder_mdroot}"
            return 0
        fi
    done

    # メイン mdRoot のファイル (変換不要)
    echo "$virtual_path"
}

# mergeSubfolderDocs 情報を初期化
declare -a subfolder_paths=()
declare -a subfolder_mdroot_paths=()

if [[ -n "$mergeSubfolderDocs" ]]; then
    set_subfolder_paths "$mergeSubfolderDocs" || exit 1
    detect_subfolder_docs || exit 1
    # insert-toc.sh 用に環境変数をエクスポート
    export MERGE_SUBFOLDER_DOCS="$mergeSubfolderDocs"
    export SUBFOLDER_DOCS_PATHS="$(printf '%s\n' "${subfolder_mdroot_paths[@]}")"
fi

#-------------------------------------------------------------------

# relativeFile のパス検証 (追加ドキュメント サブフォルダー対応)
if [[ -n $relativeFile ]]; then
    path_type=""
    resolved_relativeFile="$relativeFile"

    # 1. 追加ドキュメント サブフォルダー実パスのチェック
    if [[ -n "$mergeSubfolderDocs" ]]; then
        for entry in "${subfolder_mdroot_paths[@]}"; do
            parse_subfolder_mdroot_entry "$entry"
            if [[ $relativeFile == ${subfolder_path}/* || $relativeFile == ${subfolder_path} ]]; then
                path_type="subfolder_real"
                break
            fi
        done
    fi

    # 2. 仮想パスのチェック
    if [[ -z "$path_type" && -n "$mergeSubfolderDocs" ]]; then
        for entry in "${subfolder_mdroot_paths[@]}"; do
            parse_subfolder_mdroot_entry "$entry"
            if [[ $relativeFile == ${mdRoot}/${subfolder_alias}/* || $relativeFile == ${mdRoot}/${subfolder_alias} ]]; then
                path_type="subfolder_virtual"
                break
            fi
        done
    fi

    # 3. メイン mdRoot パスのチェック
    if [[ -z "$path_type" && ( $relativeFile == ${mdRoot}/* || $relativeFile == ${mdRoot} ) ]]; then
        path_type="mdroot"
    fi

    # 4. いずれにも該当しない場合はエラー
    if [[ -z "$path_type" ]]; then
        echo "Error: relativeFile is not a valid path: $relativeFile"
        exit 1
    fi

    # relativeFile が実パスの場合、仮想パスに変換 (内部処理の統一のため)
    if [[ "$path_type" == "subfolder_real" ]]; then
        for entry in "${subfolder_mdroot_paths[@]}"; do
            parse_subfolder_mdroot_entry "$entry"
            _subfolder_mdroot_rel="${subfolder_path}"

            if [[ $relativeFile == ${_subfolder_mdroot_rel}/* ]]; then
                _subpath="${relativeFile#${_subfolder_mdroot_rel}/}"
                original_relativeFile="$relativeFile"
                resolved_relativeFile="$relativeFile"
                relativeFile="${mdRoot}/${subfolder_alias}/${_subpath}"
                break
            elif [[ $relativeFile == ${_subfolder_mdroot_rel} ]]; then
                original_relativeFile="$relativeFile"
                resolved_relativeFile="$relativeFile"
                relativeFile="${mdRoot}/${subfolder_alias}"
                break
            fi
        done
    elif [[ "$path_type" == "subfolder_virtual" ]]; then
        for entry in "${subfolder_mdroot_paths[@]}"; do
            parse_subfolder_mdroot_entry "$entry"

            if [[ $relativeFile == ${mdRoot}/${subfolder_alias}/* ]]; then
                _subpath="${relativeFile#${mdRoot}/${subfolder_alias}/}"
                resolved_relativeFile="${subfolder_path}/${_subpath}"
                break
            elif [[ $relativeFile == ${mdRoot}/${subfolder_alias} ]]; then
                resolved_relativeFile="${subfolder_path}"
                break
            fi
        done
    fi
fi

if [ -n "$relativeFile" ]; then
    if [ -d "${workspaceFolder}/$resolved_relativeFile" ]; then
        # 実行モード=フォルダー
        executionMode="folder"

        # $relativeFile がフォルダー名の場合は、そのフォルダーを基準とする
        base_dir="${workspaceFolder}/${relativeFile}"

        # 当該フォルダー配下の clean (再帰)
        if [[ "$base_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_rel=${base_dir#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir_rel=""
        fi

        for langElement in ${lang}; do
            for details_suffix in "${details_suffixes[@]}"; do
                for _out_type in html html-self-contain docx; do
                    if [[ -n "$publish_dir_rel" ]]; then
                        _target="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${_out_type}/${publish_dir_rel}"
                    else
                        _target="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${_out_type}"
                    fi
                    if [[ -d "$_target" ]]; then
                        rm -rf "$_target"
                    fi
                done
                if [[ -n "$publish_dir_rel" ]]; then
                    mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/${publish_dir_rel}"
                else
                    mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html"
                fi
            done
        done
    else
        # 実行モード=ファイル
        executionMode="singlefile"

        # 単一ファイルの場合は、そのファイルのあるフォルダーを基準とする
        base_dir="${workspaceFolder}/$(dirname "$relativeFile")"
    fi
else
    # 実行モード=ワークスペース
    executionMode="workspace"

    base_dir="${workspaceFolder}/${mdRoot}"
    mkdir -p "${workspaceFolder}/${pubRoot}"

    # 出力フォルダーの clean (対象言語に絞る)
    for langElement in ${lang}; do
        if [[ "$details" == "both" ]]; then
            # 両方出力する場合は、対象言語の通常版と details 版を削除
            rm -rf "${workspaceFolder}/${pubRoot}/${langElement}"
            rm -rf "${workspaceFolder}/${pubRoot}/${langElement}-details"
        elif [[ "$details" == "true" ]]; then
            # 対象言語の "-details" ディレクトリを削除
            rm -rf "${workspaceFolder}/${pubRoot}/${langElement}-details"
        else
            # 対象言語の通常版ディレクトリを削除
            rm -rf "${workspaceFolder}/${pubRoot}/${langElement}"
        fi
    done
fi

#-------------------------------------------------------------------

# ファイルをコピーする関数
# 引数: $1=元ファイル パス, $2=コピー先ファイル パス
copy_if_different_timestamp() {
    local src_file="$1"
    local dest_file="$2"

    # 元ファイルが存在しない場合はエラー
    if [[ ! -e "$src_file" ]]; then
        echo "Error: Source file does not exist: $src_file"
        return 1
    fi

    # コピー先ファイルが存在しない場合は直接コピー
    if [[ ! -e "$dest_file" ]]; then
        #echo "Processing Other file: ${src_file#${workspaceFolder}/}"
        cp -p "$src_file" "$dest_file"
        return 0
    fi

    # タイムスタンプを比較
    if [[ ! "$src_file" -nt "$dest_file" && ! "$dest_file" -ot "$src_file" ]]; then
        # ファイルのタイムスタンプがほぼ同じ場合はコピーしない
        #echo "File not copied: Timestamps are approximately the same."
        return 0
    fi

    # タイムスタンプが異なる場合はコピー
    #echo "Processing Other file: ${src_file#${workspaceFolder}/}"
    cp -p "$src_file" "$dest_file"
    return 0
}

# SVG ファイルのコピー / foreignObject フィルター処理。
# - .svg 以外、または <foreignObject を含まない .svg は copy_if_different_timestamp で素通し。
# - <foreignObject を含む .svg は strip-foreignobject.py を通してフィルター後のファイルを配置する。
#   ソース ファイルは変更しない。冪等性は mtime 比較で保証する。
#   フィルター失敗時は原本をコピーして警告を出す (画像欠落を防ぐ)。
copy_or_filter_svg() {
    local src_file="$1"
    local dest_file="$2"

    # SVG 以外、または foreignObject を含まない SVG は素通し (mtime・バイト温存)
    case "$src_file" in
        *.svg)
            if ! grep -q '<foreignObject' "$src_file" 2>/dev/null; then
                copy_if_different_timestamp "$src_file" "$dest_file"
                return 0
            fi
            ;;
        *)
            copy_if_different_timestamp "$src_file" "$dest_file"
            return 0
            ;;
    esac

    # foreignObject を含む SVG → フィルター処理
    # 冪等性: dest が無い、または src が dest より新しい場合のみ再生成
    if [[ -e "$dest_file" && ! "$src_file" -nt "$dest_file" && ! "$dest_file" -ot "$src_file" ]]; then
        return 0
    fi

    local tmp_file
    tmp_file=$(mktemp)
    if python3 "${SCRIPT_DIR}/strip-foreignobject.py" "$src_file" > "$tmp_file" 2>/dev/null; then
        mv "$tmp_file" "$dest_file"
        touch -r "$src_file" "$dest_file"   # mtime を src に揃えて次回実行をスキップ
    else
        # フィルター失敗時は原本をコピー (画像欠落を防ぐ)
        rm -f "$tmp_file"
        echo "Warning: strip-foreignobject に失敗しました。原本をコピーします: ${src_file}"
        cp -p "$src_file" "$dest_file"
    fi
    return 0
}

#-------------------------------------------------------------------

set_html_lang_attributes() {
    local html_file="$1"
    local lang_code="$2"
    local tmp_file=""

    if [[ ! -f "$html_file" ]]; then
        echo "Warning: Html file does not exist: $html_file"
        return 1
    fi

    tmp_file=$(mktemp)
    if ! HTML_LANG_CODE="$lang_code" perl -0777 -pe '
        my $target_lang = $ENV{HTML_LANG_CODE} // "";
        s{<html\b([^>]*)>}{
            my $attrs = $1;
            if ($attrs =~ /\blang\s*=\s*(["\x27]).*?\1/i) {
                $attrs =~ s/\blang\s*=\s*(["\x27]).*?\1/ lang="$target_lang"/i;
            } else {
                $attrs .= qq{ lang="$target_lang"};
            }
            if ($attrs =~ /\bxml:lang\s*=\s*(["\x27]).*?\1/i) {
                $attrs =~ s/\bxml:lang\s*=\s*(["\x27]).*?\1/ xml:lang="$target_lang"/i;
            } else {
                $attrs .= qq{ xml:lang="$target_lang"};
            }
            "<html$attrs>";
        }ie;
    ' "$html_file" > "$tmp_file"; then
        rm -f "$tmp_file"
        return 1
    fi

    mv "$tmp_file" "$html_file"
}

#-------------------------------------------------------------------

echo "*** pub_markdown_core start $(date -Is)"
if [ "${MAX_PARALLEL:-0}" -ge 2 ]; then
    echo "Parallelism: ${MAX_PARALLEL}"
fi
progress_log "発行処理を開始しました"

#-------------------------------------------------------------------

# insert-toc.lua のキャッシュをクリア
rm -f /tmp/insert-toc-cache.tsv > /dev/null

#-------------------------------------------------------------------

echo -n "Correcting target files..."
progress_log "対象ファイルの収集を開始しました"

# ── (A) relativeFile を使って初期リストを NUL 区切りで作成 ──
if [ -n "$relativeFile" ]; then
    # 実パスの解決
    # resolved_relativeFile にはメイン mdRoot / サブモジュール実パス / 仮想パスの
    # いずれで指定されても、実ファイル系の相対パスが入っている
    real_relativeFile="$resolved_relativeFile"

    if [ -d "${workspaceFolder}/$real_relativeFile" ]; then
        # relativeFile がディレクトリの場合: そのディレクトリ配下の対象ファイルを再帰的に収集
        # base_dir は実パスを使用 (ファイル探索用)
        real_base_dir="${workspaceFolder}/${real_relativeFile}"
        # 仮想パスの base_dir も設定 (出力パス計算用)
        base_dir="${workspaceFolder}/${relativeFile}"

        # ディレクトリ配下の対象ファイル (.md / .yaml / .json) を再帰的に収集
        # ディレクトリ制御マジックファイル (pubpart.yaml / pubchild.yaml / publocal.yaml) は発行対象から除外する
        mapfile -d '' -t files_raw_initial < <(
            find -L "${real_base_dir}" -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.json" \) \
                ! -name "pubpart.yaml" ! -name "pubchild.yaml" ! -name "publocal.yaml" -print0 | sort -z -u
        )
    else
        # relativeFile が単一ファイルの場合: そのファイルを対象とする
        # base_dir は実パスを使用
        real_base_dir="${workspaceFolder}/$(dirname "$real_relativeFile")"
        base_dir="${workspaceFolder}/$(dirname "$relativeFile")"

        files_raw_initial=("${workspaceFolder}/${real_relativeFile}")
    fi
else
    # relativeFile が指定されていない場合: mdRoot 以下の対象ファイル (.md / .yaml / .json) を対象
    # -L を付与してシンボリック リンクも対象にする
    # ディレクトリ制御マジックファイル (pubpart.yaml / pubchild.yaml / publocal.yaml) は発行対象から除外する
    mapfile -d '' -t files_raw_initial < <(
        find -L "${base_dir}" -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.json" \) \
            ! -name "pubpart.yaml" ! -name "pubchild.yaml" ! -name "publocal.yaml" -print0 | sort -z -u
    )

    # 追加ドキュメント サブフォルダーのファイルを追加 (mergeSubfolderDocs が指定されている場合)
    if [[ -n "$mergeSubfolderDocs" ]]; then
        for entry in "${subfolder_mdroot_paths[@]}"; do
            parse_subfolder_mdroot_entry "$entry"

            # 追加ドキュメント サブフォルダー配下の対象ファイルを収集
            # -L を付与してシンボリック リンクも対象にする
            # ディレクトリ制御マジックファイル (pubpart.yaml / pubchild.yaml / publocal.yaml) は発行対象から除外する
            mapfile -d '' -t subfolder_files < <(
                find -L "${subfolder_mdroot}" -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.json" \) \
                    ! -name "pubpart.yaml" ! -name "pubchild.yaml" ! -name "publocal.yaml" -print0 | sort -z -u
            )

            # files_raw_initial に追加
            files_raw_initial+=("${subfolder_files[@]}")
        done
    fi
fi

# ── (B) Git 管理下なら NUL 区切りでフィルター ──
if git -C "$workspaceFolder" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    # 追加ドキュメント サブフォルダー配下のファイルを分離 (gitignore フィルタリング対象外)
    declare -a subfolder_files_array=()
    declare -a main_files_array=()

    if [[ -n "$mergeSubfolderDocs" && ${#subfolder_mdroot_paths[@]} -gt 0 ]]; then
        for f in "${files_raw_initial[@]}"; do
            is_subfolder_file=false
            for entry in "${subfolder_mdroot_paths[@]}"; do
                parse_subfolder_mdroot_entry "$entry"
                if [[ "$f" == "${subfolder_mdroot}/"* || "$f" == "${subfolder_mdroot}" ]]; then
                    is_subfolder_file=true
                    break
                fi
            done
            if [[ "$is_subfolder_file" == "true" ]]; then
                subfolder_files_array+=("$f")
            else
                main_files_array+=("$f")
            fi
        done
    else
        main_files_array=("${files_raw_initial[@]}")
    fi

    # 1) workspaceFolder/ を切り落として相対パス化 (NUL 区切り) - メイン ファイルのみ
    mapfile -d '' -t files_rel_zero_array < <(
        printf '%s\0' "${main_files_array[@]}" | \
        sed -z "s|^${workspaceFolder}/||g"
    )

    # 2) Git check-ignore に NUL 区切りで渡し、結果も NUL 区切りで受け取る
    mapfile -d '' -t filtered_rel_array < <(
    printf '%s\0' "${files_rel_zero_array[@]}" | \
    git -C "$workspaceFolder" \
        check-ignore --verbose --non-matching --stdin -z 2>/dev/null | \
    perl -0777 -ne '
        my @records = split(/\x00/, $_);
        my @out;
        # 「rule」「path」のペアで処理。ただし空の path は捨てる
        for (my $i = 0; $i + 1 < @records; $i += 2) {
            my $rule = $records[$i];
            my $path = $records[$i + 1];
            next unless defined($path) && length($path);

            # 処理対象ファイル (.md, .yaml, .yml, .json) は .gitignore を無視
            my $is_source_file = ($path =~ /\.(md|yaml|yml|json)$/i);

            if ($is_source_file) {
                # ソース ファイルは常に含める (.gitignore を無視)
                push @out, $path;
            } elsif ($rule eq "" || $rule =~ /^!/) {
                # その他のファイルは .gitignore ルールを尊重
                push @out, $path;
            }
        }
        # 末尾に余分な NUL を付けないよう、join でまとめて出力
        print join("\0", @out);
        '
    )

    # 3) 絶対パスに戻して改行区切りで files_raw 変数に格納
    files_raw=""
    for relpath in "${filtered_rel_array[@]}"; do
        [ -z "$relpath" ] && continue
        files_raw+="${workspaceFolder}/${relpath}"$'\n'
    done

    # 4) 追加ドキュメント サブフォルダー配下のファイルを追加 (フィルタリング済みとして扱う)
    for f in "${subfolder_files_array[@]}"; do
        files_raw+="${f}"$'\n'
    done

else
    # Git 管理外ならファイル名を NUL→改行区切りに変えてそのまま使う
    files_raw=$(printf '%s\n' "${files_raw_initial[@]}")
fi

# 配列に格納
IFS=$'\n' read -r -d '' -a files <<< "$files_raw"

files_without_skip=()
for file in "${files[@]}"; do
    if is_pub_markdown_skip "$file"; then
        progress_log "pub_markdown.skip により発行対象から除外しました file=${file#${workspaceFolder}/}"
        continue
    fi
    files_without_skip+=("$file")
done
files=("${files_without_skip[@]}")

echo " done."
progress_log "対象ファイルの収集を終了しました count=${#files[@]}"

#-------------------------------------------------------------------

if should_start_shared_browser; then
    start_shared_browser_server || true
else
    export -n PUB_MARKDOWN_BROWSER_WS_FILE
    progress_log "共有ブラウザ起動を省略しました mode=${PUB_MARKDOWN_BROWSER_REUSE} docxOutput=${docxOutput}"
fi

#-------------------------------------------------------------------

for file in "${files[@]}"; do
    # 単一 md の発行で、リンク先のファイルがない場合は処理しない
    # → ファイルが存在する場合のみ処理を行う
    if [[ -e "$file" ]]; then
        # 追加ドキュメント サブフォルダー使用時は仮想パスに変換して出力パスを計算
        if [[ -n "$mergeSubfolderDocs" ]]; then
            virtual_file=$(real_to_virtual_path "$file")
        else
            virtual_file="$file"
        fi

        publish_dir=$(dirname "${virtual_file}")
        if [[ "$publish_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir="html/${publish_dir#${workspaceFolder}/${mdRoot}/}"
        else
            publish_dir="html"
        fi

        for langElement in ${lang}; do
            for details_suffix in "${details_suffixes[@]}"; do
                mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir"
            done
        done
        publish_file="html/${virtual_file#${workspaceFolder}/${mdRoot}/}"

        # NOTE: OpenAPI ファイルは発行時に同梱すべきかと考えたため、コピーを行う (除外処理をしない)
        if [[ "$file" != *.md ]] ; then
            # コンテンツのコピー (実パスを使用)
            echo "Processing Other file: ${virtual_file#${workspaceFolder}/}"
            for langElement in ${lang}; do
                for details_suffix in "${details_suffixes[@]}"; do
                    copy_if_different_timestamp "$file" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_file"
                done
            done
        fi
    fi
done

# CSS の配置
for langElement in ${lang}; do
    for details_suffix in "${details_suffixes[@]}"; do
        mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html"
        copy_if_different_timestamp "${htmlStyleSheet}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/html-style.css"
        copy_if_different_timestamp "${mermaidScript}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/mermaid.min.js"
        # DOCX ダウンロードリンク用アイコン (docxOutput の設定切り替えで既存 HTML が参照する場合に備えて常時配置する)
        copy_if_different_timestamp "${htmlWordIconSvg}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/docsfw-word-icon.svg"
        # 概要版/詳細版 切替リンク用アイコン (details の設定切り替えで既存 HTML が参照する場合に備えて常時配置する)
        copy_if_different_timestamp "${htmlDetailsIconSvg}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/docsfw-details-icon.svg"
        copy_if_different_timestamp "${htmlOverviewIconSvg}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/docsfw-overview-icon.svg"
        # Doxygen 単一ページ リンク用アイコン (doxygenLinkEnable の設定切り替えで既存 HTML が参照する場合に備えて常時配置する)
        copy_if_different_timestamp "${htmlDoxygenIconSvg}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/docsfw-doxygen-icon.svg"
        # Git 単一ページ リンク用 プロバイダ別アイコン (gitLinkEnable の設定切り替えで既存 HTML が参照する場合に備えて常時配置する)
        for _gitIconSvg in "${htmlGitIconSvgs[@]}"; do
            copy_if_different_timestamp "${_gitIconSvg}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/$(basename "${_gitIconSvg}")"
        done
        # 検索・ナビゲーション用静的アセットの配置
        if [[ "$htmlSearchEnable" == "true" || "$htmlNavTreeEnable" == "true" ]]; then
            copy_if_different_timestamp "${miniSearchScript}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/minisearch.min.js"
            copy_if_different_timestamp "${htmlTokenizeScript}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/docsfw-tokenize.js"
            copy_if_different_timestamp "${htmlSearchScript}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/docsfw-search.js"
            copy_if_different_timestamp "${htmlNavScript}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/docsfw-nav.js"
            copy_if_different_timestamp "${htmlSearchUiCss}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/docsfw-ui.css"
        fi
    done
done

# ファイル レベルの並列処理用追跡配列
declare -a _file_pids=()
declare -a _file_names=()
declare -a _file_status_files=()
_pm_job_index=0

for file in "${files[@]}"; do
    # 追加ドキュメント サブフォルダー使用時は仮想パスに変換して出力パスを計算
    if [[ -n "$mergeSubfolderDocs" ]]; then
        virtual_file=$(real_to_virtual_path "$file")
    else
        virtual_file="$file"
    fi

    if [[ "$file" == *.yaml ]] || [[ "$file" == *.json ]]; then # TODO: OpenAPI ファイルを .yaml 拡張子で判断してよいかどうかは怪しい。ファイル内に"openapi:"があることくらいは見たほうがいい。

        # FIXME: markdown ファイルとの重複処理は統合すべき。
        # OpenAPI 処理全体を一時ファイルにバッファリングし、ロックでアトミックに出力する
        # (.md の並列ジョブと printf "\e[33m" / "\e[0m" が競合するのを防ぐ)
        _pm_openapi_tmpout=$(mktemp)
        {

        echo "Processing OpenAPI file: ${file#${workspaceFolder}/}"

        # html (仮想パス ベースで出力パスを計算)
        publish_dir=$(dirname "${virtual_file}")
        if [[ "$publish_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir=html/${publish_dir#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir=html
        fi
        publish_file=html/${virtual_file#${workspaceFolder}/${mdRoot}/}

        # html-self-contain
        publish_dir_self_contain=$(dirname "${virtual_file}")
        if [[ "$publish_dir_self_contain" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_self_contain="html-self-contain/${publish_dir_self_contain#${workspaceFolder}/${mdRoot}/}"
        else
            publish_dir_self_contain="html-self-contain"
        fi
        if [[ "$htmlSelfContainOutput" == "true" ]]; then
            for langElement in ${lang}; do
                for details_suffix in "${details_suffixes[@]}"; do
                    mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir_self_contain"
                done
            done
        fi
        publish_file_self_contain="html-self-contain/${virtual_file#${workspaceFolder}/${mdRoot}/}"

        # docx
        publish_dir_docx=$(dirname "${virtual_file}")
        if [[ "$publish_dir_docx" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_docx=docx/${publish_dir_docx#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir_docx=docx
        fi
        if [[ "$docxOutput" == "true" ]]; then
            for langElement in ${lang}; do
                for details_suffix in "${details_suffixes[@]}"; do
                    mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir_docx"
                done
            done
        fi
        publish_file_docx=docx/${virtual_file#${workspaceFolder}/${mdRoot}/}

        # path to css
        nest_count=$(echo "$publish_file" | grep -o '/' | wc -l)
        up_dir=""
        for ((i=2; i<=nest_count; i++)); do
            up_dir+="../"
        done

        # ナビゲーション リンク メタデータの構築
        navigation_link_metadata_args=()
        if [[ "$htmlNavigationLinkEnable" == "true" ]]; then
            navigation_link_metadata_args=(--metadata "homelink=${up_dir}index.html")
        fi

        # 検索・ナビゲーション メタデータの構築
        # publish_file は ".md" 拡張子のままなので ".html" に変換してから html/ を除去する
        search_metadata_args=()
        if [[ "$htmlSearchEnable" == "true" || "$htmlNavTreeEnable" == "true" ]]; then
            _search_current="${publish_file%.*}.html"
            _search_current="${_search_current#html/}"
            search_metadata_args=(
                --metadata "search-enable=true"
                --metadata "search-base=${up_dir}"
                --metadata "search-current=${_search_current}"
            )
        fi

        # DOCX ダウンロードリンク メタデータの構築
        # docx 出力が有効な場合のみ、対応する docx への相対 URL とアイコンの URL を HTML に埋め込む
        # (self-contain HTML には渡さない。実在確認はテンプレート内の JavaScript が行う)
        docx_link_metadata_args=()
        if [[ "$docxOutput" == "true" ]]; then
            docx_link_metadata_args=(
                --metadata "docx-url=${up_dir}../${publish_file_docx%.*}.docx"
                --metadata "docx-icon=${up_dir}docsfw-word-icon.svg"
            )
        fi

        # 概要版/詳細版 切替リンク メタデータの構築
        # details=both の場合のみ渡す (それ以外は切替先ツリーが存在しない)。
        # 切替先 URL はバリアントコピー最適化と両立させるためビルド時に確定せず、
        # テンプレート内の JavaScript が実行時の URL から算出する (実在確認も JavaScript が行う)
        details_link_metadata_args=()
        if [[ "$details" == "both" ]]; then
            details_link_metadata_args=(
                --metadata "details-switch-root=${up_dir}../../"
                --metadata "details-icon-base=${up_dir}"
            )
        fi

        if [[ "$autoSetDate" == "true" ]]; then
            # get_file_date.sh "$file" を実行し、結果を DOCUMENT_DATE に設定
            export DOCUMENT_DATE=$(sh ${SCRIPT_DIR}/get_file_date.sh "$file")
        else
            export -n DOCUMENT_DATE
        fi

        if [[ "$autoSetAuthor" == "true" ]]; then
            # get_file_author.sh "$file" を実行し、結果を DOCUMENT_AUTHOR に設定
            export DOCUMENT_AUTHOR=$(sh ${SCRIPT_DIR}/get_file_author.sh "$file")
        else
            export -n DOCUMENT_AUTHOR
        fi

        # オリジナルのソース ファイル名を環境変数に保持
        export SOURCE_FILE="$file"

        # NOTE: --code true を取り除き、--language_tabs http --language_tabs shell --omitHeader のように与えるとサンプル コードを出力できる。shell, http, javascript, ruby, python, php, java, go
        # TODO: --user_templates の切替機構未実装
        openapi_md=$(${WIDDERSHINS} --code true --user_templates ${HOME_DIR}/styles/widdershins/openapi3 --omitHeader "$file" | sed '1,/^<!--/ d')
        openapi_md_title=$(echo "${openapi_md}" \
            | sed -n '/^#/p' \
            | head -n 1 \
            | sed 's/^# *//' \
            | tr -d '\r')

        firstLang=""
        firstSuffix=""
        for details_suffix in "${details_suffixes[@]}"; do
            for langElement in ${lang}; do

                export DOCUMENT_LANG=$langElement
                build_doxygen_link_metadata_args "$file" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" "${up_dir}docsfw-doxygen-icon.svg"
                build_git_link_metadata_args "$file" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" "$up_dir"

                if [ "$firstLang" == "" ]; then
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                    _pm_pandoc_stderr=$(mktemp)
                    echo "${openapi_md}" | \
                        "$PANDOC" -s "${html_toc_args[@]}" --shift-heading-level-by=-1 -N --eol=lf --metadata title="$openapi_md_title" --metadata "lang=${langElement}" "${navigation_link_metadata_args[@]}" "${search_metadata_args[@]}" "${docx_link_metadata_args[@]}" "${details_link_metadata_args[@]}" "${doxygen_link_metadata_args[@]}" "${git_link_metadata_args[@]}" -f markdown+hard_line_breaks${markExtension}${mathExtension} \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/admonition.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                            --template="${htmlTemplate}" -c "${up_dir}html-style.css" \
                            --metadata "mermaid-js=${up_dir}mermaid.min.js" \
                            "${pandoc_crossref_args[@]}" \
                            "${math_jax_args[@]}" \
                            --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                            --wrap=none -t html -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" \
                            2>"$_pm_pandoc_stderr"
                    if [[ -s "$_pm_pandoc_stderr" ]]; then
                        printf "\e[33m"
                        cat "$_pm_pandoc_stderr"
                        printf "\e[0m"
                    fi
                    rm -f "$_pm_pandoc_stderr"
                    set_html_lang_attributes "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" "$langElement"
                    if [[ "$htmlSelfContainOutput" == "true" ]]; then
                        build_doxygen_link_metadata_args "$file" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/docsfw-doxygen-icon.svg"
                        echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                        _pm_pandoc_stderr=$(mktemp)
                        echo "${openapi_md}" | \
                            "$PANDOC" -s "${html_toc_args[@]}" --shift-heading-level-by=-1 -N --eol=lf --metadata title="$openapi_md_title" --metadata "lang=${langElement}" "${navigation_link_metadata_args[@]}" "${search_metadata_args[@]}" "${doxygen_link_metadata_args[@]}" -f markdown+hard_line_breaks${markExtension}${mathExtension} \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/admonition.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                                "${pandoc_crossref_args[@]}" \
                                "${math_jax_args[@]}" \
                                --template="${htmlSelfContainTemplate}" -c "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/html-style.css" \
                                --metadata "mermaid-js=${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/mermaid.min.js" \
                                --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                                --wrap=none -t html --embed-resources --standalone -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html" \
                                2>"$_pm_pandoc_stderr"
                        if [[ -s "$_pm_pandoc_stderr" ]]; then
                            printf "\e[33m"
                            cat "$_pm_pandoc_stderr"
                            printf "\e[0m"
                        fi
                        rm -f "$_pm_pandoc_stderr"
                        set_html_lang_attributes "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html" "$langElement"
                    fi
                    if [[ "$docxOutput" == "true" ]]; then
                        echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                        _pm_pandoc_stderr=$(mktemp)
                        echo "${openapi_md}" | \
                            "$PANDOC" -s --shift-heading-level-by=-1 --eol=lf --metadata title="$openapi_md_title" -f markdown+hard_line_breaks${markExtension}${mathExtension} \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/horizontal-rule.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/admonition.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/toc-pagebreak.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/page-break-before-heading.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/separate-consecutive-blockquotes.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/replace-table-br.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-docx.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/inline-code-style.lua" \
                                "${pandoc_crossref_args[@]}" \
                                --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                                --wrap=none -t docx --reference-doc="${docxTemplate}" -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx" \
                                2>"$_pm_pandoc_stderr"
                        if [[ -s "$_pm_pandoc_stderr" ]]; then
                            printf "\e[33m"
                            cat "$_pm_pandoc_stderr"
                            printf "\e[0m"
                        fi
                        rm -f "$_pm_pandoc_stderr"
                        python3 "${SCRIPT_DIR}/pandoc-filters/fit-docx-images-to-page.py" \
                            "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx" \
                            >/dev/null 2>/dev/null || true
                        python3 "${SCRIPT_DIR}/pandoc-filters/inject-toc-placeholder.py" \
                            "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx" \
                            2>/dev/null || true
                    fi
                    firstLang="${langElement}"
                    firstSuffix="${details_suffix}"
                else
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                    cp -p "${workspaceFolder}/${pubRoot}/${firstLang}${firstSuffix}/${publish_file%.*}.html" \
                          "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" \
                        || echo "Warning: Failed to copy HTML file: ${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                    set_html_lang_attributes "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" "$langElement"
                    if [[ "$htmlSelfContainOutput" == "true" ]]; then
                        echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                        cp -p "${workspaceFolder}/${pubRoot}/${firstLang}${firstSuffix}/${publish_file_self_contain%.*}.html" \
                              "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html" \
                            || echo "Warning: Failed to copy HTML file: ${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                        set_html_lang_attributes "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html" "$langElement"
                    fi
                    if [[ "$docxOutput" == "true" ]]; then
                        echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                        cp -p "${workspaceFolder}/${pubRoot}/${firstLang}${firstSuffix}/${publish_file_docx%.*}.docx" \
                              "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx" \
                            || echo "Warning: Failed to copy DOCX file: ${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                    fi
                fi
            done
        done

        } >"$_pm_openapi_tmpout" 2>&1
        while ! mkdir "${OUTPUT_LOCK}.lck" 2>/dev/null; do sleep 0.01; done
        cat "$_pm_openapi_tmpout"
        rmdir "${OUTPUT_LOCK}.lck"
        rm -f "$_pm_openapi_tmpout"
    elif [[ "$file" == *.md ]]; then
        # .md ファイルを並列処理する
        # 空きスロットが生じるまで待ってからバックグラウンドで起動する
        _pm_job_index=$((_pm_job_index + 1))
        # 親シェルで確定させる: サブシェル exit 後に親側から読み取る
        _pm_statusfile="${_PM_STATUS_DIR}/job-${_pm_job_index}"
        _pm_infofile="${_pm_statusfile}.info"
        wait_for_parallel_slot
        (
        # サブシェルがどの経路で終了してもステータスを書き込む。
        # あわせて defaults 用の一時ファイルを確実に削除する。
        trap '
            _pm_trap_exit=$?
            rmdir "${OUTPUT_LOCK}.lck" 2>/dev/null
            echo "$_pm_trap_exit" > "$_pm_statusfile"
            [[ ${#defaults_metadata_tmpfiles[@]} -gt 0 ]] && rm -f "${defaults_metadata_tmpfiles[@]}"
        ' EXIT
        # 親の無進捗監視 (ウォッチドッグ) 用ハートビート ファイル。
        # progress_log と pandoc の Lua フィルター (plantuml.lua / mermaid.lua) が
        # 進捗のたびに更新し、親はこの更新を検出してタイムアウトのタイマーをリセットする。
        _pm_heartbeat_file="${_pm_statusfile}.hb"
        _pm_phase_file="${_pm_statusfile}.phase"
        printf 'pid=%s\nfile=%s\n' "$BASHPID" "$file" > "$_pm_infofile"
        touch "$_pm_heartbeat_file"
        # pandoc.exe (Win32) の Lua がパスを解決できるよう
        # cygpath -m で Windows ネイティブ形式に変換して渡す
        if is_windows_host && command -v cygpath >/dev/null 2>&1; then
            export PUB_MARKDOWN_JOB_HEARTBEAT_FILE="$(cygpath -m "$_pm_heartbeat_file")"
            export PUB_MARKDOWN_JOB_PHASE_FILE="$(cygpath -m "$_pm_phase_file")"
        else
            export PUB_MARKDOWN_JOB_HEARTBEAT_FILE="$_pm_heartbeat_file"
            export PUB_MARKDOWN_JOB_PHASE_FILE="$_pm_phase_file"
        fi
        # このサブシェル内の出力を一時ファイルにバッファリングし、
        # 完了後に flock でアトミックに標準出力へ書き出す (並列実行時の出力混在を防ぐ)
        _pm_tmpout=$(mktemp)
        {
        # .md ファイルの処理
        set_job_phase "Markdown 処理"
        progress_log "Markdown 処理を開始しました file=${file#${workspaceFolder}/}"
        echo "Processing Markdown file: ${file#${workspaceFolder}/}"

        # html (仮想パス ベースで出力パスを計算)
        publish_dir=$(dirname "${virtual_file}")
        if [[ "$publish_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir=html/${publish_dir#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir=html
        fi
        publish_file=html/${virtual_file#${workspaceFolder}/${mdRoot}/}

        # html-self-contain
        publish_dir_self_contain=$(dirname "${virtual_file}")
        if [[ "$publish_dir_self_contain" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_self_contain="html-self-contain/${publish_dir_self_contain#${workspaceFolder}/${mdRoot}/}"
        else
            publish_dir_self_contain="html-self-contain"
        fi
        if [[ "$htmlSelfContainOutput" == "true" ]]; then
            for langElement in ${lang}; do
                for details_suffix in "${details_suffixes[@]}"; do
                    mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir_self_contain"
                done
            done
        fi
        publish_file_self_contain="html-self-contain/${virtual_file#${workspaceFolder}/${mdRoot}/}"

        # docx
        publish_dir_docx=$(dirname "${virtual_file}")
        if [[ "$publish_dir_docx" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_docx=docx/${publish_dir_docx#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir_docx=docx
        fi
        if [[ "$docxOutput" == "true" ]]; then
            for langElement in ${lang}; do
                for details_suffix in "${details_suffixes[@]}"; do
                    mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir_docx"
                done
            done
        fi
        publish_file_docx=docx/${virtual_file#${workspaceFolder}/${mdRoot}/}

        # README.md / SKILL.md を index.* に変換するロジック
        # 優先順位は index.md > README.md > SKILL.md
        file_basename=$(basename "$file")
        file_basename_lower=$(echo "$file_basename" | tr '[:upper:]' '[:lower:]')
        file_dirname=$(dirname "$file")
        docx_download_name_from_title=false

        if [[ "$file_basename_lower" == "index.md" ]]; then
            docx_download_name_from_title=true
        elif [[ "$file_basename_lower" == "readme.md" || "$file_basename_lower" == "skill.md" ]]; then
            # 同じディレクトリに上位候補が存在するかチェック (大文字小文字を無視)
            index_md_exists=false
            readme_md_exists=false
            if [ -d "$file_dirname" ]; then
                for potential_index in "$file_dirname"/*; do
                    if [[ -f "$potential_index" ]]; then
                        potential_basename=$(basename "$potential_index" | tr '[:upper:]' '[:lower:]')
                        if [[ "$potential_basename" == "index.md" ]]; then
                            index_md_exists=true
                        elif [[ "$potential_basename" == "readme.md" ]]; then
                            readme_md_exists=true
                        fi
                    fi
                done
            fi

            # README.md は index.md がない場合、SKILL.md は index.md / README.md がない場合のみ索引にする
            if [[ "$file_basename_lower" == "readme.md" && "$index_md_exists" == "false" ]] ||
               [[ "$file_basename_lower" == "skill.md" && "$index_md_exists" == "false" && "$readme_md_exists" == "false" ]]; then
                publish_file="${publish_file%/*}/index.md"
                publish_file_self_contain="${publish_file_self_contain%/*}/index.md"
                publish_file_docx="${publish_file_docx%/*}/index.md"
                docx_download_name_from_title=true
            fi
        fi

        # \toc の早期検出 (タイムスタンプ スキップ判定で使用)
        _has_toc=false
        if grep -qF '\toc' "$file" 2>/dev/null; then
            _has_toc=true
        fi

        # タイムスタンプ ベース スキップ判定 (\toc を含まないファイルのみ)
        _skip_generation=false
        if [[ "$_has_toc" == "false" ]]; then
            _all_outputs_fresh=true
            for _chk_lang in ${lang}; do
                for _chk_suffix in "${details_suffixes[@]}"; do
                    _chk_out="${workspaceFolder}/${pubRoot}/${_chk_lang}${_chk_suffix}/${publish_file%.*}.html"
                    if [[ ! -f "$_chk_out" ]] || [[ "$file" -nt "$_chk_out" ]]; then
                        _all_outputs_fresh=false
                        break 2
                    fi
                    if [[ "$htmlSelfContainOutput" == "true" ]]; then
                        _chk_out="${workspaceFolder}/${pubRoot}/${_chk_lang}${_chk_suffix}/${publish_file_self_contain%.*}.html"
                        if [[ ! -f "$_chk_out" ]] || [[ "$file" -nt "$_chk_out" ]]; then
                            _all_outputs_fresh=false
                            break 2
                        fi
                    fi
                    if [[ "$docxOutput" == "true" ]]; then
                        _chk_out="${workspaceFolder}/${pubRoot}/${_chk_lang}${_chk_suffix}/${publish_file_docx%.*}.docx"
                        if [[ ! -f "$_chk_out" ]] || [[ "$file" -nt "$_chk_out" ]]; then
                            _all_outputs_fresh=false
                            break 2
                        fi
                    fi
                done
            done
            if [[ "$_all_outputs_fresh" == "true" ]]; then
                _skip_generation=true
            fi
        fi

        if [[ "$_skip_generation" == "true" ]]; then
            echo "  (up-to-date)"
            progress_log "出力が最新のためスキップしました file=${file#${workspaceFolder}/}"
        else

        # path to css
        nest_count=$(echo "$publish_file" | grep -o '/' | wc -l)
        up_dir=""
        for ((i=2; i<=nest_count; i++)); do
            up_dir+="../"
        done

        # ナビゲーション リンク メタデータの構築
        navigation_link_metadata_args=()
        if [[ "$htmlNavigationLinkEnable" == "true" ]]; then
            navigation_link_metadata_args=(--metadata "homelink=${up_dir}index.html")
        fi

        # 検索・ナビゲーション メタデータの構築
        # publish_file は ".md" 拡張子のままなので ".html" に変換してから html/ を除去する
        search_metadata_args=()
        if [[ "$htmlSearchEnable" == "true" || "$htmlNavTreeEnable" == "true" ]]; then
            _search_current="${publish_file%.*}.html"
            _search_current="${_search_current#html/}"
            search_metadata_args=(
                --metadata "search-enable=true"
                --metadata "search-base=${up_dir}"
                --metadata "search-current=${_search_current}"
            )
        fi

        # DOCX ダウンロードリンク メタデータの構築
        # docx 出力が有効な場合のみ、対応する docx への相対 URL とアイコンの URL を HTML に埋め込む
        # (self-contain HTML には渡さない。実在確認はテンプレート内の JavaScript が行う)
        docx_link_metadata_args=()
        if [[ "$docxOutput" == "true" ]]; then
            docx_link_metadata_args=(
                --metadata "docx-url=${up_dir}../${publish_file_docx%.*}.docx"
                --metadata "docx-icon=${up_dir}docsfw-word-icon.svg"
            )
        fi

        # 概要版/詳細版 切替リンク メタデータの構築
        # details=both の場合のみ渡す (それ以外は切替先ツリーが存在しない)。
        # 切替先 URL はバリアントコピー最適化と両立させるためビルド時に確定せず、
        # テンプレート内の JavaScript が実行時の URL から算出する (実在確認も JavaScript が行う)
        details_link_metadata_args=()
        if [[ "$details" == "both" ]]; then
            details_link_metadata_args=(
                --metadata "details-switch-root=${up_dir}../../"
                --metadata "details-icon-base=${up_dir}"
            )
        fi

        if [[ "$autoSetDate" == "true" ]]; then
            # get_file_date.sh "$file" を実行し、結果を DOCUMENT_DATE に設定
            progress_log "文書日付の取得を開始しました file=${file#${workspaceFolder}/}"
            export DOCUMENT_DATE=$(sh ${SCRIPT_DIR}/get_file_date.sh "$file")
            progress_log "文書日付の取得を終了しました file=${file#${workspaceFolder}/}"
        else
            export -n DOCUMENT_DATE
        fi

        if [[ "$autoSetAuthor" == "true" ]]; then
            # get_file_author.sh "$file" を実行し、結果を DOCUMENT_AUTHOR に設定
            progress_log "文書著者の取得を開始しました file=${file#${workspaceFolder}/}"
            export DOCUMENT_AUTHOR=$(sh ${SCRIPT_DIR}/get_file_author.sh "$file")
            progress_log "文書著者の取得を終了しました file=${file#${workspaceFolder}/}"
        else
            export -n DOCUMENT_AUTHOR
        fi

        # オリジナルのソース ファイル名を環境変数に保持
        export SOURCE_FILE="$file"

        # Markdown から参照されているリソース ファイルを html 出力ディレクトリにコピー
        # (pandoc の --resource-path は html 出力ディレクトリを参照するため、
        #  files[] に含まれない画像 (images/ サブディレクトリ等) を事前にコピーしておく)
        _pm_src_dir=$(dirname "$file")
        while IFS= read -r img_ref; do
            img_path="${img_ref%%[?#]*}"
            [ -z "$img_path" ] && continue
            src_img="${_pm_src_dir}/${img_path}"
            if [ -f "$src_img" ]; then
                for langElement in ${lang}; do
                    for details_suffix in "${details_suffixes[@]}"; do
                        dest_img="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_dir}/${img_path}"
                        mkdir -p "$(dirname "$dest_img")"
                        copy_or_filter_svg "$src_img" "$dest_img"
                    done
                done
            fi
        done < <(grep -oE '!\[[^]]*\]\([^)]+\)' "$file" 2>/dev/null \
            | sed 's/.*(\(.*\))/\1/' \
            | grep -Ev '^https?://')

        # バリアント不変性の検出
        _has_lang_tags=false
        _has_details_tags=false
        if grep -qE '^<!--details:(-->)?$|^(<!--)?:details-->$' "$file" 2>/dev/null; then
            _has_details_tags=true
        fi
        if grep -E '^<!--[a-z]+:(-->)?$|^(<!--)?:[a-z]+-->$' "$file" 2>/dev/null \
           | grep -qvF 'details'; then
            _has_lang_tags=true
        fi
        _lang_invariant=false
        _details_invariant=false
        [[ "$_has_lang_tags" == "false" && "$_has_toc" == "false" ]] && _lang_invariant=true
        [[ "$_has_details_tags" == "false" ]] && _details_invariant=true

        declare -A _generated_for_lang=()
        declare -A _generated_for_details=()
        _first_generated_lang=""
        _first_generated_suffix=""

        # ディレクトリ階層の publocal / pubpart / pubchild から
        # フロントマター デフォルト値 (--metadata-file 群) を構築する。
        # 内容は lang / details に依存しないため 1 回だけ構築する。
        build_defaults_metadata_args "$file"

        for details_suffix in "${details_suffixes[@]}"; do
            # details_suffix から details 値を決定
            if [[ "$details_suffix" == "-details" ]]; then
                current_details="true"
            else
                current_details="false"
            fi

            for langElement in ${lang}; do
                # コピーで済むかどうかの判定
                _need_generate=true
                _copy_source_lang=""
                _copy_source_suffix=""
                if [[ "$_lang_invariant" == "true" && "$_details_invariant" == "true" ]]; then
                    if [[ -n "$_first_generated_lang" ]]; then
                        _need_generate=false
                        _copy_source_lang="$_first_generated_lang"
                        _copy_source_suffix="$_first_generated_suffix"
                    fi
                elif [[ "$_lang_invariant" == "true" && "$_details_invariant" == "false" ]]; then
                    if [[ -v _generated_for_details[${details_suffix:-__normal__}] ]]; then
                        _need_generate=false
                        _copy_source_lang="${_generated_for_details[${details_suffix:-__normal__}]}"
                        _copy_source_suffix="$details_suffix"
                    fi
                elif [[ "$_lang_invariant" == "false" && "$_details_invariant" == "true" ]]; then
                    if [[ -v _generated_for_lang[$langElement] ]]; then
                        _need_generate=false
                        _copy_source_lang="$langElement"
                        _copy_source_suffix="${_generated_for_lang[$langElement]}"
                    fi
                fi

                if [[ "$_need_generate" == "true" ]]; then
                # Markdown の最初にコメントがあると、--shift-heading-level-by=-1 を使った title の抽出に失敗するので
                # 独自に抽出を行う。コードのリファクタリングがなされておらず冗長だが動作はする。
                replaced_md=$(replace-tag.sh --lang=${langElement} --details=${current_details} < "${file}")
                md_title=$(echo "${replaced_md}" \
                    | perl -0777 -pe 's/<!--.*?-->//gs' \
                    | sed -n '/^#/p' \
                    | head -n 1 \
                    | sed 's/^# *//' \
                    | tr -d '\r')
                docx_download_name_metadata_args=()
                if [[ "$docx_download_name_from_title" == "true" && -n "$md_title" ]]; then
                    docx_download_name_encoded=$(printf "%s" "$md_title" | encode_docx_download_name_from_title)
                    docx_download_name_metadata_args=(--metadata "docx-download-name-encoded=${docx_download_name_encoded}")
                fi
                # コードフェンス外のレベル 1 見出し (ドキュメント タイトル) のみを本文から取り除く。
                # sed '/^# /d' はコードフェンス内の行頭 # まで消すため、フェンスを追跡する awk を用いる
                # (フェンス判定の基準は replace-tag.sh に合わせている)。
                md_body=$(echo "${replaced_md}" | awk '
                    /^```/ { in_code = !in_code }
                    !in_code && /^# / { next }
                    { print }
                ')

                # ナビゲーション ツリー / \toc 用の簡潔タイトルを解決する
                # short-title 系フィールドが指定されていない場合は空文字になる
                nav_title=$(extract_short_title "${file}" "${langElement}" "${current_details}")

                export DOCUMENT_LANG=$langElement
                export DOCUMENT_DETAILS=$current_details

                echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                # Markdown の最初にコメントがあると、レベル 1 のタイトルを取り除くことができない。md_body 生成時に awk でコードフェンス外のレベル 1 見出しを取り除いている。
                _pm_pandoc_stderr=$(mktemp)
                set_job_phase "HTML 生成 lang=${langElement} details=${current_details}"
                progress_log "HTML 生成を開始しました file=${file#${workspaceFolder}/} lang=${langElement} details=${current_details}"
                # nav_title が指定されている場合、docsfw-nav-title メタデータを付与する
                _nav_title_option=()
                [[ -n "$nav_title" ]] && _nav_title_option=(--metadata "docsfw-nav-title=${nav_title}")
                build_doxygen_link_metadata_args "$file" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" "${up_dir}docsfw-doxygen-icon.svg"
                build_git_link_metadata_args "$file" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" "$up_dir"
                echo "${md_body}" | \
                    "$PANDOC" -s "${html_toc_args[@]}" --shift-heading-level-by=-1 -N --eol=lf --metadata title="$md_title" --metadata "lang=${langElement}" "${navigation_link_metadata_args[@]}" "${search_metadata_args[@]}" "${docx_link_metadata_args[@]}" "${docx_download_name_metadata_args[@]}" "${details_link_metadata_args[@]}" "${doxygen_link_metadata_args[@]}" "${git_link_metadata_args[@]}" -f markdown+hard_line_breaks${markExtension}${mathExtension} \
                        "${defaults_metadata_file_args[@]}" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/admonition.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                        "${pandoc_crossref_args[@]}" \
                        "${math_jax_args[@]}" \
                        --template="${htmlTemplate}" -c "${up_dir}html-style.css" \
                        --metadata "mermaid-js=${up_dir}mermaid.min.js" \
                        --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                        "${_nav_title_option[@]}" \
                        --wrap=none -t html -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" \
                        2>"$_pm_pandoc_stderr"
                progress_log "HTML 生成を終了しました file=${file#${workspaceFolder}/} lang=${langElement} details=${current_details}"
                if [[ -s "$_pm_pandoc_stderr" ]]; then
                    printf "\e[33m"
                    cat "$_pm_pandoc_stderr"
                    printf "\e[0m"
                fi
                rm -f "$_pm_pandoc_stderr"
                set_html_lang_attributes "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" "$langElement"
                if [[ "$htmlSelfContainOutput" == "true" ]]; then
                    build_doxygen_link_metadata_args "$file" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/docsfw-doxygen-icon.svg"
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                    # Markdown の最初にコメントがあると、レベル 1 のタイトルを取り除くことができない。md_body 生成時に awk でコードフェンス外のレベル 1 見出しを取り除いている。
                    _pm_pandoc_stderr=$(mktemp)
                    echo "${md_body}" | \
                        "$PANDOC" -s "${html_toc_args[@]}" --shift-heading-level-by=-1 -N --eol=lf --metadata title="$md_title" --metadata "lang=${langElement}" "${navigation_link_metadata_args[@]}" "${search_metadata_args[@]}" "${doxygen_link_metadata_args[@]}" -f markdown+hard_line_breaks${markExtension}${mathExtension} \
                            "${defaults_metadata_file_args[@]}" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/admonition.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                            "${pandoc_crossref_args[@]}" \
                            "${math_jax_args[@]}" \
                            --template="${htmlSelfContainTemplate}" -c "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/html-style.css" \
                            --metadata "mermaid-js=${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/mermaid.min.js" \
                            --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                            "${_nav_title_option[@]}" \
                            --wrap=none -t html --embed-resources --standalone -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html" \
                            2>"$_pm_pandoc_stderr"
                    if [[ -s "$_pm_pandoc_stderr" ]]; then
                        printf "\e[33m"
                        cat "$_pm_pandoc_stderr"
                        printf "\e[0m"
                    fi
                    rm -f "$_pm_pandoc_stderr"
                    set_html_lang_attributes "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html" "$langElement"
                fi
                if [[ "$docxOutput" == "true" ]]; then
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                    # Markdown の最初にコメントがあると、レベル 1 のタイトルを取り除くことができない。md_body 生成時に awk でコードフェンス外のレベル 1 見出しを取り除いている。
                    _pm_pandoc_stderr=$(mktemp)
                    set_job_phase "DOCX 生成 lang=${langElement} details=${current_details}"
                    progress_log "DOCX 生成を開始しました file=${file#${workspaceFolder}/} lang=${langElement} details=${current_details}"
                    echo "${md_body}" | \
                        "$PANDOC" -s --shift-heading-level-by=-1 --metadata shift-heading-level-by=-1 --eol=lf --metadata title="$md_title" -f markdown+hard_line_breaks${markExtension}${mathExtension} \
                            "${defaults_metadata_file_args[@]}" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/horizontal-rule.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/admonition.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/toc-pagebreak.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/page-break-before-heading.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/separate-consecutive-blockquotes.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/replace-table-br.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/replace-table-br.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-docx.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/inline-code-style.lua" \
                            "${pandoc_crossref_args[@]}" \
                            --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                            --wrap=none -t docx --reference-doc="${docxTemplate}" -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx" \
                            2>"$_pm_pandoc_stderr"
                    progress_log "DOCX 生成を終了しました file=${file#${workspaceFolder}/} lang=${langElement} details=${current_details}"
                    if [[ -s "$_pm_pandoc_stderr" ]]; then
                        printf "\e[33m"
                        cat "$_pm_pandoc_stderr"
                        printf "\e[0m"
                    fi
                    rm -f "$_pm_pandoc_stderr"
                    python3 "${SCRIPT_DIR}/pandoc-filters/fit-docx-images-to-page.py" \
                        "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx" \
                        >/dev/null 2>/dev/null || true
                    python3 "${SCRIPT_DIR}/pandoc-filters/inject-toc-placeholder.py" \
                        "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx" \
                        2>/dev/null || true
                fi
                # 生成済みとして記録
                if [[ -z "$_first_generated_lang" ]]; then
                    _first_generated_lang="$langElement"
                    _first_generated_suffix="$details_suffix"
                fi
                _generated_for_lang["$langElement"]="$details_suffix"
                _generated_for_details["${details_suffix:-__normal__}"]="$langElement"
                else
                echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html (copy)"
                cp -p "${workspaceFolder}/${pubRoot}/${_copy_source_lang}${_copy_source_suffix}/${publish_file%.*}.html" \
                      "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" \
                    || echo "Warning: Failed to copy HTML file: ${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                set_html_lang_attributes "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" "$langElement"
                if [[ "$htmlSelfContainOutput" == "true" ]]; then
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html (copy)"
                    cp -p "${workspaceFolder}/${pubRoot}/${_copy_source_lang}${_copy_source_suffix}/${publish_file_self_contain%.*}.html" \
                          "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html" \
                        || echo "Warning: Failed to copy HTML file: ${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                    set_html_lang_attributes "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html" "$langElement"
                fi
                if [[ "$docxOutput" == "true" ]]; then
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx (copy)"
                    cp -p "${workspaceFolder}/${pubRoot}/${_copy_source_lang}${_copy_source_suffix}/${publish_file_docx%.*}.docx" \
                          "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx" \
                        || echo "Warning: Failed to copy DOCX file: ${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                fi
                fi
            done
        done
        fi
        } >"$_pm_tmpout" 2>&1
        _pm_exit=$?
        progress_log "Markdown 処理を終了しました file=${file#${workspaceFolder}/} exit=${_pm_exit}"
        # mkdir をアトミック ロックとして使い、バッファリングした出力を表示する
        # (mkdir は Linux/MSYS2/Windows いずれでもアトミック操作)
        while ! mkdir "${OUTPUT_LOCK}.lck" 2>/dev/null; do sleep 0.01; done
        cat "$_pm_tmpout"
        rmdir "${OUTPUT_LOCK}.lck" 2>/dev/null
        rm -f "$_pm_tmpout"
        exit $_pm_exit
        ) &
        _file_pids+=($!)
        _file_names+=("$file")
        _file_status_files+=("$_pm_statusfile")
        (( _running_count++ ))
    fi
done

#-------------------------------------------------------------------

#-------------------------------------------------------------------
# 全ファイル ジョブの完了待機
#-------------------------------------------------------------------

_overall_exit=0
# 無進捗ウォッチドッグ: ジョブのハートビート ファイルが FILE_PROCESS_TIMEOUT_SEC 秒間
# 更新されない場合のみハング (デッドロックなど) とみなして kill する。
# 図の多いファイルは正常でも長時間かかるため、処理時間の絶対値では kill しない。
# FILE_PROCESS_TIMEOUT_SEC を未指定または 0 にすると、無進捗ウォッチドッグを無効にする。
# 長時間の PlantUML や Pandoc 変換は正当な処理であり、通常の発行では時間だけで停止しない。
# 正の整数を指定した場合だけ、ハートビートが更新されないジョブを停止する。
_file_job_timeout_sec="${FILE_PROCESS_TIMEOUT_SEC:-0}"
if ! [[ "$_file_job_timeout_sec" =~ ^[0-9]+$ ]]; then
    echo >&2 "Error: FILE_PROCESS_TIMEOUT_SEC must be a non-negative integer."
    exit 1
fi

for _i in "${!_file_pids[@]}"; do
    _cur_pid="${_file_pids[$_i]}"
    _cur_statusfile="${_file_status_files[$_i]}"
    _cur_infofile="${_cur_statusfile}.info"
    _cur_heartbeat="${_cur_statusfile}.hb"
    _cur_phase="${_cur_statusfile}.phase"

    # プロセスが実行中の場合のみポーリングで無進捗監視を適用する。
    # EXIT trap がステータスファイルを書き込んだらサブシェル完了とみなす。
    # kill -0 はゾンビプロセスにも 0 を返す場合があるため、
    # ステータスファイルの有無を主判定条件とし、ゾンビはポーリングを抜けて wait でリープする。
    if (( _file_job_timeout_sec > 0 )) && kill -0 "$_cur_pid" 2>/dev/null; then
        _poll_start=$SECONDS
        _last_heartbeat_sig=""
        while [[ ! -s "$_cur_statusfile" ]] && kill -0 "$_cur_pid" 2>/dev/null; do
            # ハートビートの mtime とサイズが変化していたら進捗ありとみなしタイマーをリセット
            _cur_heartbeat_sig=$(stat -c '%Y:%s' "$_cur_heartbeat" 2>/dev/null || echo "")
            if [[ "$_cur_heartbeat_sig" != "$_last_heartbeat_sig" ]]; then
                _last_heartbeat_sig="$_cur_heartbeat_sig"
                _poll_start=$SECONDS
            fi
            if (( SECONDS - _poll_start >= _file_job_timeout_sec )); then
                echo >&2 "Warning: No progress for ${_file_job_timeout_sec}s ${_file_names[$_i]}, killing."
                if [[ -s "$_cur_phase" ]]; then
                    echo >&2 "Warning: Last phase: $(cat "$_cur_phase")"
                fi
                if is_windows_host && command -v taskkill.exe >/dev/null 2>&1; then
                    # 先に kill (SIGTERM) でサブシェルの bash を終了させると native の子
                    # (pandoc.exe、powershell.exe など) が孤児化し、taskkill /T がツリーを
                    # たどれなくなる。孤児は継承したパイプ ハンドルを保持し続けるため、
                    # スクリプト終了後も呼び出し元に制御が戻らない。
                    # プロセス ツリーが健在なうちに taskkill /T /F で子孫ごと強制終了する。
                    MSYS2_ARG_CONV_EXCL='*' taskkill.exe /PID "$(win_pid_of "$_cur_pid")" /T /F >/dev/null 2>&1 || true
                fi
                kill "$_cur_pid" 2>/dev/null
                break
            fi
            sleep 1
        done
    fi

    wait "$_cur_pid" 2>/dev/null
    # bash の cleanup_dead_jobs で PID がすでに回収されていても、
    # サブシェル EXIT trap が書き込んだステータスを参照する
    _pm_job_exit=$(cat "$_cur_statusfile" 2>/dev/null || echo "127")
    if [[ "$_pm_job_exit" == "127" && ! -s "$_cur_statusfile" ]]; then
        echo >&2 "Error: Process exited without a result status: ${_file_names[$_i]}"
        if [[ -s "$_cur_infofile" ]]; then
            sed 's/^/Error: Job /' "$_cur_infofile" >&2
        fi
    fi
    rm -f "$_cur_statusfile" "$_cur_infofile" "$_cur_heartbeat" "$_cur_phase"
    if [[ "${_pm_job_exit}" -ne 0 ]]; then
        echo >&2 "Error: Failed to process ${_file_names[$_i]}"
        _overall_exit=1
    fi
done

if [[ $_overall_exit -ne 0 ]]; then
    exit 1
fi

#-------------------------------------------------------------------
# 検索インデックス・ナビゲーション ツリーの後処理生成
# (全 HTML ファイルの生成完了後にバリアントごとに 1 回実行)
#-------------------------------------------------------------------

for langElement in ${lang}; do
    for details_suffix in "${details_suffixes[@]}"; do
        _html_root="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html"
        if [[ ! -d "${_html_root}" ]]; then
            continue
        fi
        if [[ "$htmlNavTreeEnable" == "true" ]]; then
            echo "Generating nav tree: ${pubRoot}/${langElement}${details_suffix}/html/"
            # 第 2 引数にソース mdRoot を渡す。各ディレクトリの publocal.yaml の order を
            # 参照して並び順を上書きするために使う (未指定時は従来の名前順)。
            # 第 3 引数以降に mergeSubfolderDocs の "alias=実ソース ディレクトリ" を渡し、
            # マージされたサブフォルダー配下の publocal.yaml も解決できるようにする。
            _nav_merge_map=()
            if [[ -n "$mergeSubfolderDocs" ]]; then
                for entry in "${subfolder_mdroot_paths[@]}"; do
                    parse_subfolder_mdroot_entry "$entry"
                    _nav_merge_map+=("${subfolder_alias}=${subfolder_mdroot}")
                done
            fi
            python3 "${htmlNavTreeScript}" "${_html_root}" "${PUB_MARKDOWN_MAIN_MDROOT}" "${_nav_merge_map[@]}"
        fi
        if [[ "$htmlSearchEnable" == "true" ]]; then
            echo "Generating search index: ${pubRoot}/${langElement}${details_suffix}/html/"
            node "${htmlBuildSearchScript}" "${_html_root}"
        fi
    done
done

#-------------------------------------------------------------------

echo "*** pub_markdown_core end   $(date -Is)"

#-------------------------------------------------------------------

exit 0
