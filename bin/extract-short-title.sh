#!/bin/bash

# extract-short-title.sh - YAML フロントマターから short-title を解決するヘルパー
#
# このスクリプトは source 専用です。直接実行しないでください。
# 関数 extract_short_title を提供します。
#
# 呼び出し形式:
#   source "$(dirname "${BASH_SOURCE[0]}")/extract-short-title.sh"
#   result=$(extract_short_title <file> <lang> <details>)
#
# 優先順位 (details=true 時):
#   short-title-<lang>-details > short-title-<lang>
#                              > short-title-details > short-title
#
# 優先順位 (details=false 時):
#   short-title-<lang> > short-title
#
# <lang> が空または "neutral" の場合、言語別フィールドを参照しない。
# 値が見つからない場合は空文字を echo して終了コード 0 を返す。

# extract_short_title <file> <lang> <details>
# short-title 系フィールドを優先順位付きで探索し、見つかった値を echo する。
# 見つからなければ空文字を echo する。終了コードは常に 0。
extract_short_title() {
    local file_path="$1"
    local lang_code="${2:-}"
    local details="${3:-false}"

    if [[ ! -f "$file_path" ]]; then
        echo ""
        return 0
    fi

    # YAML フロントマターを抽出 (先頭 --- ~ 次の --- または ... まで)
    # CR を除去してから処理 (Windows 形式のファイルに対応)
    local frontmatter=""
    local in_fm=false
    local line_count=0
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"  # CR 除去
        ((line_count++))
        if [[ $line_count -eq 1 ]]; then
            if [[ "$line" == "---" ]]; then
                in_fm=true
            else
                # フロントマターなし
                break
            fi
            continue
        fi
        if [[ "$in_fm" == true ]]; then
            if [[ "$line" == "---" || "$line" == "..." ]]; then
                break
            fi
            frontmatter+="$line"$'\n'
        fi
        if [[ $line_count -ge 100 ]]; then
            break
        fi
    done < "$file_path"

    if [[ -z "$frontmatter" ]]; then
        echo ""
        return 0
    fi

    # フィールド候補リストを優先順位順に構築
    local candidates=()
    if [[ -n "$lang_code" && "$lang_code" != "neutral" ]]; then
        if [[ "$details" == "true" ]]; then
            candidates+=("short-title-${lang_code}-details")
        fi
        candidates+=("short-title-${lang_code}")
    fi
    if [[ "$details" == "true" ]]; then
        candidates+=("short-title-details")
    fi
    candidates+=("short-title")

    # 各候補を frontmatter から探索
    local key
    for key in "${candidates[@]}"; do
        # YAML 行: key: value または key: "value" または key: 'value'
        local raw_line
        raw_line=$(printf '%s' "$frontmatter" | grep -m1 "^${key}:[[:space:]]*")
        if [[ -z "$raw_line" ]]; then
            continue
        fi
        local value="${raw_line#${key}:}"
        # 前後空白除去
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"
        # 囲みダブルクォート除去
        if [[ "$value" =~ ^\"(.*)\"$ ]]; then
            value="${BASH_REMATCH[1]}"
        # 囲みシングルクォート除去
        elif [[ "$value" =~ ^\'(.*)\'$ ]]; then
            value="${BASH_REMATCH[1]}"
        fi
        # 空でなければ返す
        if [[ -n "$value" ]]; then
            echo "$value"
            return 0
        fi
    done

    echo ""
    return 0
}
