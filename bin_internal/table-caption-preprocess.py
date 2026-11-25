#!/usr/bin/env python3
"""Pandoc に渡す Markdown の表のキャプション (Table: 段落) を並べ替える前処理。

標準入力の Markdown を、前置きの Table: を表の後ろへ並べ替えて標準出力へ書く。
規則は table_caption_position.prepare_for_pandoc を参照。警告は標準エラー出力へ
書く。処理中に例外が発生した場合は、入力をそのまま出力する。

使い方: table-caption-preprocess.py [警告に表示するファイル名] < input.md > output.md
"""

import os
import sys

# 埋め込み版 Python (._pth) はスクリプトのディレクトリを sys.path に入れないため、明示的に追加する。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from table_caption_position import prepare_for_pandoc  # noqa: E402


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "(stdin)"
    stdin = sys.stdin.buffer.read().decode("utf-8")
    text = stdin.replace("\r\n", "\n")
    try:
        output, warnings = prepare_for_pandoc(text)
    except Exception as exc:  # 前処理の失敗で発行を止めない
        sys.stderr.write(f"[table-caption-preprocess] {name}: 前処理に失敗したため、入力をそのまま使います: {exc}\n")
        output, warnings = text, []
    for message in warnings:
        sys.stderr.buffer.write(f"[table-caption-preprocess] {name}: {message}\n".encode("utf-8"))
    sys.stdout.buffer.write(output.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
