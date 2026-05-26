#!/bin/bash
#set -x

SCRIPT_DIR=$(cd $(dirname "$0"); pwd)
HOME_DIR=$(cd $SCRIPT_DIR; cd ..; pwd) # bin フォルダの上位が home
PATH=$SCRIPT_DIR:$PATH # 優先的に bin フォルダを選択させる
cd $HOME_DIR

# 並列ジョブ内では stdout / stderr を一時ファイルへ集約するため、
# 進捗ログだけは元の stderr を保持した FD 3 へ直接出力する。
exec 3>&2

# PUB_MARKDOWN_PROGRESS_LOG=1 のときだけ、長時間処理の進行状況を stderr に出力する。
progress_log() {
    [[ "${PUB_MARKDOWN_PROGRESS_LOG:-0}" == "1" ]] || return 0
    printf '[pub_markdown %s] %s\n' "$(date '+%H:%M:%S')" "$*" >&3
}

is_skip() {
    local file="$1"
    local line
    local key
    local value
    local skip_flag_found=false

    [[ "$file" == *.md ]] || return 1
    [[ -f "$file" ]] || return 1

    IFS= read -r line < "$file" || return 1
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*---[[:space:]]*$ ]] || return 1

    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        if [[ "$line" =~ ^[[:space:]]*---[[:space:]]*$ ]]; then
            [[ "$skip_flag_found" == "true" ]]
            return
        fi

        if [[ "$line" == *:* ]]; then
            key="${line%%:*}"
            value="${line#*:}"
            key="${key#"${key%%[![:space:]]*}"}"
            key="${key%"${key##*[![:space:]]}"}"
            value="${value%%#*}"
            value="${value#"${value%%[![:space:]]*}"}"
            value="${value%"${value##*[![:space:]]}"}"
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"
            value=$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')

            if [[ "$key" == "pub_markdown.skip" && "$value" == "true" ]]; then
                skip_flag_found=true
            fi
        fi
    done < <(tail -n +2 "$file")

    return 1
}

# 終了時に実行する共通クリーンアップ処理
cleanup_resources() {
    if [[ "${CLEANUP_DONE:-0}" == "1" ]]; then
        return 0
    fi
    CLEANUP_DONE=1

    # 共有ブラウザサーバーを停止
    if [[ -n "${BROWSER_SERVER_PID:-}" ]]; then
        kill "$BROWSER_SERVER_PID" 2>/dev/null
        wait "$BROWSER_SERVER_PID" 2>/dev/null
    fi
    if [[ -n "${PUB_MARKDOWN_BROWSER_WS_FILE:-}" ]]; then
        rm -f "$PUB_MARKDOWN_BROWSER_WS_FILE" 2>/dev/null
    fi

    # そのほかのバックグラウンドジョブを停止
    local _bg_jobs
    _bg_jobs=$(jobs -rp 2>/dev/null)
    [[ -n "$_bg_jobs" ]] && kill $_bg_jobs 2>/dev/null
    wait 2>/dev/null

    if [[ -n "${OUTPUT_LOCK:-}" ]]; then
        rm -rf "${OUTPUT_LOCK}.lck" 2>/dev/null
    fi
    if [[ -n "${_PM_STATUS_DIR:-}" ]]; then
        rm -rf "${_PM_STATUS_DIR}" 2>/dev/null
    fi
    if [[ -n "${PUB_MARKDOWN_TOC_OUTPUT_CACHE_DIR:-}" ]]; then
        rm -rf "$PUB_MARKDOWN_TOC_OUTPUT_CACHE_DIR" 2>/dev/null
    fi
}

# Ctrl+C (SIGINT) や SIGTERM を捕まえて実行する処理
cleanup_on_signal() {
    #echo >&2 "スクリプトが中断されました。"
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
# マルチプラットフォーム対応
#-------------------------------------------------------------------

LINUX=0
WSL=0

if [[ "$(uname -s)" == "Linux" ]]; then
    LINUX=1
    # WSL環境かどうかを判定
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
        # WSL2 から Edge (127.0.0.1でLISTEN) にアクセスできない。
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
# PANDOC-CROSSREF に "-F {pandoc-crossref のパス}" を設定
if [ -x "${SCRIPT_DIR}/pandoc-crossref" ] || [ -x "${SCRIPT_DIR}/pandoc-crossref.exe" ]; then
    PANDOC_CROSSREF="-F ${SCRIPT_DIR}/pandoc-crossref"
elif command -v pandoc-crossref >/dev/null 2>&1 || command -v pandoc-crossref.exe >/dev/null 2>&1; then
    PANDOC_CROSSREF="-F pandoc-crossref"
else
    PANDOC_CROSSREF=""
fi

# ${SCRIPT_DIR}/node_modules/.bin が存在しない場合はセットアップを試みる
# package-lock.json を利用して固定バージョンでセットアップするため、npm install ではなく npm ci
if [ ! -d "${SCRIPT_DIR}/node_modules/.bin" ]; then
    echo "Installing node.js modules..."
    (cd "${SCRIPT_DIR}" && npm ci)
    #echo "Error: ${SCRIPT_DIR}/node_modules/.bin not found. Please 'npm ci' in the ${SCRIPT_DIR} directory."
    #exit 1
fi

# node.js の警告を非表示にする
export NODE_NO_WARNINGS=1

#-------------------------------------------------------------------
# 共有ブラウザインスタンスの起動
#-------------------------------------------------------------------

# rsvg-convert.js や mmdc-reuse.js が共有ブラウザに接続するための
# WebSocket エンドポイントファイルを設定
export PUB_MARKDOWN_BROWSER_WS_FILE="/tmp/pub_markdown_browser_ws_$$"
BROWSER_SERVER_PID=""
export PUB_MARKDOWN_MAIN_MDROOT="${workspaceFolder:-}/docs"
export PUB_MARKDOWN_TOC_OUTPUT_CACHE_DIR="$(mktemp -d)"

# 共有ブラウザサーバーをバックグラウンドで起動
# NOTE: browser-server.js は Puppeteer のデフォルトブラウザ検出を使用する。
#       prepare_puppeteer_env.sh (chrome-wrapper.sh) はここでは適用しない。
#       chrome-wrapper.sh の WebSocket 競合回避はファイルベースの待機で代替する。
#       フォールバック時 (rsvg-convert 単体実行) は従来通り chrome-wrapper.sh が使われる。
node "${SCRIPT_DIR}/browser-server.js" "$PUB_MARKDOWN_BROWSER_WS_FILE" &
BROWSER_SERVER_PID=$!
progress_log "共有ブラウザ起動待機を開始しました pid=${BROWSER_SERVER_PID}"

# WebSocket エンドポイントファイルが作成されるまで待機 (最大 30 秒)
for _i in $(seq 1 300); do
    if [[ -f "$PUB_MARKDOWN_BROWSER_WS_FILE" ]]; then
        break
    fi
    sleep 0.1
done

if [[ ! -f "$PUB_MARKDOWN_BROWSER_WS_FILE" ]]; then
    echo "Warning: Shared browser server failed to start. Falling back to per-process browser instances."
    BROWSER_SERVER_PID=""
    export -n PUB_MARKDOWN_BROWSER_WS_FILE
    progress_log "共有ブラウザ起動待機を終了しました result=fallback"
else
    progress_log "共有ブラウザ起動待機を終了しました result=ready"
fi

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

# 並列出力の排他制御用ロックベースパス
# flock (Linux 専用) の代わりに mkdir アトミックロックを使用することで
# MSYS2 (Windows) 環境でも動作する
OUTPUT_LOCK=$(mktemp -u)
_PM_STATUS_DIR=$(mktemp -d)

# 実行中のバックグラウンドジョブ数が MAX_PARALLEL に達している場合、
# 1つ完了するまで待機する関数
wait_for_parallel_slot() {
    while (( $(jobs -rp 2>/dev/null | wc -l) >= MAX_PARALLEL )); do
        # 一部環境では wait -n 実行後に PID を個別 wait できず
        # "not a child of this shell" になるため、ここでは状態監視のみにする。
        sleep 0.1
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
        # 相対パスの場合はワークスペースフォルダからの絶対パスを作成
        local workspace_resolved_path="$(realpath "$workspaceFolder/$input_path" 2>/dev/null)"
        if [[ -e "$workspace_resolved_path" ]]; then
            resolved_path="$workspace_resolved_path"
        else
            # ワークスペースフォルダに存在しない場合は pub_markdown のホームディレクトリを使用
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

# 定義ファイルのデフォルトパス
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
if [[ "$htmlTocEnable" == "true" ]]; then
    htmlTocOption="--toc --toc-depth=${htmlTocDepth}"
fi

# 設定ファイルに mathLatexEnable が指定されなかった場合の値を true にする
if [[ "$mathLatexEnable" == "" ]]; then
    mathLatexEnable="true"
fi

# 数式サポート (LaTeX 書式) 関連オプションの組み立て
# mathExtension: Pandoc 入力拡張。\[...\] \(...\) 書式の LaTeX 数式を認識させる (HTML/docx 共通)
# mathJaxOption: MathJax によるブラウザレンダリングを指定する Pandoc オプション (HTML のみ)
if [[ "$mathLatexEnable" == "true" ]]; then
    mathExtension="+tex_math_single_backslash"
    mathJaxOption="--mathjax"
fi

# 設定ファイルに autoSetDate が指定されなかった場合の値を true にする
if [[ "$autoSetDate" == "" ]]; then
    autoSetDate="true"
fi

# 設定ファイルに autoSetAuthor が指定されなかった場合の値を true にする
if [[ "$autoSetAuthor" == "" ]]; then
    autoSetAuthor="true"
fi

# 設定ファイルに htmlNavigationLinkEnable (ナビゲーションリンク) が指定されなかった場合の値を true にする
if [[ "$htmlNavigationLinkEnable" == "" ]]; then
    htmlNavigationLinkEnable="true"
fi

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
# 追加ドキュメントサブフォルダー機能
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

# 追加ドキュメントサブフォルダー設定 1 件を解析する関数
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
# 形式: "alias|path|mdRoot絶対パス"
parse_subfolder_mdroot_entry() {
    local entry="$1"
    local rest

    subfolder_alias="${entry%%|*}"
    rest="${entry#*|}"
    subfolder_path="${rest%%|*}"
    subfolder_mdroot="${rest#*|}"
}

# 設定ファイルで指定された追加ドキュメントサブフォルダーのパスリストを設定する関数
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

# mergeSubfolderDocs で指定された追加ドキュメントサブフォルダーを検出する関数
# 戻り値: グローバル配列 subfolder_mdroot_paths に "alias|path|ドキュメントルート絶対パス" を設定
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

    # 追加ドキュメントサブフォルダーのパスかチェック
    for entry in "${subfolder_mdroot_paths[@]}"; do
        parse_subfolder_mdroot_entry "$entry"

        if [[ "$real_path" == "${subfolder_mdroot}/"* ]]; then
            # 追加ドキュメントサブフォルダー配下のファイル
            local relative="${real_path#${subfolder_mdroot}/}"
            echo "${workspaceFolder}/${mdRoot}/${subfolder_alias}/${relative}"
            return 0
        elif [[ "$real_path" == "${subfolder_mdroot}" ]]; then
            # 追加ドキュメントサブフォルダー自体
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

    # 追加ドキュメントサブフォルダー名で始まるかチェック
    for entry in "${subfolder_mdroot_paths[@]}"; do
        parse_subfolder_mdroot_entry "$entry"

        if [[ "$relative" == "${subfolder_alias}/"* ]]; then
            # 追加ドキュメントサブフォルダーへのパスに変換
            local subfolder_relative="${relative#${subfolder_alias}/}"
            echo "${subfolder_mdroot}/${subfolder_relative}"
            return 0
        elif [[ "$relative" == "${subfolder_alias}" ]]; then
            # 追加ドキュメントサブフォルダー自体
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

# relativeFile のパス検証 (追加ドキュメントサブフォルダー対応)
if [[ -n $relativeFile ]]; then
    path_type=""
    resolved_relativeFile="$relativeFile"

    # 1. 追加ドキュメントサブフォルダー実パスのチェック
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
        # 実行モード=フォルダ
        executionMode="folder"

        # $relativeFile がフォルダ名の場合は、そのフォルダを基準とする
        base_dir="${workspaceFolder}/${relativeFile}"

        # 当該フォルダ配下の clean (再帰)
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

        # 単一ファイルの場合は、そのファイルのあるフォルダを基準とする
        base_dir="${workspaceFolder}/$(dirname "$relativeFile")"
    fi
else
    # 実行モード=ワークスペース
    executionMode="workspace"

    base_dir="${workspaceFolder}/${mdRoot}"
    mkdir -p "${workspaceFolder}/${pubRoot}"

    # 出力フォルダの clean (対象言語に絞る)
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
# 引数: $1=元ファイルパス, $2=コピー先ファイルパス
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
        mapfile -d '' -t files_raw_initial < <(
            find -L "${real_base_dir}" -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.json" \) -print0 | sort -z -u
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
    mapfile -d '' -t files_raw_initial < <(
        find -L "${base_dir}" -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.json" \) -print0 | sort -z -u
    )

    # 追加ドキュメントサブフォルダーのファイルを追加 (mergeSubfolderDocs が指定されている場合)
    if [[ -n "$mergeSubfolderDocs" ]]; then
        for entry in "${subfolder_mdroot_paths[@]}"; do
            parse_subfolder_mdroot_entry "$entry"

            # 追加ドキュメントサブフォルダー配下の対象ファイルを収集
            # -L を付与してシンボリック リンクも対象にする
            mapfile -d '' -t subfolder_files < <(
                find -L "${subfolder_mdroot}" -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.json" \) -print0 | sort -z -u
            )

            # files_raw_initial に追加
            files_raw_initial+=("${subfolder_files[@]}")
        done
    fi
fi

# ── (B) Git 管理下なら NUL 区切りでフィルタ ──
if git -C "$workspaceFolder" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    # 追加ドキュメントサブフォルダー配下のファイルを分離 (gitignore フィルタリング対象外)
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

    # 1) workspaceFolder/ を切り落として相対パス化 (NUL 区切り) - メインファイルのみ
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
                # ソースファイルは常に含める (.gitignore を無視)
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

    # 4) 追加ドキュメントサブフォルダー配下のファイルを追加 (フィルタリング済みとして扱う)
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
    if is_skip "$file"; then
        progress_log "pub_markdown.skip により発行対象から除外しました file=${file#${workspaceFolder}/}"
        continue
    fi
    files_without_skip+=("$file")
done
files=("${files_without_skip[@]}")

echo " done."
progress_log "対象ファイルの収集を終了しました count=${#files[@]}"

#-------------------------------------------------------------------

for file in "${files[@]}"; do
    # 単一 md の発行で、リンク先のファイルがない場合は処理しない
    # → ファイルが存在する場合のみ処理を行う
    if [[ -e "$file" ]]; then
        # 追加ドキュメントサブフォルダー使用時は仮想パスに変換して出力パスを計算
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
    done
done

# ファイルレベルの並列処理用追跡配列
declare -a _file_pids=()
declare -a _file_names=()
declare -a _file_status_files=()
_pm_job_index=0

for file in "${files[@]}"; do
    # 追加ドキュメントサブフォルダー使用時は仮想パスに変換して出力パスを計算
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

        # html (仮想パスベースで出力パスを計算)
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

        # ナビゲーションリンクメタデータの構築
        navigationLinkMetadata=""
        if [[ "$htmlNavigationLinkEnable" == "true" ]]; then
            navigationLinkMetadata="--metadata homelink=${up_dir}index.html"
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

        # オリジナルのソースファイル名を環境変数に保持
        export SOURCE_FILE="$file"

        # NOTE: --code true を取り除き、--language_tabs http --language_tabs shell --omitHeader のように与えるとサンプルコードを出力できる。shell, http, javascript, ruby, python, php, java, go
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

                if [ "$firstLang" == "" ]; then
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                    _pm_pandoc_stderr=$(mktemp)
                    echo "${openapi_md}" | \
                        ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --eol=lf --metadata title="$openapi_md_title" ${navigationLinkMetadata} -f markdown+hard_line_breaks${mathExtension} \
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
                            ${PANDOC_CROSSREF} \
                            ${mathJaxOption} \
                            --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                            --wrap=none -t html -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" \
                            2>"$_pm_pandoc_stderr"
                    if [[ -s "$_pm_pandoc_stderr" ]]; then
                        printf "\e[33m"
                        cat "$_pm_pandoc_stderr"
                        printf "\e[0m"
                    fi
                    rm -f "$_pm_pandoc_stderr"
                    if [[ "$htmlSelfContainOutput" == "true" ]]; then
                        echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                        _pm_pandoc_stderr=$(mktemp)
                        echo "${openapi_md}" | \
                            ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --eol=lf --metadata title="$openapi_md_title" ${navigationLinkMetadata} -f markdown+hard_line_breaks${mathExtension} \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/admonition.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                                ${PANDOC_CROSSREF} \
                                ${mathJaxOption} \
                                --template="${htmlSelfContainTemplate}" -c "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/html-style.css" \
                                --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                                --wrap=none -t html --embed-resources --standalone -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html" \
                                2>"$_pm_pandoc_stderr"
                        if [[ -s "$_pm_pandoc_stderr" ]]; then
                            printf "\e[33m"
                            cat "$_pm_pandoc_stderr"
                            printf "\e[0m"
                        fi
                        rm -f "$_pm_pandoc_stderr"
                    fi
                    if [[ "$docxOutput" == "true" ]]; then
                        echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                        _pm_pandoc_stderr=$(mktemp)
                        echo "${openapi_md}" | \
                            ${PANDOC} -s --shift-heading-level-by=-1 --eol=lf --metadata title="$openapi_md_title" -f markdown+hard_line_breaks${mathExtension} \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/admonition.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/toc-pagebreak.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/page-break-before-heading.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/separate-consecutive-blockquotes.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/replace-table-br.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-docx.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                                ${PANDOC_CROSSREF} \
                                --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                                --wrap=none -t docx --reference-doc="${docxTemplate}" -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx" \
                                2>"$_pm_pandoc_stderr"
                        if [[ -s "$_pm_pandoc_stderr" ]]; then
                            printf "\e[33m"
                            cat "$_pm_pandoc_stderr"
                            printf "\e[0m"
                        fi
                        rm -f "$_pm_pandoc_stderr"
                        python3 "${SCRIPT_DIR}/pandoc-filters/inject-toc-placeholder.py" \
                            "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx" \
                            2>/dev/null || true
                    fi
                    firstLang="${langElement}"
                    firstSuffix="${details_suffix}"
                else
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                    cp -p "${workspaceFolder}/${pubRoot}/${firstLang}${firstSuffix}/${publish_file%.*}.html" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                    if [[ "$htmlSelfContainOutput" == "true" ]]; then
                        echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                        cp -p "${workspaceFolder}/${pubRoot}/${firstLang}${firstSuffix}/${publish_file_self_contain%.*}.html" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                    fi
                    if [[ "$docxOutput" == "true" ]]; then
                        echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                        cp -p "${workspaceFolder}/${pubRoot}/${firstLang}${firstSuffix}/${publish_file_docx%.*}.docx" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
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
        wait_for_parallel_slot
        (
        # サブシェルがどの経路で終了してもステータスを書き込む
        trap 'echo "$?" > "$_pm_statusfile"' EXIT
        # このサブシェル内の出力を一時ファイルにバッファリングし、
        # 完了後に flock でアトミックに標準出力へ書き出す (並列実行時の出力混在を防ぐ)
        _pm_tmpout=$(mktemp)
        {
        # .md ファイルの処理
        progress_log "Markdown 処理を開始しました file=${file#${workspaceFolder}/}"
        echo "Processing Markdown file: ${file#${workspaceFolder}/}"

        # html (仮想パスベースで出力パスを計算)
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

        if [[ "$file_basename_lower" == "readme.md" || "$file_basename_lower" == "skill.md" ]]; then
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
            fi
        fi

        # \toc の早期検出 (タイムスタンプスキップ判定で使用)
        _has_toc=false
        if grep -qF '\toc' "$file" 2>/dev/null; then
            _has_toc=true
        fi

        # タイムスタンプベーススキップ判定 (\toc を含まないファイルのみ)
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

        # ナビゲーションリンクメタデータの構築
        navigationLinkMetadata=""
        if [[ "$htmlNavigationLinkEnable" == "true" ]]; then
            navigationLinkMetadata="--metadata homelink=${up_dir}index.html"
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

        # オリジナルのソースファイル名を環境変数に保持
        export SOURCE_FILE="$file"

        # Markdown から参照されているリソースファイルを html 出力ディレクトリにコピー
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
                        copy_if_different_timestamp "$src_img" "$dest_img"
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
                replaced_md=$(cat "${file}" | replace-tag.sh --lang=${langElement} --details=${current_details})
                md_title=$(echo "${replaced_md}" \
                    | perl -0777 -pe 's/<!--.*?-->//gs' \
                    | sed -n '/^#/p' \
                    | head -n 1 \
                    | sed 's/^# *//' \
                    | tr -d '\r')
                md_body=$(echo "${replaced_md}" | sed '/^# /d')

                export DOCUMENT_LANG=$langElement

                echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                # Markdown の最初にコメントがあると、レベル1のタイトルを取り除くことができない。sed '/^# /d' で取り除く。
                _pm_pandoc_stderr=$(mktemp)
                progress_log "HTML 生成を開始しました file=${file#${workspaceFolder}/} lang=${langElement} details=${current_details}"
                echo "${md_body}" | \
                    ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --eol=lf --metadata title="$md_title" ${navigationLinkMetadata} -f markdown+hard_line_breaks${mathExtension} \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/admonition.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                        ${PANDOC_CROSSREF} \
                        ${mathJaxOption} \
                        --template="${htmlTemplate}" -c "${up_dir}html-style.css" \
                        --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                        --wrap=none -t html -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html" \
                        2>"$_pm_pandoc_stderr"
                progress_log "HTML 生成を終了しました file=${file#${workspaceFolder}/} lang=${langElement} details=${current_details}"
                if [[ -s "$_pm_pandoc_stderr" ]]; then
                    printf "\e[33m"
                    cat "$_pm_pandoc_stderr"
                    printf "\e[0m"
                fi
                rm -f "$_pm_pandoc_stderr"
                if [[ "$htmlSelfContainOutput" == "true" ]]; then
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                    # Markdown の最初にコメントがあると、レベル1のタイトルを取り除くことができない。sed '/^# /d' で取り除く。
                    _pm_pandoc_stderr=$(mktemp)
                    echo "${md_body}" | \
                        ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --eol=lf --metadata title="$md_title" ${navigationLinkMetadata} -f markdown+hard_line_breaks${mathExtension} \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/admonition.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                            ${PANDOC_CROSSREF} \
                            ${mathJaxOption} \
                            --template="${htmlSelfContainTemplate}" -c "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/html-style.css" \
                            --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                            --wrap=none -t html --embed-resources --standalone -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html" \
                            2>"$_pm_pandoc_stderr"
                    if [[ -s "$_pm_pandoc_stderr" ]]; then
                        printf "\e[33m"
                        cat "$_pm_pandoc_stderr"
                        printf "\e[0m"
                    fi
                    rm -f "$_pm_pandoc_stderr"
                fi
                if [[ "$docxOutput" == "true" ]]; then
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                    # Markdown の最初にコメントがあると、レベル1のタイトルを取り除くことができない。sed '/^# /d' で取り除く。
                    _pm_pandoc_stderr=$(mktemp)
                    progress_log "DOCX 生成を開始しました file=${file#${workspaceFolder}/} lang=${langElement} details=${current_details}"
                    echo "${md_body}" | \
                        ${PANDOC} -s --shift-heading-level-by=-1 --metadata shift-heading-level-by=-1 --eol=lf --metadata title="$md_title" -f markdown+hard_line_breaks${mathExtension} \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/admonition.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/toc-pagebreak.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/page-break-before-heading.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/separate-consecutive-blockquotes.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/replace-table-br.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/replace-table-br.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-docx.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                            ${PANDOC_CROSSREF} \
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
                      "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                if [[ "$htmlSelfContainOutput" == "true" ]]; then
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html (copy)"
                    cp -p "${workspaceFolder}/${pubRoot}/${_copy_source_lang}${_copy_source_suffix}/${publish_file_self_contain%.*}.html" \
                          "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                fi
                if [[ "$docxOutput" == "true" ]]; then
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx (copy)"
                    cp -p "${workspaceFolder}/${pubRoot}/${_copy_source_lang}${_copy_source_suffix}/${publish_file_docx%.*}.docx" \
                          "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                fi
                fi
            done
        done
        fi
        } >"$_pm_tmpout" 2>&1
        _pm_exit=$?
        progress_log "Markdown 処理を終了しました file=${file#${workspaceFolder}/} exit=${_pm_exit}"
        # mkdir をアトミックロックとして使い、バッファリングした出力を表示する
        # (mkdir は Linux/MSYS2/Windows いずれでもアトミック操作)
        while ! mkdir "${OUTPUT_LOCK}.lck" 2>/dev/null; do sleep 0.01; done
        cat "$_pm_tmpout"
        rmdir "${OUTPUT_LOCK}.lck"
        rm -f "$_pm_tmpout"
        exit $_pm_exit
        ) &
        _file_pids+=($!)
        _file_names+=("$file")
        _file_status_files+=("$_pm_statusfile")
    fi
done

#-------------------------------------------------------------------

#-------------------------------------------------------------------
# 全ファイルジョブの完了待機
#-------------------------------------------------------------------

_overall_exit=0
for _i in "${!_file_pids[@]}"; do
    wait "${_file_pids[$_i]}" 2>/dev/null
    # bash の cleanup_dead_jobs で PID が既に回収されていても、
    # サブシェル EXIT trap が書き込んだステータスを参照する
    _pm_job_exit=$(cat "${_file_status_files[$_i]}" 2>/dev/null || echo "127")
    rm -f "${_file_status_files[$_i]}"
    if [[ "${_pm_job_exit}" -ne 0 ]]; then
        echo >&2 "Error: Failed to process ${_file_names[$_i]}"
        _overall_exit=1
    fi
done

if [[ $_overall_exit -ne 0 ]]; then
    exit 1
fi

#-------------------------------------------------------------------

echo "*** pub_markdown_core end   $(date -Is)"

#-------------------------------------------------------------------

exit 0
