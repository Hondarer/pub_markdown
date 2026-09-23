#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RESOLVER="${SCRIPT_DIR}/resolve-node-components.js"

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

# node へ渡すパスを、実行中の node が解釈できる形式にする。
# Git Bash (MSYS) は引数などの POSIX 形式のパスを変換するが、JSON の値やスクリプト本文に埋め込んだパスは変換しない。
# see: https://www.msys2.org/docs/filesystem-paths/
native_path() {
    if command -v cygpath > /dev/null 2>&1; then
        cygpath -m "$1"
    else
        printf '%s\n' "$1"
    fi
}

NATIVE_SCRIPT_DIR=$(native_path "$SCRIPT_DIR")

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
fake_root=$(native_path "$fake_root")

NODE_PATH="$fake_root" node "$RESOLVER" > "${tmp_dir}/with-global.json"
node -e '
const fs = require("fs");
const data = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
if (!data.packages.minimist || data.packages.minimist.source !== "global") process.exit(1);
if (data.packages.minimist.version !== "1.2.8") process.exit(1);
' "${tmp_dir}/with-global.json"

# 共有側に適合するバージョンが存在しないパッケージは、ローカルの node_modules を継続して使用する。
# 未導入のパッケージ (WSL から見た Windows 側のローカル ツリーなど) は固定の対象外であることだけを確認する。
node -e '
const fs = require("fs");
const path = require("path");
const data = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
const localRoot = path.resolve(process.argv[2]);
if (data.packages.minimist.source !== "global") process.exit(1);
Object.keys(data.packages).forEach((name) => {
  const resolved = data.packages[name];
  const pinned = Object.prototype.hasOwnProperty.call(data.globalPackages, name);
  if (!resolved) {
    if (pinned) process.exit(1);
    return;
  }
  if (resolved.source === "global") {
    if (!pinned || data.globalPackages[name] !== resolved.dir) process.exit(1);
    return;
  }
  if (pinned) process.exit(1);
  if (path.resolve(resolved.dir).indexOf(localRoot) !== 0) process.exit(1);
});
' "${tmp_dir}/with-global.json" "${SCRIPT_DIR}/node_modules"

NODE_PATH="$fake_root" node "$RESOLVER" --dry-run --ensure > "${tmp_dir}/dry-run.json"
node -e '
const fs = require("fs");
const data = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
if (data.packages.minimist.source !== "global") process.exit(1);
// グローバルから採用したパッケージは導入対象にしない。ほかの未導入パッケージの有無は実行環境に依存する。
if (data.missing.indexOf("minimist") !== -1) process.exit(1);
if (data.missing.length === 0 && data.action !== "none") process.exit(1);
' "${tmp_dir}/dry-run.json"

old_range_root="${tmp_dir}/old/node_modules"
mkdir -p "${old_range_root}/puppeteer"
printf '{"name":"puppeteer","version":"23.0.0"}\n' > "${old_range_root}/puppeteer/package.json"
old_range_root=$(native_path "$old_range_root")
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
echo "$env_out" | grep -q '^export DOCSFW_NODE_GLOBAL_PACKAGES$'

# グローバルから採用したパッケージは、root ではなくディレクトリ単位で公開する。
# 実行環境の共有ツリーから採用したパッケージも並ぶため、キーの順序ではなく minimist の採用先で判定する。
NODE_PATH="$fake_root" node "$RESOLVER" --export-env > "${tmp_dir}/global-env.sh"
(
    # shellcheck source=/dev/null
    . "${tmp_dir}/global-env.sh"
    node -e '
const path = require("path");
const packages = JSON.parse(process.env.DOCSFW_NODE_GLOBAL_PACKAGES || "{}");
if (typeof packages.minimist !== "string") process.exit(1);
if (path.resolve(packages.minimist) !== path.resolve(process.argv[1], "minimist")) process.exit(1);
' "$fake_root"
)

# 異なるプラットフォームの node_modules を採用しないことを確認する。
node -e '
const { parseWindowsMountPoints, isForeignPlatformPath } = require(process.argv[1]);
const mounts = [
  "C:\\134 /mnt/c 9p rw,noatime,aname=drvfs;path=C:\\;uid=1000,cache=5 0 0",
  "D:\\134 /mnt/d drvfs rw,noatime 0 0",
  "E:\\134 /mnt/my\\040disk drvfs rw,noatime 0 0",
  "drivers /usr/lib/wsl/drivers 9p ro,nosuid,aname=drivers,cache=5 0 0",
  "/dev/sdd / ext4 rw,relatime 0 0",
  "",
].join("\n");
const points = parseWindowsMountPoints(mounts);
const expected = ["/mnt/c", "/mnt/d", "/mnt/my disk"];
if (points.join("|") !== expected.join("|")) process.exit(1);
if (process.platform !== "win32") {
  if (!isForeignPlatformPath("/mnt/c/devbin/bin/node_modules", points)) process.exit(1);
  if (!isForeignPlatformPath("/mnt/my disk/node_modules", points)) process.exit(1);
  if (isForeignPlatformPath("/mnt/city/node_modules", points)) process.exit(1);
  if (isForeignPlatformPath("/home/user/node_modules", points)) process.exit(1);
}
' "$RESOLVER"

