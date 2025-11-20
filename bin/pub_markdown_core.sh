#!/bin/bash
#set -x

SCRIPT_DIR=$(cd $(dirname "$0"); pwd)
HOME_DIR=$(cd $SCRIPT_DIR; cd ..; pwd) # bin フォルダの上位が home
PATH=$SCRIPT_DIR:$PATH # 優先的に bin フォルダを選択させる
cd $HOME_DIR

#── Ctrl+C（SIGINT）や SIGTERM を捕まえて実行するクリーンアップ処理 ──
cleanup() {
    #echo >&2 "スクリプトが中断されました。"
    printf "\e[0m" # 文字色を通常に設定
    exit 1
}
# SIGINT (Ctrl+C) と SIGTERM (kill コマンドなど) を捕捉
trap 'cleanup' INT TERM

#-------------------------------------------------------------------
# マルチプラットフォーム対応
#-------------------------------------------------------------------

LINUX=0
if [[ "$(uname -s)" == "Linux" ]]; then
    LINUX=1
fi

if [ $LINUX -eq 1 ]; then
    chmod +x "${SCRIPT_DIR}/replace-tag.sh"
    chmod +x "${SCRIPT_DIR}/mmdc-wrapper.sh"
    chmod +x "${SCRIPT_DIR}/chrome-wrapper.sh"
    WIDDERSHINS="${SCRIPT_DIR}/node_modules/.bin/widdershins"
    chmod +x "${SCRIPT_DIR}/pandoc-filters/insert-toc.sh"
else
    WIDDERSHINS="${SCRIPT_DIR}/node_modules/.bin/widdershins.cmd"
    EDGE_PATH="${ProgramW6432} (x86)/Microsoft/Edge/Application/msedge.exe"
    if [ -f "$EDGE_PATH" ]; then
        export PUPPETEER_EXECUTABLE_PATH="$EDGE_PATH"
        #echo "PUPPETEER_EXECUTABLE_PATH = ${PUPPETEER_EXECUTABLE_PATH}"
    fi
fi

# pandoc が ${SCRIPT_DIR} にある または PATH が通っていれば
# PANDOC に pandoc のパスを設定
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

    # 絶対パスの判定（Linux/Unix および Windows Git Bash 対応）
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
    lang=$(parse_yaml "$config_content" "lang")
    htmlStyleSheet=$(parse_yaml "$config_content" "htmlStyleSheet")
    htmlTemplate=$(parse_yaml "$config_content" "htmlTemplate")
    htmlSelfContainTemplate=$(parse_yaml "$config_content" "htmlSelfContainTemplate")
    htmlSelfContainCondition=$(parse_yaml "$config_content" "htmlSelfContainCondition")
    htmlTocEnable=$(parse_yaml "$config_content" "htmlTocEnable")
    htmlTocDepth=$(parse_yaml "$config_content" "htmlTocDepth")
    docxTemplate=$(parse_yaml "$config_content" "docxTemplate")
    docxCondition=$(parse_yaml "$config_content" "docxCondition")
    autoSetDate=$(parse_yaml "$config_content" "autoSetDate")
    autoSetAuthor=$(parse_yaml "$config_content" "autoSetAuthor")
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

# 設定ファイルに autoSetDate が指定されなかった場合の値を false にする
if [[ "$autoSetDate" == "" ]]; then
    autoSetDate="false"
fi

# 設定ファイルに autoSetAuthor が指定されなかった場合の値を false にする
if [[ "$autoSetAuthor" == "" ]]; then
    autoSetAuthor="false"
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

# 設定ファイルに htmlSelfContainCondition が指定されなかった場合の値を disable にする
if [[ "$htmlSelfContainCondition" == "" ]]; then
    htmlSelfContainCondition="disable"
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

# 設定ファイルに docxCondition が指定されなかった場合の値を singlefile にする
if [[ "$docxCondition" == "" ]]; then
    docxCondition="singlefile"
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

