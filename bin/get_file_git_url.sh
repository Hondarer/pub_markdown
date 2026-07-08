#!/usr/bin/env bash

# get_file_git_url FILEPATH
#   Markdown ソース ファイルに対応する Git ホスティング上の単一ページ (blob ビュー) URL を解決する。
#
#   出力 (標準出力 1 行): "<url><TAB><provider>"
#     provider は github / gitlab / gitbucket / gitea / git のいずれか (アイコン選択に使用)。
#   以下の場合は何も出力しない (= リンクを表示しない):
#     ・git コマンドが使えない
#     ・Git 管理下にない (未追跡)
#     ・.gitignore 対象 (例: doxyfw 等の生成物 .md)
#     ・remote URL が解決できない
#
#   マージ機能 (mergeSubfolderDocs) でサブモジュール配下の docs を取り込んでいても、
#   入力はディスク上の実体パスのため git rev-parse --show-toplevel が当該リポジトリ
#   (サブモジュールならサブモジュール ルート) を返し、その remote が解決先になる。
#
#   環境変数:
#     GIT_LINK_HOST_PROVIDER  自己ホスト用 host=provider マッピング (スペース区切り)。
#                             provider@webhost 形式で Web ホストの読み替えも指定可能。
#                             例: "git.example.com=gitlab githost.example.com=gitlab@www.example.com"

