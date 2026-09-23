#!/usr/bin/env node
'use strict';

/**
 * Resolve docsfw npm components from a global prefix first, then from
 * framework/docsfw/bin/node_modules. Optionally install only the missing
 * top-level packages.
 *
 * Usage:
 *   node resolve-node-components.js
 *   node resolve-node-components.js --ensure
 *   node resolve-node-components.js --export-env
 *   node resolve-node-components.js --ensure --export-env
 *   node resolve-node-components.js --dry-run --ensure
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const SCRIPT_DIR = __dirname;
const PACKAGE_JSON_PATH = path.join(SCRIPT_DIR, 'package.json');
const PACKAGE_LOCK_PATH = path.join(SCRIPT_DIR, 'package-lock.json');
const LOCAL_NODE_MODULES = path.join(SCRIPT_DIR, 'node_modules');

const INSTALL_PACKAGES = [
  '@mermaid-js/mermaid-cli',
  '@plantuml/core',
  'minimist',
  'minisearch',
  'puppeteer',
  'puppeteer-core',
  'sharp',
  'widdershins',
];

const CLI_NAMES = {
  '@mermaid-js/mermaid-cli': 'mmdc',
  widdershins: 'widdershins',
};

function parseArgs(argv) {
  return {
    ensure: argv.includes('--ensure'),
    exportEnv: argv.includes('--export-env'),
    dryRun: argv.includes('--dry-run'),
  };
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

// A Windows file system seen from WSL holds no native modules for the running
// platform, so node_modules trees from the other platform are never adopted.
// Locate where Windows drives are mounted to recognize them.
const WINDOWS_DRIVE_FS_TYPES = ['drvfs'];
const PROC_MOUNTS_PATH = '/proc/mounts';

let windowsMountPointsCache = null;

function unescapeMountField(value) {
  return String(value).replace(/\\([0-7]{3})/g, (match, code) => String.fromCharCode(parseInt(code, 8)));
}

function isWindowsDriveMount(fsType, options) {
  if (WINDOWS_DRIVE_FS_TYPES.indexOf(fsType) !== -1) {
    return true;
  }
  // WSL2 exposes drvfs through 9p or virtiofs and keeps aname=drvfs in the options.
  return /(^|,)aname=drvfs\b/.test(String(options || ''));
}

function parseWindowsMountPoints(mountsText) {
  const points = [];
  String(mountsText).split('\n').forEach((line) => {
    const fields = line.trim().split(/\s+/);
    if (fields.length < 4) {
      return;
    }
    if (!isWindowsDriveMount(fields[2], fields[3])) {
      return;
    }
    const mountPoint = unescapeMountField(fields[1]);
    if (mountPoint && points.indexOf(mountPoint) === -1) {
      points.push(mountPoint);
    }
  });
  return points;
}

function windowsMountPoints() {
  if (windowsMountPointsCache !== null) {
    return windowsMountPointsCache;
  }
  if (process.platform === 'win32') {
    windowsMountPointsCache = [];
    return windowsMountPointsCache;
  }
  try {
    windowsMountPointsCache = parseWindowsMountPoints(fs.readFileSync(PROC_MOUNTS_PATH, 'utf8'));
  } catch (error) {
    windowsMountPointsCache = [];
  }
  return windowsMountPointsCache;
}

function isUnderDirectory(target, directory) {
  const base = path.resolve(directory);
  if (target === base) {
    return true;
  }
  const prefix = base.endsWith(path.sep) ? base : `${base}${path.sep}`;
  return target.startsWith(prefix);
}

/**
 * Tell whether the path belongs to a platform other than the running one:
 * a Windows drive mount seen from WSL, or a WSL UNC path seen from Windows.
 */
function isForeignPlatformPath(target, mountPoints) {
  if (!target) {
    return false;
  }
  const resolved = path.resolve(target);
  if (process.platform === 'win32') {
    return /^\\\\wsl(\$|\.localhost)\\/i.test(resolved);
  }
  const points = mountPoints || windowsMountPoints();
  return points.some((point) => isUnderDirectory(resolved, point));
}