if [[ -n $relativeFile && $relativeFile != ${mdRoot}/* && $relativeFile != ${mdRoot} ]]; then
    # NOTE: ワークスペース外のファイルの場合、ここでチェックアウトされる
    echo "Error: relativeFile does not start with '${mdRoot}/'. Exiting."
    exit 1
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

    # 出力フォルダの clean
    if [[ "$details" == "both" ]]; then
        # 両方出力する場合は、doxygen 以外のすべてのディレクトリを削除
        find "${workspaceFolder}/${pubRoot}" \
            -mindepth 1 -type d \
            -name 'doxygen' -prune \
            -o -type d ! -name 'doxygen' -exec rm -rf {} +
    elif [[ "$details" == "true" ]]; then
        # "-details" で終わっているディレクトリを削除、doxygen は常に残す
        # 先に doxygen を prune して探索・削除対象から外す
        find "${workspaceFolder}/${pubRoot}" \
            -mindepth 1 -type d \
            -name 'doxygen' -prune \
            -o -type d ! -name 'doxygen' -name '*-details' -exec rm -rf {} +
    else
        # "-details" で終わっていないディレクトリを削除、doxygen は常に残す
        # doxygen と *-details を prune し、残りのみ削除
        find "${workspaceFolder}/${pubRoot}" \
            -mindepth 1 -type d \
            \( -name 'doxygen' -o -name '*-details' \) -prune \
            -o -type d -exec rm -rf {} +
    fi
fi

# 実行条件をチェックする関数
# この関数は以下の仕様で動作します:
#
#  - 引数: $1=executionMode, $2=condition
#  - 戻り値: 0=true, 1=false (bash の標準的な戻り値)
#
#  条件判定ロジック:
#  - condition="disable" → 常に false
#  - condition="workspace" → 常に true
#  - condition="folder" → executionMode が "folder" または "singlefile" の時 true
#  - condition="singlefile" → executionMode が "singlefile" の時のみ true
#  - 未知の condition → デフォルトで false
should_execute() {
    local execution_mode="$1"
    local condition="$2"

    case "$condition" in
        "disable")
            return 1  # false
            ;;
        "workspace")
            return 0  # true
            ;;
        "folder")
            if [[ "$execution_mode" == "folder" || "$execution_mode" == "singlefile" ]]; then
                return 0  # true
            else
                return 1  # false
            fi
            ;;
        "singlefile")
            if [[ "$execution_mode" == "singlefile" ]]; then
                return 0  # true
            else
                return 1  # false
            fi
            ;;
        *)
            # 未知の condition の場合はデフォルトで false
            return 1
            ;;
    esac
}

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
    if [ -d "${workspaceFolder}/$relativeFile" ]; then
        # relativeFile がディレクトリの場合: そのディレクトリ内のリンク先も含めて収集
        base_dir="${workspaceFolder}/${relativeFile}"

        # 1) Markdown や YAML に埋め込まれたリンク資産を抽出
        declare -a files_linked=()
        while IFS= read -r -d '' md_file; do
            extract_links_from_markdown "$md_file" "$base_dir"
        done < <(find "${base_dir}" -maxdepth 1 -type f -name "*.md" -print0)
        unset IFS

        # 2) ディレクトリ直下のすべてのファイルを追加
        mapfile -d '' -t additional_files < <(
            find "${base_dir}" -maxdepth 1 -type f -print0
        )

        # 3) マージ＆ソート＆重複排除
        merge_and_deduplicate_files "${files_linked[@]}" "${additional_files[@]}"
    else
        # relativeFile が単一ファイルの場合: そのファイル＋リンク先ファイルを抽出
        declare -a files_linked=()
        if [[ -f "${workspaceFolder}/${relativeFile}" ]]; then
            extract_links_from_markdown "${workspaceFolder}/${relativeFile}" "$base_dir"
        fi

        # マージ＆ソート＆重複排除 (単一ファイル自身も含める)
        merge_and_deduplicate_files "${files_linked[@]}" "${workspaceFolder}/${relativeFile}"
    fi
else
    # relativeFile が指定されていない場合: mdRoot 以下の全ファイルを対象
    mapfile -d '' -t files_raw_initial < <(
        find "${base_dir}" -type f -print0 | sort -z -u
    )
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
    # 1) workspaceFolder/ を切り落として相対パス化 (NUL 区切り)
    mapfile -d '' -t files_rel_zero_array < <(
        printf '%s\0' "${files_raw_initial[@]}" | \
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
            # ルールが空（:: 相当）または「!」で始まるルールのみ採用
            if ($rule eq "" || $rule =~ /^!/) {
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

else
    # Git 管理外ならファイル名を NUL→改行区切りに変えてそのまま使う
    files_raw=$(printf "%s" "${files_raw_initial[@]}" | tr '\0' '\n')
fi

# 配列に格納
IFS=$'\n' read -r -d '' -a files <<< "$files_raw"

#echo "***"
#for file in "${files[@]}"; do
#    echo ${file}
#done
#echo "***"
#exit

echo " done."

#-------------------------------------------------------------------

for file in "${files[@]}"; do
    # 単一 md の発行で、リンク先のファイルがない場合は処理しない
    # → ファイルが存在する場合のみ処理を行う
    if [[ -e "$file" ]]; then
        publish_dir=$(dirname "${file}")
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
        publish_file="html/${file#${workspaceFolder}/${mdRoot}/}"

        # NOTE: OpenAPI ファイルは発行時に同梱すべきかと考えたため、コピーを行う(除外処理をしない)
        if [[ "$file" != *.md ]] ; then
            # コンテンツのコピー
            echo "Processing Other file: ${file#${workspaceFolder}/}"
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

for file in "${files[@]}"; do
    if [[ "$file" == *.yaml ]] || [[ "$file" == *.json ]]; then # TODO: OpenAPI ファイルを .yaml 拡張子で判断してよいかどうかは怪しい。ファイル内に"openapi:"があることくらいは見たほうがいい。
        
        # FIXME: markdown ファイルとの重複処理は統合すべき。
        echo "Processing OpenAPI file: ${file#${workspaceFolder}/}"

        # html
        publish_dir=$(dirname "${file}")
        if [[ "$publish_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir=html/${publish_dir#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir=html
        fi
        publish_file=html/${file#${workspaceFolder}/${mdRoot}/}

        # html-self-contain
        publish_dir_self_contain=$(dirname "${file}")
        if [[ "$publish_dir_self_contain" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_self_contain="html-self-contain/${publish_dir_self_contain#${workspaceFolder}/${mdRoot}/}"
        else
            publish_dir_self_contain="html-self-contain"
        fi
        if should_execute "$executionMode" "$htmlSelfContainCondition"; then
            for langElement in ${lang}; do
                for details_suffix in "${details_suffixes[@]}"; do
                    mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir_self_contain"
                done
            done
        fi
        publish_file_self_contain="html-self-contain/${file#${workspaceFolder}/${mdRoot}/}"

        # docx
        publish_dir_docx=$(dirname "${file}")
        if [[ "$publish_dir_docx" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_docx=docx/${publish_dir_docx#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir_docx=docx
        fi
        if should_execute "$executionMode" "$docxCondition"; then
            for langElement in ${lang}; do
                for details_suffix in "${details_suffixes[@]}"; do
                    mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir_docx"
                done
            done
        fi
        publish_file_docx=docx/${file#${workspaceFolder}/${mdRoot}/}

        # path to css
        nest_count=$(echo "$publish_file" | grep -o '/' | wc -l)
        up_dir=""
        for ((i=2; i<=nest_count; i++)); do
            up_dir+="../"
        done

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
                    printf "\e[33m" # 文字色を黄色に設定
                    echo "${openapi_md}" | \
                        ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --eol=lf --metadata title="$openapi_md_title" -f markdown+hard_line_breaks \
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
                            --wrap=none -t html -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                    printf "\e[0m" # 文字色を通常に設定
                    if should_execute "$executionMode" "$htmlSelfContainCondition"; then
                        echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                        printf "\e[33m" # 文字色を黄色に設定
                        echo "${openapi_md}" | \
                            ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --eol=lf --metadata title="$openapi_md_title" -f markdown+hard_line_breaks \
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
                                --wrap=none -t html --embed-resources --standalone -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                        printf "\e[0m" # 文字色を通常に設定
                    fi
                    if should_execute "$executionMode" "$docxCondition"; then
                        echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                        printf "\e[33m" # 文字色を黄色に設定
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
                                --wrap=none -t docx --reference-doc="${docxTemplate}" -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                        printf "\e[0m" # 文字色を通常に設定
                    fi
                    firstLang="${langElement}"
                    firstSuffix="${details_suffix}"
                else
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                    cp -p "${workspaceFolder}/${pubRoot}/${firstLang}${firstSuffix}/${publish_file%.*}.html" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                    if should_execute "$executionMode" "$htmlSelfContainCondition"; then
                        echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                        cp -p "${workspaceFolder}/${pubRoot}/${firstLang}${firstSuffix}/${publish_file_self_contain%.*}.html" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                    fi
                    if should_execute "$executionMode" "$docxCondition"; then
                        echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                        cp -p "${workspaceFolder}/${pubRoot}/${firstLang}${firstSuffix}/${publish_file_docx%.*}.docx" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                    fi
                fi
            done
        done
    elif [[ "$file" == *.md ]]; then
        # .md ファイルの処理
        echo "Processing Markdown file: ${file#${workspaceFolder}/}"

        # html
        publish_dir=$(dirname "${file}")
        if [[ "$publish_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir=html/${publish_dir#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir=html
        fi
        publish_file=html/${file#${workspaceFolder}/${mdRoot}/}

        # html-self-contain
        publish_dir_self_contain=$(dirname "${file}")
        if [[ "$publish_dir_self_contain" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_self_contain="html-self-contain/${publish_dir_self_contain#${workspaceFolder}/${mdRoot}/}"
        else
            publish_dir_self_contain="html-self-contain"
        fi
        if should_execute "$executionMode" "$htmlSelfContainCondition"; then
            for langElement in ${lang}; do
                for details_suffix in "${details_suffixes[@]}"; do
                    mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir_self_contain"
                done
            done
        fi
        publish_file_self_contain="html-self-contain/${file#${workspaceFolder}/${mdRoot}/}"

        # docx
        publish_dir_docx=$(dirname "${file}")
        if [[ "$publish_dir_docx" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_docx=docx/${publish_dir_docx#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir_docx=docx
        fi
        if should_execute "$executionMode" "$docxCondition"; then
            for langElement in ${lang}; do
                for details_suffix in "${details_suffixes[@]}"; do
                    mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir_docx"
                done
            done
        fi
        publish_file_docx=docx/${file#${workspaceFolder}/${mdRoot}/}

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
                printf "\e[33m" # 文字色を黄色に設定
                echo "${md_body}" | \
                    ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --eol=lf --metadata title="$md_title" -f markdown+hard_line_breaks \
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
                        --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                        --wrap=none -t html -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
                printf "\e[0m" # 文字色を通常に設定
                if should_execute "$executionMode" "$htmlSelfContainCondition"; then
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                    # Markdown の最初にコメントがあると、レベル1のタイトルを取り除くことができない。sed '/^# /d' で取り除く。
                    printf "\e[33m" # 文字色を黄色に設定
                    echo "${md_body}" | \
                        ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --eol=lf --metadata title="$md_title" -f markdown+hard_line_breaks \
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
                            --wrap=none -t html --embed-resources --standalone -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
                    printf "\e[0m" # 文字色を通常に設定
                fi
                if should_execute "$executionMode" "$docxCondition"; then
                    echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                    # Markdown の最初にコメントがあると、レベル1のタイトルを取り除くことができない。sed '/^# /d' で取り除く。
                    printf "\e[33m" # 文字色を黄色に設定
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
                            --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" \
                            --wrap=none -t docx --reference-doc="${docxTemplate}" -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_docx%.*}.docx"
                    printf "\e[0m" # 文字色を通常に設定
                fi
            done
        done
    fi
done

#-------------------------------------------------------------------

echo "*** pub_markdown_core end   $(date -Is)"

#-------------------------------------------------------------------

exit 0
