#!/bin/bash

SCRIPT_DIR=$(cd $(dirname $0); pwd)
HOME_DIR=$(cd $SCRIPT_DIR; cd ..; pwd) # bin フォルダの上位が home
PATH=$PATH:$SCRIPT_DIR
cd $HOME_DIR

mkdir -p target
rm -rf target/*

mkdir -p "target/ja/html"
mkdir -p "target/en/html"
cp -p "bin/styles/html-style.css" "target/ja/html"
cp -p "bin/styles/html-style.css" "target/en/html"

# get file list
files=`find "src" -type f`

for file in $files; do

    target_dir=$(dirname ${file})
    if [[ "$target_dir" != "src" ]]; then
        target_dir=html/${target_dir#src/}
    else
        target_dir=html
    fi
    mkdir -p "target/ja/$target_dir"
    mkdir -p "target/en/$target_dir"
    target_file=html/${file#src/}

    if [[ "$file" == *.md ]]; then
        # .md ファイルの処理
        echo "Processing Markdown file for html: $file"
        # html

        # path to css
        nest_count=$(echo "$file" | grep -o '/' | wc -l)
        up_dir=""
        for ((i=2; i<=nest_count; i++)); do
            up_dir+="../"
        done

        # TODO: --self-contained を指定しているので、すべての処理が終わったら html ファイル以外は削除してもよい。
        #       正確には、--self-contained は別の成果物として扱う必要があろう。

        # ja
        sed -e "s/<!--en:-->/<!--en:/" -e "s/<!--:en-->/:en-->/" -e "s/<!--ja:[^-]/<!--ja:-->/" -e "s/[^-]:ja-->/<!--:ja-->/" -e "s/<!--ja:$/<!--ja:-->/" -e "s/^:ja-->/<!--:ja-->/" "$file" | \
            pandoc.exe -s --toc --toc-depth=2 --shift-heading-level-by=-1 -N -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --template="bin/styles/html-template.html" -c "${up_dir}html-style.css" --resource-path="target/ja/$target_dir" --wrap=none -t html --self-contained -o "target/ja/${target_file%.*}.html"
        # en
        sed -e "s/<!--ja:-->/<!--ja:/" -e "s/<!--:ja-->/:ja-->/" -e "s/<!--en:[^-]/<!--en:-->/" -e "s/[^-]:en-->/<!--:en-->/" -e "s/<!--en:$/<!--en:-->/" -e "s/^:en-->/<!--:en-->/" "$file" | \
            pandoc.exe -s --toc --toc-depth=2 --shift-heading-level-by=-1 -N -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --template="bin/styles/html-template.html" -c "${up_dir}html-style.css" --resource-path="target/en/$target_dir" --wrap=none -t html --self-contained -o "target/en/${target_file%.*}.html"
    else
        # その他の拡張子の処理
        echo "Processing Other file: $file"
        cp -p "$file" "target/ja/$target_file"
        cp -p "$file" "target/en/$target_file"
    fi
done

for file in $files; do
    if [[ "$file" == *.md ]]; then
        # .md ファイルの処理B
        echo "Processing Markdown file for docx: $file"
        # docx
        target_dir=$(dirname ${file})
        if [[ "$target_dir" != "src" ]]; then
            resource_dir=html/${target_dir#src/}
            target_dir=docx/${target_dir#src/}
        else
            resource_dir=html
            target_dir=docx
        fi
        mkdir -p "target/ja/$target_dir"
        mkdir -p "target/en/$target_dir"
        target_file=docx/${file#src/}
        # ja
        sed -e "s/<!--en:-->/<!--en:/" -e "s/<!--:en-->/:en-->/" -e "s/<!--ja:[^-]/<!--ja:-->/" -e "s/[^-]:ja-->/<!--:ja-->/" -e "s/<!--ja:$/<!--ja:-->/" -e "s/^:ja-->/<!--:ja-->/" "$file" | \
            pandoc.exe -s --shift-heading-level-by=-1 -N -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-docx.lua" --resource-path="target/ja/$resource_dir" --wrap=none -t docx --reference-doc="bin/styles/docx-style.dotx" -o "target/ja/${target_file%.*}.docx"
        # en
        sed -e "s/<!--ja:-->/<!--ja:/" -e "s/<!--:ja-->/:ja-->/" -e "s/<!--en:[^-]/<!--en:-->/" -e "s/[^-]:en-->/<!--:en-->/" -e "s/<!--en:$/<!--en:-->/" -e "s/^:en-->/<!--:en-->/" "$file" | \
            pandoc.exe -s --shift-heading-level-by=-1 -N -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-docx.lua" --resource-path="target/en/$resource_dir" --wrap=none -t docx --reference-doc="bin/styles/docx-style.dotx" -o "target/en/${target_file%.*}.docx"
    fi
done
