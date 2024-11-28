#!/bin/bash

details=false

# サポート対象の言語一覧
supported_langs=("ja" "en")

# パラメーターから言語名 (--lang=xx) と詳細出力フラグ (--details=true または --details=false) を受け取る
while [[ $# -gt 0 ]]; do
  case "$1" in
    --lang=*)
      lang="${1#*=}"
      shift
      ;;
    --details=*)
      details="${1#*=}"
      shift
      ;;
    *)
      shift
      ;;
  esac
done

# 言語がサポート対象でない場合はエラーを出力して終了
if [[ ! " ${supported_langs[@]} " =~ " ${lang} " ]]; then
  echo "Error: Unsupported language '${lang}'. Supported languages are: ${supported_langs[*]}" >&2
  exit 1
fi

# 標準入力から Markdown を読み込む
markdown_text=$(cat)

markdown_text=$(awk -v lang="$lang" -v details="$details" -v supported_langs="$(IFS=,; echo "${supported_langs[*]}")" '
BEGIN {
    # サポート対象の言語一覧を分割して配列に格納
    split(supported_langs, langs, ",");
}

{
    if (/^```/) {
        in_code_block = !in_code_block
    }

    if (in_code_block) {
        # 入力をそのまま出力する
        print $0
    } else {
        # サポートされている言語を処理
        for (i in langs) {
            current_lang = langs[i]
            if (current_lang == lang) {
                # 対象の言語の場合、言語タグをコメント化して内部を活かす
                $0 = gensub("<!--" current_lang ":([^\\-])", "<!--" current_lang ":-->\\1", "g")
                $0 = gensub("([^-]):" current_lang "-->", "\\1<!--:" current_lang "-->", "g")
                gsub("<!--" current_lang ":$", "<!--" current_lang ":-->")
                gsub("^:" current_lang "-->", "<!--:" current_lang "-->")
            } else {
                # 対象以外の言語は言語タグを使って内部をコメント化
                gsub("<!--" current_lang ":-->", "<!--" current_lang ":")
                gsub("<!--:" current_lang "-->", ":" current_lang "-->")
            }
        }

        # details フラグの処理
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
