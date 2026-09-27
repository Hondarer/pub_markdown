#!/usr/bin/env python3
"""全文検索の索引を、通常版と詳細版に分けて書き出す。

mkdocs-material の search プラグインは、配信中の全ページを 1 つの
``search/search_index.json`` にまとめる。通常版と詳細版を同時に配信すると
索引が 2 倍になり、ブラウザーの検索 Worker が索引の構築で数百 MB を使う。
Worker はページと同じレンダラー プロセスで動くため、そのページから開いた
別ウインドウ (依存関係レポートなど) までメモリ不足になることがある。

この hook は search プラグインの後に動き、``<variant>/search/search_index.json``
へ版ごとの索引を書き出す。各ページは theme/main.html で ``__config.base`` を
版のルートへ向けるため、Material はその版の索引だけを読み込む。
索引内の ``location`` は版のルートからの相対パスに書き換える。
どの版にも属さないページは、ルートの索引に残す。
設計は docs/livedocs-design.md を参照。
"""

import json
import logging
import os

log = logging.getLogger("mkdocs.livedocs_search")

INDEX_PATH = os.path.join("search", "search_index.json")


def split_search_index(index, variants):
    """索引を版ごとに分け、``{版: 索引, None: 版に属さない索引}`` を返す。"""
    docs = index.get("docs") or []
    buckets = {variant: [] for variant in variants}
    buckets[None] = []
    for doc in docs:
        location = doc.get("location") or ""
        head, sep, rest = location.partition("/")
        if sep and head in buckets and head is not None:
            item = dict(doc)
            item["location"] = rest
            buckets[head].append(item)
        else:
            buckets[None].append(doc)
    result = {}
    for key, bucket in buckets.items():
        item = {k: v for k, v in index.items() if k != "docs"}
        item["docs"] = bucket
        result[key] = item
    return result


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))


def write_variant_indexes(site_dir, variants):
    """``site_dir`` の索引を版ごとに分割して書き出す。索引が無ければ何もしない。"""
    root_path = os.path.join(site_dir, INDEX_PATH)
    if not variants or not os.path.exists(root_path):
        return False
    with open(root_path, encoding="utf-8") as handle:
        index = json.load(handle)
    parts = split_search_index(index, variants)
    for variant in variants:
        _write_json(os.path.join(site_dir, variant, INDEX_PATH), parts[variant])
    _write_json(root_path, parts[None])
    log.debug(
        "search index split: %s",
        ", ".join("{}={}".format(v, len(parts[v]["docs"])) for v in variants),
    )
    return True


def on_post_build(config, **kwargs):
    extra = config.get("extra") or {}
    variants = [v for v in (extra.get("livedocs_variants") or []) if v]
    write_variant_indexes(config["site_dir"], variants)
