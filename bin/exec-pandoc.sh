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
    lang="ja"

fi

#-------------------------------------------------------------------

if [[ -n $relativeFile && $relativeFile != ${mdRoot}/* ]]; then
    echo "Error: relativeFile does not start with '${mdRoot}/'. Exiting."
    exit 1
fi

if [ -n "$relativeFile" ]; then
    base_dir=$(dirname "$relativeFile")
else
    base_dir="${mdRoot}"
    
    # 出力フォルダの clean
    mkdir -p publish
    rm -rf publish/*
    
    mkdir -p "publish/ja/html"
    mkdir -p "publish/en/html"
    cp -p "bin/styles/html/html-style.css" "publish/ja/html"
    cp -p "bin/styles/html/html-style.css" "publish/en/html"
fi

# get file list (配列に格納)
files_raw=$(find "${base_dir}" -type f)
IFS=$'\n' read -r -d '' -a files <<< "$files_raw"

for file in "${files[@]}"; do
    publish_dir=$(dirname "${file}")
    if [[ "$publish_dir" != "${mdRoot}" ]]; then
        publish_dir=html/${publish_dir#${mdRoot}/}
    else
        publish_dir=html
    fi
    mkdir -p "publish/ja/$publish_dir"
    mkdir -p "publish/en/$publish_dir"
    publish_file=html/${file#${mdRoot}/}

    # NOTE: OpenAPI ファイルは発行時に同梱すべきかと考えたため、コピーを行う(除外処理をしない)
    if [[ "$file" != *.md ]] && [[ "${file##*/}" != .gitignore ]] && [[ "${file##*/}" != .gitkeep ]]; then
        # コンテンツのコピー
        echo "Processing Other file: $file"
        cp -p "$file" "publish/ja/$publish_file"
        cp -p "$file" "publish/en/$publish_file"
    fi
done

# 個別 md が指定されていたら、ターゲットを個別設定
if [ -n "$relativeFile" ]; then
  files=("$relativeFile")
fi

for file in "${files[@]}"; do
    if [[ "$file" == *.yaml ]] || [[ "$file" == *.json ]]; then # TODO: OpenAPI ファイルを .yaml 拡張子で判断してよいかどうかは怪しい。ファイル内に"openapi:"があることくらいは見たほうがいい。
        
        # FIXME: markdown ファイルとの重複処理は統合すべき。

        echo "Processing OpenAPI file for html: $file"
        # html
        publish_dir=$(dirname "${file}")
        if [[ "$publish_dir" != "${mdRoot}" ]]; then
            publish_dir=html/${publish_dir#${mdRoot}/}
        else
            publish_dir=html
        fi
        publish_file=html/${file#${mdRoot}/}

        # path to css
        nest_count=$(echo "$file" | grep -o '/' | wc -l)
        up_dir=""
        for ((i=2; i<=nest_count; i++)); do
            up_dir+="../"
        done

        # NOTE: --code true を取り除き、--language_tabs http --language_tabs shell --omitHeader のように与えるとサンプルコードを出力できる。shell, http, javascript, ruby, python, php, java, go
        openapi_md=$(${SCRIPT_DIR}/widdershins/widdershins.exe --code true --omitHeader "$file")

        ja_title=$(echo "$openapi_md" | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

        # ja
        echo "${openapi_md}" | \
            pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$ja_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/pagebreak.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --template="bin/styles/html/html-template.html" -c "${up_dir}html-style.css" --resource-path="publish/ja/$publish_dir" --wrap=none -t html -o "publish/ja/${publish_file%.*}.html"
        # en
        cp -p "publish/ja/${publish_file%.*}.html" "publish/en/${publish_file%.*}.html"

        publish_dir_self_contain=$(dirname "${file}")
        if [[ "$publish_dir_self_contain" != "${mdRoot}" ]]; then
            publish_dir_self_contain=html-self-contain/${publish_dir_self_contain#${mdRoot}/}
        else
            publish_dir_self_contain=html-self-contain
        fi
        mkdir -p "publish/ja/$publish_dir_self_contain"
        mkdir -p "publish/en/$publish_dir_self_contain"
        publish_file_self_contain=html-self-contain/${file#${mdRoot}/}

        # ja (self_contain)
        echo "${openapi_md}" | \
            pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$ja_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/pagebreak.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --template="bin/styles/html-self-contain/html-template.html" -c "${up_dir}html-style.css" --resource-path="publish/ja/$publish_dir" --wrap=none -t html --embed-resources --standalone -o "publish/ja/${publish_file_self_contain%.*}.html"
        # en (self_contain)
        cp -p "publish/ja/${publish_file_self_contain%.*}.html" "publish/en/${publish_file_self_contain%.*}.html"

    elif [[ "$file" == *.md ]]; then
        # .md ファイルの処理
        echo "Processing Markdown file for html: $file"
        # html
        publish_dir=$(dirname "${file}")
        if [[ "$publish_dir" != "${mdRoot}" ]]; then
            publish_dir=html/${publish_dir#${mdRoot}/}
        else
            publish_dir=html
        fi
        publish_file=html/${file#${mdRoot}/}

        # path to css
        nest_count=$(echo "$file" | grep -o '/' | wc -l)
        up_dir=""
        for ((i=2; i<=nest_count; i++)); do
            up_dir+="../"
        done

        # Markdown の最初にコメントがあると、--shift-heading-level-by=-1 を使った title の抽出に失敗するので
        # 独自に抽出を行う。コードのリファクタリングがなされておらず冗長だが動作はする。
        ja_title=$(cat "$file" | replace-tag.sh --lang=ja | perl -0777 -pe 's/<!--.*?-->//gs' | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')
        en_title=$(cat "$file" | replace-tag.sh --lang=ja | perl -0777 -pe 's/<!--.*?-->//gs' | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

        # ja
        cat "$file" | replace-tag.sh --lang=ja | \
            pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$ja_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/pagebreak.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --template="bin/styles/html/html-template.html" -c "${up_dir}html-style.css" --resource-path="publish/ja/$publish_dir" --wrap=none -t html -o "publish/ja/${publish_file%.*}.html"
        # en
        cat "$file" | replace-tag.sh --lang=en | \
            pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$en_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/pagebreak.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --template="bin/styles/html/html-template.html" -c "${up_dir}html-style.css" --resource-path="publish/en/$publish_dir" --wrap=none -t html -o "publish/en/${publish_file%.*}.html"

        publish_dir_self_contain=$(dirname "${file}")
        if [[ "$publish_dir_self_contain" != "${mdRoot}" ]]; then
            publish_dir_self_contain=html-self-contain/${publish_dir_self_contain#${mdRoot}/}
        else
            publish_dir_self_contain=html-self-contain
        fi
        mkdir -p "publish/ja/$publish_dir_self_contain"
        mkdir -p "publish/en/$publish_dir_self_contain"
        publish_file_self_contain=html-self-contain/${file#${mdRoot}/}

        # ja (self_contain)
        cat "$file" | replace-tag.sh --lang=ja | \
            pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$ja_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/pagebreak.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --template="bin/styles/html-self-contain/html-template.html" -c "${up_dir}html-style.css" --resource-path="publish/ja/$publish_dir" --wrap=none -t html --embed-resources --standalone -o "publish/ja/${publish_file_self_contain%.*}.html"
        # en (self_contain)
        cat "$file" | replace-tag.sh --lang=en | \
            pandoc.exe -s --toc --toc-depth=3 --shift-heading-level-by=-1 -N --metadata title="$en_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/pagebreak.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --template="bin/styles/html-self-contain/html-template.html" -c "${up_dir}html-style.css" --resource-path="publish/en/$publish_dir" --wrap=none -t html --embed-resources --standalone -o "publish/en/${publish_file_self_contain%.*}.html"
    fi
done

for file in "${files[@]}"; do
    if [[ "$file" == *.yaml ]] || [[ "$file" == *.json ]]; then # TODO: OpenAPI ファイルを .yaml 拡張子で判断してよいかどうかは怪しい。ファイル内に"openapi:"があることくらいは見たほうがいい。
        
        # FIXME: markdown ファイルとの重複処理は統合すべき。

        echo "Processing OpenAPI file for docx: $file"
        # docx
        publish_dir=$(dirname "${file}")
        if [[ "$publish_dir" != "${mdRoot}" ]]; then
            resource_dir=html/${publish_dir#${mdRoot}/}
            publish_dir=docx/${publish_dir#${mdRoot}/}
        else
            resource_dir=html
            publish_dir=docx
        fi
        mkdir -p "publish/ja/$publish_dir"
        mkdir -p "publish/en/$publish_dir"
        publish_file=docx/${file#${mdRoot}/}

        # NOTE: --code true を取り除き、--language_tabs http --language_tabs shell --omitHeader のように与えるとサンプルコードを出力できる。shell, http, javascript, ruby, python, php, java, go
        openapi_md=$(${SCRIPT_DIR}/widdershins/widdershins.exe --code true --omitHeader "$file")

        ja_title=$(echo "$openapi_md" | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

        # ja
        echo "${openapi_md}" | \
            pandoc.exe -s --shift-heading-level-by=-1 -N --metadata title="$ja_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/pagebreak.lua" --lua-filter="bin/pandoc-filters/link-to-docx.lua" --resource-path="publish/ja/$resource_dir" --wrap=none -t docx --reference-doc="bin/styles/docx/docx-style.dotx" -o "publish/ja/${publish_file%.*}.docx" 2>&1 | \
            grep -a -v "rsvg-convert: createProcess: does not exist (No such file or directory)"
        # en
        cp -p "publish/ja/${publish_file%.*}.docx" "publish/en/${publish_file%.*}.docx"

   elif [[ "$file" == *.md ]]; then
        # .md ファイルの処理
        echo "Processing Markdown file for docx: $file"
        # docx
        publish_dir=$(dirname "${file}")
        if [[ "$publish_dir" != "${mdRoot}" ]]; then
            resource_dir=html/${publish_dir#${mdRoot}/}
            publish_dir=docx/${publish_dir#${mdRoot}/}
        else
            resource_dir=html
            publish_dir=docx
        fi
        mkdir -p "publish/ja/$publish_dir"
        mkdir -p "publish/en/$publish_dir"
        publish_file=docx/${file#${mdRoot}/}

        # Markdown の最初にコメントがあると、--shift-heading-level-by=-1 を使った title の抽出に失敗するので
        # 独自に抽出を行う。コードのリファクタリングがなされておらず冗長だが動作はする。
        ja_title=$(cat "$file" | replace-tag.sh --lang=ja | perl -0777 -pe 's/<!--.*?-->//gs' | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')
        en_title=$(cat "$file" | replace-tag.sh --lang=ja | perl -0777 -pe 's/<!--.*?-->//gs' | sed -n '/^#/p' | head -n 1 | sed 's/^# *//')

        # ja
        cat "$file" | replace-tag.sh --lang=ja | \
            pandoc.exe -s --shift-heading-level-by=-1 -N --metadata title="$ja_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/pagebreak.lua" --lua-filter="bin/pandoc-filters/link-to-docx.lua" --resource-path="publish/ja/$resource_dir" --wrap=none -t docx --reference-doc="bin/styles/docx/docx-style.dotx" -o "publish/ja/${publish_file%.*}.docx" 2>&1 | \
            grep -a -v "rsvg-convert: createProcess: does not exist (No such file or directory)"
        # en
        cat "$file" | replace-tag.sh --lang=en | \
            pandoc.exe -s --shift-heading-level-by=-1 -N --metadata title="$en_title" --metadata date="$EXEC_DATE" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/pagebreak.lua" --lua-filter="bin/pandoc-filters/link-to-docx.lua" --resource-path="publish/en/$resource_dir" --wrap=none -t docx --reference-doc="bin/styles/docx/docx-style.dotx" -o "publish/en/${publish_file%.*}.docx" 2>&1 | \
            grep -a -v "rsvg-convert: createProcess: does not exist (No such file or directory)"
    fi
done

exit 0
