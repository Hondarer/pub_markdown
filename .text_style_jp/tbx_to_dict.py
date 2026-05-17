#!/usr/bin/env python3
"""
tbx_to_dict.py - Microsoft tbx 用語集から md_style_jp 用辞書ファイルを生成する

Usage:
    # デフォルト: スクリプトと同じディレクトリの JAPANESE.tbx を読み込み、
    #            同ディレクトリに 10_microsoft.json を出力する
    python3 tbx_to_dict.py

    # パスを明示する場合
    python3 tbx_to_dict.py --tbx /path/to/JAPANESE.tbx --output /path/to/out.json

Input:
    JAPANESE.tbx  - Microsoft Terminology Collection (tbx 形式)
                    tbx ファイルのダウンロード元 (Downloading Microsoft Terminology):
                    https://download.microsoft.com/download/b/2/d/b2db7a7c-8d33-47f3-b2c1-ee5e6445cf45/MicrosoftTermCollection.zip
                    Web ベースの用語検索 (Microsoft Terminology Search):
                    https://msit.powerbi.com/view?r=eyJrIjoiODJmYjU4Y2YtM2M0ZC00YzYxLWE1YTktNzFjYmYxNTAxNjQ0IiwidCI6IjcyZjk4OGJmLTg2ZjEtNDFhZi05MWFiLTJkN2NkMDExZGI0NyIsImMiOjV9

Output:
    10_microsoft.json  - md_style_jp 用辞書ファイル
                         no_space:  tbx 単独カタカナ語の許可リスト (長さ ≥ 3)
                                    Sudachi B モードの過剰分割を抑制するために使う
                         replace:   末尾 ー 省略形 → Microsoft 標準形 (順方向)
                                    + ー 付き形が tbx 未登録の場合に ー 削除形へ正規化 (逆方向)
                         add_space: スペースなし複合語 → Microsoft 標準形（スペース区切り）

    tbx 未収録の社内独自カタカナ語は別ファイル (例: 90_local-katakana.json) で補う前提とする。
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

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
    """tbx ファイルをストリームパースし、日本語カタカナ単語と複合語を収集する。

    Returns:
        tuple[set[str], set[str], set[str], set[str]]:
            - all_words:   tbx に登場する全カタカナ単語（スペースなし、複合語の構成要素も含む）
            - eer_words:   ー で終わるカタカナ単語
            - compounds:   スペース区切りの全カタカナ複合語
            - singletons:  単独語として tbx に登録されたカタカナ語（スペース無し）
    """
    all_words = set()
    eer_words = set()
    compounds = set()
    singletons = set()
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
                    elif is_pure_katakana(text):
                        singletons.add(text)
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

    return all_words, eer_words, compounds, singletons


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
        all_words: tbx 全カタカナ単語の集合

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


def is_safe_reverse_replace(from_word, to_word, all_words):
    """逆方向 (ー 付き → ー なし) replace の安全性を確認する。

    順方向と同様、from_word の直後が ー 以外で始まる別の語の接頭辞になっている場合は
    誤変換になるため除外する。

    Args:
        from_word: 置換前の文字列（末尾が ー）
        to_word:   置換後の文字列（from_word から末尾の ー を除去したもの）
        all_words: tbx 全カタカナ単語の集合

    Returns:
        bool: True = 安全（辞書に含めてよい）、False = 危険（除外すべき）
    """
    flen = len(from_word)
    for word in all_words:
        if word == from_word:
            continue
        if not word.startswith(from_word):
            continue
        if len(word) <= flen:
            continue
        # from_word より長く、from_word で始まる別の語が存在する
        # 例: from_word = "メモリー", word = "メモリーリーク" のようなケース
        # 直後が ー 以外なら誤変換になる
        if word[flen] != "ー":
            return False
    return True


def collect_eer_ending_chars(eer_words):
    """ー で終わる tbx 単独語の、ー の直前 1 文字の集合を返す。

    この集合は「Microsoft が ー 付与を採用した語末音」のサンプルとして使う。
    逆方向 replace の生成対象を「同じ音で終わる語」に限定することで、
    実用上発生し得ない変換 (例: アイスー → アイス) の生成を抑制する。
    """
    return {w[-2] for w in eer_words if len(w) >= 2}


def build_reverse_replace_pairs(singletons, all_words, eer_words):
    """ー 付き形が tbx に登録されていない単独語から逆方向 replace ペアを生成する。

    from = w + "ー"  (ー 付きの非標準形)
    to   = w          (tbx 単独語、Microsoft 標準形)

    生成条件:
      1. w が tbx 単独語に存在し、末尾が ー でない
      2. w の末尾 1 文字が、tbx の eer_words の ー 直前文字集合に含まれる
         (= Microsoft が同じ音で ー 付与を採用しているパターンに合致)
      3. w + "ー" が tbx の単独語にも複合語構成要素にも存在しない (all_words に無い)
      4. is_safe_reverse_replace を満たす (接頭辞衝突なし)

    例: カテゴリ ◯, カテゴリー ✗ → {from: "カテゴリー", to: "カテゴリ"}
    例: メモリ ◯, メモリー ✗ → {from: "メモリー", to: "メモリ"}

    両方存在する場合 (例: コンピュータ / コンピューター) は条件 3 で除外され、
    順方向 replace に任せる。
    末尾音が ー 付与パターンと一致しない場合 (例: アイス、マウス) は条件 2 で除外する。
    """
    valid_endings = collect_eer_ending_chars(eer_words)

    pairs = []
    skipped = []
    for w in singletons:
        if not w or w.endswith("ー"):
            continue
        if w[-1] not in valid_endings:
            continue
        candidate = w + "ー"
        # ー 付き形が tbx 内に登録されていれば、両方標準として併存するためスキップ
        if candidate in all_words:
            continue
        if is_safe_reverse_replace(candidate, w, all_words):
            pairs.append({"from": candidate, "to": w})
        else:
            skipped.append((candidate, w))
    pairs.sort(key=lambda p: p["from"])
    return pairs, skipped


def build_no_space_words(singletons, all_words, min_length=3):
    """tbx 単独カタカナ語から no_space リストを生成する。

    SudachiPy モード B の過剰分割 (例: ワークスペース → ワーク スペース) を
    抑制するため、tbx 単独語のうち長さ min_length 以上を登録する。

    除外条件:
      - 長さ < min_length (短い語は他の合成語の接頭辞になりやすく誤マッチリスク大)
      - ー で終わらない単独語のうち、ー 付き形 (w + "ー") も tbx に存在するもの
        例: 「スライドショ」は singleton だが「スライドショー」も singleton
        ⇒ no_space に登録すると forward replace の ー 付与が阻害されるため除外

    Returns:
        list[str]: 長さ降順でソートされた no_space リスト
    """
    words = []
    for w in singletons:
        if len(w) < min_length:
            continue
        if not w.endswith("ー") and (w + "ー") in all_words:
            # ー 付き形が tbx に存在する = forward replace の対象なので、ー なし形は保護しない
            continue
        words.append(w)
    words.sort(key=lambda w: (-len(w), w))
    return words


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
    default_output = os.path.join(script_dir, "10_microsoft.json")

    parser = argparse.ArgumentParser(
        description="Microsoft tbx 用語集から md_style_jp 用辞書ファイルを生成する",
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
        help=f"tbx ファイルのパス (デフォルト: <スクリプトと同じディレクトリ>/JAPANESE.tbx)",
    )
    parser.add_argument(
        "--output", "-o",
        default=default_output,
        metavar="PATH",
        help=f"出力 JSON ファイルのパス (デフォルト: <スクリプトと同じディレクトリ>/10_microsoft.json)",
    )
    args = parser.parse_args()

    tbx_path = args.tbx
    output_path = args.output

    if not os.path.isfile(tbx_path):
        print(f"エラー: tbx ファイルが見つかりません: {tbx_path}", file=sys.stderr)
        sys.exit(1)

    print(f"tbx をパース中: {tbx_path}")
    all_words, eer_words, compounds, singletons = collect_katakana_words(tbx_path)
    print(f"  全カタカナ単語: {len(all_words)} 件")
    print(f"  単独カタカナ語: {len(singletons)} 件")
    print(f"  ー 終わりカタカナ単語: {len(eer_words)} 件")
    print(f"  カタカナ複合語: {len(compounds)} 件")

    forward_replace_pairs, forward_skipped = build_replace_pairs(eer_words, all_words)
    print(f"  順方向 replace ペア (ー 付与): {len(forward_replace_pairs)} 件 (除外: {len(forward_skipped)} 件)")
    if forward_skipped:
        print("  除外された語 (接頭辞衝突により誤変換の恐れあり):")
        for f, t in sorted(forward_skipped):
            print(f"    {f} → {t}")

    reverse_replace_pairs, reverse_skipped = build_reverse_replace_pairs(singletons, all_words, eer_words)
    print(f"  逆方向 replace ペア (ー 削除): {len(reverse_replace_pairs)} 件 (除外: {len(reverse_skipped)} 件)")
    if reverse_skipped:
        print("  逆方向で除外された語 (接頭辞衝突により誤変換の恐れあり):")
        for f, t in sorted(reverse_skipped):
            print(f"    {f} → {t}")

    # 順方向と逆方向を結合（順方向を先に置く: ー 付与は ー 削除より頻度が高く一般的）
    replace_pairs = forward_replace_pairs + reverse_replace_pairs

    no_space_words = build_no_space_words(singletons, all_words, min_length=3)
    print(f"  no_space 単独語 (長さ ≥ 3): {len(no_space_words)} 件")

    add_space_pairs = build_add_space_pairs(compounds)
    print(f"  add_space ペア: {len(add_space_pairs)} 件 (長さ降順でソート済み)")

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    data = {
        "_source": (
            "Microsoft Terminology Collection "
            "(Downloading Microsoft Terminology / Microsoft Terminology Search)"
        ),
        "_description": (
            "Microsoft 日本語スタイルガイドに基づくカタカナ語の表記ルール。"
            "源泉: tbx ファイルのダウンロード元は "
            "https://download.microsoft.com/download/b/2/d/b2db7a7c-8d33-47f3-b2c1-ee5e6445cf45/MicrosoftTermCollection.zip "
            "(Downloading Microsoft Terminology)、"
            "Web ベースの用語検索は "
            "https://msit.powerbi.com/view?r=eyJrIjoiODJmYjU4Y2YtM2M0ZC00YzYxLWE1YTktNzFjYmYxNTAxNjQ0IiwidCI6IjcyZjk4OGJmLTg2ZjEtNDFhZi05MWFiLTJkN2NkMDExZGI0NyIsImMiOjV9 "
            "(Microsoft Terminology Search)。"
            "no_space: tbx に単独語として登録されたカタカナ語 (長さ ≥ 3) の許可リスト。"
            "Sudachi B モードの過剰分割を抑制する。"
            "replace: 順方向 (ー 付与) は末尾 ー が省略された語を Microsoft 標準形に変換する。"
            "逆方向 (ー 削除) は ー 付き形が tbx 未登録の語 (例: カテゴリー → カテゴリ) を正規化する。"
            "add_space: スペースなしのカタカナ複合語を Microsoft 標準形（スペース区切り）に変換する。"
            "tbx 未収録の社内独自語は別の番号付き辞書 (例: 90_local-katakana.json) で補う。"
            "no_space と add_space は長さ降順に処理されるため prefix 衝突は自動的に解決される。"
        ),
        "no_space": no_space_words,
        "replace": replace_pairs,
        "add_space": add_space_pairs,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"出力完了: {output_path}")

    # 主要語の確認 (順方向 replace: ー 付与)
    key_terms = ["サーバー", "コンピューター", "プリンター", "フォルダー", "ドライバー",
                 "マネージャー", "ユーザー", "コントローラー", "モニター"]
    print("\n[順方向 replace] 主要語の収録確認:")
    forward_to_set = {p["to"] for p in forward_replace_pairs}
    for term in key_terms:
        found = term in eer_words
        in_pairs = term in forward_to_set
        status = "✓" if in_pairs else ("除外" if found else "なし")
        print(f"  [{status}] {term[:-1]} → {term}")

    # 主要語の確認 (逆方向 replace: ー 削除)
    key_reverse_terms = ["カテゴリ", "メモリ", "プロパティ", "ファクトリ", "リポジトリ", "ライブラリ"]
    print("\n[逆方向 replace] 主要語の収録確認:")
    reverse_from_map = {p["from"]: p["to"] for p in reverse_replace_pairs}
    for term in key_reverse_terms:
        candidate = term + "ー"
        if candidate in reverse_from_map:
            print(f"  ✓ {candidate} → {term}")
        elif term in singletons and candidate in all_words:
            print(f"  - {candidate} → {term} (両方標準のため逆方向は生成しない)")
        else:
            print(f"  - {candidate} → {term} (該当なし)")

    # no_space の確認
    key_singletons = [
        "トラブルシューティング", "インライン", "ワークスペース",
        "サブディレクトリ", "クロスプラットフォーム",
    ]
    print("\n[no_space] tbx 単独語の収録確認:")
    no_space_set = set(no_space_words)
    for term in key_singletons:
        status = "✓" if term in no_space_set else "なし"
        print(f"  [{status}] {term}")

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
