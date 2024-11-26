#!/bin/bash

details=false

# パラメーターから言語名 (--lang=ja または --lang=en) と詳細出力フラグ (--details=true または --details=false) を受け取る
while [[ $# -gt 0 ]]; do
  case "$1" in
    --lang=*)
      lang="${1#*=}"
      shift
      ;;
    --details)
      details="${1#*=}"
      shift
      ;;
    *)
      shift
      ;;
  esac
done

# 標準入力から Markdown を読み込む
markdown_text=$(cat)

markdown_text=$(awk -v lang="$lang" -v details="$details" '
{
    if (/^```/) {
        in_code_block = !in_code_block
    }

    if (in_code_block) {
        # 入力をそのまま出力する
        print $0
    } else {
        
        if (lang == "ja") {
            gsub(/<!--en:-->/, "<!--en:")
            gsub(/<!--:en-->/, ":en-->")
            $0 = gensub(/<!--ja:([^-])/, "<!--ja:-->\\1", "g")
            $0 = gensub(/([^-]):ja-->/, "\\1<!--:ja-->", "g")
            gsub(/<!--ja:$/, "<!--ja:-->")
            gsub(/^:ja-->/, "<!--:ja-->")
        }
        if (lang == "en") {
            gsub(/<!--ja:-->/, "<!--ja:")
            gsub(/<!--:ja-->/, ":ja-->")
            $0 = gensub(/<!--en:([^-])/, "<!--en:-->\\1", "g")
            $0 = gensub(/([^-]):en-->/, "\\1<!--:en-->", "g")
            gsub(/<!--en:$/, "<!--en:-->")
            gsub(/^:en-->/, "<!--:en-->")
        }

        if (details == "true") {
            $0 = gensub(/<!--details:([^-])/, "<!--details:-->\\1", "g")
            $0 = gensub(/([^-]):details-->/, "\\1<!--:details-->", "g")
            gsub(/<!--details:$/, "<!--details:-->")
            gsub(/^:details-->/, "<!--:details-->")
        } else {
            gsub(/<!--details:-->/, "<!--details:")
            gsub(/<!--:details-->/, ":details-->")
        }

        print $0
    }
}' <<< "$markdown_text")

echo "$markdown_text"
exit
