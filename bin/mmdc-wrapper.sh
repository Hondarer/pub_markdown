#!/bin/bash

SCRIPT_DIR=$(cd $(dirname "$0"); pwd)

# 共有ブラウザが利用可能な場合は mmdc-reuse.js を使用
if [[ -n "${PUB_MARKDOWN_BROWSER_WS_FILE}" ]] && [[ -f "${PUB_MARKDOWN_BROWSER_WS_FILE}" ]]; then
    node "${SCRIPT_DIR}/mmdc-reuse.js" "$@"
else
    # prepare to chrome-wrapper.sh
    . "${SCRIPT_DIR}/prepare_puppeteer_env.sh"

    # Pass all arguments from shell script to mmdc
    "${SCRIPT_DIR}/node_modules/.bin/mmdc" "$@"
fi
