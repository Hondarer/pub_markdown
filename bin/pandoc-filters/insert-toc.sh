#!/bin/bash

# insert-toc.sh - Markdown インデックス生成スクリプト
# 引数解釈と処理

# このスクリプト自身の場所を特定し、共有ヘルパーを読み込む
_INSERT_TOC_SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)
source "${_INSERT_TOC_SCRIPT_DIR}/../extract-short-title.sh"

source "${_INSERT_TOC_SCRIPT_DIR}/../pub-markdown-skip.sh"
# キャッシュファイルパス
CACHE_FILE="/tmp/insert-toc-cache.tsv"

# メモリ内キャッシュ (連想配列)
# キー: 絶対パス
# 値: "ファイル名\t種別\tベースタイトル\t言語別タイトル\tshort-titleキャッシュ"
# short-titleキャッシュ形式: "<key>:<value>|<key>:<value>" (key = lang または lang-details)
# 解決済みで値なし: "<key>:" (空値を保持してキャッシュ済みとマーク)
declare -A memory_cache

# ソート前キーリスト (順序付き配列)
declare -a unsorted_keys

# ソート済みキーリスト (順序付き配列)
declare -a sorted_keys

# キャッシュ変更フラグ
cache_modified=false
scan_output_base_dir=""

# 引数の取得
DEPTH="$1"
CURRENT_FILE="$2"
DOCUMENT_LANG="${3:-neutral}" # 指定がない場合はニュートラル言語
EXCLUDE="$4"
BASEDIR="$5"
EXCLUDE_BASEDIR="${6:-false}"

# pub_markdown_core.sh が export する詳細フラグを継承する
DOCUMENT_DETAILS="${DOCUMENT_DETAILS:-false}"

# PUB_MARKDOWN_PROGRESS_LOG=1 のときだけ、長時間処理の進行状況を stderr に出力する。
progress_log() {
    [[ "${PUB_MARKDOWN_PROGRESS_LOG:-0}" == "1" ]] || return 0
    if { true >&3; } 2>/dev/null; then
        printf '[insert-toc %s] %s\n' "$(date '+%H:%M:%S')" "$*" >&3
    else
        printf '[insert-toc %s] %s\n' "$(date '+%H:%M:%S')" "$*" >&2
    fi
}

# 環境変数から追加ドキュメントサブフォルダー設定を取得
# 値はスペース区切りの alias=path リスト (空の場合は機能無効)
MERGE_SUBFOLDER_DOCS="${MERGE_SUBFOLDER_DOCS:-}"
# 改行区切りの文字列を配列に変換
declare -a subfolder_entries=()
if [[ -n "$SUBFOLDER_DOCS_PATHS" ]]; then
    while IFS= read -r entry; do
        [[ -n "$entry" ]] && subfolder_entries+=("$entry")
    done <<< "$SUBFOLDER_DOCS_PATHS"
fi

# デバッグ用: 引数をエコー
#echo "# Debug: Received arguments" >&2
#echo "DEPTH: $DEPTH" >&2
#echo "CURRENT_FILE: $CURRENT_FILE" >&2
#echo "DOCUMENT_LANG: $DOCUMENT_LANG" >&2
#echo "EXCLUDE: $EXCLUDE" >&2
#echo "BASEDIR: $BASEDIR" >&2
#echo "MERGE_SUBFOLDER_DOCS: $MERGE_SUBFOLDER_DOCS" >&2
#echo "SUBFOLDER_DOCS_PATHS: $SUBFOLDER_DOCS_PATHS" >&2

parse_subfolder_entry() {
    local entry="$1"
    local rest

    subfolder_alias="${entry%%|*}"
    rest="${entry#*|}"
    subfolder_path="${rest%%|*}"
    subfolder_docs_src="${rest#*|}"
}

