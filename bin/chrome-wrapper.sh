#!/bin/bash

# ------------------------------------------------------------------------------
# chrome-wrapper.sh
#
# 概要:
# このスクリプトは Puppeteer で Chromium を起動する際に使用するラッパーである。
# WSL 環境などで起こり得る DevTools WebSocket の接続タイミング競合を防ぐために、
# stderr に出力される "DevTools listening on ws://..." の行を一時的にバッファリングし、
# 対応するポートが LISTEN 状態かつ完全に使用可能になるまで待機してから Puppeteer に渡す。
#
# この対策をしないと、puppeteer.launch() で
# connect ECONNREFUSED 127.0.0.1:{PORT} のエラーが発生することがある。
#
# 利用方法:
#   chmod +x chrome-wrapper.sh
#   export PUPPETEER_EXECUTABLE_PATH="./chrome-wrapper.sh"
#   node your-script.js
#
# ------------------------------------------------------------------------------

echo "Chrome wrapper script started." >&2

# Puppeteer に組み込まれた Chromium のパスを取得する
# このシェル自身が PUPPETEER_EXECUTABLE_PATH に設定されているため、
# 再帰防止として一時的に PUPPETEER_EXECUTABLE_PATH を無効化する
CHROME=$(unset PUPPETEER_EXECUTABLE_PATH && node -e "console.log(require('puppeteer').executablePath())")
if [ ! -x "$CHROME" ]; then
  echo "Chromium not found: $CHROME" >&2
  exit 1
fi

# Puppeteer に返す stderr を FD 3 に退避しておく
exec 3>&2

# stderr の行を一時的に受け取るための FIFO (名前付きパイプ) を作成する
FIFO=$(mktemp -u)
mkfifo "$FIFO"
trap 'rm -f "$FIFO"' EXIT

# DevTools 行が現れたらポートが LISTEN 状態になるまで出力を遅延させる
(
  PORT_LINE=""
  BUFFERED_OUTPUT=""
  while IFS= read -r line; do
    if [[ "$line" == DevTools\ listening\ on\ ws://127.0.0.1:* ]]; then
      # ポート番号を抽出する
      PORT=$(echo "$line" | grep -oP 'ws://127\.0\.0\.1:\K[0-9]+')
      PORT_LINE="$line"

      # 該当ポートが完全に使用可能になるまで待機（LISTEN 状態 + /json/version 応答）
      for i in {1..50}; do
        if [ "$(ss -tln | awk '{print $1, $4}' | grep -E '^LISTEN\s+127\.0\.0\.1:'"$PORT"'$' | wc -l)" -gt 0 ]; then
          if curl -s --max-time 0.2 "http://127.0.0.1:$PORT/json/version" | grep -q '"webSocketDebuggerUrl"'; then
            break
          fi
        fi
        sleep 0.05
      done

      # 抑制していた出力をまとめて Puppeteer に返す
      echo "$BUFFERED_OUTPUT" >&3
      echo "$line" >&3
      BUFFERED_OUTPUT=""
    else
      # DevTools 行がまだ現れていない間はバッファする
      if [ -z "$PORT_LINE" ]; then
        BUFFERED_OUTPUT+="$line"$'\n'
      else
        echo "$line" >&3
      fi
    fi
  done < "$FIFO"
) &

# Chrome を起動し、その stderr を FIFO に流す (stdout はそのまま)
"$CHROME" "$@" 2> "$FIFO"
