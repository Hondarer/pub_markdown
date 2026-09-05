#!/usr/bin/env python3
"""多言語タグと詳細タグを解決するフィルター。

``bin/replace-tag.sh`` の awk 実装を Python へ移植したものです。
766 ファイルごとにシェルを起動する負荷を避けるため、プロセス内で処理します。

タグの書式は次のとおりです。

    <!--ja:-->      … <!--:ja-->        言語ブロック
    <!--details:--> … <!--:details-->   詳細ブロック

対象外のキーを持つブロックは、タグ行ごと本文から取り除きます。
対象のキーを持つブロックは、タグ行だけを取り除いて中身を残します。
コード フェンス (```) の内側にあるタグは処理しません。
"""

import re

SUPPORTED_LANGS = ("ja", "en")

_FENCE_RE = re.compile(r"^```")
_OPEN_TAG_RE = re.compile(r"^<!--([a-z]+):-->$")
_CLOSE_TAG_RE = re.compile(r"^<!--:([a-z]+)-->$")
_BROKEN_OPEN_RE = re.compile(r"^<!--([a-z]+):$")
_BROKEN_CLOSE_RE = re.compile(r"^:([a-z]+)-->$")


def filter_lang_details(text, lang, details, supported_langs=SUPPORTED_LANGS):
    """``text`` から対象外の言語ブロックと詳細ブロックを取り除く。

    :param text: 対象の Markdown 本文。
    :param lang: 残す言語コード (``ja`` など)。
    :param details: 詳細ブロックを残す場合は ``True``。
    :param supported_langs: 言語タグとして解釈するキーの一覧。
    :return: フィルター後の Markdown 本文。
    """
    valid_keys = {key: (key == lang) for key in supported_langs}
    valid_keys["details"] = bool(details)

    out = []
    in_code_block = False
    skip_key = None

    for raw_line in text.split("\n"):
        line = raw_line.rstrip("\r")

        # コード フェンスの追跡は skip 中も続け、状態がずれないようにする。
        if _FENCE_RE.match(line):
            in_code_block = not in_code_block

        if in_code_block:
            if skip_key is None:
                out.append(line)
            continue

        # 不完全なタグを補正する。
        broken_open = _BROKEN_OPEN_RE.match(line)
        if broken_open:
            line = "<!--{}:-->".format(broken_open.group(1))
        broken_close = _BROKEN_CLOSE_RE.match(line)
        if broken_close:
            line = "<!--:{}-->".format(broken_close.group(1))

        open_tag = _OPEN_TAG_RE.match(line)
        if open_tag:
            key = open_tag.group(1)
            if key in valid_keys:
                if not valid_keys[key]:
                    skip_key = key
                # 有効でも無効でもタグ行自体は出力しない。
                continue

        close_tag = _CLOSE_TAG_RE.match(line)
        if close_tag:
            key = close_tag.group(1)
            if key in valid_keys:
                if skip_key is not None and key == skip_key:
                    skip_key = None
                continue

        if skip_key is not None:
            continue

        out.append(line)

    return "\n".join(out)


def has_lang_or_details_tags(text):
    """``text`` が言語タグまたは詳細タグを含むかどうかを返す。"""
    for raw_line in text.split("\n"):
        line = raw_line.rstrip("\r")
        if _OPEN_TAG_RE.match(line) or _CLOSE_TAG_RE.match(line):
            return True
        if _BROKEN_OPEN_RE.match(line) or _BROKEN_CLOSE_RE.match(line):
            return True
    return False
