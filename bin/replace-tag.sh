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
    split(supported_langs, langs, ",");
    in_code_block = 0;
    in_skip = 0;
    skip_key = "";

    # 有効なキーセットを初期化 (1: 有効、0: 無効)
    # details キー
    valid_keys["details"] = (details == "true") ? 1 : 0;
    # 言語キー (対象言語のみ有効)
    for (i in langs) {
        valid_keys[langs[i]] = (langs[i] == lang) ? 1 : 0;
    }
}

{
    # CRLF 対応: 行末の \r を除去
    gsub(/\r$/, "");

    # コードブロック追跡 (skip 中でも追跡して状態がずれないようにする)
    if (/^```/) in_code_block = !in_code_block;

    # コードブロック内: skip 中でなければそのまま出力
    if (in_code_block) {
        if (!in_skip) print $0;
        next;
    }

    # ステップ 1: 不完全なタグを補正 (コードブロック外のみ)
    # 行全体が <!--key: の形式 → <!--key:-->
    if (/^<!--[a-z]+:$/) {
        key = substr($0, 5, length($0) - 5);
        $0 = "<!--" key ":-->";
    }
    # 行全体が :key--> の形式 → <!--:key-->
    if (/^:[a-z]+-->$/) {
        key = substr($0, 2, length($0) - 4);
        $0 = "<!--:" key "-->";
    }

    # ステップ 2: 開始タグ <!--key:--> の処理
    if (/^<!--[a-z]+:-->$/) {
        key = substr($0, 5, length($0) - 8);
        if (key in valid_keys) {
            if (!valid_keys[key]) {
                # 無効なキー: 削除モードに入る
                in_skip = 1;
                skip_key = key;
            }
            # 有効・無効どちらもタグ行は出力しない
            next;
        }
    }

    # ステップ 2: 終了タグ <!--:key--> の処理
    if (/^<!--:[a-z]+-->$/) {
        key = substr($0, 6, length($0) - 8);
        if (key in valid_keys) {
            if (in_skip && key == skip_key) {
                # 削除モードを終了
                in_skip = 0;
                skip_key = "";
            }
            # 有効・無効どちらもタグ行は出力しない
            next;
        }
    }

    # 削除モード中は出力しない
    if (in_skip) next;

    print $0;
}' <<< "$markdown_text")

echo "$markdown_text"
exit
