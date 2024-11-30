#!/bin/bash

SCRIPT_DIR=$(cd $(dirname "$0"); pwd)
HOME_DIR=$(cd $SCRIPT_DIR; cd ..; pwd) # bin フォルダの上位が home
PATH=$PATH:$SCRIPT_DIR
cd $HOME_DIR

export EXEC_DATE=`date -R`

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
    pubRoot=$(parse_yaml "$config_content" "pubRoot")
    details=$(parse_yaml "$config_content" "details")
    lang=$(parse_yaml "$config_content" "lang")
    htmlStyleSheet=$(parse_yaml "$config_content" "htmlStyleSheet")
    htmlTemplate=$(parse_yaml "$config_content" "htmlTemplate")
    htmlSelfContainTemplate=$(parse_yaml "$config_content" "htmlSelfContainTemplate")
    docxTemplate=$(parse_yaml "$config_content" "docxTemplate")
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
        resolved_path="$(realpath "$workspaceFolder/$input_path")"
    fi

    echo "$resolved_path"
}

# 設定ファイルに htmlStyleSheet が指定されなかった場合の値を "$HOME_DIR/bin/styles/html/html-style.css" にする
if [[ "$htmlStyleSheet" == "" ]]; then
    htmlStyleSheet="$HOME_DIR/styles/html/html-style.css"
else
    htmlStyleSheet=$(resolve_path ${htmlStyleSheet})
fi
if [[ ! -e "$htmlStyleSheet" ]]; then
    echo "Error: Html style sheets file does not exist: $htmlStyleSheet"
    return 1
fi

# 設定ファイルに htmlTemplate が指定されなかった場合の値を "$HOME_DIR/bin/styles/html/html-template.html" にする
if [[ "$htmlTemplate" == "" ]]; then
    htmlTemplate="$HOME_DIR/styles/html/html-template.html"
else
    htmlTemplate=$(resolve_path ${htmlTemplate})
fi
if [[ ! -e "$htmlTemplate" ]]; then
    echo "Error: Html template file does not exist: $htmlTemplate"
    return 1
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
    return 1
fi

# 設定ファイルに docxTemplate が指定されなかった場合の値を "$HOME_DIR/styles/docx/docx-template.dotx" にする
if [[ "$docxTemplate" == "" ]]; then
    docxTemplate="$HOME_DIR/styles/docx/docx-template.dotx"
else
    docxTemplate=$(resolve_path ${docxTemplate})
fi
if [[ ! -e "$docxTemplate" ]]; then
    echo "Error: Docx template file does not exist: $docxTemplate"
    return 1
fi

#-------------------------------------------------------------------