function uniquePush(list, value) {
  if (!value) {
    return;
  }
  const resolved = path.resolve(value);
  if (isForeignPlatformPath(resolved)) {
    return;
  }
  if (!fs.existsSync(resolved) || !fs.statSync(resolved).isDirectory()) {
    return;
  }
  if (list.indexOf(resolved) !== -1) {
    return;
  }
  list.push(resolved);
}

/**
 * Quote one argument of a shell command line.
 * @param {string} value
 * @returns {string}
 */
function shellQuote(value) {
  const text = String(value);
  if (process.platform === 'win32') {
    return /[\s"&|<>^()%!]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }
  return `'${text.replace(/'/g, `'\\''`)}'`;
}

/**
 * Run a command. Windows needs the shell to locate npm.cmd through PATHEXT,
 * and spawnSync() concatenates the argument array without escaping when the
 * shell option is on, so build the command line here instead of handing over
 * an argument array.
 * see: https://nodejs.org/api/deprecations.html#DEP0190
 * @param {string} command
 * @param {Array<string>} args
 * @param {object} options
 * @returns {object} Result of spawnSync().
 */
function runCommand(command, args, options) {
  const useShell = process.platform === 'win32';
  const commandLine = useShell ? [command].concat(args || []).map(shellQuote).join(' ') : command;
  const result = spawnSync(commandLine, useShell ? [] : args, Object.assign({
    encoding: 'utf8',
    shell: useShell,
  }, options));
  return result;
}

function npmRootGlobal() {
  const result = runCommand('npm', ['root', '-g']);
  if (result.status !== 0 || !result.stdout) {
    return '';
  }
  return result.stdout.toString().trim();
}

function isExecutableFile(filePath) {
  try {
    if (!fs.statSync(filePath).isFile()) {
      return false;
    }
    fs.accessSync(filePath, fs.constants.X_OK);
    return true;
  } catch (error) {
    return false;
  }
}

// `command -v` is a shell builtin, and only some distributions ship a
// /usr/bin/command wrapper, so PATH is walked here instead of spawning it.
// A zero-length entry in PATH means the current directory, while an unset or
// empty PATH searches nothing.
// Directories owned by another platform are skipped rather than ending the
// search, so a native entry later in PATH is still found.
// see: https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap08.html
function findOnPath(name, pathValue, mountPoints) {
  if (!pathValue) {
    return '';
  }
  const entries = String(pathValue).split(path.delimiter);
  for (let i = 0; i < entries.length; i += 1) {
    const dir = path.resolve(entries[i] || '.');
    if (isForeignPlatformPath(dir, mountPoints)) {
      continue;
    }
    const candidate = path.join(dir, name);
    if (isExecutableFile(candidate)) {
      return candidate;
    }
  }
  return '';
}

function whichCommand(name) {
  if (process.platform !== 'win32') {
    return findOnPath(name, process.env.PATH);
  }
  const result = runCommand('where', [name]);
  if (result.status !== 0 || !result.stdout) {
    return '';
  }
  const first = result.stdout.toString().split(/\r?\n/).find((line) => line.trim());
  if (!first) {
    return '';
  }
  const located = first.trim();
  return isForeignPlatformPath(located) ? '' : located;
}

function enclosingNodeModules(filePath) {
  let dir = path.dirname(filePath);
  while (dir !== path.dirname(dir)) {
    if (path.basename(dir) === 'node_modules') {
      return dir;
    }
    dir = path.dirname(dir);
  }
  return '';
}

/**
 * List the node_modules candidates implied by an installed CLI.
 * Windows npm places <name>.cmd beside node_modules in the prefix.
 * Unix npm places bin/<name> as a symlink into <prefix>/lib/node_modules,
 * and nvm, Volta, or a project-local .bin may use other layouts, so the
 * node_modules that holds the symlink target is also listed.
 */
function binSearchRoots(located) {
  const roots = [path.join(path.dirname(located), 'node_modules')];
  if (process.platform === 'win32') {
    return roots;
  }
  roots.push(path.join(path.dirname(path.dirname(located)), 'lib', 'node_modules'));
  try {
    const target = enclosingNodeModules(fs.realpathSync(located));
    if (target) {
      roots.push(target);
    }
  } catch (error) {
    // a dangling symlink implies no root
  }
  return roots;
}

function listSearchRoots() {
  const roots = [];
  const nodePath = process.env.NODE_PATH || '';
  nodePath.split(path.delimiter).forEach((entry) => uniquePush(roots, entry));
  uniquePush(roots, '/usr/local/lib/node_modules');
  uniquePush(roots, npmRootGlobal());
  uniquePush(roots, path.join(path.dirname(process.execPath), 'node_modules'));
  uniquePush(roots, path.join(path.dirname(process.execPath), 'lib', 'node_modules'));
  // PATH の走査は名前ごとに行うため、.cmd は Windows に限って探す。
  const cliNames = [];
  Object.keys(CLI_NAMES).forEach((packageName) => {
    const binName = CLI_NAMES[packageName];
    cliNames.push(binName);
    if (process.platform === 'win32') {
      cliNames.push(cliFileName(binName));
    }
  });
  cliNames.forEach((name) => {
    const located = whichCommand(name);
    if (!located) {
      return;
    }
    binSearchRoots(located).forEach((root) => uniquePush(roots, root));
  });
  uniquePush(roots, LOCAL_NODE_MODULES);
  return roots;
}

function parseVersion(version) {
  return String(version).split('.').map((part) => {
    const match = part.match(/^\d+/);
    return match ? Number(match[0]) : 0;
  });
}

function compareVersion(left, right) {
  const a = parseVersion(left);
  const b = parseVersion(right);
  const length = Math.max(a.length, b.length);
  for (let i = 0; i < length; i += 1) {
    const av = a[i] || 0;
    const bv = b[i] || 0;
    if (av > bv) {
      return 1;
    }
    if (av < bv) {
      return -1;
    }
  }
  return 0;
}

function satisfiesRange(version, range) {
  if (!range) {
    return true;
  }
  const spec = String(range).trim();
  if (spec.startsWith('^')) {
    const base = spec.slice(1);
    if (compareVersion(version, base) < 0) {
      return false;
    }
    const baseParts = parseVersion(base);
    const versionParts = parseVersion(version);
    if (baseParts[0] !== 0) {
      return versionParts[0] === baseParts[0];
    }
    if (baseParts[1] !== 0) {
      return versionParts[0] === 0 && versionParts[1] === baseParts[1];
    }
    return version === base;
  }
  if (spec.startsWith('~')) {
    const base = spec.slice(1);
    if (compareVersion(version, base) < 0) {
      return false;
    }
    const baseParts = parseVersion(base);
    const versionParts = parseVersion(version);
    return versionParts[0] === baseParts[0] && versionParts[1] === baseParts[1];
  }
  return version === spec;
}

function packageDir(root, name) {
  return path.join(root, ...name.split('/'));
}

function findPackage(name, roots, range) {
  for (let i = 0; i < roots.length; i += 1) {
    const dir = packageDir(roots[i], name);
    const manifest = path.join(dir, 'package.json');
    if (!fs.existsSync(manifest)) {
      continue;
    }
    let version = '';
    try {
      version = readJson(manifest).version || '';
    } catch (error) {
      continue;
    }
    if (!satisfiesRange(version, range)) {
      continue;
    }
    return {
      name,
      dir,
      version,
      root: roots[i],
      source: path.resolve(roots[i]) === path.resolve(LOCAL_NODE_MODULES) ? 'local' : 'global',
    };
  }
  return null;
}

function cliFileName(binName) {
  return process.platform === 'win32' ? `${binName}.cmd` : binName;
}

function findBin(binName, pkg, roots) {
  const fileName = cliFileName(binName);
  const candidates = [];
  if (pkg) {
    candidates.push(path.join(pkg.root, '.bin', fileName));
    candidates.push(path.join(path.dirname(pkg.root), fileName));
    candidates.push(path.join(path.dirname(pkg.root), 'bin', fileName));
    if (process.platform === 'win32') {
      candidates.push(path.join(pkg.root, '.bin', binName));
    }
    try {
      const manifest = readJson(path.join(pkg.dir, 'package.json'));
      const binField = manifest.bin;
      let rel = '';
      if (typeof binField === 'string') {
        rel = binField;
      } else if (binField && typeof binField === 'object') {
        rel = binField[binName] || binField[Object.keys(binField)[0]] || '';
      }
      if (rel) {
        candidates.push(path.join(pkg.dir, rel));
      }
    } catch (error) {
      // ignore malformed package.json
    }
  }
  roots.forEach((root) => {
    candidates.push(path.join(root, '.bin', fileName));
    candidates.push(path.join(path.dirname(root), fileName));
    candidates.push(path.join(path.dirname(root), 'bin', fileName));
  });
  const fromPath = whichCommand(fileName) || whichCommand(binName);
  if (fromPath) {
    candidates.push(fromPath);
  }
  for (let i = 0; i < candidates.length; i += 1) {
    const candidate = candidates[i];
    if (candidate && fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return '';
}

function findMermaidJs(roots, mermaidCli) {
  const candidates = [];
  const mermaidPkg = findPackage('mermaid', roots, '');
  if (mermaidPkg) {
    candidates.push(path.join(mermaidPkg.dir, 'dist', 'mermaid.min.js'));
  }
  if (mermaidCli) {
    candidates.push(path.join(mermaidCli.dir, 'node_modules', 'mermaid', 'dist', 'mermaid.min.js'));
  }
  roots.forEach((root) => {
    candidates.push(path.join(root, 'mermaid', 'dist', 'mermaid.min.js'));
    candidates.push(path.join(root, '@mermaid-js', 'mermaid-cli', 'node_modules', 'mermaid', 'dist', 'mermaid.min.js'));
  });
  for (let i = 0; i < candidates.length; i += 1) {
    if (fs.existsSync(candidates[i])) {
      return candidates[i];
    }
  }
  return '';
}

function findMinisearchJs(minisearchPkg) {
  if (!minisearchPkg) {
    return '';
  }
  const candidates = [
    path.join(minisearchPkg.dir, 'dist', 'umd', 'index.min.js'),
    path.join(minisearchPkg.dir, 'dist', 'umd', 'index.js'),
  ];
  for (let i = 0; i < candidates.length; i += 1) {
    if (fs.existsSync(candidates[i])) {
      return candidates[i];
    }
  }
  return '';
}

function lockfileVersion(lockfile, name) {
  const entry = lockfile.packages && lockfile.packages[`node_modules/${name}`];
  return entry && entry.version ? entry.version : '';
}

function collect(packageJson, lockfile) {
  const ranges = packageJson.dependencies || {};
  const roots = listSearchRoots();
  const packages = {};
  INSTALL_PACKAGES.forEach((name) => {
    packages[name] = findPackage(name, roots, ranges[name] || '');
  });
  const mermaidCli = packages['@mermaid-js/mermaid-cli'];
  const minisearch = packages.minisearch;
  const missing = INSTALL_PACKAGES.filter((name) => !packages[name]);
  const mermaidJs = findMermaidJs(roots, mermaidCli);
  const minisearchJs = findMinisearchJs(minisearch);
  if (!mermaidJs) {
    missing.push('mermaid');
  }
  if (!minisearchJs) {
    missing.push('minisearch-umd');
  }
  const mmdc = findBin('mmdc', mermaidCli, roots);
  const widdershins = findBin('widdershins', packages.widdershins, roots);
  if (!mmdc) {
    missing.push('mmdc');
  }
  if (!widdershins) {
    missing.push('widdershins-cli');
  }
  // 実行時の require をパッケージ単位で固定する。root 単位で探索先を差し替えると、
  // ここで semver により不採用としたグローバルのバージョンが再び参照される。
  const globalPackages = {};
  INSTALL_PACKAGES.forEach((name) => {
    const resolved = packages[name];
    if (resolved && resolved.source === 'global') {
      globalPackages[name] = resolved.dir;
    }
  });
  return {
    roots,
    packages,
    missing: Array.from(new Set(missing)),
    paths: {
      mmdc,
      widdershins,
      mermaidJs,
      minisearchJs,
      plantumlCore: packages['@plantuml/core'] ? packages['@plantuml/core'].dir : '',
      puppeteer: packages.puppeteer ? packages.puppeteer.dir : '',
    },
    globalPackages,
    ranges,
    lockfile,
  };
}

function installAction(missingInstallPackages) {
  if (missingInstallPackages.length === 0) {
    return { action: 'none', specs: [] };
  }
  if (missingInstallPackages.length === INSTALL_PACKAGES.length) {
    return { action: 'npm-ci', specs: [] };
  }
  return {
    action: 'npm-install',
    specs: missingInstallPackages,
  };
}

function missingInstallPackages(state) {
  return INSTALL_PACKAGES.filter((name) => !state.packages[name]);
}

function runNpm(args) {
  const env = Object.assign({}, process.env, { PUPPETEER_SKIP_DOWNLOAD: '1' });
  const result = runCommand('npm', args, {
    cwd: SCRIPT_DIR,
    env,
    stdio: ['ignore', process.stderr, process.stderr],
  });
  if (result.status !== 0) {
    throw new Error(`npm ${args.join(' ')} failed with status ${result.status}`);
  }
}

function ensure(state, dryRun) {
  const missingPkgs = missingInstallPackages(state);
  const plan = installAction(missingPkgs);
  if (plan.action === 'none') {
    return plan;
  }
  process.stderr.write(`Installing node.js modules (${plan.action})...\n`);
  if (dryRun) {
    return plan;
  }
  if (plan.action === 'npm-ci') {
    runNpm(['ci']);
    return plan;
  }
  const specs = plan.specs.map((name) => {
    const version = lockfileVersion(state.lockfile, name);
    if (!version) {
      throw new Error(`lockfile version not found for ${name}`);
    }
    return `${name}@${version}`;
  });
  runNpm(['install', '--no-save'].concat(specs));
  return plan;
}

function shQuote(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}

function exportEnv(state) {
  const lines = [];
  const assign = (name, value) => {
    lines.push(`${name}=${shQuote(value || '')}`);
    lines.push(`export ${name}`);
  };
  assign('DOCSFW_WIDDERSHINS', state.paths.widdershins);
  assign('DOCSFW_MMDC', state.paths.mmdc);
  assign('DOCSFW_MERMAID_JS', state.paths.mermaidJs);
  assign('DOCSFW_MINISEARCH_JS', state.paths.minisearchJs);
  assign('DOCSFW_PLANTUML_CORE', state.paths.plantumlCore);
  assign('DOCSFW_PUPPETEER_ROOT', state.paths.puppeteer);
  const globalPackageNames = Object.keys(state.globalPackages);
  assign('DOCSFW_NODE_GLOBAL_PACKAGES', globalPackageNames.length ? JSON.stringify(state.globalPackages) : '');
  assign('DOCSFW_PREFER_GLOBAL_MODULES', path.join(SCRIPT_DIR, 'docsfw-prefer-global-modules.js'));
  return `${lines.join('\n')}\n`;
}

function toReport(state, plan) {
  const packages = {};
  INSTALL_PACKAGES.forEach((name) => {
    const resolved = state.packages[name];
    packages[name] = resolved
      ? { version: resolved.version, dir: resolved.dir, source: resolved.source }
      : null;
  });
  return {
    action: plan.action,
    missing: state.missing,
    packages,
    paths: state.paths,
    globalPackages: state.globalPackages,
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const packageJson = readJson(PACKAGE_JSON_PATH);
  const lockfile = readJson(PACKAGE_LOCK_PATH);
  let state = collect(packageJson, lockfile);
  const plan = args.ensure ? ensure(state, args.dryRun) : installAction(missingInstallPackages(state));
  if (args.ensure && !args.dryRun && plan.action !== 'none') {
    state = collect(packageJson, lockfile);
  }
  if (args.ensure && !args.dryRun && state.missing.length > 0) {
    process.stderr.write(`Error: unresolved node components: ${state.missing.join(', ')}\n`);
    process.exit(1);
  }
  if (args.exportEnv) {
    process.stdout.write(exportEnv(state));
    return;
  }
  process.stdout.write(`${JSON.stringify(toReport(state, plan), null, 2)}\n`);
}

module.exports = {
  INSTALL_PACKAGES,
  satisfiesRange,
  parseWindowsMountPoints,
  isForeignPlatformPath,
  findOnPath,
  binSearchRoots,
  listSearchRoots,
  collect,
  installAction,
  missingInstallPackages,
};

if (require.main === module) {
  try {
    main();
  } catch (error) {
    process.stderr.write(`Error: ${error.message}\n`);
    process.exit(1);
  }
}
