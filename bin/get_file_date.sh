#!/usr/bin/env bash

# get_file_date FILEPATH
#   ・git コマンドが使えない           → ファイルの最終更新時刻 (RFC2822)
#   ・Git 管理下にない                 → ファイルの最終更新時刻 (RFC2822)
#   ・Git 管理下にあり、変更あり       → ファイルの最終更新時刻 (RFC2822) + " " + 最終コミットID + "+"
#   ・Git 管理下にあり、変更なし       → 最終コミット時刻 (RFC2822) + " " + 最終コミットID
get_file_date() {
  local file=$1

  # ─── 0) ファイルの絶対パスを取得 ───────────────────────────────
  local abs_file
  if [[ "$file" = /* ]]; then
    # 既に絶対パス
    abs_file="$file"
  else
    # 相対パスを絶対パスに変換
    abs_file="$(cd "$(dirname "$file")" && pwd)/$(basename "$file")"
  fi

  # デバッグ用出力
  #echo "abs_file=$abs_file" >&2

  # ─── 1) git コマンドの存在チェック ─────────────────────────────
  if ! command -v git &>/dev/null; then
    # git コマンドがない → ファイルの最終更新時刻
    echo "$(LC_TIME=C date -R -r "$abs_file")"
    return
  fi

  # ─── 2) Git リポジトリのルートを取得 ───────────────────────────
  local repo
  repo=$(git -C "$(dirname "$abs_file")" rev-parse --show-toplevel 2>/dev/null) || {
    # ルートが取得できない → ファイルの最終更新時刻
    echo "$(LC_TIME=C date -R -r "$abs_file")"
    return
  }

  # デバッグ用出力
  #echo "repo=$repo" >&2

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
      rel=$(git -C "$repo" ls-files --full-name -- "$abs_file" 2>/dev/null | head -1)
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
      rel=$(git -C "$repo" ls-files --full-name -- "$abs_file" 2>/dev/null | head -1)
      if [[ -z "$rel" ]]; then
        #echo ""
        return
      fi
    fi
  fi

  # デバッグ用出力
  #echo "rel=$rel" >&2

  # ─── 4) 管理下にあるかチェック ─────────────────────────────────
  if ! git -C "$repo" ls-files --error-unmatch -- "$rel" &>/dev/null; then
    # 管理下にない → ファイルの最終更新時刻
    echo "$(LC_TIME=C date -R -r "$abs_file")"
    return
  fi

  # ─── 5) 未コミット差分の有無チェック ─────────────────────────────
  if ! git -C "$repo" diff --quiet HEAD -- "$rel"; then
    # 差分あり → ファイルの最終更新時刻 (RFC2822) + " " + 最終コミットID + "+"
    local commit_id
    commit_id=$(git -C "$repo" log -1 --format=%h -- "$rel")
    echo "$(LC_TIME=C date -R -r "$abs_file") $commit_id+"
  else
    # 差分なし → 最終コミットのコミッター日時 (RFC2822) + " " + 最終コミットID
    git -C "$repo" log -1 --format="%cD %h" -- "$rel"
  fi
}

# スクリプト実行時のエントリポイント
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [[ -z "$1" ]]; then
    echo "Usage: $0 <file-path>"
    exit 1
  fi
  get_file_date "$1"
fi
