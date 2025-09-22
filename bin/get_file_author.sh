#!/usr/bin/env bash

# get_file_author FILEPATH
#   ・git コマンドが使えない             → 空文字
#   ・Git 管理下にない                   → 空文字
#   ・Git 管理下にあり、コミット履歴あり → コミッターリスト (新しい順、重複排除)
get_file_author() {
  local file=$1

  # ─── 0) git コマンドの存在チェック ─────────────────────────────
  if ! command -v git &>/dev/null; then
    #echo ""
    return
  fi

  # ─── 1) ファイルの絶対パスを取得 ───────────────────────────────
  local abs_file
  if [[ "$file" = /* ]]; then
    # 既に絶対パス
    abs_file="$file"
  else
    # 相対パスを絶対パスに変換
    abs_file="$(cd "$(dirname "$file")" && pwd)/$(basename "$file")"
  fi

  # ─── 2) Git リポジトリのルートを取得 ───────────────────────────
  local repo
  repo=$(git -C "$(dirname "$abs_file")" rev-parse --show-toplevel 2>/dev/null) || {
    #echo ""
    return
  }

  # ─── 3) リポジトリルートからの相対パスを計算 ─────────────────────
  local rel
  # MinGW環境でのパス形式の違いに対応
  if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    # MinGW/MSYS環境: Windowsパス形式をUnix形式に正規化
    local unix_repo unix_file
    unix_repo=$(cygpath -u "$repo" 2>/dev/null || echo "$repo" | sed 's|\\|/|g; s|^\([A-Za-z]\):|/\L\1|')
    unix_file=$(cygpath -u "$abs_file" 2>/dev/null || echo "$abs_file" | sed 's|\\|/|g; s|^\([A-Za-z]\):|/\L\1|')
    
    # 共通プレフィックスを削除して相対パスを取得
    if [[ "$unix_file" == "$unix_repo"/* ]]; then
      rel="${unix_file#"$unix_repo"/}"
    else
      # fallback: gitで現在のファイルパスを取得
      if ! rel=$(git -C "$repo" ls-files --full-name -- "$abs_file" 2>/dev/null | head -1); then
        #echo ""
        return
      fi
      if [[ -z "$rel" ]]; then
        #echo ""
        return
      fi
    fi
  else
    # Linux/Unix環境: 通常の処理
    if [[ "$abs_file" == "$repo"/* ]]; then
      rel="${abs_file#"$repo"/}"
    else
      # fallback: gitで現在のファイルパスを取得
      if ! rel=$(git -C "$repo" ls-files --full-name -- "$abs_file" 2>/dev/null | head -1); then
        #echo ""
        return
      fi
      if [[ -z "$rel" ]]; then
        #echo ""
        return
      fi
    fi
  fi

  # ─── 4) 管理下にあるかチェック ─────────────────────────────────
  if ! git -C "$repo" ls-files --error-unmatch -- "$rel" &>/dev/null; then
    #echo $(git -C "$repo" config user.name 2>/dev/null)
    return
  fi

  # ─── 5) 未コミット差分の有無チェック ─────────────────────────────
  local has_uncommitted=false
  if ! git -C "$repo" diff --quiet HEAD -- "$rel" 2>/dev/null; then
    has_uncommitted=true
  fi

  # ─── 6) コミッター名を取得 (古い順、重複排除) ─────────────────
  local authors
  authors=$(git -C "$repo" log --reverse --format='%cn' -- "$rel" | \
    awk '!seen[$0]++')

  # ─── 7) 未コミットの場合、自身の名前を末尾に追加 ─────────────────
  if [[ "$has_uncommitted" == true ]]; then
    local current_user
    current_user=$(git -C "$repo" config user.name 2>/dev/null)

    if [[ -n "$current_user" ]]; then
      # 現在のユーザー名を末尾に追加し、重複を排除
      authors=$(echo -e "$authors\n$current_user" | awk '!seen[$0]++')
    fi
  fi

  if [[ -z "$authors" ]]; then
    #echo ""
    return
  fi

  echo "$authors"
}

# スクリプト実行時のエントリポイント
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [[ -z "$1" ]]; then
    echo "Usage: $0 <file-path>"
    exit 1
  fi
  get_file_author "$1"
fi
