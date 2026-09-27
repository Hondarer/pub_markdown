#!/bin/bash

# ------------------------------------------------------------------------------
# chrome-wrapper.sh
#
# 概要:
# このスクリプトは Puppeteer で Chromium を起動する際に使用するラッパーです。
# WSL 環境などで発生し得る DevTools WebSocket の接続タイミング競合を防ぐために、
# stderr に出力される "DevTools listening on ws://..." の行を一時的にバッファリングし、
# 対応するポートが LISTEN 状態かつ完全に使用可能になるまで待機してから Puppeteer に渡します。
#
# この対策を実施しない場合、puppeteer.launch() で
# connect ECONNREFUSED 127.0.0.1:{PORT} のエラーが発生することがあります。
#
# 利用方法:
#   chmod +x chrome-wrapper.sh
#   export ORG_PUPPETEER_EXECUTABLE_PATH="{IF_YOU_WANT_SPECIFY_IT}"
#   export PUPPETEER_EXECUTABLE_PATH="./chrome-wrapper.sh"
#   node your-script.js
#
# ------------------------------------------------------------------------------

echo "Chrome wrapper script started." >&2

# このシェル自身が PUPPETEER_EXECUTABLE_PATH に設定されているため、
# 元の PUPPETEER_EXECUTABLE_PATH を復元します。
if [[ ! -z "${ORG_PUPPETEER_EXECUTABLE_PATH}" ]]; then
  export PUPPETEER_EXECUTABLE_PATH="$ORG_PUPPETEER_EXECUTABLE_PATH"
else
  unset PUPPETEER_EXECUTABLE_PATH
fi

# Puppeteer に組み込まれた Chromium のパスを取得します。
CHROME=$(cd "$(dirname "$0")" && node -e \
  "Promise.resolve(require('puppeteer').executablePath()).then(console.log).catch(error => { console.error(error); process.exit(1); })")
if [ ! -x "$CHROME" ]; then
  echo "Chromium not found at: $CHROME" >&2

  # executablePath() の戻り値からキャッシュ ディレクトリの親ディレクトリを推定
  # 例: /home/user/.cache/puppeteer/chrome/linux-142.0.7444.175/chrome-linux64/chrome
  #     → /home/user/.cache/puppeteer/chrome
  PUPPETEER_CACHE_DIR=$(dirname "$(dirname "$CHROME")")

  # パスにバージョン番号らしき部分 (linux-X.X.X.X) が含まれるか確認
  if [[ "$CHROME" =~ (.*)/linux-[0-9.]+/(.*) ]]; then
    PUPPETEER_CACHE_DIR="${BASH_REMATCH[1]}"
    CHROME_SUBPATH="${BASH_REMATCH[2]}"

    echo "Searching for alternative Chromium in $PUPPETEER_CACHE_DIR..." >&2

    if [ -d "$PUPPETEER_CACHE_DIR" ]; then
      # 各バージョン ディレクトリ内の chrome 実行ファイルを検索し、バージョン順にソートします。
      # 元のパスと同一のサブパス構造を持つものを優先します。
      LATEST_CHROME=$(find "$PUPPETEER_CACHE_DIR" -type f -path "*/linux-*/$CHROME_SUBPATH" -executable 2>/dev/null | while read chrome_path; do
        # パスからバージョン番号を抽出 (例: linux-142.0.7444.175 から 142.0.7444.175)
        version=$(echo "$chrome_path" | grep -oP 'linux-\K[0-9.]+' | head -1)
        if [ ! -z "$version" ]; then
          echo "$version $chrome_path"
        fi
      done | sort -V -r | head -1 | awk '{print $2}')

      if [ ! -z "$LATEST_CHROME" ] && [ -x "$LATEST_CHROME" ]; then
        CHROME="$LATEST_CHROME"
        echo "Using alternative Chromium: $CHROME" >&2
      else
        echo "No alternative Chromium found in $PUPPETEER_CACHE_DIR" >&2
        exit 1
      fi
    else
      echo "Puppeteer cache directory not found: $PUPPETEER_CACHE_DIR" >&2
      exit 1
    fi
  else
    echo "Unable to determine cache directory structure from path: $CHROME" >&2
    exit 1
  fi
fi

# Browser Server から指定された場合は、代替バージョンの探索後に確定した
# Chrome の実行パスを診断表示用のファイルへ記録します。
if [[ -n "${DOCSFW_BROWSER_EXECUTABLE_REPORT_FILE:-}" ]]; then
  if ! printf '%s\n' "$CHROME" > "$DOCSFW_BROWSER_EXECUTABLE_REPORT_FILE"; then
    echo "Unable to report browser executable: $DOCSFW_BROWSER_EXECUTABLE_REPORT_FILE" >&2
  fi
  unset DOCSFW_BROWSER_EXECUTABLE_REPORT_FILE
fi

# Puppeteer に返す stderr を FD 3 に退避します。
exec 3>&2

# stderr の行を一時的に受け取るための FIFO (名前付きパイプ) を作成します。
FIFO=$(mktemp -u)
mkfifo "$FIFO"
trap 'rm -f "$FIFO"' EXIT

# DevTools 行が現れた場合は、ポートが LISTEN 状態になるまで出力を遅延させます。
(
  PORT_LINE=""
  BUFFERED_OUTPUT=""
  while IFS= read -r line; do
    if [[ "$line" == DevTools\ listening\ on\ ws://127.0.0.1:* ]]; then
      # ポート番号を抽出します。
      PORT=$(echo "$line" | grep -oP 'ws://127\.0\.0\.1:\K[0-9]+')
      PORT_LINE="$line"

      # 該当ポートが完全に使用可能になるまで待機 (LISTEN 状態 + /json/version 応答)
      for i in {1..50}; do
        if [ "$(ss -tln | awk '{print $1, $4}' | grep -E '^LISTEN\s+127\.0\.0\.1:'"$PORT"'$' | wc -l)" -gt 0 ]; then
          if curl -s --max-time 0.2 "http://127.0.0.1:$PORT/json/version" | grep -q '"webSocketDebuggerUrl"'; then
            break
          fi
        fi
        sleep 0.05
      done

      # 抑制していた出力を一括して Puppeteer に返します。
      echo "$BUFFERED_OUTPUT" >&3
      echo "$line" >&3
      BUFFERED_OUTPUT=""
    else
      # DevTools 行がまだ現れていない間はバッファリングします。
      if [ -z "$PORT_LINE" ]; then
        BUFFERED_OUTPUT+="$line"$'\n'
      else
        echo "$line" >&3
      fi
    fi
  done < "$FIFO"
) &

# Chrome を起動し、その stderr を FIFO に渡します (stdout はそのまま)。
# --no-sandbox: CI/コンテナー環境ではサンドボックスが使用できないため無効化する。
# このラッパー経由の起動は自動レンダリング用途 (Mermaid/SVG 変換等) に限られるため安全です。
"$CHROME" --no-sandbox "$@" 2> "$FIFO"