if [[ -n $relativeFile && $relativeFile != ${mdRoot}/* ]]; then
    # NOTE: ワークスペース外のファイルの場合、ここでチェックアウトされる
    echo "Error: relativeFile does not start with '${mdRoot}/'. Exiting."
    exit 1
fi

if [ -n "$relativeFile" ]; then
    base_dir="${workspaceFolder}/$(dirname "$relativeFile")"
else
    base_dir="${workspaceFolder}/${mdRoot}"
    # 出力フォルダの clean
    mkdir -p "${workspaceFolder}/${pubRoot}"
    # workspaceFolder に空白文字が含まれている可能性を考慮して、配下のファイルを clean する
    find "${workspaceFolder}/${pubRoot}" -mindepth 1 -exec rm -rf {} +

    for langElement in ${lang}; do
        mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}/html"
        cp -p "${htmlStyleSheet}" "${workspaceFolder}/${pubRoot}/${langElement}/html/html-style.css"
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
        mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}/$publish_dir"
    done
    publish_file=html/${file#${workspaceFolder}/${mdRoot}/}

    # NOTE: OpenAPI ファイルは発行時に同梱すべきかと考えたため、コピーを行う(除外処理をしない)
    if [[ "$file" != *.md ]] && [[ "${file##*/}" != .gitignore ]] && [[ "${file##*/}" != .gitkeep ]]; then
        # コンテンツのコピー
        for langElement in ${lang}; do
            copy_if_different_timestamp "$file" "${workspaceFolder}/${pubRoot}/${langElement}/$publish_file"
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
                    pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$openapi_md_title" -f markdown+hard_line_breaks --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-date.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" --template="${htmlTemplate}" -c "${up_dir}html-style.css" --resource-path="${workspaceFolder}/${pubRoot}/${langElement}/$publish_dir" --wrap=none -t html -o "${workspaceFolder}/${pubRoot}/${langElement}/${publish_file%.*}.html"
                firstLang=${langElement}
            else
                cp -p "${workspaceFolder}/${pubRoot}/${firstLang}/${publish_file%.*}.html" "${workspaceFolder}/${pubRoot}/${langElement}/${publish_file%.*}.html"
            fi
        done

        publish_dir_self_contain=$(dirname "${file}")
        if [[ "$publish_dir_self_contain" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_self_contain=html-self-contain/${publish_dir_self_contain#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir_self_contain=html-self-contain
        fi
        for langElement in ${lang}; do
            mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}/$publish_dir_self_contain"
        done
        publish_file_self_contain=html-self-contain/${file#${workspaceFolder}/${mdRoot}/}

        firstLang=""
        for langElement in ${lang}; do
            if [ "$firstLang" == "" ]; then
                echo "${openapi_md}" | \
                    pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$openapi_md_title" -f markdown+hard_line_breaks --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-date.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" --template="${htmlSelfContainTemplate}" -c "${workspaceFolder}/${pubRoot}/${langElement}/html/html-style.css" --resource-path="${workspaceFolder}/${pubRoot}/${langElement}/$publish_dir" --wrap=none -t html --embed-resources --standalone -o "${workspaceFolder}/${pubRoot}/${langElement}/${publish_file_self_contain%.*}.html"
               firstLang=${langElement}
            else
                cp -p "${workspaceFolder}/${pubRoot}/${firstLang}/${publish_file_self_contain%.*}.html" "${workspaceFolder}/${pubRoot}/${langElement}/${publish_file_self_contain%.*}.html"
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

            # Markdown の最初にコメントがあると、レベル1のタイトルを取り除くことができない。sed '/^# /d' で取り除く。
            cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | sed '/^# /d' | \
                pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$md_title" -f markdown+hard_line_breaks --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-date.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" --template="${htmlTemplate}" -c "${up_dir}html-style.css" --resource-path="${workspaceFolder}/${pubRoot}/${langElement}/$publish_dir" --wrap=none -t html -o "${workspaceFolder}/${pubRoot}/${langElement}/${publish_file%.*}.html"
        done

        publish_dir_self_contain=$(dirname "${file}")
        if [[ "$publish_dir_self_contain" != "${workspaceFolder}/${mdRoot}" ]]; then
            publish_dir_self_contain=html-self-contain/${publish_dir_self_contain#${workspaceFolder}/${mdRoot}/}
        else
            publish_dir_self_contain=html-self-contain
        fi
        for langElement in ${lang}; do
            mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}/$publish_dir_self_contain"
        done
        publish_file_self_contain=html-self-contain/${file#${workspaceFolder}/${mdRoot}/}

        for langElement in ${lang}; do
            # Markdown の最初にコメントがあると、--shift-heading-level-by=-1 を使った title の抽出に失敗するので
            # 独自に抽出を行う。コードのリファクタリングがなされておらず冗長だが動作はする。
            md_title=$(cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | perl -0777 -pe 's/<!--.*?-->//gs' | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

            # Markdown の最初にコメントがあると、レベル1のタイトルを取り除くことができない。sed '/^# /d' で取り除く。
            cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | sed '/^# /d' | \
                pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$md_title" -f markdown+hard_line_breaks --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-date.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-html.lua" --template="${htmlSelfContainTemplate}" -c "${workspaceFolder}/${pubRoot}/${langElement}/html/html-style.css" --resource-path="${workspaceFolder}/${pubRoot}/${langElement}/$publish_dir" --wrap=none -t html --embed-resources --standalone -o "${workspaceFolder}/${pubRoot}/${langElement}/${publish_file_self_contain%.*}.html"
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
            mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}/$publish_dir"
        done
        publish_file=docx/${file#${workspaceFolder}/${mdRoot}/}

        # NOTE: --code true を取り除き、--language_tabs http --language_tabs shell --omitHeader のように与えるとサンプルコードを出力できる。shell, http, javascript, ruby, python, php, java, go
        openapi_md=$(${SCRIPT_DIR}/widdershins/widdershins.exe --code true --omitHeader "$file")

        openapi_md_title=$(echo "$openapi_md" | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

        firstLang=""
        for langElement in ${lang}; do
            if [ "$firstLang" == "" ]; then
                echo "${openapi_md}" | \
                    pandoc.exe -s --shift-heading-level-by=-1 -N --metadata title="$openapi_md_title" -f markdown+hard_line_breaks --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-date.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-docx.lua" --resource-path="${workspaceFolder}/${pubRoot}/${langElement}/$resource_dir" --wrap=none -t docx --reference-doc="${docxTemplate}" -o "${workspaceFolder}/${pubRoot}/${langElement}/${publish_file%.*}.docx"
               firstLang=${langElement}
            else
                cp -p "${workspaceFolder}/${pubRoot}/${firstLang}/${publish_file%.*}.docx" "${workspaceFolder}/${pubRoot}/${langElement}/${publish_file%.*}.docx"
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
            mkdir -p "${workspaceFolder}/${pubRoot}/${langElement}/$publish_dir"
        done
        publish_file=docx/${file#${workspaceFolder}/${mdRoot}/}

        for langElement in ${lang}; do
            # Markdown の最初にコメントがあると、--shift-heading-level-by=-1 を使った title の抽出に失敗するので
            # 独自に抽出を行う。コードのリファクタリングがなされておらず冗長だが動作はする。
            md_title=$(cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | perl -0777 -pe 's/<!--.*?-->//gs' | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')
            
            # Markdown の最初にコメントがあると、レベル1のタイトルを取り除くことができない。sed '/^# /d' で取り除く。
            cat "$file" | replace-tag.sh --lang=${langElement} --details=${details} | sed '/^# /d' | \
                pandoc.exe -s --shift-heading-level-by=-1 -N --metadata title="$md_title" -f markdown+hard_line_breaks --lua-filter="${SCRIPT_DIR}/pandoc-filters/set-date.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/fix-line-break.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/plantuml.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/pagebreak.lua" --lua-filter="${SCRIPT_DIR}/pandoc-filters/link-to-docx.lua" --resource-path="${workspaceFolder}/${pubRoot}/${langElement}/$resource_dir" --wrap=none -t docx --reference-doc="${docxTemplate}" -o "${workspaceFolder}/${pubRoot}/${langElement}/${publish_file%.*}.docx"
        done
    fi
done

exit 0
