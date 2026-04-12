#!/usr/bin/env python3
"""
tbx_to_dict.py - Microsoft TBX 用語集から md_style_jp 用辞書ファイルを生成する

Usage:
    # デフォルト: スクリプトと同じディレクトリの JAPANESE.tbx を読み込み、
    #            同ディレクトリに microsoft.json を出力する
    python3 tbx_to_dict.py

    # パスを明示する場合
    python3 tbx_to_dict.py --tbx /path/to/JAPANESE.tbx --output /path/to/out.json

Input:
    JAPANESE.tbx  - Microsoft Terminology Collection (TBX 形式)
                    https://www.microsoft.com/en-us/language/terminology

Output:
    microsoft.json  - md_style_jp 用辞書ファイル
                      replace:   末尾 ー 省略形 → Microsoft 標準形
                      add_space: スペースなし複合語 → Microsoft 標準形（スペース区切り）
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

# カタカナ Unicode 範囲: U+30A0–U+30FF (ー U+30FC を含む)
_KATAKANA_MIN = 0x30A0
_KATAKANA_MAX = 0x30FF


def is_pure_katakana(s):
    """スペースも混じり文字も含まない、純粋なカタカナ単語かどうかを判定する。
    長さ 3 文字以上を有効とする（短すぎる語の誤変換を避けるため）。
    """
    if len(s) < 3:
        return False
    for c in s:
        if not (_KATAKANA_MIN <= ord(c) <= _KATAKANA_MAX):
            return False
    return True


def is_katakana_compound(s):
    """スペース区切りの全カタカナ複合語かどうかを判定する（2コンポーネント以上）。"""
    parts = s.split(" ")
    if len(parts) < 2:
        return False
    return all(is_pure_katakana(p) for p in parts)


def collect_katakana_words(tbx_path):
    """TBX ファイルをストリームパースし、日本語カタカナ単語と複合語を収集する。

    Returns:
        tuple[set[str], set[str], set[str]]:
            - all_words:   TBX に登場する全カタカナ単語（スペースなし）
            - eer_words:   ー で終わるカタカナ単語
            - compounds:   スペース区切りの全カタカナ複合語
    """
    all_words = set()
    eer_words = set()
    compounds = set()
    in_ja = False
    in_term = False

    for event, elem in ET.iterparse(tbx_path, events=("start", "end")):
        tag = elem.tag

        if event == "start":
            if tag == "langSet":
                lang = elem.get("{http://www.w3.org/XML/1998/namespace}lang") or elem.get("xml:lang", "")
                in_ja = lang.startswith("ja")
            elif tag == "term" and in_ja:
                in_term = True

        elif event == "end":
            if tag == "term" and in_term:
                text = (elem.text or "").strip()
                if text:
                    if is_katakana_compound(text):
                        compounds.add(text)
                    # 複合語はスペースで分割して各コンポーネントも収集
                    for part in text.split(" "):
                        if is_pure_katakana(part):
                            all_words.add(part)
                            if part.endswith("ー"):
                                eer_words.add(part)
                in_term = False
            elif tag == "langSet":
                in_ja = False

            # メモリ節約: 処理済み要素を解放
            elem.clear()

    return all_words, eer_words, compounds


def build_add_space_pairs(compounds):
    """スペース区切りカタカナ複合語から add_space ペアリストを生成する。

    from = スペースを除去した複合語（連結形）
    to   = スペース区切りの複合語（Microsoft 標準形）

    同じ from に複数の to が存在する場合（分割位置の揺れ）は、
    スペース数が最少のもの（最も保守的な分割）を採用する。

    処理は長い from から順に行われるため、prefix 衝突は自然に解決される。
    （add_space は JSON の記載順に適用されるため、長さ降順でソートして出力する）
    """
    from_map = {}  # from_word -> to_word (スペース数最少のものを保持)
    for compound in compounds:
        from_word = compound.replace(" ", "")
        # 同じ from に複数の to: スペース数（分割粒度）が少ない方を優先
        if from_word not in from_map:
            from_map[from_word] = compound
        else:
            existing = from_map[from_word]
            if existing.count(" ") > compound.count(" "):
                from_map[from_word] = compound

    # from の長さ降順でソート（長い複合語を先に処理してprefixの誤置換を防ぐ）
    pairs = [{"from": f, "to": t} for f, t in from_map.items()]
    pairs.sort(key=lambda p: len(p["from"]), reverse=True)
    return pairs


def is_safe_replace(from_word, to_word, all_words):
    """この replace エントリが誤変換を起こさないかを確認する。

    _replace_skip_existing は「from_word の位置に to_word が既存すればスキップ」する。
    したがって from_word の直後が ー で始まる語（例: メンバーシップ）は安全に処理できる。
    一方、from_word の直後が ー 以外の語（例: モニタリング）は誤変換となるため除外する。

    Args:
        from_word: 置換前の文字列
        to_word:   置換後の文字列（from_word + ー）
        all_words: TBX 全カタカナ単語の集合

    Returns:
        bool: True = 安全（辞書に含めてよい）、False = 危険（除外すべき）
    """
    flen = len(from_word)
    for word in all_words:
        if word == to_word:
            continue
        if not word.startswith(from_word):
            continue
        if len(word) <= flen:
            continue
        # from_word より長く、from_word で始まる別の語が存在する
        if word[flen] != "ー":
            # 直後が ー 以外 → _replace_skip_existing でも誤変換が発生する
            return False
    return True


def build_replace_pairs(eer_words, all_words):
    """ー 終わりカタカナ単語から replace ペアリストを生成する。

    from = 末尾の ー を除去した単語
    to   = 元の単語（Microsoft 標準形）

    誤変換が発生しうるエントリ（from_word が別のカタカナ語の接頭辞になる場合）は除外する。
    """
    pairs = []
    skipped = []
    for word in eer_words:
        from_word = word[:-1]   # 末尾の ー を除去
        if not from_word or from_word == word:
            continue
        if is_safe_replace(from_word, word, all_words):
            pairs.append({"from": from_word, "to": word})
        else:
            skipped.append((from_word, word))
    # from キーでソート（アルファベット順、実際はカタカナ順）
    pairs.sort(key=lambda p: p["from"])
    return pairs, skipped


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_tbx = os.path.join(script_dir, "JAPANESE.tbx")
    default_output = os.path.join(script_dir, "microsoft.json")

    parser = argparse.ArgumentParser(
        description="Microsoft TBX 用語集から md_style_jp 用辞書ファイルを生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "例:\n"
            "  python3 tbx_to_dict.py\n"
            "  python3 tbx_to_dict.py --tbx /path/to/JAPANESE.tbx\n"
            "  python3 tbx_to_dict.py --tbx /path/to/JAPANESE.tbx --output /path/to/out.json\n"
        ),
    )
    parser.add_argument(
        "--tbx",
        default=default_tbx,
        metavar="PATH",
        help=f"TBX ファイルのパス (デフォルト: <スクリプトと同じディレクトリ>/JAPANESE.tbx)",
    )
    parser.add_argument(
        "--output", "-o",
        default=default_output,
        metavar="PATH",
        help=f"出力 JSON ファイルのパス (デフォルト: <スクリプトと同じディレクトリ>/microsoft.json)",
    )
    args = parser.parse_args()

    tbx_path = args.tbx
    output_path = args.output

    if not os.path.isfile(tbx_path):
        print(f"エラー: TBX ファイルが見つかりません: {tbx_path}", file=sys.stderr)
        sys.exit(1)

    print(f"TBX をパース中: {tbx_path}")
    all_words, eer_words, compounds = collect_katakana_words(tbx_path)
    print(f"  全カタカナ単語: {len(all_words)} 件")
    print(f"  ー 終わりカタカナ単語: {len(eer_words)} 件")
    print(f"  カタカナ複合語: {len(compounds)} 件")

    replace_pairs, skipped = build_replace_pairs(eer_words, all_words)
    print(f"  replace ペア: {len(replace_pairs)} 件 (除外: {len(skipped)} 件)")
    if skipped:
        print("  除外された語 (接頭辞衝突により誤変換の恐れあり):")
        for f, t in sorted(skipped):
            print(f"    {f} → {t}")

    add_space_pairs = build_add_space_pairs(compounds)
    print(f"  add_space ペア: {len(add_space_pairs)} 件 (長さ降順でソート済み)")

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    data = {
        "_source": "Microsoft Terminology Collection (JAPANESE.tbx)",
        "_description": (
            "Microsoft 日本語スタイルガイドに基づくカタカナ語の表記ルール。"
            "replace: 末尾の ー が省略されたカタカナ語を Microsoft 標準形に変換する。"
            "add_space: スペースなしのカタカナ複合語を Microsoft 標準形（スペース区切り）に変換する。"
            "add_space は長さ降順に処理されるため prefix 衝突は自動的に解決される。"
        ),
        "replace": replace_pairs,
        "no_space": [],
        "add_space": add_space_pairs,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"出力完了: {output_path}")

    # 主要語の確認 (replace)
    key_terms = ["サーバー", "コンピューター", "プリンター", "フォルダー", "ドライバー",
                 "マネージャー", "ユーザー", "コントローラー", "モニター"]
    print("\n[replace] 主要語の収録確認:")
    for term in key_terms:
        found = term in eer_words
        in_pairs = any(p["to"] == term for p in replace_pairs)
        status = "✓" if in_pairs else ("除外" if found else "なし")
        print(f"  [{status}] {term[:-1]} → {term}")

    # add_space の確認
    key_compounds = [
        "ファイルマネージャー", "アイテムマネージャー", "アウトラインビュー",
        "ネットワークアダプター", "ユーザーインターフェイス",
    ]
    print("\n[add_space] 複合語サンプル:")
    as_map = {p["from"]: p["to"] for p in add_space_pairs}
    for term in key_compounds:
        if term in as_map:
            print(f"  ✓ \"{term}\" → \"{as_map[term]}\"")
        else:
            print(f"  - \"{term}\" (なし)")


if __name__ == "__main__":
    main()
