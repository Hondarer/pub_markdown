#!/bin/bash

SCRIPT_DIR=$(cd $(dirname "$0"); pwd)
HOME_DIR=$(cd $SCRIPT_DIR; cd ..; pwd) # bin フォルダの上位が home
PATH=$PATH:$SCRIPT_DIR
cd $HOME_DIR

EXEC_DATE=`date -R`

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspaceFolder=*)
            workspaceFolder="${1#*=}"
            workspaceFolder="${workspaceFolder//\\/\/}"
            shift
        ;;
        --relativeFile=*)
            relativeFile="${1#*=}"
            relativeFile="${relativeFile//\\/\/}"
            shift
        ;;
        *)
            shift
        ;;
    esac
done

#-------------------------------------------------------------------

# キーを指定して値を取得する関数
parse_yaml() {
  local yaml="$1"
  local key="$2"
  local value=$(echo "$yaml" | awk -v k="$key" 'BEGIN {FS=":"} $1 == k {sub(/[ \t]*#.*$/, "", $2); sub(/^[ \t]+/, "", $2); print $2}')
  echo "$value"
}

# 定義ファイルのパス
config_path="${workspaceFolder}/.vscode/pub_markdown.config.yaml"

if [ -f "$config_path" ]; then

    # ファイルの内容を読み込む
    config_content=$(cat "$config_path")

    # キーを指定して値を取得する
    mdRoot=$(parse_yaml "$config_content" "mdRoot")
    details=$(parse_yaml "$config_content" "details")
    lang=$(parse_yaml "$config_content" "lang")

else

    mdRoot="doc"
    details="false"
    lang="ja en"

fi

#-------------------------------------------------------------------

