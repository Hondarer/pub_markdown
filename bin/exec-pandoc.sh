#!/bin/bash

SCRIPT_DIR=$(cd $(dirname $0); pwd)
HOME_DIR=$(cd $SCRIPT_DIR; cd ..; pwd) # bin フォルダの上位が home
PATH=$PATH:$SCRIPT_DIR
cd $HOME_DIR

mkdir -p target
rm -rf target/*

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
        #html
        # ja
        sed -e "s/<!--en:-->/<!--en:/" -e "s/<!--:en-->/:en-->/" -e "s/<!--ja:[^-]/<!--ja:-->/" -e "s/[^-]:ja-->/<!--:ja-->/" -e "s/<!--ja:$/<!--ja:-->/" -e "s/^:ja-->/<!--:ja-->/" "$file" | pandoc.exe -s -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --resource-path="target/ja/$target_dir" --wrap=none -t html --metadata title="${file%.*}" -o "target/ja/${target_file%.*}.html"
        # en
        sed -e "s/<!--ja:-->/<!--ja:/" -e "s/<!--:ja-->/:ja-->/" -e "s/<!--en:[^-]/<!--en:-->/" -e "s/[^-]:en-->/<!--:en-->/" -e "s/<!--en:$/<!--en:-->/" -e "s/^:en-->/<!--:en-->/" "$file" | pandoc.exe -s -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-html.lua" --resource-path="target/en/$target_dir" --wrap=none -t html --metadata title="${file%.*}" -o "target/en/${target_file%.*}.html"
    else
        # その他の拡張子の処理
        echo "Processing Other file: $file"
        cp -p "$file" "target/ja/$target_file"
        cp -p "$file" "target/en/$target_file"
    fi
done

for file in $files; do
    if [[ "$file" == *.md ]]; then
        # .md ファイルの処理
        echo "Processing Markdown file for docx: $file"
        #docx
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
        sed -e "s/<!--en:-->/<!--en:/" -e "s/<!--:en-->/:en-->/" -e "s/<!--ja:[^-]/<!--ja:-->/" -e "s/[^-]:ja-->/<!--:ja-->/" -e "s/<!--ja:$/<!--ja:-->/" -e "s/^:ja-->/<!--:ja-->/" "$file" | pandoc.exe -s -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-docx.lua" --resource-path="target/ja/$resource_dir" --wrap=none -t docx --reference-doc="bin/styles/docx-style.dotx" -o "target/ja/${target_file%.*}.docx"
        # en
        sed -e "s/<!--ja:-->/<!--ja:/" -e "s/<!--:ja-->/:ja-->/" -e "s/<!--en:[^-]/<!--en:-->/" -e "s/[^-]:en-->/<!--:en-->/" -e "s/<!--en:$/<!--en:-->/" -e "s/^:en-->/<!--:en-->/" "$file" | pandoc.exe -s -f markdown+hard_line_breaks --lua-filter="bin/pandoc-filters/plantuml.lua" --lua-filter="bin/pandoc-filters/link-to-docx.lua" --resource-path="target/en/$resource_dir" --wrap=none -t docx --reference-doc="bin/styles/docx-style.dotx" -o "target/en/${target_file%.*}.docx"
    fi
done
