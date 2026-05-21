#!/bin/bash

# make docs 関連ログから warning 行のみを抽出して warn ファイルに保存する
# Extract warning lines from make docs related logs and save them to a warn file.

set -u

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <log_file> <warn_file>" >&2
    exit 1
fi

log_file="$1"
warn_file="$2"
tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

# 各行末の CR を除去する
sed $'s/\r$//' "$log_file" > "$tmpfile"

# 黄色で囲まれた行（ESC[33m ... ESC[0m）を抽出し、ANSI コードを除去して保存
sed -n 's/.*\x1b\[33m\(.*\)\x1b\[0m.*/\1/p' "$tmpfile" > "$warn_file" 2>/dev/null || true

# 既存の warning キーワードも併せて抽出（互換性維持）
sed 's/\x1b\[[0-9;]*[mK]//g' "$tmpfile" | \
    grep -Ei '(: warning:?|: 警告:|\[warning\]|^warning:|^警告:)' >> "$warn_file" 2>/dev/null || true

# 重複を削除してソート
if [ -s "$warn_file" ]; then
    sort -u "$warn_file" -o "$warn_file"
fi

if [ ! -s "$warn_file" ]; then
    rm -f "$warn_file"
fi