resolve_file_git_context() {
  local file=$1
  local require_tracked=${2:-true}

  # 1) git コマンドの存在チェック
  if ! command -v git &>/dev/null; then
    return
  fi

  # 2) ファイルの絶対パスを取得 (シンボリックリンクは実体へ解決)
  # .agents/skills 配下のように symlink 経由で発行されるファイルに対応するため、
  # ディレクトリ部を pwd -P で物理パスへ解決する。これにより git の索引上の実体パス
  # (リンク先のリポジトリ / サブモジュール) で追跡・remote を解決できる。
  local abs_file abs_dir
  abs_dir="$(cd "$(dirname "$file")" 2>/dev/null && pwd -P)"
  if [[ -n "$abs_dir" ]]; then
    abs_file="$abs_dir/$(basename "$file")"
  elif [[ "$file" = /* ]]; then
    abs_file="$file"
  else
    abs_file="$PWD/$file"
  fi

  # 3) Git リポジトリのルートを取得
  local repo
  repo=$(git -C "$(dirname "$abs_file")" rev-parse --show-toplevel 2>/dev/null) || return

  # 4) リポジトリ ルートからの相対パスを計算
  local rel
  # MinGW 環境でのパス形式の違いに対応 (get_file_date.sh と同手法)
  if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    local unix_repo unix_file
    unix_repo=$(cygpath -u "$repo" 2>/dev/null || echo "$repo" | sed 's|\\|/|g; s|^\([A-Za-z]\):|/\L\1|')
    unix_file=$(cygpath -u "$abs_file" 2>/dev/null || echo "$abs_file" | sed 's|\\|/|g; s|^\([A-Za-z]\):|/\L\1|')
    if [[ "$unix_file" == "$unix_repo"/* ]]; then
      rel="${unix_file#"$unix_repo"/}"
    else
      rel=$(git -C "$repo" ls-files --full-name -- "$abs_file" 2>/dev/null | head -1)
      [[ -z "$rel" ]] && return
    fi
  else
    if [[ "$abs_file" == "$repo"/* ]]; then
      rel="${abs_file#"$repo"/}"
    else
      rel=$(git -C "$repo" ls-files --full-name -- "$abs_file" 2>/dev/null | head -1)
      [[ -z "$rel" ]] && return
    fi
  fi

  if [[ "$require_tracked" == "true" ]]; then
    # 5) 管理下にあるかチェック (未追跡なら非表示)
    if ! git -C "$repo" ls-files --error-unmatch -- "$rel" &>/dev/null; then
      return
    fi

    # 6) .gitignore 対象なら非表示 (生成物 .md 等を除外)
    if git -C "$repo" check-ignore -q -- "$rel" 2>/dev/null; then
      return
    fi
  fi

  printf '%s\t%s\n' "$repo" "$rel"
}

# host から provider 種別 (および Web ホスト読み替え) を判定する
#   引数: host
#   出力: "<provider>\t<webhost>" (webhost が無い場合は "<provider>" のみ)
#   設定形式: host=provider または host=provider@webhost
detect_provider() {
  local host=$1
  local entry entry_host entry_value entry_provider entry_webhost

  # 設定マッピングを最優先で参照する
  for entry in $GIT_LINK_HOST_PROVIDER; do
    entry_host="${entry%%=*}"
    entry_value="${entry#*=}"
    if [[ "$entry_host" == "$host" ]]; then
      # provider@webhost 形式を分解する
      if [[ "$entry_value" == *@* ]]; then
        entry_provider="${entry_value%%@*}"
        entry_webhost="${entry_value#*@}"
        printf '%s\t%s\n' "$entry_provider" "$entry_webhost"
      else
        echo "$entry_value"
      fi
      return
    fi
  done

  # 既知の公開ホストを自動判定する
  case "$host" in
    github.com)
      echo "github"
      ;;
    gitlab.com)
      echo "gitlab"
      ;;
    *gitlab*)
      echo "gitlab"
      ;;
    *gitbucket*)
      echo "gitbucket"
      ;;
    *)
      # 不明なホストは汎用 Git 扱い (URL 形式は GitHub 系 /blob/ を用いる)
      echo "git"
      ;;
  esac
}

# remote URL を web ベース URL (scheme://host/owner/repo) に正規化する
#   引数: remote_url
#   出力: "<base_url><TAB><host>" (解決不可なら空)
normalize_remote_url() {
  local url=$1
  local host rest base

  # 末尾の .git を除去
  url="${url%.git}"
  # 末尾スラッシュを除去
  url="${url%/}"

  if [[ "$url" =~ ^https?:// ]]; then
    # https://host/owner/repo または http://host/owner/repo
    base="$url"
    rest="${url#*://}"
    host="${rest%%/*}"
  elif [[ "$url" =~ ^ssh:// ]]; then
    # ssh://git@host[:port]/owner/repo
    rest="${url#ssh://}"
    rest="${rest#*@}"          # user@ を除去
    host="${rest%%/*}"         # host[:port]
    host="${host%%:*}"         # port を除去
    base="https://${host}/${rest#*/}"
  elif [[ "$url" =~ ^[^/]+@[^/]+: ]]; then
    # git@host:owner/repo (scp ライク)
    rest="${url#*@}"           # host:owner/repo
    host="${rest%%:*}"
    base="https://${host}/${rest#*:}"
  else
    # 解決不可
    return
  fi

  printf '%s\t%s\n' "$base" "$host"
}

get_file_git_remote_context() {
  local repo=$1

  # remote URL を取得
  local remote_url
  remote_url=$(git -C "$repo" config --get remote.origin.url 2>/dev/null)
  [[ -z "$remote_url" ]] && return

  # web ベース URL と host を正規化
  local normalized base host
  normalized=$(normalize_remote_url "$remote_url")
  [[ -z "$normalized" ]] && return
  base="${normalized%%$'\t'*}"
  host="${normalized##*$'\t'}"

  # ─── 9) provider を判定 (webhost 読み替えがあれば base を置換) ────
  local provider_result provider webhost
  provider_result=$(detect_provider "$host")
  if [[ "$provider_result" == *$'\t'* ]]; then
    provider="${provider_result%%$'\t'*}"
    webhost="${provider_result##*$'\t'}"
    # base URL のホスト部分を webhost で置換する
    base="${base//$host/$webhost}"
  else
    provider="$provider_result"
  fi

  printf '%s\t%s\t%s\n' "$base" "$host" "$provider"
}

# パス セグメントを URL エンコードする (区切り '/' は保持)
urlencode_path() {
  local path=$1
  if command -v python3 &>/dev/null; then
    printf '%s' "$path" | python3 -c '
import sys, urllib.parse
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
sys.stdout.write(urllib.parse.quote(sys.stdin.read(), safe="/"))
'
  else
    # python3 が無い環境では素のパスを返す (ASCII パス前提)
    printf '%s' "$path"
  fi
}

get_file_git_provider() {
  local file=$1
  local context repo remote_context provider

  context=$(resolve_file_git_context "$file" false) || return
  repo="${context%%$'\t'*}"
  remote_context=$(get_file_git_remote_context "$repo") || return
  provider="${remote_context##*$'\t'}"
  [[ -z "$provider" ]] && return
  printf '%s\n' "$provider"
}

get_file_git_url() {
  local file=$1
  local context repo rel remote_context base provider

  context=$(resolve_file_git_context "$file" true) || return
  repo="${context%%$'\t'*}"
  rel="${context##*$'\t'}"

  remote_context=$(get_file_git_remote_context "$repo") || return
  base="${remote_context%%$'\t'*}"
  provider="${remote_context##*$'\t'}"

  # ref はリンク対象ファイルの最終コミット SHA とする。
  local ref
  ref=$(git -C "$repo" log -1 --format=%H -- "$rel" 2>/dev/null)
  [[ -z "$ref" ]] && return

  # blob URL を組み立て
  local encoded_rel url
  encoded_rel=$(urlencode_path "$rel")
  if [[ "$provider" == "gitlab" ]]; then
    url="${base}/-/blob/${ref}/${encoded_rel}"
  else
    # github / gitbucket / gitea / git (汎用) は /blob/ 形式
    url="${base}/blob/${ref}/${encoded_rel}"
  fi

  printf '%s\t%s\n' "$url" "$provider"
}

# スクリプト実行時のエントリポイント
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [[ "$1" == "--provider" ]]; then
    if [[ -z "$2" ]]; then
      echo "Usage: $0 --provider <file-path>" >&2
      exit 1
    fi
    get_file_git_provider "$2"
    exit 0
  fi

  if [[ -z "$1" ]]; then
    echo "Usage: $0 <file-path>" >&2
    exit 1
  fi
  get_file_git_url "$1"
fi
