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
    chmod +x "${SCRIPT_DIR}/pandoc"
    chmod +x "${SCRIPT_DIR}/pandoc-crossref"
    WIDDERSHINS="${SCRIPT_DIR}/node_modules/.bin/widdershins"
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
# それ以外の場合は、PANDOC-CROSSREF は設定しない
if [ -x "${SCRIPT_DIR}/pandoc-crossref" ] || [ -x "${SCRIPT_DIR}/pandoc-crossref.exe" ]; then
    PANDOC_CROSSREF="-F ${SCRIPT_DIR}/pandoc-crossref"
elif command -v pandoc-crossref >/dev/null 2>&1 || command -v pandoc-crossref.exe >/dev/null 2>&1; then
    PANDOC_CROSSREF="-F pandoc-crossref"
else
    PANDOC_CROSSREF=""
fi

# ${SCRIPT_DIR}/node_modules/.bin が存在しない場合はエラーを表示して終了
if [ ! -d "${SCRIPT_DIR}/node_modules/.bin" ]; then
    echo "Error: ${SCRIPT_DIR}/node_modules/.bin not found. Please 'npm install' in the ${SCRIPT_DIR} directory."
    exit 1
fi

# node.js の警告を非表示にする
export NODE_NO_WARNINGS=1

#-------------------------------------------------------------------

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

# 定義ファイルのデフォルトパス
configFile="${workspaceFolder}/.vscode/pub_markdown.config.yaml"

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
    config_content=$(cat "$configFile")

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
    htmlTocEnable=$(parse_yaml "$config_content" "htmlTocEnable")
    htmlTocDepth=$(parse_yaml "$config_content" "htmlTocDepth")
    docxTemplate=$(parse_yaml "$config_content" "docxTemplate")
    autoSetDate=$(parse_yaml "$config_content" "autoSetDate")
    autoSetAuthor=$(parse_yaml "$config_content" "autoSetAuthor")
fi

# 設定ファイルに mdRoot が指定されなかった場合の値を "doc" にする
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
# autoSetDate が true の場合、各ドキュメント間でタイムスタンプに差異が発生しないように実行時間を記憶する
if [[ "$autoSetDate" == "true" ]]; then
    export EXEC_DATE=`date -R`
else
    export -n EXEC_DATE
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

# Adjust output directories based on the `details` flag
if [[ "$details" == "true" ]]; then
    details_suffix="-details"
else
    details_suffix=""
fi

#-------------------------------------------------------------------

