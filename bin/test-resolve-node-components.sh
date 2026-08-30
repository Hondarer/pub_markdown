#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RESOLVER="${SCRIPT_DIR}/resolve-node-components.js"

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

node -e '
const { satisfiesRange, installAction, INSTALL_PACKAGES } = require(process.argv[1]);
if (!satisfiesRange("24.43.1", "^24.40.0")) process.exit(1);
if (satisfiesRange("25.0.0", "^24.40.0")) process.exit(1);
if (!satisfiesRange("0.34.9", "^0.34.5")) process.exit(1);
if (satisfiesRange("0.35.0", "^0.34.5")) process.exit(1);
if (!satisfiesRange("7.2.0", "7.2.0")) process.exit(1);
if (satisfiesRange("7.2.1", "7.2.0")) process.exit(1);
const none = installAction([]);
if (none.action !== "none") process.exit(1);
const ci = installAction(INSTALL_PACKAGES.slice());
if (ci.action !== "npm-ci") process.exit(1);
const partial = installAction(["puppeteer"]);
if (partial.action !== "npm-install" || partial.specs[0] !== "puppeteer") process.exit(1);
' "$RESOLVER"

report=$(node "$RESOLVER")
echo "$report" | node -e '
const fs = require("fs");
const data = JSON.parse(fs.readFileSync(0, "utf8"));
if (!data.paths || typeof data.paths.mmdc !== "string") process.exit(1);
if (!Object.prototype.hasOwnProperty.call(data, "action")) process.exit(1);
if (!Array.isArray(data.missing)) process.exit(1);
'

fake_root="${tmp_dir}/node_modules"
mkdir -p "${fake_root}/minimist"
printf '{"name":"minimist","version":"1.2.8"}\n' > "${fake_root}/minimist/package.json"

NODE_PATH="$fake_root" node "$RESOLVER" > "${tmp_dir}/with-global.json"
node -e '
const fs = require("fs");
const data = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
if (!data.packages.minimist || data.packages.minimist.source !== "global") process.exit(1);
if (data.packages.minimist.version !== "1.2.8") process.exit(1);
' "${tmp_dir}/with-global.json"

NODE_PATH="$fake_root" node "$RESOLVER" --dry-run --ensure > "${tmp_dir}/dry-run.json"
node -e '
const fs = require("fs");
const data = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
if (data.packages.minimist.source !== "global") process.exit(1);
if (data.action !== "none") process.exit(1);
if (data.missing.length !== 0) process.exit(1);
' "${tmp_dir}/dry-run.json"

old_range_root="${tmp_dir}/old/node_modules"
mkdir -p "${old_range_root}/puppeteer"
printf '{"name":"puppeteer","version":"23.0.0"}\n' > "${old_range_root}/puppeteer/package.json"
NODE_PATH="$old_range_root" node "$RESOLVER" > "${tmp_dir}/old-range.json"
node -e '
const fs = require("fs");
const data = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
const resolved = data.packages.puppeteer;
if (resolved && resolved.source === "global" && resolved.version === "23.0.0") process.exit(1);
' "${tmp_dir}/old-range.json"

env_out=$(node "$RESOLVER" --export-env)
echo "$env_out" | grep -q '^export DOCSFW_MMDC$'
echo "$env_out" | grep -q '^export DOCSFW_WIDDERSHINS$'

printf 'resolve-node-components tests passed.\n'
