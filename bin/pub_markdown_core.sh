#!/bin/bash
#set -x

SCRIPT_DIR=$(cd $(dirname "$0"); pwd)
HOME_DIR=$(cd $SCRIPT_DIR; cd ..; pwd) # bin フォルダの上位が home
PATH=$SCRIPT_DIR:$PATH # 優先的に bin フォルダを選択させる
cd $HOME_DIR

# Ctrl+C (SIGINT) や SIGTERM を捕まえて実行するクリーンアップ処理
cleanup() {
    #echo >&2 "スクリプトが中断されました。"
    # バックグラウンドジョブを停止
    local _bg_jobs
    _bg_jobs=$(jobs -rp 2>/dev/null)
    [[ -n "$_bg_jobs" ]] && kill $_bg_jobs 2>/dev/null
    wait 2>/dev/null
    # 共有ブラウザサーバーを停止
    if [[ -n "$BROWSER_SERVER_PID" ]]; then
        kill "$BROWSER_SERVER_PID" 2>/dev/null
        wait "$BROWSER_SERVER_PID" 2>/dev/null
        rm -f "$PUB_MARKDOWN_BROWSER_WS_FILE" 2>/dev/null
    fi
    rm -rf "${OUTPUT_LOCK}.lck" 2>/dev/null
    printf "\e[0m" # 文字色を通常に設定
    exit 1
}
# SIGINT (Ctrl+C) と SIGTERM (kill コマンドなど) を捕捉
trap 'cleanup' INT TERM

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
    EDGE_REG_PATH=$(reg query "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\msedge.exe" //v Path 2>/dev/null | grep "Path" | sed 's/.*REG_SZ[[:space:]]*//' | tr -d '\r')
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
if [ ! -d "${SCRIPT_DIR}/node_modules/.bin" ]; then
    echo "Installing node.js modules..."
    (cd "${SCRIPT_DIR}" && npm install)
    #echo "Error: ${SCRIPT_DIR}/node_modules/.bin not found. Please 'npm install' in the ${SCRIPT_DIR} directory."
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

# 共有ブラウザサーバーをバックグラウンドで起動
# NOTE: browser-server.js は Puppeteer のデフォルトブラウザ検出を使用する。
#       prepare_puppeteer_env.sh (chrome-wrapper.sh) はここでは適用しない。
#       chrome-wrapper.sh の WebSocket 競合回避はファイルベースの待機で代替する。
#       フォールバック時 (rsvg-convert 単体実行) は従来通り chrome-wrapper.sh が使われる。
node "${SCRIPT_DIR}/browser-server.js" "$PUB_MARKDOWN_BROWSER_WS_FILE" &
BROWSER_SERVER_PID=$!

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
fi

#-------------------------------------------------------------------

#-------------------------------------------------------------------
# 並列処理設定
#-------------------------------------------------------------------

# 並列処理の最大ジョブ数
# 環境変数 PUB_MARKDOWN_PARALLEL で上書き可能 (例: PUB_MARKDOWN_PARALLEL=2 pub_markdown_core.sh ...)
MAX_PARALLEL=${PUB_MARKDOWN_PARALLEL:-$(nproc 2>/dev/null || echo 4)}

# 並列出力の排他制御用ロックベースパス
# flock (Linux 専用) の代わりに mkdir アトミックロックを使用することで
# MSYS2 (Windows) 環境でも動作する
OUTPUT_LOCK=$(mktemp -u)

# 実行中のバックグラウンドジョブ数が MAX_PARALLEL に達している場合、
# 1つ完了するまで待機する関数
wait_for_parallel_slot() {
    while (( $(jobs -rp 2>/dev/null | wc -l) >= MAX_PARALLEL )); do
        # wait -n はいずれか1つのジョブ完了まで待機 (bash 4.3+)
        # 未対応環境では 0.05 秒ポーリングにフォールバック
        wait -n 2>/dev/null || sleep 0.05
    done
}

#-------------------------------------------------------------------

# Markdown ファイルからリンク先ファイルを抽出する関数
# 引数: $1=Markdownファイルのパス, $2=ベースディレクトリのパス
# 戻り値: グローバル配列 files_linked に抽出されたファイルパスを追加
extract_links_from_markdown() {
    local md_file="$1"
    local base_dir="$2"
    local line

    if command -v realpath >/dev/null 2>&1; then
        base_dir="$(realpath -m "$base_dir")"
    fi

    [[ -f "$md_file" ]] || return 0

    while IFS= read -r line; do
        # 画像リンクをすべて抽出
        while IFS= read -r link_path; do
            # フィルタ条件
            if [[ ! $link_path =~ ^(https?://|mailto:|ftp://) ]] \
               && [[ ! $link_path =~ ^# ]] \
               && [[ ! $link_path =~ \.(md|yaml)$ ]]; then
                local full_path="${base_dir}/${link_path}"
                if command -v realpath >/dev/null 2>&1; then
                    full_path="$(realpath -m "$full_path")"
                fi
                [[ -e "$full_path" ]] && files_linked+=("$full_path")
            fi
        done < <(printf '%s\n' "$line" | grep -oP '!\[[^]]*\]\(\K[^)\s]+(?=\))')

        # 通常リンクをすべて抽出
        while IFS= read -r link_path; do
            if [[ ! $link_path =~ ^(https?://|mailto:|ftp://) ]] \
               && [[ ! $link_path =~ ^# ]] \
               && [[ ! $link_path =~ \.(md|yaml)$ ]]; then
                local full_path="${base_dir}/${link_path}"
                if command -v realpath >/dev/null 2>&1; then
                    full_path="$(realpath -m "$full_path")"
                fi
                [[ -e "$full_path" ]] && files_linked+=("$full_path")
            fi
        done < <(printf '%s\n' "$line" | grep -oP '\[[^]]*\]\(\K[^)\s]+(?=\))')

    done < "$md_file"
}

# ファイル配列をマージ・ソート・重複排除する関数
# 引数: 複数のファイルパス
# 戻り値: グローバル配列 files_raw_initial にソート済みの重複排除されたファイルパスを設定
merge_and_deduplicate_files() {
    declare -A unique_files
    for file in "$@"; do
        [[ -n "$file" ]] && unique_files["$file"]=1
    done
    files_raw_initial=()
    for file in "${!unique_files[@]}"; do
        files_raw_initial+=("$file")
    done
    # ソート
    IFS=$'\n' files_raw_initial=($(sort <<< "${files_raw_initial[*]}"))
    unset IFS
}

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
            configFile=$(resolve_path "${configFile//\\/\/}")
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
        --docx=*)
            docxOutput="${1#*=}"
            #echo docxOutput=${docxOutput}
            shift
        ;;
        --htmlSelfContain=*)
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
configFile="${workspaceFolder}/.vscode/pub_markdown.config.yaml"

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
    mergeSubmoduleDocs=$(parse_yaml "$config_content" "mergeSubmoduleDocs")
    htmlNavigationLinkEnable=$(parse_yaml "$config_content" "htmlNavigationLinkEnable")
fi

# 設定ファイルに mdRoot が指定されなかった場合の値を "docs-src" にする
if [[ "$mdRoot" == "" ]]; then
    mdRoot="docs-src"
fi

# 設定ファイルに pubRoot が指定されなかった場合の値を "docs" にする
if [[ "$pubRoot" == "" ]]; then
    pubRoot="docs"
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
# サブモジュール mdRoot マージ機能
#-------------------------------------------------------------------

# 設定ファイルで指定されたサブモジュールのパスリストを設定する関数
# 引数: $1=スペース区切りのサブモジュール名リスト (例: "doxyfw makefw testfw")
# 戻り値: グローバル配列 submodule_paths にサブモジュールパスを設定
set_submodule_paths() {
    local submodule_list="$1"
    submodule_paths=()

    if [[ -z "$submodule_list" ]]; then
        return 0
    fi

    # スペース区切りで配列に変換
    read -ra submodule_paths <<< "$submodule_list"
}

# サブモジュール内の mdRoot ディレクトリを検出する関数
# 戻り値: グローバル配列 submodule_mdroot_paths に "サブモジュール名:mdRootパス" を設定
detect_submodule_docs() {
    submodule_mdroot_paths=()

    for submodule in "${submodule_paths[@]}"; do
        local submodule_mdroot_path="${workspaceFolder}/${submodule}/${mdRoot}"
        if [[ -d "$submodule_mdroot_path" ]]; then
            submodule_mdroot_paths+=("${submodule}:${submodule_mdroot_path}")
        fi
    done
}

# 実パスを仮想パス (mdRoot 基準) に変換する関数
# 引数: $1=実パス (絶対パス)
# 戻り値: 標準出力に仮想パスを出力
real_to_virtual_path() {
    local real_path="$1"

    # サブモジュール mdRoot のパスかチェック
    for entry in "${submodule_mdroot_paths[@]}"; do
        local submodule="${entry%%:*}"
        local submodule_mdroot="${entry#*:}"

        if [[ "$real_path" == "${submodule_mdroot}/"* ]]; then
            # サブモジュール mdRoot 配下のファイル
            local relative="${real_path#${submodule_mdroot}/}"
            echo "${workspaceFolder}/${mdRoot}/${submodule}/${relative}"
            return 0
        elif [[ "$real_path" == "${submodule_mdroot}" ]]; then
            # サブモジュール mdRoot 自体
            echo "${workspaceFolder}/${mdRoot}/${submodule}"
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

    # サブモジュール名で始まるかチェック
    for entry in "${submodule_mdroot_paths[@]}"; do
        local submodule="${entry%%:*}"
        local submodule_mdroot="${entry#*:}"

        if [[ "$relative" == "${submodule}/"* ]]; then
            # サブモジュール mdRoot へのパスに変換
            local submodule_relative="${relative#${submodule}/}"
            echo "${submodule_mdroot}/${submodule_relative}"
            return 0
        elif [[ "$relative" == "${submodule}" ]]; then
            # サブモジュール mdRoot 自体
            echo "${submodule_mdroot}"
            return 0
        fi
    done

    # メイン mdRoot のファイル (変換不要)
    echo "$virtual_path"
}

# サブモジュール情報を初期化
declare -a submodule_paths=()
declare -a submodule_mdroot_paths=()

if [[ -n "$mergeSubmoduleDocs" ]]; then
    set_submodule_paths "$mergeSubmoduleDocs"
    detect_submodule_docs
    # insert-toc.sh 用に環境変数をエクスポート
    export MERGE_SUBMODULE_DOCS="$mergeSubmoduleDocs"
    export SUBMODULE_DOCS_PATHS="${submodule_mdroot_paths[*]}"
fi

#-------------------------------------------------------------------

# relativeFile のパス検証 (サブモジュールマージ対応)
if [[ -n $relativeFile ]]; then
    path_type=""

    # 1. メイン mdRoot パスのチェック
    if [[ $relativeFile == ${mdRoot}/* || $relativeFile == ${mdRoot} ]]; then
        path_type="mdroot"
    fi

    # 2. サブモジュール実パスのチェック
    if [[ -z "$path_type" && -n "$mergeSubmoduleDocs" ]]; then
        for entry in "${submodule_mdroot_paths[@]}"; do
            _submodule="${entry%%:*}"
            if [[ $relativeFile == ${_submodule}/${mdRoot}/* || $relativeFile == ${_submodule}/${mdRoot} ]]; then
                path_type="submodule_real"
                break
            fi
        done
    fi

    # 3. 仮想パスのチェック
    if [[ -z "$path_type" && -n "$mergeSubmoduleDocs" ]]; then
        for entry in "${submodule_mdroot_paths[@]}"; do
            _submodule="${entry%%:*}"
            if [[ $relativeFile == ${mdRoot}/${_submodule}/* || $relativeFile == ${mdRoot}/${_submodule} ]]; then
                path_type="submodule_virtual"
                break
            fi
        done
    fi

    # 4. いずれにも該当しない場合はエラー
    if [[ -z "$path_type" ]]; then
        echo "Error: relativeFile is not a valid path: $relativeFile"
        exit 1
    fi

    # relativeFile が実パスの場合、仮想パスに変換 (内部処理の統一のため)
    if [[ "$path_type" == "submodule_real" ]]; then
        for entry in "${submodule_mdroot_paths[@]}"; do
            _submodule="${entry%%:*}"
            _submodule_mdroot_rel="${_submodule}/${mdRoot}"

            if [[ $relativeFile == ${_submodule_mdroot_rel}/* ]]; then
                _subpath="${relativeFile#${_submodule_mdroot_rel}/}"
                original_relativeFile="$relativeFile"
                relativeFile="${mdRoot}/${_submodule}/${_subpath}"
                break
            elif [[ $relativeFile == ${_submodule_mdroot_rel} ]]; then
                original_relativeFile="$relativeFile"
                relativeFile="${mdRoot}/${_submodule}"
                break
            fi
        done
    fi
fi

if [ -n "$relativeFile" ]; then
    if [ -d "${workspaceFolder}/$relativeFile" ]; then
        # 実行モード=フォルダ
        executionMode="folder"

        # $relativeFile がフォルダ名の場合は、そのフォルダを基準とする
        base_dir="${workspaceFolder}/${relativeFile}"

        # 当該フォルダ限定の clean
        if [[ "$base_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir=html/${base_dir#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir=html
        fi

        for langElement in ${lang}; do
            for details_suffix in "${details_suffixes[@]}"; do
                mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir"
                find "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" -maxdepth 1 -type f -exec rm -f {} +
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

#-------------------------------------------------------------------

# insert-toc.lua のキャッシュをクリア
rm -f /tmp/insert-toc-cache.tsv > /dev/null

#-------------------------------------------------------------------

echo -n "Correcting target files..."

# ── (A) relativeFile を使って初期リストを NUL 区切りで作成 ──
if [ -n "$relativeFile" ]; then
    # 実パスの解決
    # original_relativeFile が設定されている場合 (実パス→仮想パス変換が行われた場合) はそれを使用
    # そうでない場合は relativeFile をそのまま使用 (メイン mdRoot のファイル)
    if [[ -n "$original_relativeFile" ]]; then
        real_relativeFile="$original_relativeFile"
    else
        # 仮想パスから実パスへの変換 (仮想パスで指定された場合)
        real_relativeFile="$relativeFile"
        if [[ -n "$mergeSubmoduleDocs" ]]; then
            for entry in "${submodule_mdroot_paths[@]}"; do
                _submodule="${entry%%:*}"
                _submodule_mdroot="${entry#*:}"

                if [[ $relativeFile == ${mdRoot}/${_submodule}/* ]]; then
                    _subpath="${relativeFile#${mdRoot}/${_submodule}/}"
                    real_relativeFile="${_submodule}/${mdRoot}/${_subpath}"
                    break
                elif [[ $relativeFile == ${mdRoot}/${_submodule} ]]; then
                    real_relativeFile="${_submodule}/${mdRoot}"
                    break
                fi
            done
        fi
    fi

    if [ -d "${workspaceFolder}/$real_relativeFile" ]; then
        # relativeFile がディレクトリの場合: そのディレクトリ内のリンク先も含めて収集
        # base_dir は実パスを使用 (ファイル探索用)
        real_base_dir="${workspaceFolder}/${real_relativeFile}"
        # 仮想パスの base_dir も設定 (出力パス計算用)
        base_dir="${workspaceFolder}/${relativeFile}"

        # 1) Markdown や YAML に埋め込まれたリンク資産を抽出
        declare -a files_linked=()
        while IFS= read -r -d '' md_file; do
            extract_links_from_markdown "$md_file" "$real_base_dir"
        done < <(find "${real_base_dir}" -maxdepth 1 -type f -name "*.md" -print0)
        unset IFS

        # 2) ディレクトリ直下のすべてのファイルを追加
        mapfile -d '' -t additional_files < <(
            find "${real_base_dir}" -maxdepth 1 -type f -print0
        )

        # 3) マージ＆ソート＆重複排除
        merge_and_deduplicate_files "${files_linked[@]}" "${additional_files[@]}"
    else
        # relativeFile が単一ファイルの場合: そのファイル＋リンク先ファイルを抽出
        # base_dir は実パスを使用
        real_base_dir="${workspaceFolder}/$(dirname "$real_relativeFile")"
        base_dir="${workspaceFolder}/$(dirname "$relativeFile")"

        declare -a files_linked=()
        if [[ -f "${workspaceFolder}/${real_relativeFile}" ]]; then
            extract_links_from_markdown "${workspaceFolder}/${real_relativeFile}" "$real_base_dir"
        fi

        # マージ＆ソート＆重複排除 (単一ファイル自身も含める)
        merge_and_deduplicate_files "${files_linked[@]}" "${workspaceFolder}/${real_relativeFile}"
    fi
else
    # relativeFile が指定されていない場合: mdRoot 以下の全ファイルを対象
    mapfile -d '' -t files_raw_initial < <(
        find "${base_dir}" -type f -print0 | sort -z -u
    )

    # サブモジュール mdRoot のファイルを追加 (mergeSubmoduleDocs が指定されている場合)
    if [[ -n "$mergeSubmoduleDocs" ]]; then
        for entry in "${submodule_mdroot_paths[@]}"; do
            _submodule="${entry%%:*}"
            _submodule_mdroot="${entry#*:}"

            # サブモジュール mdRoot 配下のファイルを収集
            mapfile -d '' -t submodule_files < <(
                find "${_submodule_mdroot}" -type f -print0 | sort -z -u
            )

            # files_raw_initial に追加
            files_raw_initial+=("${submodule_files[@]}")
        done
    fi
fi

# ── (B) files_raw_initial から .gitignore と .gitkeep を除外 ──
{
    # 一時配列を作って、除外後に元の配列へ上書き
    mapfile -d '' -t _tmp_filtered < <(
    for _f in "${files_raw_initial[@]}"; do
        # basename が .gitignore でも .gitkeep でもなければ、残す
        case "${_f##*/}" in
        .gitignore|.gitkeep) 
            ;;
        *) 
            printf '%s\0' "$_f"
            ;;
        esac
    done
    )
    files_raw_initial=( "${_tmp_filtered[@]}" )
    unset _tmp_filtered
}

# ── (C) Git 管理下なら NUL 区切りでフィルタ ──
if git -C "$workspaceFolder" rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    # サブモジュール配下のファイルを分離 (gitignore フィルタリング対象外)
    declare -a submodule_files_array=()
    declare -a main_files_array=()

    if [[ -n "$mergeSubmoduleDocs" && ${#submodule_mdroot_paths[@]} -gt 0 ]]; then
        for f in "${files_raw_initial[@]}"; do
            is_submodule_file=false
            for entry in "${submodule_mdroot_paths[@]}"; do
                _submodule_mdroot="${entry#*:}"
                if [[ "$f" == "${_submodule_mdroot}/"* || "$f" == "${_submodule_mdroot}" ]]; then
                    is_submodule_file=true
                    break
                fi
            done
            if [[ "$is_submodule_file" == "true" ]]; then
                submodule_files_array+=("$f")
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

    # 4) サブモジュール配下のファイルを追加 (フィルタリング済みとして扱う)
    for f in "${submodule_files_array[@]}"; do
        files_raw+="${f}"$'\n'
    done

else
    # Git 管理外ならファイル名を NUL→改行区切りに変えてそのまま使う
    files_raw=$(printf '%s\n' "${files_raw_initial[@]}")
fi

# 配列に格納
IFS=$'\n' read -r -d '' -a files <<< "$files_raw"

echo " done."

#-------------------------------------------------------------------

for file in "${files[@]}"; do
    # 単一 md の発行で、リンク先のファイルがない場合は処理しない
    # → ファイルが存在する場合のみ処理を行う
    if [[ -e "$file" ]]; then
        # サブモジュールマージ時は仮想パスに変換して出力パスを計算
        if [[ -n "$mergeSubmoduleDocs" ]]; then
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
        copy_if_different_timestamp "${htmlStyleSheet}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/html-style.css"
    done
done

# ファイルレベルの並列処理用追跡配列
declare -a _file_pids=()
declare -a _file_names=()

for file in "${files[@]}"; do
    # サブモジュールマージ時は仮想パスに変換して出力パスを計算
    if [[ -n "$mergeSubmoduleDocs" ]]; then
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
                        ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --eol=lf --metadata title="$openapi_md_title" ${navigationLinkMetadata} -f markdown+hard_line_breaks \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                            --template="${htmlTemplate}" -c "${up_dir}html-style.css" \
                            ${PANDOC_CROSSREF} \
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
                            ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --eol=lf --metadata title="$openapi_md_title" ${navigationLinkMetadata} -f markdown+hard_line_breaks \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                                ${PANDOC_CROSSREF} \
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
                            ${PANDOC} -s --shift-heading-level-by=-1 --eol=lf --metadata title="$openapi_md_title" -f markdown+hard_line_breaks \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                                --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
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
        wait_for_parallel_slot
        (
        # このサブシェル内の出力を一時ファイルにバッファリングし、
        # 完了後に flock でアトミックに標準出力へ書き出す (並列実行時の出力混在を防ぐ)
        _pm_tmpout=$(mktemp)
        {
        # .md ファイルの処理
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

        # README.md を index.html に変換するロジック
        # index.md が存在しない場合のみ、README.md を index.html として出力
        file_basename=$(basename "$file")
        file_basename_lower=$(echo "$file_basename" | tr '[:upper:]' '[:lower:]')
        file_dirname=$(dirname "$file")

        if [[ "$file_basename_lower" == "readme.md" ]]; then
            # 同じディレクトリに index.md が存在するかチェック (大文字小文字を無視)
            index_md_exists=false
            if [ -d "$file_dirname" ]; then
                for potential_index in "$file_dirname"/*; do
                    if [[ -f "$potential_index" ]]; then
                        potential_basename=$(basename "$potential_index" | tr '[:upper:]' '[:lower:]')
                        if [[ "$potential_basename" == "index.md" ]]; then
                            index_md_exists=true
                            break
                        fi
                    fi
                done
            fi

            # index.md が存在しない場合のみ、README.md を index.html として出力
            if [[ "$index_md_exists" == "false" ]]; then
                publish_file="${publish_file%/*}/index.md"
                publish_file_self_contain="${publish_file_self_contain%/*}/index.md"
                publish_file_docx="${publish_file_docx%/*}/index.md"
            fi
        fi

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

        for details_suffix in "${details_suffixes[@]}"; do
            # details_suffix から details 値を決定
            if [[ "$details_suffix" == "-details" ]]; then
                current_details="true"
            else
                current_details="false"
            fi

            for langElement in ${lang}; do
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
                echo "${md_body}" | \
                    ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --eol=lf --metadata title="$md_title" ${navigationLinkMetadata} -f markdown+hard_line_breaks \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                        ${PANDOC_CROSSREF} \
                        --template="${htmlTemplate}" -c "${up_dir}html-style.css" \
                        --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir:$(dirname "$file")" \
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
                    # Markdown の最初にコメントがあると、レベル1のタイトルを取り除くことができない。sed '/^# /d' で取り除く。
                    _pm_pandoc_stderr=$(mktemp)
                    echo "${md_body}" | \
                        ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --eol=lf --metadata title="$md_title" ${navigationLinkMetadata} -f markdown+hard_line_breaks \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                            ${PANDOC_CROSSREF} \
                            --template="${htmlSelfContainTemplate}" -c "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/html-style.css" \
                            --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir:$(dirname "$file")" \
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
                    echo "${md_body}" | \
                        ${PANDOC} -s --shift-heading-level-by=-1 --eol=lf --metadata title="$md_title" -f markdown+hard_line_breaks \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/insert-toc.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/replace-table-br.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/replace-table-br.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-docx.lua" \
                            --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                            ${PANDOC_CROSSREF} \
                            --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir_docx:$(dirname "$file")" \
                            --wrap=none -t docx --reference-doc="${docxTemplate}" -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx" \
                            2>"$_pm_pandoc_stderr"
                    if [[ -s "$_pm_pandoc_stderr" ]]; then
                        printf "\e[33m"
                        cat "$_pm_pandoc_stderr"
                        printf "\e[0m"
                    fi
                    rm -f "$_pm_pandoc_stderr"
                fi
            done
        done
        } >"$_pm_tmpout" 2>&1
        _pm_exit=$?
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
    fi
done

#-------------------------------------------------------------------

#-------------------------------------------------------------------
# 全ファイルジョブの完了待機
#-------------------------------------------------------------------

_overall_exit=0
for _i in "${!_file_pids[@]}"; do
    wait "${_file_pids[$_i]}"
    if [[ $? -ne 0 ]]; then
        echo >&2 "Error: Failed to process ${_file_names[$_i]}"
        _overall_exit=1
    fi
done

if [[ $_overall_exit -ne 0 ]]; then
    # 共有ブラウザサーバーを停止してから終了
    if [[ -n "$BROWSER_SERVER_PID" ]]; then
        kill "$BROWSER_SERVER_PID" 2>/dev/null
        wait "$BROWSER_SERVER_PID" 2>/dev/null
        rm -f "$PUB_MARKDOWN_BROWSER_WS_FILE" 2>/dev/null
    fi
    exit 1
fi

#-------------------------------------------------------------------

#-------------------------------------------------------------------
# 共有ブラウザサーバーの停止
#-------------------------------------------------------------------

if [[ -n "$BROWSER_SERVER_PID" ]]; then
    kill "$BROWSER_SERVER_PID" 2>/dev/null
    wait "$BROWSER_SERVER_PID" 2>/dev/null
    rm -f "$PUB_MARKDOWN_BROWSER_WS_FILE" 2>/dev/null
fi

echo "*** pub_markdown_core end   $(date -Is)"

#-------------------------------------------------------------------

exit 0
