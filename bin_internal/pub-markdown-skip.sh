#!/usr/bin/env bash

# Return success when a Markdown front matter sets pub_markdown.skip to true.
is_pub_markdown_skip() {
    local file="$1"
    local line
    local key
    local value
    local skip_flag_found=false
    local first_line=true

    [[ "$file" == *.md || "$file" == *.markdown ]] || return 1
    [[ -f "$file" ]] || return 1

    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        if [[ "$first_line" == "true" ]]; then
            first_line=false
            [[ "$line" =~ ^[[:space:]]*---[[:space:]]*$ ]] || return 1
            continue
        fi

        if [[ "$line" =~ ^[[:space:]]*---[[:space:]]*$ ]]; then
            [[ "$skip_flag_found" == "true" ]]
            return
        fi

        if [[ "$line" == *:* ]]; then
            key="${line%%:*}"
            value="${line#*:}"
            key="${key#"${key%%[![:space:]]*}"}"
            key="${key%"${key##*[![:space:]]}"}"
            value="${value%%#*}"
            value="${value#"${value%%[![:space:]]*}"}"
            value="${value%"${value##*[![:space:]]}"}"
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"
            value="${value,,}"

            if [[ "$key" == "pub_markdown.skip" && "$value" == "true" ]]; then
                skip_flag_found=true
            fi
        fi
    done < "$file"

    return 1
}
