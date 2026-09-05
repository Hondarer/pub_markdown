#!/usr/bin/env python3
"""発行者と発行日時の文字列を組み立てる。

docsfw の ``bin/get_file_author.sh``、``bin/get_file_date.sh`` と
``bin/pandoc-filters/set-meta.lua`` が作る文字列を、そのまま再現します。
同じページについて、静的発行と動的発行が同一の文字列を出すことが要件です。

git は呼びません。材料は ``git_link.PublishFacts`` として受け取ります。

設計は docs/publish-info.md を参照。
"""

from __future__ import annotations

import email.utils
import os


def format_author(names):
    """コミッター名の並びを、静的発行と同じ 1 行の文字列へ整形する。

    ``set-meta.lua`` と同じく、人数に応じて表現を変えます。

    - 1 名: ``登録者``
    - 2 名: ``登録者, 編集者``
    - 3 名以上: ``登録者, 最終編集者 et al.``

    空の並びには空文字を返します。
    """
    ordered = [name for name in (names or []) if name]
    if not ordered:
        return ""
    if len(ordered) == 1:
        return ordered[0]
    if len(ordered) == 2:
        return "{}, {}".format(ordered[0], ordered[1])
    return "{}, {} et al.".format(ordered[0], ordered[-1])


def file_mtime_rfc2822(real_path):
    """ファイルの最終更新時刻を RFC2822 で返す。取得できなければ空文字。

    ``get_file_date.sh`` の ``LC_TIME=C date -R -r`` と同じ書式です。
    ``email.utils.formatdate`` は曜日と月名を英語の短縮形で出すため、
    ロケールに依存せず C ロケールの ``date -R`` と一致します。
    """
    try:
        mtime = os.path.getmtime(real_path)
    except OSError:
        return ""
    return email.utils.formatdate(mtime, localtime=True)


def build_author(facts):
    """``PublishFacts`` から発行者の文字列を組み立てる。

    未コミット差分があれば、``get_file_author.sh`` と同じく現在のユーザー名を
    末尾へ足し、重複を排除します。追跡済みでないパスは空文字です。
    """
    if not facts.tracked:
        return ""

    names = [name for name in facts.authors if name]
    if facts.dirty and facts.user_name:
        if facts.user_name in names:
            names.remove(facts.user_name)
        names.append(facts.user_name)

    return format_author(names)


def build_date(real_path, facts):
    """``PublishFacts`` から発行日時と最終コミット ID の文字列を組み立てる。

    ``get_file_date.sh`` と同じ 3 分岐です。日時とコミット ID は 1 つの文字列に
    連結し、未コミット差分がある場合はコミット ID の末尾へ ``+`` を付けます。

    - 追跡済み・差分なし: ``<コミッター日時> <短縮 SHA>``
    - 追跡済み・差分あり: ``<ファイル mtime> <短縮 SHA>+``
    - 未追跡 / Git 管理外: ``<ファイル mtime>``
    """
    if not facts.tracked or not facts.short_sha:
        return file_mtime_rfc2822(real_path)

    if facts.dirty:
        mtime = file_mtime_rfc2822(real_path)
        if not mtime:
            return ""
        return "{} {}+".format(mtime, facts.short_sha)

    if not facts.committer_date:
        return file_mtime_rfc2822(real_path)

    return "{} {}".format(facts.committer_date, facts.short_sha)


def build_publish_info(real_path, facts, auto_author=True, auto_date=True):
    """``(発行者, 発行日時)`` を返す。無効にした側は空文字。"""
    author = build_author(facts) if auto_author else ""
    date = build_date(real_path, facts) if auto_date else ""
    return author, date