if [[ -n $relativeFile && $relativeFile != ${mdRoot}/* ]]; then
    echo "Error: relativeFile does not start with '${mdRoot}/'. Exiting."
    exit 1
fi

if [ -n "$relativeFile" ]; then
    base_dir="${workspaceFolder}/$(dirname "$relativeFile")"
else
    base_dir="${workspaceFolder}/${mdRoot}"
    # 出力フォルダの clean
    mkdir -p "${workspaceFolder}/publish"
    # workspaceFolder に空白文字が含まれている可能性を考慮して、配下のファイルを clean する
    find "${workspaceFolder}/publish" -mindepth 1 -exec rm -rf {} +

    for langElement in ${lang}; do
        mkdir -p "${workspaceFolder}/publish/${langElement}/html"
        cp -p "${SCRIPT_DIR}/styles/html/html-style.css" "${workspaceFolder}/publish/${langElement}/html"
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
        echo "Processing Other file: ${src_file#${workspaceFolder}/}"
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
    echo "Processing Other file: ${src_file#${workspaceFolder}/}"
    cp -p "$src_file" "$dest_file"
    return 0
}

#-------------------------------------------------------------------

# get file list (配列に格納)
files_raw=$(find "${base_dir}" -type f)
IFS=$'\n' read -r -d '' -a files <<< "$files_raw"

for file in "${files[@]}"; do
    publish_dir=$(dirname "${file}")
    if [[ "$publish_dir" != "${workspaceFolder}/${mdRoot}" ]]; then
        publish_dir=html/${publish_dir#${workspaceFolder}/${mdRoot}/}
    else
        publish_dir=html
    fi

    for langElement in ${lang}; do
        mkdir -p "${workspaceFolder}/publish/${langElement}/$publish_dir"
    done
    publish_file=html/${file#${workspaceFolder}/${mdRoot}/}

    # NOTE: OpenAPI ファイルは発行時に同梱すべきかと考えたため、コピーを行う(除外処理をしない)
    if [[ "$file" != *.md ]] && [[ "${file##*/}" != .gitignore ]] && [[ "${file##*/}" != .gitkeep ]]; then
        # コンテンツのコピー
        for langElement in ${lang}; do
            copy_if_different_timestamp "$file" "${workspaceFolder}/publish/${langElement}/$publish_file"
        done
    fi
done

# 個別 md が指定されていたら、ターゲットを個別設定
if [ -n "$relativeFile" ]; then
  files=("${workspaceFolder}/${relativeFile}")
fi

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
        openapi_md=$(${SCRIPT_DIR}/widdershins/widdershins.exe --code true --omitHeader "$file")

        openapi_md_title=$(echo "$openapi_md" | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

        firstLang=""
        for langElement in ${lang}; do
            if [ "$firstLang" == "" ]; then
                echo "${openapi_md}" | \
                    pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$openapi_md_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" --template="${SCRIPT_DIR}/styles/html/html-template.html" -c "${up_dir}html-style.css" --resource-path="${workspaceFolder}/publish/${langElement}/$publish_dir" --wrap=none -t html -o "${workspaceFolder}/publish/${langElement}/${publish_file%.*}.html"
                firstLang=${langElement}
            else
                cp -p "${workspaceFolder}/publish/${firstLang}/${publish_file%.*}.html" "${workspaceFolder}/publish/${langElement}/${publish_file%.*}.html"
            fi
        done

        publish_dir_self_contain=$(dirname "${file}")
        if [[ "$publish_dir_self_contain" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_self_contain=html-self-contain/${publish_dir_self_contain#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir_self_contain=html-self-contain
        fi
        for langElement in ${lang}; do
            mkdir -p "${workspaceFolder}/publish/${langElement}/$publish_dir_self_contain"
        done
        publish_file_self_contain=html-self-contain/${file#${workspaceFolder}/${mdRoot}/}

        firstLang=""
        for langElement in ${lang}; do
            if [ "$firstLang" == "" ]; then
                echo "${openapi_md}" | \
                    pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$openapi_md_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" --template="${SCRIPT_DIR}/styles/html-self-contain/html-template.html" -c "${workspaceFolder}/publish/${langElement}/html/html-style.css" --resource-path="${workspaceFolder}/publish/${langElement}/$publish_dir" --wrap=none -t html --embed-resources --standalone -o "${workspaceFolder}/publish/${langElement}/${publish_file_self_contain%.*}.html"
               firstLang=${langElement}
            else
                cp -p "${workspaceFolder}/publish/${firstLang}/${publish_file_self_contain%.*}.html" "${workspaceFolder}/publish/${langElement}/${publish_file_self_contain%.*}.html"
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

        for langElement in ${lang}; do
            # Markdown の最初にコメントがあると、--shift-heading-level-by=-1 を使った title の抽出に失敗するので
            # 独自に抽出を行う。コードのリファクタリングがなされておらず冗長だが動作はする。
            md_title=$(cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | perl -0777 -pe 's/<!--.*?-->//gs' | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

            cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | \
                pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$md_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" --template="${SCRIPT_DIR}/styles/html/html-template.html" -c "${up_dir}html-style.css" --resource-path="${workspaceFolder}/publish/${langElement}/$publish_dir" --wrap=none -t html -o "${workspaceFolder}/publish/${langElement}/${publish_file%.*}.html"
        done

        publish_dir_self_contain=$(dirname "${file}")
        if [[ "$publish_dir_self_contain" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_self_contain=html-self-contain/${publish_dir_self_contain#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir_self_contain=html-self-contain
        fi
        for langElement in ${lang}; do
            mkdir -p "${workspaceFolder}/publish/${langElement}/$publish_dir_self_contain"
        done
        publish_file_self_contain=html-self-contain/${file#${workspaceFolder}/${mdRoot}/}

        for langElement in ${lang}; do
            # Markdown の最初にコメントがあると、--shift-heading-level-by=-1 を使った title の抽出に失敗するので
            # 独自に抽出を行う。コードのリファクタリングがなされておらず冗長だが動作はする。
            md_title=$(cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | perl -0777 -pe 's/<!--.*?-->//gs' | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

            cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | \
                pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$md_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" --template="${SCRIPT_DIR}/styles/html-self-contain/html-template.html" -c "${workspaceFolder}/publish/${langElement}/html/html-style.css" --resource-path="${workspaceFolder}/publish/${langElement}/$publish_dir" --wrap=none -t html --embed-resources --standalone -o "${workspaceFolder}/publish/${langElement}/${publish_file_self_contain%.*}.html"
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
            mkdir -p "${workspaceFolder}/publish/${langElement}/$publish_dir"
        done
        publish_file=docx/${file#${workspaceFolder}/${mdRoot}/}

        # NOTE: --code true を取り除き、--language_tabs http --language_tabs shell --omitHeader のように与えるとサンプルコードを出力できる。shell, http, javascript, ruby, python, php, java, go
        openapi_md=$(${SCRIPT_DIR}/widdershins/widdershins.exe --code true --omitHeader "$file")

        openapi_md_title=$(echo "$openapi_md" | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

        firstLang=""
        for langElement in ${lang}; do
            if [ "$firstLang" == "" ]; then
                echo "${openapi_md}" | \
                    pandoc.exe -s --shift-heading-level-by=-1 -N --metadata title="$openapi_md_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-docx.lua" --resource-path="${workspaceFolder}/publish/${langElement}/$resource_dir" --wrap=none -t docx --reference-doc="${SCRIPT_DIR}/styles/docx/docx-style.dotx" -o "${workspaceFolder}/publish/${langElement}/${publish_file%.*}.docx" 2>&1 | \
                    grep -a -v "rsvg-convert: createProcess: does not exist (No such file or directory)"
               firstLang=${langElement}
            else
                cp -p "${workspaceFolder}/publish/${firstLang}/${publish_file%.*}.docx" "${workspaceFolder}/publish/${langElement}/${publish_file%.*}.docx"
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
            mkdir -p "${workspaceFolder}/publish/${langElement}/$publish_dir"
        done
        publish_file=docx/${file#${workspaceFolder}/${mdRoot}/}

        for langElement in ${lang}; do
            # Markdown の最初にコメントがあると、--shift-heading-level-by=-1 を使った title の抽出に失敗するので
            # 独自に抽出を行う。コードのリファクタリングがなされておらず冗長だが動作はする。
            md_title=$(cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | perl -0777 -pe 's/<!--.*?-->//gs' | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')
            
            cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | \
                pandoc.exe -s --shift-heading-level-by=-1 -N --metadata title="$md_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-docx.lua" --resource-path="${workspaceFolder}/publish/${langElement}/$resource_dir" --wrap=none -t docx --reference-doc="${SCRIPT_DIR}/styles/docx/docx-style.dotx" -o "${workspaceFolder}/publish/${langElement}/${publish_file%.*}.docx" 2>&1 | \
                grep -a -v "rsvg-convert: createProcess: does not exist (No such file or directory)"
        done
    fi
done

exit 0
