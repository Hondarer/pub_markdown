#!/bin/bash

# insert-toc.sh - Markdown インデックス生成スクリプト
# 引数解釈と処理

# キャッシュファイルパス
CACHE_FILE="/tmp/insert-toc-cache.tsv"

# メモリ内キャッシュ（連想配列）
# キー: 絶対パス, 値: "ファイル名\t種別\tベースタイトル\t言語別タイトル"
declare -A memory_cache

# ソート前キーリスト（順序付き配列）
declare -a unsorted_keys

# ソート済みキーリスト（順序付き配列）
declare -a sorted_keys

# キャッシュ変更フラグ
cache_modified=false

# 引数の取得
DEPTH="$1"
CURRENT_FILE="$2"
DOCUMENT_LANG="${3:-neutral}" # 指定がない場合はニュートラル言語
EXCLUDE="$4"

# デバッグ用: 引数をエコー
#echo "# Debug: Received arguments" >&2
#echo "DEPTH: $DEPTH" >&2
#echo "CURRENT_FILE: $CURRENT_FILE" >&2
#echo "DOCUMENT_LANG: $DOCUMENT_LANG" >&2
#echo "EXCLUDE: $EXCLUDE" >&2

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
    while IFS=$'\t' read -r abs_path filename type base_title lang_titles; do
        # 空行やコメント行はスキップ
        [[ -z "$abs_path" || "$abs_path" =~ ^# ]] && continue

        # メモリキャッシュに追加
        memory_cache["$abs_path"]="$filename"$'\t'"$type"$'\t'"$base_title"$'\t'"$lang_titles"
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

    # キーが既に存在する場合はスキップ
    if [[ -n "${memory_cache[$abs_path]:-}" ]]; then
        #echo "# メモリキャッシュスキップ (既存): $abs_path ($type)" >&2
        return 0
    fi

    # メモリキャッシュに追加
    memory_cache["$abs_path"]="$filename"$'\t'"$type"$'\t'"$base_title"$'\t'"$lang_titles"
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

    # TSVの4番目のフィールド（言語別タイトル）を取得
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

    # エントリを分解
    local filename type base_title lang_titles
    IFS=$'\t' read -r filename type base_title lang_titles <<< "$cache_entry"

    # 言語別タイトルを更新
    if [[ -z "$lang_titles" ]]; then
        lang_titles="$new_lang_title"
    else
        # 同じ言語コードが既に存在するかチェック
        if [[ "$lang_titles" =~ $lang_code: ]]; then
            # 既存の言語タイトルを置換（bash parameter expansion使用）
            if [[ "$lang_titles" =~ (.*)(${lang_code}:[^|]*)(.*) ]]; then
                lang_titles="${BASH_REMATCH[1]}${new_lang_title}${BASH_REMATCH[3]}"
            fi
        else
            # 新しい言語タイトルを追加
            lang_titles="${lang_titles}|${new_lang_title}"
        fi
    fi

    # メモリキャッシュを更新
    memory_cache["$abs_path"]="$filename"$'\t'"$type"$'\t'"$base_title"$'\t'"$lang_titles"
    cache_modified=true
    #echo "# メモリキャッシュタイトル更新: $abs_path -> $new_lang_title" >&2
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

    while IFS= read -r line && ((line_count < 100)); do
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

    # 対象言語のタイトルが見つからない場合、従来の処理（最初の # 見出し）を実行
    line_count=0
    while IFS= read -r line && ((line_count < 50)); do
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

    # 階層数をカウント（スラッシュの数）
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
#   - "pattern"   : パスに pattern を含むものを除外（部分文字列マッチング）
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
            # ディレクトリ配下すべてを除外するパターン (例: doxybook/*)
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
# 引数: 基準ディレクトリ 最大深度 除外パターン 言語コード
generate_toc() {
    local base_dir="$1"
    local max_depth="$2"
    local lang_code="$3"
    local exclude_patterns="$4"

    #echo "# 目次生成開始" >&2

    # sorted_keys をフィルタリングして目次生成対象を絞り込み
    local filtered_keys=()

    #echo "# フィルタリング開始 (基準ディレクトリ: $base_dir, 最大深度: $max_depth)" >&2

    # PROGRESS
    #printf '%s' " -> filter" >&2

    # 第1段階: 基本的なフィルタリング
    for abs_path in "${sorted_keys[@]}"; do
        local entry="${memory_cache[$abs_path]}"
        [[ -z "$entry" ]] && continue

        local type
        IFS=$'\t' read -r _ type _ _ <<< "$entry"

        # 1. 基準ディレクトリより上位のエントリを除外
        if [[ "$abs_path" != "$base_dir"/* && "$abs_path" != "$base_dir" ]]; then
            #echo "# 除外 (上位 / 他ツリーディレクトリ): $abs_path" >&2
            continue
        fi

        # 2. 基準ディレクトリ自体を除外（配下のファイル/ディレクトリは保持）
        #if [[ "$abs_path" == "$base_dir" ]]; then
        #    echo "# 除外 (基準ディレクトリ): $abs_path" >&2
        #    continue
        #fi

        # 3. 深度制限チェック
        if [[ "$max_depth" -ge 0 ]]; then
            local depth
            if [[ "$type" == "file" ]]; then
                # ファイルの場合は親ディレクトリの深度をチェック
                depth=$(get_depth_level "$base_dir" "$(dirname "$abs_path")")
            else
                # ディレクトリの場合はそのディレクトリの深度をチェック
                depth=$(get_depth_level "$base_dir" "$abs_path")
            fi

            if [[ $depth -gt $max_depth ]]; then
                #echo "# 除外 (深度超過 $depth > $max_depth): $abs_path" >&2
                continue
            fi
        fi

        # 4. 除外パターンチェック
        if is_excluded "$abs_path" "$exclude_patterns"; then
            #echo "# 除外 (パターンマッチ): $abs_path" >&2
            continue
        fi

        # フィルタを通過
        filtered_keys+=("$abs_path")
    done

    #echo "# 第1段階フィルタリング完了: ${#filtered_keys[@]} エントリ" >&2

    # PROGRESS
    #printf '%s' "." >&2

    # 第2段階: 空ディレクトリの除去
    local final_keys=()

    for abs_path in "${filtered_keys[@]}"; do
        local entry="${memory_cache[$abs_path]}"
        local type
        IFS=$'\t' read -r _ type _ _ <<< "$entry"
        #echo "entry, type: ${entry}, ${type}" >&2

        if [[ "$type" == "directory" ]]; then
            # ディレクトリの場合、配下に有効なファイルがあるかチェック
            local has_files=false

            # 効率的なアルゴリズム: filtered_keys をループして前方一致チェック
            for check_path in "${filtered_keys[@]}"; do
                # チェックするディレクトリ配下のパスかどうかを前方一致で確認
                if [[ "$check_path" == "$abs_path"/* ]]; then
                    # ディレクトリ名部分を削除して残りの文字列を取得
                    local remaining_path="${check_path#$abs_path/}"

                    # 残った文字列にピリオドが含まれていればファイルと判断
                    if [[ "$remaining_path" == *.* ]]; then
                        has_files=true
                        break
                    fi
                fi
            done

            if [[ "$has_files" == "true" ]]; then
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
    for abs_path in "${sorted_keys[@]}"; do
        local entry="${memory_cache[$abs_path]}"
        local filename type base_title lang_titles

        IFS=$'\t' read -r filename type base_title lang_titles <<< "$entry"

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
            local file_basename_lower=$(echo "$file_basename_only" | tr '[:upper:]' '[:lower:]')

            # index.md はディレクトリインデックスとして扱われるため、通常のファイルとしては表示しない
            if [[ "$file_basename_lower" == "index.md" ]]; then
                continue
            fi

            # README.md は、同じディレクトリに index.md が存在しない場合のみディレクトリインデックスとして扱われる
            if [[ "$file_basename_lower" == "readme.md" ]]; then
                # 同じディレクトリに index.md が存在するかチェック
                local file_dir_path=$(dirname "$abs_path")
                local has_index_md=false
                for sibling_path in "${sorted_keys[@]}"; do
                    if [[ $(dirname "$sibling_path") == "$file_dir_path" ]]; then
                        local sibling_basename=$(basename "$sibling_path" | tr '[:upper:]' '[:lower:]')
                        if [[ "$sibling_basename" == "index.md" ]]; then
                            has_index_md=true
                            break
                        fi
                    fi
                done

                # index.md が存在しない場合は、README.md をディレクトリインデックスとして扱う
                if [[ "$has_index_md" == "false" ]]; then
                    continue
                fi
            fi

            # Markdownファイルの場合：タイトルとリンクを出力
            local display_title="$base_title"

            # 指定言語のタイトルがあれば使用
            if [[ -n "$lang_titles" && "$lang_titles" =~ ${lang_code}:([^|]*) ]]; then
                display_title="${BASH_REMATCH[1]}"
            fi

            # 基準ディレクトリからの相対パスを計算
            local file_relative_path="${abs_path#$base_dir/}"

            # Markdownリンク形式で出力
            echo "${indent}- 📄 [$display_title]($file_relative_path)"

        elif [[ "$type" == "directory" ]]; then
            # ディレクトリの場合

            # PROGRESS
            #printf '%s' "." >&2

            # ディレクトリインデックスを探す
            # 優先順位: 1. index.md, 2. README.md (index.md に読み替え)
            local index_file_found=""
            local index_display_title=""
            local index_relative_path=""

            # ディレクトリ配下のインデックスファイルを検索 (ケース揺らぎ許容)
            local dir_prefix="$abs_path/"
            for check_path in "${sorted_keys[@]}"; do
                # 前方一致チェック: abs_path 配下でない場合は即座にスキップ
                [[ "$check_path" != "$dir_prefix"* ]] && continue

                # check_path から abs_path を取り除いてファイル名部分を取得
                local remaining_path="${check_path#$dir_prefix}"

                # スラッシュが含まれていれば直下のファイルではない
                [[ "$remaining_path" == */* ]] && continue

                # type チェック
                local check_entry="${memory_cache[$check_path]}"
                [[ -z "$check_entry" ]] && continue
                [[ "$check_entry" != *$'\t'file$'\t'* ]] && continue

                # index.md かチェック (ケース揺らぎ許容)
                if [[ "$remaining_path" =~ ^[Ii][Nn][Dd][Ee][Xx]\.[Mm][Dd]$ ]]; then
                    index_file_found="$check_path"

                    # ファイルの情報を取得
                    local file_base_title file_lang_titles
                    IFS=$'\t' read -r _ _ file_base_title file_lang_titles <<< "$check_entry"

                    # 表示タイトルを決定
                    index_display_title="$file_base_title"
                    if [[ -n "$file_lang_titles" && "$file_lang_titles" =~ ${lang_code}:([^|]*) ]]; then
                        index_display_title="${BASH_REMATCH[1]}"
                    fi

                    # 基準ディレクトリからの相対パスを計算
                    index_relative_path="${check_path#$base_dir/}"

                    break  # index.md が見つかったので終了
                fi
            done

            # index.md が見つからなかった場合、README.md を探す
            if [[ -z "$index_file_found" ]]; then
                for check_path in "${sorted_keys[@]}"; do
                    [[ "$check_path" != "$dir_prefix"* ]] && continue
                    local remaining_path="${check_path#$dir_prefix}"
                    [[ "$remaining_path" == */* ]] && continue

                    local check_entry="${memory_cache[$check_path]}"
                    [[ -z "$check_entry" ]] && continue
                    [[ "$check_entry" != *$'\t'file$'\t'* ]] && continue

                    # README.md かチェック (ケース揺らぎ許容)
                    if [[ "$remaining_path" =~ ^[Rr][Ee][Aa][Dd][Mm][Ee]\.[Mm][Dd]$ ]]; then
                        index_file_found="$check_path"

                        # ファイルの情報を取得
                        local file_base_title file_lang_titles
                        IFS=$'\t' read -r _ _ file_base_title file_lang_titles <<< "$check_entry"

                        # 表示タイトルを決定
                        index_display_title="$file_base_title"
                        if [[ -n "$file_lang_titles" && "$file_lang_titles" =~ ${lang_code}:([^|]*) ]]; then
                            index_display_title="${BASH_REMATCH[1]}"
                        fi

                        # 基準ディレクトリからの相対パスを計算 (README.md を index.md に読み替え)
                        # README.md の親ディレクトリを取得
                        local readme_dir="$(dirname "$check_path")"
                        local readme_dir_relative="${readme_dir#$base_dir}"
                        readme_dir_relative="${readme_dir_relative#/}"  # 先頭スラッシュ除去

                        if [[ -z "$readme_dir_relative" ]]; then
                            # ルートディレクトリの README.md
                            index_relative_path="index.md"
                        else
                            # サブディレクトリの README.md
                            index_relative_path="$readme_dir_relative/index.md"
                        fi

                        break  # README.md が見つかったので終了
                    fi
                done
            fi

            # インデックスファイルが見つかった場合はリンク付きで出力、そうでなければディレクトリ名のみ
            if [[ -n "$index_file_found" ]]; then
                echo "${indent}- 📁 [$index_display_title]($index_relative_path)"
            else
                echo "${indent}- 📁 $base_title"
            fi
        fi
    done

    #echo "# 目次生成完了" >&2
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

    #echo "# ディレクトリ探索開始: $start_dir (depth=$max_depth)" >&2

    # PROGRESS
    #printf '%s' " scan" >&2

    # find コマンドで探索
    local find_args=("$start_dir")
    if [[ "$max_depth" -ge 0 ]]; then
        find_args+=(-maxdepth $((max_depth + 1)))
    fi

    while read -r path; do
        # 絶対パス取得
        local abs_path
        abs_path="$path"

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

            # Markdownタイトル抽出（キャッシュに指定言語のタイトルがない場合のみ）
            if ! has_lang_title_in_memory_cache "$abs_path" "$lang_code"; then
                #echo "# Markdownタイトル抽出実行: $abs_path" >&2
                local lang_title
                if lang_title=$(extract_markdown_title "$abs_path" "$lang_code"); then
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
    done < <(find "${find_args[@]}" \( -type f -iname "*.md" \) -o \( -type f -iname "*.markdown" \) -o -type d)

    #echo "# ディレクトリ探索完了: $start_dir" >&2
}

# ========================================
# メイン処理
# ========================================

# キャッシュをメモリに読み込み
load_cache

# CURRENT_FILE のディレクトリを基準に探索
if [[ -n "$CURRENT_FILE" && "$CURRENT_FILE" != "-" ]]; then
    # CURRENT_FILE からディレクトリパスを取得
    current_dir=$(dirname "$CURRENT_FILE")
    # 絶対パスに変換
    current_dir=$(readlink -f "$current_dir" 2>/dev/null || realpath "$current_dir" 2>/dev/null || echo "$current_dir")
else
    # CURRENT_FILE が指定されていない場合は現在のディレクトリを使用
    current_dir=$(pwd)
fi
#echo "# 探索基準ディレクトリ: $current_dir" >&2

# ディレクトリ探索実行
scan_directory "$current_dir" "$DEPTH" "$DOCUMENT_LANG"

# キャッシュを永続化ファイルに保存
save_cache

# unsorted_keys をソートして sorted_keys に設定
mapfile -t sorted_keys < <(printf '%s\n' "${unsorted_keys[@]}" | sort)

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
generate_toc "$current_dir" "$DEPTH" "$DOCUMENT_LANG" "$EXCLUDE"

# PROGRESS
#printf '%s\n' " -> done" >&2