# 固定の規則 (採用先を含む node_modules の算出と、指定子の一致判定) を確認する。
node -e '
const path = require("path");
const pinned = require(process.argv[1]);
const root = path.resolve("/docsfw-test/lib/node_modules");
const entries = pinned.buildEntries({
  "@docsfw/scoped": path.join(root, "@docsfw", "scoped"),
  "plain": path.join(root, "plain"),
});
if (entries.length !== 2) process.exit(1);
entries.forEach((entry) => {
  if (entry.root !== root) process.exit(1);
  if (entry.parentURL.indexOf("file:") !== 0) process.exit(1);
});
if (pinned.findEntry(entries, "@docsfw/scoped/sub").name !== "@docsfw/scoped") process.exit(1);
if (pinned.findEntry(entries, "plain") === null) process.exit(1);
if (pinned.findEntry(entries, "plainer") !== null) process.exit(1);
if (pinned.findEntry(entries, "./plain") !== null) process.exit(1);
' "${SCRIPT_DIR}/docsfw-pinned-packages.js"

# 採用したパッケージだけを require の解決先へ固定する。
# 採用先が node_modules 配下にない場合は、ディレクトリへの読み替えで解決する。
fake_pkg=$(native_path "${tmp_dir}/pinned/minimist")
mkdir -p "$fake_pkg"
printf '{"name":"minimist","version":"1.2.8","main":"index.js"}\n' > "${fake_pkg}/package.json"
printf 'module.exports = "pinned";\n' > "${fake_pkg}/index.js"
DOCSFW_NODE_GLOBAL_PACKAGES="{\"minimist\":\"${fake_pkg}\"}" \
    node --require "${SCRIPT_DIR}/docsfw-prefer-global-modules.js" -e '
const path = require("path");
const expected = path.join(process.argv[1], "index.js");
if (require.resolve("minimist") !== expected) process.exit(1);
if (require("minimist") !== "pinned") process.exit(1);
if (require.resolve("minimist/package.json") !== path.join(process.argv[1], "package.json")) process.exit(1);
// 固定していないパッケージは通常の解決に従い、探索先を差し替えない。
let notFound = false;
try {
  require.resolve("docsfw-not-installed-package");
} catch (error) {
  notFound = error.code === "MODULE_NOT_FOUND";
}
if (!notFound) process.exit(1);
' "$fake_pkg"

# 採用先が node_modules 配下にある場合は、package.json の exports 定義に従って解決する。
# ディレクトリを直接指定すると main が選ばれ、require 用ではないエントリが読み込まれる。
exports_root=$(native_path "${tmp_dir}/exports/node_modules")
exports_pkg="${exports_root}/docsfw-pinned-sample"
mkdir -p "$exports_pkg"
cat > "${exports_pkg}/package.json" <<'PACKAGE_JSON'
{
  "name": "docsfw-pinned-sample",
  "version": "1.0.0",
  "main": "main.js",
  "exports": {
    ".": {
      "require": "./required.cjs",
      "import": "./imported.mjs"
    }
  }
}
PACKAGE_JSON
printf 'module.exports = "main";\n' > "${exports_pkg}/main.js"
printf 'module.exports = "required";\n' > "${exports_pkg}/required.cjs"
printf 'export default "imported";\n' > "${exports_pkg}/imported.mjs"

export DOCSFW_NODE_GLOBAL_PACKAGES="{\"docsfw-pinned-sample\":\"${exports_pkg}\"}"

node --require "${SCRIPT_DIR}/docsfw-prefer-global-modules.js" -e '
if (require("docsfw-pinned-sample") !== "required") process.exit(1);
'

# ES モジュールの import は require のフックを通らないため、同じ固定を解決フックで行う。
node --require "${SCRIPT_DIR}/docsfw-prefer-global-modules.js" --input-type=module -e '
const pinnedModule = await import("docsfw-pinned-sample");
if (pinnedModule.default !== "imported") process.exit(1);
// 固定していないパッケージは通常の解決に従う。
let notFound = false;
try {
  await import("docsfw-not-installed-package");
} catch (error) {
  notFound = error.code === "ERR_MODULE_NOT_FOUND";
}
if (!notFound) process.exit(1);
'

# module.registerHooks を持たない Node.js では module.register 経由で同じ固定を行う。
cat > "${tmp_dir}/without-register-hooks.js" <<PRELOAD
require("module").registerHooks = undefined;
require("${NATIVE_SCRIPT_DIR}/docsfw-prefer-global-modules.js");
PRELOAD
node --require "${tmp_dir}/without-register-hooks.js" --input-type=module -e '
const pinnedModule = await import("docsfw-pinned-sample");
if (pinnedModule.default !== "imported") process.exit(1);
'

unset DOCSFW_NODE_GLOBAL_PACKAGES

printf 'resolve-node-components tests passed.\n'
