#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
eval "$(awk '
    /^configure_external_puppeteer_browser\(\)/,/^}/
    /^compute_setup_hash\(\)/,/^}/
    /^install_node_modules_and_browsers\(\)/,/^}/
    /^print_browser_executable\(\)/,/^}/
' "${SCRIPT_DIR}/pub_markdown_core.sh")"

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

expect_managed_browser() {
    DOCSFW_EXTERNAL_BROWSER=true
    configure_external_puppeteer_browser
    [[ "$DOCSFW_EXTERNAL_BROWSER" == "false" ]]
}

unset PUPPETEER_EXECUTABLE_PATH PUPPETEER_SKIP_DOWNLOAD ORG_PUPPETEER_EXECUTABLE_PATH
expect_managed_browser

PUPPETEER_SKIP_DOWNLOAD=true
expect_managed_browser

PUPPETEER_EXECUTABLE_PATH="${tmp_dir}/missing-chrome"
ORG_PUPPETEER_EXECUTABLE_PATH="${tmp_dir}/stale-chrome"
expect_managed_browser
[[ -z "${PUPPETEER_EXECUTABLE_PATH:-}" ]]
[[ -z "${ORG_PUPPETEER_EXECUTABLE_PATH:-}" ]]

PUPPETEER_EXECUTABLE_PATH="${SCRIPT_DIR}/chrome-wrapper.sh"
expect_managed_browser
[[ -z "${PUPPETEER_EXECUTABLE_PATH:-}" ]]

PUPPETEER_EXECUTABLE_PATH=/bin/true
configure_external_puppeteer_browser
[[ "$DOCSFW_EXTERNAL_BROWSER" == "true" ]]
[[ "$PUPPETEER_EXECUTABLE_PATH" == "/bin/true" ]]

legacy_hash=$(cat "${SCRIPT_DIR}/package.json" "${SCRIPT_DIR}/package-lock.json" | sha256sum | awk '{print $1}')
DOCSFW_EXTERNAL_BROWSER=false
[[ "$(compute_setup_hash)" == "$legacy_hash" ]]
DOCSFW_EXTERNAL_BROWSER=true
[[ "$(compute_setup_hash)" != "$legacy_hash" ]]

command_log="${tmp_dir}/commands.log"
npm() {
    printf 'npm %s skip=%s\n' "$*" "${PUPPETEER_SKIP_DOWNLOAD:-}" >> "$command_log"
}
npx() {
    printf 'npx %s skip=%s\n' "$*" "${PUPPETEER_SKIP_DOWNLOAD:-}" >> "$command_log"
}

DOCSFW_EXTERNAL_BROWSER=true
install_node_modules_and_browsers
[[ "$(sed -n '1p' "$command_log")" == "npm ci skip=1" ]]
[[ "$(wc -l < "$command_log")" -eq 1 ]]

: > "$command_log"
DOCSFW_EXTERNAL_BROWSER=false
install_node_modules_and_browsers
[[ "$(sed -n '1p' "$command_log")" == "npm ci skip=1" ]]
[[ "$(sed -n '2p' "$command_log")" == "npx puppeteer browsers install chrome skip=" ]]
[[ "$(sed -n '3p' "$command_log")" == "npx puppeteer browsers install chrome-headless-shell skip=" ]]
[[ "$(wc -l < "$command_log")" -eq 3 ]]

(
    export PUPPETEER_EXECUTABLE_PATH=/bin/true
    unset ORG_PUPPETEER_EXECUTABLE_PATH
    source "${SCRIPT_DIR}/prepare_puppeteer_env.sh"
    [[ "$PUPPETEER_EXECUTABLE_PATH" -ef "${SCRIPT_DIR}/chrome-wrapper.sh" ]]
    [[ "$ORG_PUPPETEER_EXECUTABLE_PATH" == "/bin/true" ]]
)

browser_report="${tmp_dir}/browser-executable"
DOCSFW_BROWSER_EXECUTABLE_REPORT_FILE="$browser_report" \
ORG_PUPPETEER_EXECUTABLE_PATH=/bin/true \
PUPPETEER_EXECUTABLE_PATH="${SCRIPT_DIR}/chrome-wrapper.sh" \
    "${SCRIPT_DIR}/chrome-wrapper.sh" --version >/dev/null 2>&1
[[ "$(cat "$browser_report")" == "/bin/true" ]]

DOCSFW_BROWSER_EXECUTABLE_REPORT_FILE="${tmp_dir}/missing/browser-executable" \
ORG_PUPPETEER_EXECUTABLE_PATH=/bin/true \
PUPPETEER_EXECUTABLE_PATH="${SCRIPT_DIR}/chrome-wrapper.sh" \
    "${SCRIPT_DIR}/chrome-wrapper.sh" --version >/dev/null 2>&1

fallback_chrome="${tmp_dir}/chrome/linux-999.0.0.0/chrome-linux64/chrome"
missing_chrome="${tmp_dir}/chrome/linux-100.0.0.0/chrome-linux64/chrome"
mkdir -p "$(dirname "$fallback_chrome")"
printf '#!/usr/bin/env bash\nexit 0\n' > "$fallback_chrome"
chmod +x "$fallback_chrome"
(
    node() {
        printf '%s\n' "$FAKE_PUPPETEER_EXECUTABLE"
    }
    export -f node
    export FAKE_PUPPETEER_EXECUTABLE="$missing_chrome"
    export DOCSFW_BROWSER_EXECUTABLE_REPORT_FILE="$browser_report"
    unset ORG_PUPPETEER_EXECUTABLE_PATH PUPPETEER_EXECUTABLE_PATH
    "${SCRIPT_DIR}/chrome-wrapper.sh" --version >/dev/null 2>&1
)
[[ "$(cat "$browser_report")" == "$fallback_chrome" ]]

[[ "$(print_browser_executable "$browser_report")" == "Browser executable: ${fallback_chrome}" ]]
rm -f "$browser_report"
[[ "$(print_browser_executable "$browser_report")" == "Browser executable: (unknown)" ]]

printf 'puppeteer setup tests passed.\n'
