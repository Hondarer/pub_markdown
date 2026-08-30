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

function uniquePush(list, value) {
  if (!value) {
    return;
  }
  const resolved = path.resolve(value);
  if (!fs.existsSync(resolved) || !fs.statSync(resolved).isDirectory()) {
    return;
  }
  if (list.indexOf(resolved) !== -1) {
    return;
  }
  list.push(resolved);
}

function runCommand(command, args, options) {
  const result = spawnSync(command, args, Object.assign({
    encoding: 'utf8',
    shell: process.platform === 'win32',
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

function whichCommand(name) {
  const command = process.platform === 'win32' ? 'where' : 'command';
  const args = process.platform === 'win32' ? [name] : ['-v', name];
  const result = runCommand(command, args);
  if (result.status !== 0 || !result.stdout) {
    return '';
  }
  const first = result.stdout.toString().split(/\r?\n/).find((line) => line.trim());
  return first ? first.trim() : '';
}

function listSearchRoots() {
  const roots = [];
  const nodePath = process.env.NODE_PATH || '';
  nodePath.split(path.delimiter).forEach((entry) => uniquePush(roots, entry));
  uniquePush(roots, '/usr/local/lib/node_modules');
  uniquePush(roots, npmRootGlobal());
  uniquePush(roots, path.join(path.dirname(process.execPath), 'node_modules'));
  uniquePush(roots, path.join(path.dirname(process.execPath), 'lib', 'node_modules'));
  ['mmdc', 'mmdc.cmd', 'widdershins', 'widdershins.cmd'].forEach((name) => {
    const located = whichCommand(name);
    if (!located) {
      return;
    }
    uniquePush(roots, path.join(path.dirname(located), 'node_modules'));
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
  const globalRoots = [];
  INSTALL_PACKAGES.forEach((name) => {
    const resolved = packages[name];
    if (resolved && resolved.source === 'global') {
      uniquePush(globalRoots, resolved.root);
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
    globalRoots,
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
  assign('DOCSFW_NODE_GLOBAL_ROOTS', state.globalRoots.join(path.delimiter));
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
    globalRoots: state.globalRoots,
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
