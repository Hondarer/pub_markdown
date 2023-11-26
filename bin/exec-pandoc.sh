#!/bin/bash

SCRIPT_DIR=$(cd $(dirname $0); pwd)
HOME_DIR=$(cd $SCRIPT_DIR; cd ..; pwd) # bin フォルダの上位が home
PATH=$PATH:$SCRIPT_DIR
cd $HOME_DIR

mkdir -p publish
rm -rf publish/*

mkdir -p "publish/ja/html"
mkdir -p "publish/en/html"
cp -p "bin/styles/html/html-style.css" "publish/ja/html"
cp -p "bin/styles/html/html-style.css" "publish/en/html"

# get file list (配列に格納)
files_raw=`find "src" -type f`
IFS=$'
' read -r -d '' -a files <<< $files_raw

for file in "${files[@]}"; do
    publish_dir=$(dirname "${file}")
    if [[ "$publish_dir" != "src" ]]; then
        publish_dir=html/${publish_dir#src/}
    else
        publish_dir=html
    fi
    mkdir -p "publish/ja/$publish_dir"
    mkdir -p "publish/en/$publish_dir"
    publish_file=html/${file#src/}

    # MEMO: コピー不要なファイルがあれば、ここに追記していく
    if [[ "$file" != *.md ]] && [[ "${file##*/}" != .gitignore ]] && [[ "${file##*/}" != .gitkeep ]]; then
        # コンテンツのコピー
        echo "Processing Other file: $file"
        cp -p "$file" "publish/ja/$publish_file"
        cp -p "$file" "publish/en/$publish_file"
    fi
done

for file in "${files[@]}"; do
    if [[ "$file" == *.md ]]; then
        # .md ファイルの処理
        echo "Processing Markdown file for html: $file"
        # html

        publish_dir=$(dirname ${file})
        if [[ "$publish_dir" != "src" ]]; then
            publish_dir=html/${publish_dir#src/}
        else
            publish_dir=html
        fi
        publish_file=html/${file#src/}

        # path to css
        nest_count=$(echo "$file" | grep -o '/' | wc -l)
        up_dir=""
        for ((i=2; i<=nest_count; i++)); do
            up_dir+="../"
        done

        # ja
        sed -e "s/<!--en:-->/<!--en:/" -e "s/<!--:en-->/:en-->/" -e "s/<!--ja:[^-]/<!--ja:-->/" -e "s/[^-]:ja-->/<!--:ja-->/" -e "s/<!--ja:$/<!--ja:-->/" -e "s/^:ja-->/<!--:ja-->/" "$file" | \
            pandoc.exe -s --toc --toc-depth=2 --shift-heading-level-by=-1 -N --metadata date="`date -R`" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --template="bin/styles/html/html-template.html" -c "${up_dir}html-style.css" --resource-path="publish/ja/$publish_dir" --wrap=none -t html -o "publish/ja/${publish_file%.*}.html"
        # en
        sed -e "s/<!--ja:-->/<!--ja:/" -e "s/<!--:ja-->/:ja-->/" -e "s/<!--en:[^-]/<!--en:-->/" -e "s/[^-]:en-->/<!--:en-->/" -e "s/<!--en:$/<!--en:-->/" -e "s/^:en-->/<!--:en-->/" "$file" | \
            pandoc.exe -s --toc --toc-depth=2 --shift-heading-level-by=-1 -N --metadata date="`date -R`" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --template="bin/styles/html/html-template.html" -c "${up_dir}html-style.css" --resource-path="publish/en/$publish_dir" --wrap=none -t html -o "publish/en/${publish_file%.*}.html"

        publish_dir_self_contain=$(dirname ${file})
        if [[ "$publish_dir_self_contain" != "src" ]]; then
            publish_dir_self_contain=html-self-contain/${publish_dir_self_contain#src/}
        else
            publish_dir_self_contain=html-self-contain
        fi
        mkdir -p "publish/ja/$publish_dir_self_contain"
        mkdir -p "publish/en/$publish_dir_self_contain"
        publish_file_self_contain=html-self-contain/${file#src/}

        # ja (self_contain)
        sed -e "s/<!--en:-->/<!--en:/" -e "s/<!--:en-->/:en-->/" -e "s/<!--ja:[^-]/<!--ja:-->/" -e "s/[^-]:ja-->/<!--:ja-->/" -e "s/<!--ja:$/<!--ja:-->/" -e "s/^:ja-->/<!--:ja-->/" "$file" | \
            pandoc.exe -s --toc --toc-depth=2 --shift-heading-level-by=-1 -N --metadata date="`date -R`" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --template="bin/styles/html-self-contain/html-template.html" -c "${up_dir}html-style.css" --resource-path="publish/ja/$publish_dir" --wrap=none -t html --embed-resources --standalone -o "publish/ja/${publish_file_self_contain%.*}.html"
        # en (self_contain)
        sed -e "s/<!--ja:-->/<!--ja:/" -e "s/<!--:ja-->/:ja-->/" -e "s/<!--en:[^-]/<!--en:-->/" -e "s/[^-]:en-->/<!--:en-->/" -e "s/<!--en:$/<!--en:-->/" -e "s/^:en-->/<!--:en-->/" "$file" | \
            pandoc.exe -s --toc --toc-depth=2 --shift-heading-level-by=-1 -N --metadata date="`date -R`" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --template="bin/styles/html-self-contain/html-template.html" -c "${up_dir}html-style.css" --resource-path="publish/en/$publish_dir" --wrap=none -t html --embed-resources --standalone -o "publish/en/${publish_file_self_contain%.*}.html"
    fi
done

for file in "${files[@]}"; do
    if [[ "$file" == *.md ]]; then
        # .md ファイルの処理
        echo "Processing Markdown file for docx: $file"
        # docx
        publish_dir=$(dirname ${file})
        if [[ "$publish_dir" != "src" ]]; then
            resource_dir=html/${publish_dir#src/}
            publish_dir=docx/${publish_dir#src/}
        else
            resource_dir=html
            publish_dir=docx
        fi
        mkdir -p "publish/ja/$publish_dir"
        mkdir -p "publish/en/$publish_dir"
        publish_file=docx/${file#src/}
        # ja
        sed -e "s/<!--en:-->/<!--en:/" -e "s/<!--:en-->/:en-->/" -e "s/<!--ja:[^-]/<!--ja:-->/" -e "s/[^-]:ja-->/<!--:ja-->/" -e "s/<!--ja:$/<!--ja:-->/" -e "s/^:ja-->/<!--:ja-->/" "$file" | \
            pandoc.exe -s --shift-heading-level-by=-1 -N --metadata date="`date -R`" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-docx.lua" --resource-path="publish/ja/$resource_dir" --wrap=none -t docx --reference-doc="bin/styles/docx/docx-style.dotx" -o "publish/ja/${publish_file%.*}.docx"
        # en
        sed -e "s/<!--ja:-->/<!--ja:/" -e "s/<!--:ja-->/:ja-->/" -e "s/<!--en:[^-]/<!--en:-->/" -e "s/[^-]:en-->/<!--:en-->/" -e "s/<!--en:$/<!--en:-->/" -e "s/^:en-->/<!--:en-->/" "$file" | \
            pandoc.exe -s --shift-heading-level-by=-1 -N --metadata date="`date -R`" -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/fix-line-break.lua" --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-docx.lua" --resource-path="publish/en/$resource_dir" --wrap=none -t docx --reference-doc="bin/styles/docx/docx-style.dotx" -o "publish/en/${publish_file%.*}.docx"
    fi
done