resolve_current_context() {
    local source_dir
    local relative_to_subfolder

    if [[ -n "$CURRENT_FILE" && "$CURRENT_FILE" != "-" ]]; then
        source_dir=$(dirname "$CURRENT_FILE")
        source_dir=$(readlink -f "$source_dir" 2>/dev/null || realpath "$source_dir" 2>/dev/null || echo "$source_dir")
    else
        source_dir=$(pwd)
    fi

    current_scan_dir="$source_dir"
    current_dir="$source_dir"
    current_is_subfolder=false

    for entry in "${subfolder_entries[@]}"; do
        parse_subfolder_entry "$entry"
        if [[ "$source_dir" == "$subfolder_docs_src" || "$source_dir" == "$subfolder_docs_src"/* ]]; then
            relative_to_subfolder="${source_dir#$subfolder_docs_src}"
            relative_to_subfolder="${relative_to_subfolder#/}"
            if [[ -z "$relative_to_subfolder" ]]; then
                current_dir="${PUB_MARKDOWN_MAIN_MDROOT}/${subfolder_alias}"
            else
                current_dir="${PUB_MARKDOWN_MAIN_MDROOT}/${subfolder_alias}/${relative_to_subfolder}"
            fi
            current_is_subfolder=true
            return 0
        fi
    done
}


toc_output_cache_path() {
    [[ -n "${PUB_MARKDOWN_TOC_OUTPUT_CACHE_DIR:-}" ]] || return 1
    local cache_key
    cache_key=$(
        printf '%s\0' \
            "$CURRENT_FILE" "$DEPTH" "$DOCUMENT_LANG" "$EXCLUDE" "$BASEDIR" "$EXCLUDE_BASEDIR" \
            "$MERGE_SUBFOLDER_DOCS" "${PUB_MARKDOWN_MAIN_MDROOT:-}" \
            | sha256sum | awk '{print $1}'
    )
    printf '%s/%s.md\n' "$PUB_MARKDOWN_TOC_OUTPUT_CACHE_DIR" "$cache_key"
}

# ========================================
# メモリベースキャッシュ関数
# ========================================

# 永続化ファイルからメモリキャッシュに読み込み
load_cache() {
    #echo "# キャッシュ読み込み開始: $CACHE_FILE" >&2

    # ファイルが存在しない場合は空のキャッシュで開始
    if [[ ! -f "$CACHE_FILE" ]]; then
        #echo "# キャッシュファイルなし、空キャッシュで開始" >&2
        return 0
    fi

    # TSVファイルを連想配列に読み込み
    local count=0
    while IFS=$'\t' read -r abs_path filename type base_title lang_titles short_titles; do
        # 空行やコメント行はスキップ
        [[ -z "$abs_path" || "$abs_path" =~ ^# ]] && continue

        # メモリキャッシュに追加 (short_titles は空でも保持)
        memory_cache["$abs_path"]="$filename"$'\t'"$type"$'\t'"$base_title"$'\t'"$lang_titles"$'\t'"$short_titles"
        #echo "# キャッシュ読み込み: $abs_path ($type)" >&2
        ((count++))
    done < "$CACHE_FILE"

    #echo "# キャッシュ読み込み完了: $count エントリ" >&2
}

# メモリキャッシュを永続化ファイルに保存
save_cache() {
    # 変更がない場合はスキップ
    if [[ "$cache_modified" != "true" ]]; then
        #echo "# キャッシュ保存スキップ: 変更なし" >&2
        return 0
    fi

    #echo "# キャッシュ保存開始: $CACHE_FILE" >&2

    # 一時ファイルに書き出し
    local temp_file
    temp_file=$(mktemp)

    local count=0
    for abs_path in "${!memory_cache[@]}"; do
        local entry="${memory_cache[$abs_path]}"
        printf '%s\t%s\n' "$abs_path" "$entry" >> "$temp_file"
        ((count++))
    done

    # 一時ファイルを本ファイルに移動
    mv "$temp_file" "$CACHE_FILE"

    #echo "# キャッシュ保存完了: $count エントリ" >&2
}

# メモリキャッシュにエントリを追加
# 引数: 絶対パス ファイル名 種別 ベースタイトル [言語別タイトル]
add_to_memory_cache() {
    local abs_path="$1"
    local filename="$2"
    local type="$3"
    local base_title="$4"
    local lang_titles="${5:-}"

    # キーがすでに存在する場合はスキップ
    if [[ -n "${memory_cache[$abs_path]:-}" ]]; then
        #echo "# メモリキャッシュスキップ (既存): $abs_path ($type)" >&2
        return 0
    fi

    # メモリキャッシュに追加 (short_titles は空で初期化)
    memory_cache["$abs_path"]="$filename"$'\t'"$type"$'\t'"$base_title"$'\t'"$lang_titles"$'\t'""
    cache_modified=true
    #echo "# メモリキャッシュに追加: $abs_path ($type)" >&2
}

# メモリキャッシュから絶対パスでエントリを取得
# 引数: 絶対パス
get_from_memory_cache() {
    local abs_path="$1"
    echo "${memory_cache[$abs_path]:-}"
}

# メモリキャッシュエントリに指定言語のタイトルが存在するかチェック
# 引数: 絶対パス 言語コード
# 戻り値: 0=存在する, 1=存在しない
has_lang_title_in_memory_cache() {
    local abs_path="$1"
    local lang_code="$2"

    local cache_entry="${memory_cache[$abs_path]:-}"

    if [[ -z "$cache_entry" ]]; then
        return 1  # エントリ自体が存在しない
    fi

    # TSVの4番目のフィールド (言語別タイトル) を取得
    local lang_titles
    IFS=$'\t' read -r _ _ _ lang_titles <<< "$cache_entry"

    if [[ -z "$lang_titles" ]]; then
        return 1  # 言語別タイトルフィールドが空
    fi

    # 指定言語のタイトルが存在するかチェック
    if [[ "$lang_titles" =~ ${lang_code}: ]]; then
        return 0  # 存在する
    else
        return 1  # 存在しない
    fi
}

# メモリキャッシュエントリに言語別タイトルを追加
# 引数: 絶対パス 言語コード タイトル
update_memory_cache_title() {
    local abs_path="$1"
    local lang_code="$2"
    local title="$3"
    local new_lang_title="${lang_code}:${title}"

    local cache_entry="${memory_cache[$abs_path]:-}"
    if [[ -z "$cache_entry" ]]; then
        echo "# メモリキャッシュタイトル更新失敗: エントリなし $abs_path" >&2
        return 1
    fi

    # エントリを分解 (short_titles も保持)
    local filename type base_title lang_titles short_titles
    IFS=$'\t' read -r filename type base_title lang_titles short_titles <<< "$cache_entry"

    # 言語別タイトルを更新
    if [[ -z "$lang_titles" ]]; then
        lang_titles="$new_lang_title"
    else
        # 同じ言語コードがすでに存在するかチェック
        if [[ "$lang_titles" =~ $lang_code: ]]; then
            # 既存の言語タイトルを置換 (bash parameter expansion 使用)
            if [[ "$lang_titles" =~ (.*)(${lang_code}:[^|]*)(.*) ]]; then
                lang_titles="${BASH_REMATCH[1]}${new_lang_title}${BASH_REMATCH[3]}"
            fi
        else
            # 新しい言語タイトルを追加
            lang_titles="${lang_titles}|${new_lang_title}"
        fi
    fi

    # メモリキャッシュを更新 (short_titles を保持)
    memory_cache["$abs_path"]="$filename"$'\t'"$type"$'\t'"$base_title"$'\t'"$lang_titles"$'\t'"${short_titles}"
    cache_modified=true
    #echo "# メモリキャッシュタイトル更新: $abs_path -> $new_lang_title" >&2
}

# ========================================
# short-title キャッシュ関数
# ========================================

# メモリキャッシュから short-title を取得する
# 引数: 絶対パス キャッシュキー (例: "ja", "ja-details")
# 戻り値: 0=キャッシュ済み (値は echo, 空の場合は short-title なし)
#         1=未キャッシュ
get_short_title_from_cache() {
    local abs_path="$1"
    local cache_key="$2"

    local cache_entry="${memory_cache[$abs_path]:-}"
    if [[ -z "$cache_entry" ]]; then
        return 1
    fi

    local short_titles
    IFS=$'\t' read -r _ _ _ _ short_titles <<< "$cache_entry"

    if [[ -z "$short_titles" ]]; then
        return 1
    fi

    # キーが存在するかチェック (キー: または キー:値 の形式)
    if [[ "$short_titles" =~ (^|\|)${cache_key}:([^|]*) ]]; then
        echo "${BASH_REMATCH[2]}"
        return 0
    fi

    return 1
}

# メモリキャッシュに short-title を書き込む
# 引数: 絶対パス キャッシュキー 値 (空文字も可: short-title なしの解決済みを表す)
update_short_title_cache() {
    local abs_path="$1"
    local cache_key="$2"
    local value="$3"
    local new_entry="${cache_key}:${value}"

    local cache_entry="${memory_cache[$abs_path]:-}"
    if [[ -z "$cache_entry" ]]; then
        return 1
    fi

    local filename type base_title lang_titles short_titles
    IFS=$'\t' read -r filename type base_title lang_titles short_titles <<< "$cache_entry"

    if [[ -z "$short_titles" ]]; then
        short_titles="$new_entry"
    else
        # 同じキーがすでに存在するかチェック
        if [[ "$short_titles" =~ ${cache_key}: ]]; then
            # 既存エントリを置換
            if [[ "$short_titles" =~ (.*)(${cache_key}:[^|]*)(.*) ]]; then
                short_titles="${BASH_REMATCH[1]}${new_entry}${BASH_REMATCH[3]}"
            fi
        else
            # 新しいエントリを追加
            short_titles="${short_titles}|${new_entry}"
        fi
    fi

    memory_cache["$abs_path"]="$filename"$'\t'"$type"$'\t'"$base_title"$'\t'"$lang_titles"$'\t'"$short_titles"
    cache_modified=true
}

# ========================================
# Markdownタイトル抽出関数
# ========================================

# Markdownファイルから最初のレベル1見出しを抽出
# 引数: ファイルパス 言語コード
extract_markdown_title() {
    local file_path="$1"
    local lang_code="$2"

    if [[ ! -f "$file_path" ]]; then
        return 1
    fi

    # 言語コード対応のタイトル抽出
    local in_target_lang_block=false
    local title=""
    local line_count=0

    # || [[ -n "$line" ]] で末尾改行なし最終行も読み取る
    while IFS= read -r line || [[ -n "$line" ]]; do
        if ((line_count >= 100)); then break; fi
        # 言語コードブロックの開始コメント: <!--ja: または <!--ja:--> 形式
        if [[ "$line" =~ ^[[:space:]]*\<!--${lang_code}:([[:space:]]*--\>)?[[:space:]]*$ ]]; then
            in_target_lang_block=true
            ((line_count++))
            continue
        fi

        # 言語コードブロックの終了コメント: :ja--> または <!--:ja--> 形式
        if [[ "$line" =~ ^[[:space:]]*(\<!--[[:space:]]*)?:${lang_code}[[:space:]]*--\>[[:space:]]*$ ]]; then
            in_target_lang_block=false
            # 対象言語のタイトルが見つかった場合は処理終了
            if [[ -n "$title" ]]; then
                break
            fi
            ((line_count++))
            continue
        fi

        # 対象言語ブロック内でレベル1見出しを検索
        if [[ "$in_target_lang_block" == true && "$line" =~ ^#[[:space:]](.*)$ ]]; then
            title="${BASH_REMATCH[1]}"
            # bash parameter expansion でトリム処理
            title="${title#"${title%%[![:space:]]*}"}"  # 先頭空白除去
            title="${title%"${title##*[![:space:]]}"}"  # 末尾空白除去
            break
        fi

        ((line_count++))
    done < "$file_path"

    # 対象言語のタイトルが見つかった場合
    if [[ -n "$title" ]]; then
        printf '%s:%s' "$lang_code" "$title"
        return 0
    fi

    # 対象言語のタイトルが見つからない場合、従来の処理 (最初の # 見出し) を実行
    line_count=0
    # || [[ -n "$line" ]] で末尾改行なし最終行も読み取る
    while IFS= read -r line || [[ -n "$line" ]]; do
        if ((line_count >= 50)); then break; fi
        if [[ "$line" =~ ^#[[:space:]](.*)$ ]]; then
            title="${BASH_REMATCH[1]}"
            # bash parameter expansion でトリム処理
            title="${title#"${title%%[![:space:]]*}"}"  # 先頭空白除去
            title="${title%"${title##*[![:space:]]}"}"  # 末尾空白除去
            break
        fi
        ((line_count++))
    done < "$file_path"

    if [[ -n "$title" ]]; then
        printf '%s:%s' "$lang_code" "$title"
        return 0
    fi

    return 1
}

# ========================================
# 目次生成関数
# ========================================

# パスの階層数を計算
# 引数: 基準パス 対象パス
get_depth_level() {
    local base_path="$1"
    local target_path="$2"

    # 基準パスで正規化
    local relative_path="${target_path#$base_path}"
    relative_path="${relative_path#/}"  # 先頭スラッシュ除去

    # 階層数をカウント (スラッシュの数)
    if [[ -z "$relative_path" || "$relative_path" == "$target_path" ]]; then
        echo 0  # 同じディレクトリ
    else
        echo "$relative_path" | tr -cd '/' | wc -c
    fi
}

# 除外パターンマッチング
# 引数: ファイルパス 除外パターン配列
# パターン形式:
#   - "pattern/*" : pattern ディレクトリ配下のすべてを除外
#   - "pattern"   : パスに pattern を含むものを除外 (部分文字列マッチング)
# トラブルシューティング: デバッグが必要な場合は、以下の echo 行のコメントを外してください
is_excluded() {
    local file_path="$1"
    local exclude_patterns="$2"

    # 除外パターンが空の場合は除外しない
    if [[ -z "$exclude_patterns" ]]; then
        #echo "# is_excluded: パターンなし -> 除外しない: $file_path" >&2
        return 1
    fi

    # カンマ区切りの除外パターンを処理
    IFS=',' read -ra patterns <<< "$exclude_patterns"
    #echo "# is_excluded: チェック対象: $file_path" >&2
    #echo "# is_excluded: 除外パターン: $exclude_patterns" >&2

    for pattern in "${patterns[@]}"; do
        # bash parameter expansion でトリム処理
        pattern="${pattern#"${pattern%%[![:space:]]*}"}"  # 先頭空白除去
        pattern="${pattern%"${pattern##*[![:space:]]}"}"  # 末尾空白除去
        [[ -z "$pattern" ]] && continue

        #echo "# is_excluded: パターン処理: '$pattern'" >&2

        # パターンマッチング
        if [[ "$pattern" == *"/*" ]]; then
            # ディレクトリ配下すべてを除外するパターン (例: doxybook2/*)
            local dir_pattern="${pattern%/\*}"
            #echo "# is_excluded: ディレクトリパターン検出: '$dir_pattern'" >&2
            case "$file_path" in
                *"/$dir_pattern"/*|*"/$dir_pattern")
                    #echo "# is_excluded: マッチ！ -> 除外: $file_path" >&2
                    return 0
                    ;;
            esac
            #echo "# is_excluded: マッチせず (ディレクトリパターン)" >&2
        else
            # 通常の部分文字列マッチング
            #echo "# is_excluded: 部分文字列マッチング: '$pattern'" >&2
            case "$file_path" in
                *"$pattern"*)
                    #echo "# is_excluded: マッチ！ -> 除外: $file_path" >&2
                    return 0
                    ;;
            esac
            #echo "# is_excluded: マッチせず (部分文字列)" >&2
        fi
    done

    #echo "# is_excluded: すべてのパターンでマッチせず -> 除外しない: $file_path" >&2
    return 1  # 除外しない
}

# メイン目次生成関数
# 引数: 基準ディレクトリ 最大深度 言語コード 除外パターン basedir_prefix
generate_toc() {
    local base_dir="$1"
    local max_depth="$2"
    local lang_code="$3"
    local exclude_patterns="$4"
    local basedir_prefix="$5"

    #echo "# 目次生成開始" >&2

    # sorted_keys をフィルタリングして目次生成対象を絞り込み

    #echo "# フィルタリング開始 (基準ディレクトリ: $base_dir, 最大深度: $max_depth)" >&2

    # PROGRESS
    #printf '%s' " -> filter" >&2

    progress_log "目次対象の絞り込みを開始しました entries=${#sorted_keys[@]}"

    # 第1段階-a: 基準ディレクトリ外・除外パターンによるフィルタ (depth チェックなし)
    local stage1_keys=()
    for abs_path in "${sorted_keys[@]}"; do
        local entry="${memory_cache[$abs_path]}"
        [[ -z "$entry" ]] && continue

        # 1. 基準ディレクトリより上位のエントリを除外
        if [[ "$abs_path" != "$base_dir"/* && "$abs_path" != "$base_dir" ]]; then
            #echo "# 除外 (上位 / 他ツリーディレクトリ): $abs_path" >&2
            continue
        fi

        # 2. 基準ディレクトリ自体を除外 (配下のファイル/ディレクトリは保持)
        if [[ "$EXCLUDE_BASEDIR" == "true" && "$abs_path" == "$base_dir" ]]; then
            #echo "# 除外 (基準ディレクトリ): $abs_path" >&2
            continue
        fi

        # 3. 除外パターンチェック
        if is_excluded "$abs_path" "$exclude_patterns"; then
            #echo "# 除外 (パターンマッチ): $abs_path" >&2
            continue
        fi

        stage1_keys+=("$abs_path")
    done

    # 第1段階-b: stage1_keys のファイルから空ディレクトリ判定用マップと
    # ディレクトリ index リンク用マップを構築する (depth フィルタ前に行うことで、
    # depth 制限で落ちたファイルの親ディレクトリが空扱いにならないよう保全し、
    # depth で落ちた index.md 等もフォルダ行のリンク先として参照できるようにする)
    declare -A directory_has_files=()
    declare -A direct_index_path=()
    declare -A direct_readme_path=()
    declare -A direct_skill_path=()

    for abs_path in "${stage1_keys[@]}"; do
        local entry="${memory_cache[$abs_path]}"
        local filename type
        IFS=$'\t' read -r filename type _ _ <<< "$entry"
        [[ "$type" == "file" ]] || continue

        # 祖先ディレクトリに has_files フラグを設定
        local parent_dir
        parent_dir=$(dirname "$abs_path")
        while [[ "$parent_dir" == "$base_dir" || "$parent_dir" == "$base_dir"/* ]]; do
            directory_has_files["$parent_dir"]=true
            [[ "$parent_dir" == "$base_dir" ]] && break
            parent_dir=$(dirname "$parent_dir")
        done

        # index 系ファイルのマッピング
        local filename_lower="${filename,,}"
        local file_parent_dir
        file_parent_dir=$(dirname "$abs_path")
        if [[ "$filename_lower" == "index.md" ]]; then
            direct_index_path["$file_parent_dir"]="$abs_path"
        elif [[ "$filename_lower" == "readme.md" ]]; then
            direct_readme_path["$file_parent_dir"]="$abs_path"
        elif [[ "$filename_lower" == "skill.md" ]]; then
            direct_skill_path["$file_parent_dir"]="$abs_path"
        fi
    done

    # 第1段階-c: depth 制限フィルタ
    # ファイル・ディレクトリとも abs_path 自身の相対スラッシュ数で判定する。
    # これにより depth=N は「basedir からの相対パスのスラッシュ数 ≤ N のエントリを表示」
    # という一貫した意味になる。
    local filtered_keys=()
    for abs_path in "${stage1_keys[@]}"; do
        if [[ "$max_depth" -ge 0 ]]; then
            local depth
            depth=$(get_depth_level "$base_dir" "$abs_path")
            if [[ $depth -gt $max_depth ]]; then
                #echo "# 除外 (深度超過 $depth > $max_depth): $abs_path" >&2
                continue
            fi
        fi

        filtered_keys+=("$abs_path")
    done

    #echo "# 第1段階フィルタリング完了: ${#filtered_keys[@]} エントリ" >&2

    # PROGRESS
    #printf '%s' "." >&2

    # 第2段階: 空ディレクトリの除去
    # directory_has_files は depth フィルタ前の stage1_keys から構築済み。
    # depth 制限で配下ファイルが全て落ちてもディレクトリ自体は保持される。
    # exclude パターンで全ファイルが除外されたディレクトリは未登録のため除去される。
    local final_keys=()

    for abs_path in "${filtered_keys[@]}"; do
        local entry="${memory_cache[$abs_path]}"
        local type
        IFS=$'\t' read -r _ type _ _ <<< "$entry"
        #echo "entry, type: ${entry}, ${type}" >&2

        if [[ "$type" == "directory" ]]; then
            if [[ "${directory_has_files[$abs_path]:-false}" == "true" ]]; then
                final_keys+=("$abs_path")
                #echo "# 保持 (配下にファイルあり): $abs_path" >&2
            #else
                #echo "# 除外 (空ディレクトリ): $abs_path" >&2
            fi
        else
            # ファイルの場合はそのまま保持
            final_keys+=("$abs_path")
            #echo "# 保持 (ファイル): $abs_path" >&2
        fi
    done

    #echo "# 第2段階フィルタリング完了: ${#final_keys[@]} エントリ" >&2

    # フィルタリング結果を sorted_keys に反映
    sorted_keys=("${final_keys[@]}")
    progress_log "目次対象の絞り込みを終了しました entries=${#sorted_keys[@]}"

    # フィルター後のエントリを表示
    #echo "# フィルター後のエントリ" >&2
    #echo "" >&2
    #echo '```' >&2
    #for abs_path in "${sorted_keys[@]}"; do
    #    entry="${memory_cache[$abs_path]}"
    #    printf '%s\t%s\n' "$abs_path" "$entry" >&2
    #done
    #echo '```' >&2

    # Markdown リスト形式で目次を出力
    #echo "# Markdown リスト形式で目次出力開始" >&2

    # PROGRESS
    #printf '%s' " -> list" >&2

    local depth=0
    local indent=""
    # direct_index_path / direct_readme_path / direct_skill_path は
    # 第1段階-b で stage1_keys (depth フィルタ前) から構築済み。

    progress_log "目次 Markdown の生成を開始しました entries=${#sorted_keys[@]}"
    for abs_path in "${sorted_keys[@]}"; do
        local entry="${memory_cache[$abs_path]}"
        local filename type base_title lang_titles _ignored_st

        IFS=$'\t' read -r filename type base_title lang_titles _ignored_st <<< "$entry"

        # (lang, details) の組み合わせを表すキャッシュキーを算出
        local _st_cache_key="${lang_code}"
        [[ "$DOCUMENT_DETAILS" == "true" ]] && _st_cache_key="${lang_code}-details"

        # 基準ディレクトリからの相対パスと深度を計算
        # $abs_path から $base_dir を削除して / の数で depth を計算
        local relative_path="${abs_path#$base_dir}"
        relative_path="${relative_path#/}"  # 先頭のスラッシュを削除

        if [[ -z "$relative_path" || "$relative_path" == "$abs_path" ]]; then
            depth=0  # 基準ディレクトリ自体
        else
            # bash parameter expansion でスラッシュの数をカウント
            temp="/$relative_path"
            temp_no_slash="${temp//\//}"
            depth=$((${#temp} - ${#temp_no_slash}))
        fi

        # インデント文字列を更新
        indent=""
        for ((i=0; i<depth; i++)); do
            indent="  $indent"
        done

        if [[ "$type" == "file" ]]; then
            local file_basename_only="${filename}"
            local file_basename_lower="${file_basename_only,,}"

            # index.md はディレクトリインデックスとして扱われるため、通常のファイルとしては表示しない
            if [[ "$file_basename_lower" == "index.md" ]]; then
                continue
            fi

            # README.md / SKILL.md は、上位候補がない場合のみディレクトリインデックスとして扱われる
            if [[ "$file_basename_lower" == "readme.md" || "$file_basename_lower" == "skill.md" ]]; then
                local file_dir_path
                file_dir_path=$(dirname "$abs_path")
                local has_index_md=false
                local has_readme_md=false
                [[ -n "${direct_index_path[$file_dir_path]:-}" ]] && has_index_md=true
                [[ -n "${direct_readme_path[$file_dir_path]:-}" ]] && has_readme_md=true

                if [[ "$file_basename_lower" == "readme.md" && "$has_index_md" == "false" ]] ||
                   [[ "$file_basename_lower" == "skill.md" && "$has_index_md" == "false" && "$has_readme_md" == "false" ]]; then
                    continue
                fi
            fi

            # Markdownファイルの場合：タイトルとリンクを出力
            local display_title="$base_title"

            # 指定言語のタイトルがあれば使用
            if [[ -n "$lang_titles" && "$lang_titles" =~ ${lang_code}:([^|]*) ]]; then
                display_title="${BASH_REMATCH[1]}"
            fi

            # short-title があれば最優先で使用 (キャッシュ経由)
            local _st
            if _st=$(get_short_title_from_cache "$abs_path" "$_st_cache_key"); then
                [[ -n "$_st" ]] && display_title="$_st"
            else
                _st=$(extract_short_title "$abs_path" "$lang_code" "$DOCUMENT_DETAILS")
                update_short_title_cache "$abs_path" "$_st_cache_key" "$_st"
                [[ -n "$_st" ]] && display_title="$_st"
            fi

            # 基準ディレクトリからの相対パスを計算
            local file_relative_path="${abs_path#$base_dir/}"

            # basedir_prefix を追加
            if [[ -n "$basedir_prefix" ]]; then
                file_relative_path="$basedir_prefix/$file_relative_path"
            fi

            # Markdownリンク形式で出力 (ファイル名 + 説明文)
            echo "${indent}- 📄 [$file_basename_only]($file_relative_path) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;$display_title"

        elif [[ "$type" == "directory" ]]; then
            # ディレクトリの場合

            # PROGRESS
            #printf '%s' "." >&2

            # ディレクトリインデックスを探す
            # 優先順位: 1. index.md, 2. README.md, 3. SKILL.md (後者 2 つは index.md に読み替え)
            local index_file_found=""
            local index_display_title=""
            local index_relative_path=""

            local check_path="${direct_index_path[$abs_path]:-}"
            if [[ -n "$check_path" ]]; then
                index_file_found="$check_path"
                local check_entry="${memory_cache[$check_path]}"
                local file_base_title file_lang_titles
                IFS=$'\t' read -r _ _ file_base_title file_lang_titles <<< "$check_entry"
                index_display_title="$file_base_title"
                if [[ -n "$file_lang_titles" && "$file_lang_titles" =~ ${lang_code}:([^|]*) ]]; then
                    index_display_title="${BASH_REMATCH[1]}"
                fi
                # short-title があれば最優先で使用 (キャッシュ経由)
                local _ist
                if _ist=$(get_short_title_from_cache "$check_path" "$_st_cache_key"); then
                    [[ -n "$_ist" ]] && index_display_title="$_ist"
                else
                    _ist=$(extract_short_title "$check_path" "$lang_code" "$DOCUMENT_DETAILS")
                    update_short_title_cache "$check_path" "$_st_cache_key" "$_ist"
                    [[ -n "$_ist" ]] && index_display_title="$_ist"
                fi
                index_relative_path="${check_path#$base_dir/}"
                if [[ -n "$basedir_prefix" ]]; then
                    index_relative_path="$basedir_prefix/$index_relative_path"
                fi
            fi

            # index.md が見つからなかった場合、README.md を探す
            if [[ -z "$index_file_found" ]]; then
                check_path="${direct_readme_path[$abs_path]:-}"
                if [[ -n "$check_path" ]]; then
                    index_file_found="$check_path"
                    local check_entry="${memory_cache[$check_path]}"
                    local file_base_title file_lang_titles
                    IFS=$'\t' read -r _ _ file_base_title file_lang_titles <<< "$check_entry"
                    index_display_title="$file_base_title"
                    if [[ -n "$file_lang_titles" && "$file_lang_titles" =~ ${lang_code}:([^|]*) ]]; then
                        index_display_title="${BASH_REMATCH[1]}"
                    fi
                    # short-title があれば最優先で使用 (キャッシュ経由)
                    local _ist
                    if _ist=$(get_short_title_from_cache "$check_path" "$_st_cache_key"); then
                        [[ -n "$_ist" ]] && index_display_title="$_ist"
                    else
                        _ist=$(extract_short_title "$check_path" "$lang_code" "$DOCUMENT_DETAILS")
                        update_short_title_cache "$check_path" "$_st_cache_key" "$_ist"
                        [[ -n "$_ist" ]] && index_display_title="$_ist"
                    fi

                    local readme_dir
                    readme_dir=$(dirname "$check_path")
                    local readme_dir_relative="${readme_dir#$base_dir}"
                    readme_dir_relative="${readme_dir_relative#/}"
                    if [[ -z "$readme_dir_relative" ]]; then
                        index_relative_path="index.md"
                    else
                        index_relative_path="$readme_dir_relative/index.md"
                    fi
                    if [[ -n "$basedir_prefix" ]]; then
                        index_relative_path="$basedir_prefix/$index_relative_path"
                    fi
                fi
            fi

            # README.md も見つからなかった場合、SKILL.md を探す
            if [[ -z "$index_file_found" ]]; then
                check_path="${direct_skill_path[$abs_path]:-}"
                if [[ -n "$check_path" ]]; then
                    index_file_found="$check_path"
                    local check_entry="${memory_cache[$check_path]}"
                    local file_base_title file_lang_titles
                    IFS=$'\t' read -r _ _ file_base_title file_lang_titles <<< "$check_entry"
                    index_display_title="$file_base_title"
                    if [[ -n "$file_lang_titles" && "$file_lang_titles" =~ ${lang_code}:([^|]*) ]]; then
                        index_display_title="${BASH_REMATCH[1]}"
                    fi
                    # short-title があれば最優先で使用 (キャッシュ経由)
                    local _ist
                    if _ist=$(get_short_title_from_cache "$check_path" "$_st_cache_key"); then
                        [[ -n "$_ist" ]] && index_display_title="$_ist"
                    else
                        _ist=$(extract_short_title "$check_path" "$lang_code" "$DOCUMENT_DETAILS")
                        update_short_title_cache "$check_path" "$_st_cache_key" "$_ist"
                        [[ -n "$_ist" ]] && index_display_title="$_ist"
                    fi

                    local skill_dir
                    skill_dir=$(dirname "$check_path")
                    local skill_dir_relative="${skill_dir#$base_dir}"
                    skill_dir_relative="${skill_dir_relative#/}"
                    if [[ -z "$skill_dir_relative" ]]; then
                        index_relative_path="index.md"
                    else
                        index_relative_path="$skill_dir_relative/index.md"
                    fi
                    if [[ -n "$basedir_prefix" ]]; then
                        index_relative_path="$basedir_prefix/$index_relative_path"
                    fi
                fi
            fi

            # インデックスファイルが見つかった場合はリンク付きで出力、そうでなければディレクトリ名のみ
            if [[ -n "$index_file_found" ]]; then
                echo "${indent}- 📁 [$base_title]($index_relative_path) <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;$index_display_title"
            else
                echo "${indent}- 📁 $base_title"
            fi
        fi
    done

    #echo "# 目次生成完了" >&2
    progress_log "目次 Markdown の生成を終了しました"
}

# ========================================
# ファイル探索関数
# ========================================

# ディレクトリを再帰的に探索してキャッシュに追加
# 引数: 開始ディレクトリ 最大深度
scan_directory() {
    local start_dir="$1"
    local max_depth="$2"
    local lang_code="$3"
    local virtual_base_dir="${4:-$start_dir}"

    #echo "# ディレクトリ探索開始: $start_dir (depth=$max_depth)" >&2

    # PROGRESS
    #printf '%s' " scan" >&2

    progress_log "ディレクトリ走査を開始しました dir=${start_dir} depth=${max_depth}"

    # find コマンドで探索
    local find_args=("$start_dir")
    if [[ "$max_depth" -ge 0 ]]; then
        find_args+=(-maxdepth $((max_depth + 1)))
    fi

    while read -r path; do
        # 絶対パス取得
        local abs_path
        if [[ "$virtual_base_dir" == "$start_dir" ]]; then
            abs_path="$path"
        else
            local relative_path="${path#$start_dir}"
            relative_path="${relative_path#/}"
            if [[ -z "$relative_path" ]]; then
                abs_path="$virtual_base_dir"
            else
                abs_path="${virtual_base_dir}/${relative_path}"
            fi
        fi

        # ファイル名取得
        local filename
        filename="${path##*/}"

        #echo "# find結果: $path (abs: $abs_path)" >&2

        if [[ -d "$path" ]]; then
            # ディレクトリの場合
            #echo "# ディレクトリとして処理: $abs_path" >&2

            # PROGRESS
            #printf '%s' "." >&2

            add_to_memory_cache "$abs_path" "$filename" "directory" "$filename" ""
            unsorted_keys+=("$abs_path")
        elif [[ -f "$path" ]]; then
            if is_pub_markdown_skip "$path"; then
                continue
            fi

            # ファイルの場合
            #echo "# ファイルとして処理: $abs_path" >&2
            local base_title="$filename"
            # bash parameter expansion で拡張子除去
            if [[ "$base_title" == *.md ]]; then
                base_title="${base_title%.md}"
            elif [[ "$base_title" == *.markdown ]]; then
                base_title="${base_title%.markdown}"
            fi

            add_to_memory_cache "$abs_path" "$filename" "file" "$base_title" ""
            unsorted_keys+=("$abs_path")

            # Markdownタイトル抽出 (キャッシュに指定言語のタイトルがない場合のみ)
            if ! has_lang_title_in_memory_cache "$abs_path" "$lang_code"; then
                #echo "# Markdownタイトル抽出実行: $abs_path" >&2
                local lang_title
                if lang_title=$(extract_markdown_title "$path" "$lang_code"); then
                    local title
                    title="${lang_title#*:}"
                    update_memory_cache_title "$abs_path" "$lang_code" "$title"
                fi
            #else
                #echo "# Markdownタイトル抽出スキップ (キャッシュ済): $abs_path" >&2
            fi
        else
            echo "# 不明なタイプ: $abs_path (ディレクトリでもファイルでもない)" >&2
        fi
    done < <(find -L "${find_args[@]}" \( -type f -iname "*.md" \) -o \( -type f -iname "*.markdown" \) -o -type d)

    #echo "# ディレクトリ探索完了: $start_dir" >&2
    progress_log "ディレクトリ走査を終了しました dir=${start_dir}"
}

# ========================================
# メイン処理
# ========================================

# キャッシュをメモリに読み込み
progress_log "TOC 生成を開始しました current_file=${CURRENT_FILE} depth=${DEPTH} lang=${DOCUMENT_LANG}"

resolve_current_context
progress_log "TOC 基準を解決しました base=${current_dir} scan=${current_scan_dir} subfolder=${current_is_subfolder}"

_toc_output_cache_file=$(toc_output_cache_path || true)
if [[ -n "$_toc_output_cache_file" && -f "$_toc_output_cache_file" ]]; then
    progress_log "TOC 出力キャッシュを使用しました result=hit"
    cat "$_toc_output_cache_file"
    exit 0
fi
progress_log "TOC 出力キャッシュを確認しました result=miss"

progress_log "キャッシュ読み込みを開始しました"
load_cache
progress_log "キャッシュ読み込みを終了しました entries=${#memory_cache[@]}"

# ディレクトリ探索実行
scan_directory "$current_scan_dir" "$DEPTH" "$DOCUMENT_LANG" "$current_dir"

# 追加ドキュメントサブフォルダーの探索 (mergeSubfolderDocs が指定されている場合)
# 注意: この機能は current_dir が mdRoot の場合のみ有効
if [[ -n "$MERGE_SUBFOLDER_DOCS" && ${#subfolder_entries[@]} -gt 0 && "$current_dir" == "${PUB_MARKDOWN_MAIN_MDROOT}" ]]; then
    #echo "# 追加ドキュメントサブフォルダー探索開始" >&2

    for entry in "${subfolder_entries[@]}"; do
        parse_subfolder_entry "$entry"

        #echo "# 追加ドキュメントサブフォルダー探索: $subfolder_alias -> $subfolder_docs_src" >&2

        # 追加ドキュメントサブフォルダー配下のファイルを探索
        # 仮想パスとしてキャッシュに追加(current_dir/subfolder/... として)
        if [[ -d "$subfolder_docs_src" ]]; then
            # find コマンドで探索
            progress_log "追加 docs の走査を開始しました alias=${subfolder_alias} dir=${subfolder_docs_src}"
            _find_args=("$subfolder_docs_src")
            if [[ "$DEPTH" -ge 0 ]]; then
                _find_args+=(-maxdepth $((DEPTH + 1)))
            fi

            while read -r path; do
                # 実パスから仮想パスを計算
                # 実パス: {docs_src}/path/to/file.md
                # 仮想パス: {current_dir}/{alias}/path/to/file.md
                _relative_to_docs_src="${path#$subfolder_docs_src}"
                _relative_to_docs_src="${_relative_to_docs_src#/}"  # 先頭スラッシュ除去

                if [[ -z "$_relative_to_docs_src" ]]; then
                    _virtual_abs_path="${current_dir}/${subfolder_alias}"
                else
                    _virtual_abs_path="${current_dir}/${subfolder_alias}/${_relative_to_docs_src}"
                fi

                # ファイル名取得
                # 追加ドキュメントサブフォルダーのルートディレクトリの場合は alias の最後の部分を使用
                # 例: testfw/gtest -> gtest
                if [[ "$path" == "$subfolder_docs_src" ]]; then
                    _filename="${subfolder_alias##*/}"
                else
                    _filename="${path##*/}"
                fi

                #echo "# 追加ドキュメントサブフォルダーファイル: $path -> $_virtual_abs_path" >&2

                if [[ -d "$path" ]]; then
                    # ディレクトリの場合
                    # 追加ドキュメントサブフォルダーのルートディレクトリの場合は alias の最後の部分を base_title に使用
                    if [[ "$path" == "$subfolder_docs_src" ]]; then
                        add_to_memory_cache "$_virtual_abs_path" "$_filename" "directory" "${subfolder_alias##*/}" ""
                    else
                        add_to_memory_cache "$_virtual_abs_path" "$_filename" "directory" "$_filename" ""
                    fi
                    unsorted_keys+=("$_virtual_abs_path")
                elif [[ -f "$path" ]]; then
                    if is_pub_markdown_skip "$path"; then
                        continue
                    fi

                    # ファイルの場合
                    _base_title="$_filename"
                    if [[ "$_base_title" == *.md ]]; then
                        _base_title="${_base_title%.md}"
                    elif [[ "$_base_title" == *.markdown ]]; then
                        _base_title="${_base_title%.markdown}"
                    fi

                    add_to_memory_cache "$_virtual_abs_path" "$_filename" "file" "$_base_title" ""
                    unsorted_keys+=("$_virtual_abs_path")

                    # Markdownタイトル抽出(実パスを使用)
                    if ! has_lang_title_in_memory_cache "$_virtual_abs_path" "$DOCUMENT_LANG"; then
                        if _lang_title=$(extract_markdown_title "$path" "$DOCUMENT_LANG"); then
                            _title="${_lang_title#*:}"
                            update_memory_cache_title "$_virtual_abs_path" "$DOCUMENT_LANG" "$_title"
                        fi
                    fi
                fi
            done < <(find -L "${_find_args[@]}" \( -type f -iname "*.md" \) -o \( -type f -iname "*.markdown" \) -o -type d)
            progress_log "追加 docs の走査を終了しました alias=${subfolder_alias}"
        fi
    done

    #echo "# サブモジュール docs 探索完了" >&2
fi
progress_log "追加 docs の結合判定を終了しました enabled=$([[ -n "$MERGE_SUBFOLDER_DOCS" && ${#subfolder_entries[@]} -gt 0 && "$current_dir" == "${PUB_MARKDOWN_MAIN_MDROOT}" ]] && echo true || echo false)"

# キャッシュを永続化ファイルに保存
progress_log "キャッシュ保存を開始しました changed=${cache_modified}"
save_cache
progress_log "キャッシュ保存を終了しました"

# ディレクトリ制御マジックファイル publocal.yaml の order をディレクトリ単位でキャッシュする。
# order に列挙された子 (ファイル / サブフォルダー) を先頭にその順で並べ、未列挙は名前順で末尾に置く。
declare -A _publocal_loaded   # 実ディレクトリ -> 1 (読み込み試行済み)
declare -A _publocal_index    # "実ディレクトリ<US>name" -> 0 始まりの並び順インデックス
declare -A _vreal_cache       # 仮想ディレクトリ -> 実ディレクトリ (逆引きキャッシュ)
_PUBLOCAL_SEP=$'\x1f'

# 仮想ディレクトリ (memory_cache のキーが採る形) を、publocal.yaml が実在する
# ソース ディレクトリへ逆引きする。
# - サブフォルダー内ページの TOC: current_dir(仮想) -> current_scan_dir(実)
# - mergeSubfolderDocs: ${PUB_MARKDOWN_MAIN_MDROOT}/${alias} -> ${subfolder_docs_src}
# - 主 mdRoot 配下: 仮想パスがそのまま実パス
_map_virtual_to_real_dir() {
    local vdir="$1"
    if [[ -n "${_vreal_cache[$vdir]:-}" ]]; then
        REAL_DIR="${_vreal_cache[$vdir]}"
        return
    fi
    local real="$vdir"
    if [[ "$current_is_subfolder" == "true" && -n "$current_dir" ]]; then
        if [[ "$vdir" == "$current_dir" ]]; then
            real="$current_scan_dir"
        elif [[ "$vdir" == "$current_dir"/* ]]; then
            real="${current_scan_dir}${vdir#$current_dir}"
        fi
    else
        local entry base
        for entry in "${subfolder_entries[@]}"; do
            parse_subfolder_entry "$entry"
            base="${PUB_MARKDOWN_MAIN_MDROOT}/${subfolder_alias}"
            if [[ "$vdir" == "$base" ]]; then
                real="$subfolder_docs_src"
                break
            elif [[ "$vdir" == "$base"/* ]]; then
                real="${subfolder_docs_src}${vdir#$base}"
                break
            fi
        done
    fi
    _vreal_cache[$vdir]="$real"
    REAL_DIR="$real"
}

# 指定ディレクトリの publocal.yaml を読み込み、order をキャッシュへ展開する
_load_publocal_order() {
    local dir="$1"
    [[ -n "${_publocal_loaded[$dir]:-}" ]] && return
    _publocal_loaded[$dir]=1
    local f="${dir}/publocal.yaml"
    [[ -f "$f" ]] || return

    local in_order=0 idx=0 line name key
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        if [[ "$line" =~ ^order:[[:space:]]*$ ]]; then
            in_order=1
            continue
        fi
        [[ $in_order -eq 1 ]] || continue
        if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*(.*)$ ]]; then
            name="${BASH_REMATCH[1]}"
            name="${name%%#*}"                       # 行内コメント除去
            name="${name%"${name##*[![:space:]]}"}"  # 末尾空白除去
            name="${name#\"}"; name="${name%\"}"     # 二重引用符除去
            name="${name#\'}"; name="${name%\'}"     # 単一引用符除去
            name="${name%/}"                         # フォルダー末尾スラッシュ除去
            [[ -z "$name" ]] && continue
            key="${dir}${_PUBLOCAL_SEP}${name}"
            if [[ -z "${_publocal_index[$key]:-}" ]]; then
                _publocal_index[$key]=$idx
                idx=$((idx + 1))
            fi
        elif [[ "$line" =~ ^[^[:space:]] ]]; then
            # 別のトップレベル キーで order ブロックは終了
            in_order=0
        fi
    done < "$f"
}

# order_index_for <親ディレクトリ(仮想)> <名前> -> ORDER_IDX に 0 始まりインデックス、未列挙は 999999
order_index_for() {
    local vdir="$1" name="$2"
    if [[ -z "$vdir" || "$vdir" == "/" ]]; then
        ORDER_IDX=999999
        return
    fi
    _map_virtual_to_real_dir "$vdir"
    local dir="$REAL_DIR"
    _load_publocal_order "$dir"
    local v="${_publocal_index["${dir}${_PUBLOCAL_SEP}${name}"]:-}"
    if [[ -n "$v" ]]; then
        ORDER_IDX="$v"
    else
        ORDER_IDX=999999
    fi
}

# unsorted_keys をソートして sorted_keys に設定
# カスタムソート: 各階層でファイルとディレクトリを混在させて並べる。
# 並び順は「親ディレクトリの publocal.yaml の order を優先 (6 桁ゼロ埋め)、未列挙は名前順」。
# 結果は SORT_KEY に設定する (連想配列キャッシュを保持するため command substitution を避ける)。
generate_sort_key() {
    local path="$1"
    local separator="!"

    # パスを / で分割
    IFS='/' read -ra parts <<< "$path"
    local key=""
    local last_idx=$((${#parts[@]} - 1))
    local accum=""
    local i part lc pad

    for i in "${!parts[@]}"; do
        part="${parts[$i]}"
        lc="${part,,}"
        # この component の親ディレクトリは accum。publocal.yaml の order を引く。
        order_index_for "$accum" "$part"
        printf -v pad '%06d' "$ORDER_IDX"
        key+="${pad}${lc}"
        # accum を 1 段進める
        if [[ -z "$part" ]]; then
            accum="/"
        elif [[ "$accum" == "/" ]]; then
            accum="/$part"
        elif [[ -z "$accum" ]]; then
            accum="$part"
        else
            accum="${accum}/${part}"
        fi
        if [[ $i -lt $last_idx ]]; then
            # '-' などを含む接頭辞関係の sibling より、親配下の要素を先に並べる。
            key+="$separator"
        fi
    done

    SORT_KEY="$key"
}

# ソートキーと元パスのペアを生成してソート
# generate_sort_key は SORT_KEY に書き込む。同一サブシェル内で呼ぶことで
# publocal.yaml のディレクトリ単位キャッシュをイテレーション間で共有する。
mapfile -t sorted_keys < <(
    for path in "${unsorted_keys[@]}"; do
        generate_sort_key "$path"
        printf '%s\t%s\n' "$SORT_KEY" "$path"
    done | sort -t$'\t' -k1 | cut -f2
)
progress_log "ソートを終了しました entries=${#sorted_keys[@]}"

# メモリキャッシュ内容を表示
#echo "# キャッシュ内容" >&2
#echo "" >&2
#echo '```' >&2
#for abs_path in "${sorted_keys[@]}"; do
#    entry="${memory_cache[$abs_path]}"
#    printf '%s\t%s\n' "$abs_path" "$entry" >&2
#done
#echo '```' >&2

# 実際の目次生成
if [[ -n "$_toc_output_cache_file" ]]; then
    _toc_output_tmp=$(mktemp)
    generate_toc "$current_dir" "$DEPTH" "$DOCUMENT_LANG" "$EXCLUDE" "$BASEDIR" > "$_toc_output_tmp"
    cat "$_toc_output_tmp"
    mv "$_toc_output_tmp" "$_toc_output_cache_file"
else
    generate_toc "$current_dir" "$DEPTH" "$DOCUMENT_LANG" "$EXCLUDE" "$BASEDIR"
fi
progress_log "TOC 生成を終了しました"

# PROGRESS
#printf '%s\n' " -> done" >&2