if [[ -n $relativeFile && $relativeFile != ${mdRoot}/* && $relativeFile != ${mdRoot} ]]; then
    # NOTE: ワークスペース外のファイルの場合、ここでチェックアウトされる
    echo "Error: relativeFile does not start with '${mdRoot}/'. Exiting."
    exit 1
fi

if [ -n "$relativeFile" ]; then
    if [ -d "${workspaceFolder}/$relativeFile" ]; then
        # $relativeFile がフォルダ名の場合は、そのフォルダを基準とする
        base_dir="${workspaceFolder}/${relativeFile}"

        # 当該フォルダ限定の clean
        if [[ "$base_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir=html/${base_dir#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir=html
        fi

        for langElement in ${lang}; do
            mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir"
            find "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir" -maxdepth 1 -type f -exec rm -f {} +
        done
    else
        # 単一ファイルの場合は、そのファイルのあるフォルダを基準とする
        base_dir="${workspaceFolder}/$(dirname "$relativeFile")"
    fi
else
    base_dir="${workspaceFolder}/${mdRoot}"
    mkdir -p "${workspaceFolder}/${pubRoot}"
    # 出力フォルダの clean
    if [[ "$details" == "true" ]]; then
        # "-details" で終わっているディレクトリを削除
        #echo find "${workspaceFolder}/${pubRoot}" -mindepth 1 -type d ! -name '*-details' -prune -o -type d -print
        #find "${workspaceFolder}/${pubRoot}" -mindepth 1 -type d ! -name '*-details' -prune -o -type d -print
        find "${workspaceFolder}/${pubRoot}" -mindepth 1 -type d ! -name '*-details' -prune -o -type d -exec rm -rf {} +
    else
        # "-details" で終わっていないディレクトリを削除
        #echo find "${workspaceFolder}/${pubRoot}" -mindepth 1 -type d -name '*-details' -prune -o -type d -print
        #find "${workspaceFolder}/${pubRoot}" -mindepth 1 -type d -name '*-details' -prune -o -type d -print
        find "${workspaceFolder}/${pubRoot}" -mindepth 1 -type d -name '*-details' -prune -o -type d -exec rm -rf {} +
    fi
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

    # タイムスタンプを取得 (秒単位のエポック時間)
    local src_time=$(stat -c %Y "$src_file")
    local dest_time=$(stat -c %Y "$dest_file")

    # タイムスタンプの差を計算
    local time_diff=$((src_time - dest_time))
    if [[ ${time_diff#-} -le 2 ]]; then
        #echo "File not copied: Timestamps are within 2 seconds."
        return 0
    fi

    # タイムスタンプが異なる場合はコピー
    #echo "Processing Other file: ${src_file#${workspaceFolder}/}"
    cp -p "$src_file" "$dest_file"
    return 0
}

#-------------------------------------------------------------------

echo -n "Correcting target files..."

# ── (A) relativeFile を使って初期リストを NUL 区切りで作成 ──
if [ -n "$relativeFile" ]; then
    if [ -d "${workspaceFolder}/$relativeFile" ]; then
        # relativeFile がディレクトリの場合: そのディレクトリ内のリンク先も含めて収集
        base_dir="${workspaceFolder}/${relativeFile}"

        # 1) Markdown や YAML に埋め込まれたリンク資産を抽出
        mapfile -d '' -t files_linked < <(
            find "${base_dir}" -maxdepth 1 -type f -name "*.md" -print0 | \
            xargs -0 cat | \
            grep -oE '\!\[.*?\]\((.*?)\)|\[[^\]]*\]\((.*?)\)' | \
            sed -E 's/\!\[.*?\]\((.*?)\)/\1/;s/\[[^\]]*\]\((.*?)\)/\1/' | \
            grep -vE '\.(md|yaml)$' | \
            while IFS= read -r line; do
                printf '%s\0' "${base_dir}/$line"
            done
        )

        # 2) ディレクトリ直下のすべてのファイルを追加
        mapfile -d '' -t additional_files < <(
            find "${base_dir}" -maxdepth 1 -type f -print0
        )

        # 3) マージ＆ソート＆重複排除
        mapfile -d '' -t files_raw_initial < <(
            printf '%s\0' "${files_linked[@]}" "${additional_files[@]}" | sort -z -u
        )

    else
        # relativeFile が単一ファイルの場合: そのファイル＋リンク先ファイルを抽出
        mapfile -d '' -t files_linked < <(
            grep -oE '\!\[.*?\]\((.*?)\)|\[[^\]]*\]\((.*?)\)' "${workspaceFolder}/${relativeFile}" | \
            sed -E 's/\!\[.*?\]\((.*?)\)/\1/;s/\[[^\]]*\]\((.*?)\)/\1/' | \
            grep -vE '\.(md|yaml)$' | \
            while IFS= read -r path; do
                printf '%s\0' "${base_dir}/${path}"
            done
        )

        # マージ＆ソート＆重複排除 (単一ファイル自身も含める)
        mapfile -d '' -t files_raw_initial < <(
            printf '%s\0' "${files_linked[@]}" "${workspaceFolder}/${relativeFile}" | sort -z -u
        )
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
        # レコード全体を一度に読み込んで、
        # "\x00\x00\x00<パス>\x00" にマッチする箇所だけを取り出す
        while (/\x00\x00\x00([^\x00]+)\x00/g) {
            print "$1\0";
        }
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
            mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir"
        done
        publish_file="html/${file#${workspaceFolder}/${mdRoot}/}"

        # NOTE: OpenAPI ファイルは発行時に同梱すべきかと考えたため、コピーを行う(除外処理をしない)
        if [[ "$file" != *.md ]] ; then
            # コンテンツのコピー
            echo "Processing Other file: ${file#${workspaceFolder}/}"
            for langElement in ${lang}; do
                copy_if_different_timestamp "$file" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_file"
            done
        fi
    fi
done

# CSS の配置
for langElement in ${lang}; do
    copy_if_different_timestamp "${htmlStyleSheet}" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/html/html-style.css"
done

for file in "${files[@]}"; do
    if [[ "$file" == *.yaml ]] || [[ "$file" == *.json ]]; then # TODO: OpenAPI ファイルを .yaml 拡張子で判断してよいかどうかは怪しい。ファイル内に"openapi:"があることくらいは見たほうがいい。
        
        # FIXME: markdown ファイルとの重複処理は統合すべき。
        echo "Processing OpenAPI file for html: ${file#${workspaceFolder}/}"

        # html
        publish_dir=$(dirname "${file}")
        if [[ "$publish_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir=html/${publish_dir#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir=html
        fi
        publish_file=html/${file#${workspaceFolder}/${mdRoot}/}

        # path to css
        nest_count=$(echo "$publish_file" | grep -o '/' | wc -l)
        up_dir=""
        for ((i=2; i<=nest_count; i++)); do
            up_dir+="../"
        done

        # NOTE: --code true を取り除き、--language_tabs http --language_tabs shell --omitHeader のように与えるとサンプルコードを出力できる。shell, http, javascript, ruby, python, php, java, go
        # TODO: --user_templates の切替機構未実装
        openapi_md=$(${WIDDERSHINS} --code true --user_templates ${HOME_DIR}/styles/widdershins/openapi3 --omitHeader "$file" | sed '1,/^<!--/ d')

        openapi_md_title=$(echo "$openapi_md" | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

        firstLang=""
        for langElement in ${lang}; do
            echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
            if [ "$firstLang" == "" ]; then
                printf "\e[33m" # 文字色を黄色に設定
                echo "${openapi_md}" | \
                    ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --metadata title="$openapi_md_title" -f markdown+hard_line_breaks \
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
                firstLang="${langElement}"
            else
                cp -p "${workspaceFolder}/${pubRoot}/${firstLang}${details_suffix}/${publish_file%.*}.html" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
            fi
        done

        publish_dir_self_contain=$(dirname "${file}")
        if [[ "$publish_dir_self_contain" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_self_contain="html-self-contain/${publish_dir_self_contain#${workspaceFolder}/${mdRoot}/}"
        else
            publish_dir_self_contain="html-self-contain"
        fi
        for langElement in ${lang}; do
            mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir_self_contain"
        done
        publish_file_self_contain="html-self-contain/${file#${workspaceFolder}/${mdRoot}/}"

        firstLang=""
        for langElement in ${lang}; do
            echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
            if [ "$firstLang" == "" ]; then
                printf "\e[33m" # 文字色を黄色に設定
                echo "${openapi_md}" | \
                    ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --metadata title="$openapi_md_title" -f markdown+hard_line_breaks \
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
                firstLang="${langElement}"
            else
                cp -p "${workspaceFolder}/${pubRoot}/${firstLang}${details_suffix}/${publish_file_self_contain%.*}.html" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
            fi
        done

    elif [[ "$file" == *.md ]]; then
        # .md ファイルの処理
        echo "Processing Markdown file for html: ${file#${workspaceFolder}/}"

        # html
        publish_dir=$(dirname "${file}")
        if [[ "$publish_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir=html/${publish_dir#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir=html
        fi
        publish_file=html/${file#${workspaceFolder}/${mdRoot}/}

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

        for langElement in ${lang}; do
            # Markdown の最初にコメントがあると、--shift-heading-level-by=-1 を使った title の抽出に失敗するので
            # 独自に抽出を行う。コードのリファクタリングがなされておらず冗長だが動作はする。
            md_title=$(cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | perl -0777 -pe 's/<!--.*?-->//gs' | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

            echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.html"
            # Markdown の最初にコメントがあると、レベル1のタイトルを取り除くことができない。sed '/^# /d' で取り除く。
            printf "\e[33m" # 文字色を黄色に設定
            cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | sed '/^# /d' | \
                ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --metadata title="$md_title" -f markdown+hard_line_breaks \
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
        done

        publish_dir_self_contain=$(dirname "${file}")
        if [[ "$publish_dir_self_contain" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_self_contain="html-self-contain/${publish_dir_self_contain#${workspaceFolder}/${mdRoot}/}"
        else
            publish_dir_self_contain="html-self-contain"
        fi
        for langElement in ${lang}; do
            mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir_self_contain"
        done
        publish_file_self_contain="html-self-contain/${file#${workspaceFolder}/${mdRoot}/}"

        for langElement in ${lang}; do
            # Markdown の最初にコメントがあると、--shift-heading-level-by=-1 を使った title の抽出に失敗するので
            # 独自に抽出を行う。コードのリファクタリングがなされておらず冗長だが動作はする。
            md_title=$(cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | perl -0777 -pe 's/<!--.*?-->//gs' | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

            echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file_self_contain%.*}.html"
            # Markdown の最初にコメントがあると、レベル1のタイトルを取り除くことができない。sed '/^# /d' で取り除く。
            printf "\e[33m" # 文字色を黄色に設定
            cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | sed '/^# /d' | \
                ${PANDOC} -s ${htmlTocOption} --shift-heading-level-by=-1 -N --metadata title="$md_title" -f markdown+hard_line_breaks \
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
        done
    fi
done

for file in "${files[@]}"; do
    if [[ "$file" == *.yaml ]] || [[ "$file" == *.json ]]; then # TODO: OpenAPI ファイルを .yaml 拡張子で判断してよいかどうかは怪しい。ファイル内に"openapi:"があることくらいは見たほうがいい。
        
        # FIXME: markdown ファイルとの重複処理は統合すべき。
        echo "Processing OpenAPI file for docx: ${file#${workspaceFolder}/}"

        # docx
        publish_dir=$(dirname "${file}")
        if [[ "$publish_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
            resource_dir=html/${publish_dir#${workspaceFolder}/${mdRoot}/}
            publish_dir=docx/${publish_dir#${workspaceFolder}/${mdRoot}/}
        else
            resource_dir=html
            publish_dir=docx
        fi
        for langElement in ${lang}; do
            mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir"
        done
        publish_file=docx/${file#${workspaceFolder}/${mdRoot}/}

        # NOTE: --code true を取り除き、--language_tabs http --language_tabs shell --omitHeader のように与えるとサンプルコードを出力できる。shell, http, javascript, ruby, python, php, java, go
        # TODO: --user_templates の切替機構未実装
        openapi_md=$(${WIDDERSHINS} --code true --user_templates ${HOME_DIR}/styles/widdershins/openapi3 --omitHeader "$file" | sed '1,/^<!--/ d')

        openapi_md_title=$(echo "$openapi_md" | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

        firstLang=""
        for langElement in ${lang}; do
            echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.docx"
            if [ "$firstLang" == "" ]; then
                printf "\e[33m" # 文字色を黄色に設定
                echo "${openapi_md}" | \
                    ${PANDOC} -s --shift-heading-level-by=-1 --metadata title="$openapi_md_title" -f markdown+hard_line_breaks \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-meta.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/mermaid.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/replace-table-br.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-docx.lua" \
                        --lua-filter="${SCRIPT_DIR}/pandoc-filters/codeblock-caption.lua" \
                        ${PANDOC_CROSSREF} \
                        --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$resource_dir" \
                        --wrap=none -t docx --reference-doc="${docxTemplate}" -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.docx"
                printf "\e[0m" # 文字色を通常に設定
                firstLang="${langElement}"
            else
                cp -p "${workspaceFolder}/${pubRoot}/${firstLang}${details_suffix}/${publish_file%.*}.docx" "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.docx"
            fi
        done

    elif [[ "$file" == *.md ]]; then
        # .md ファイルの処理
        echo "Processing Markdown file for docx: ${file#${workspaceFolder}/}"

        # docx
        publish_dir=$(dirname "${file}")
        if [[ "$publish_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
            resource_dir=html/${publish_dir#${workspaceFolder}/${mdRoot}/}
            publish_dir=docx/${publish_dir#${workspaceFolder}/${mdRoot}/}
        else
            resource_dir=html
            publish_dir=docx
        fi
        for langElement in ${lang}; do
            mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$publish_dir"
        done
        publish_file=docx/${file#${workspaceFolder}/${mdRoot}/}

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

        for langElement in ${lang}; do
            # Markdown の最初にコメントがあると、--shift-heading-level-by=-1 を使った title の抽出に失敗するので
            # 独自に抽出を行う。コードのリファクタリングがなされておらず冗長だが動作はする。
            md_title=$(cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | perl -0777 -pe 's/<!--.*?-->//gs' | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')
            
            echo "  > ${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.docx"
            # Markdown の最初にコメントがあると、レベル1のタイトルを取り除くことができない。sed '/^# /d' で取り除く。
            printf "\e[33m" # 文字色を黄色に設定
            cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | sed '/^# /d' | \
                ${PANDOC} -s --shift-heading-level-by=-1 --metadata title="$md_title" -f markdown+hard_line_breaks \
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
                    --resource-path="${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/$resource_dir" \
                    --wrap=none -t docx --reference-doc="${docxTemplate}" -o "${workspaceFolder}/${pubRoot}/${langElement}${details_suffix}/${publish_file%.*}.docx"
            printf "\e[0m" # 文字色を通常に設定
        done
    fi
done

exit 0
