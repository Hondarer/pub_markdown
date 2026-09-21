'use strict';

/**
 * Shared rules for the packages that resolve-node-components.js adopted from a
 * global node_modules tree.
 *
 * docsfw-prefer-global-modules.js applies them to require(), and the ES module
 * resolve hook (docsfw-prefer-global-modules.mjs, or the in-thread hook the
 * same file registers) applies them to import. Both paths must select the same
 * package directory, so the rules live here.
 */

const path = require('path');
const { pathToFileURL, fileURLToPath } = require('url');

// 解決の起点として渡す仮想ファイル。node_modules の探索基準になるだけで、実在する必要はない。
const PINNED_PARENT_FILE = '__docsfw_pinned_parent__.js';

/**
 * @param {string|object} value JSON text or an object of {name: directory}.
 * @returns {object} Parsed map; an empty object when the input is unusable.
 */
function parsePackages(value) {
  if (!value) {
    return {};
  }
  if (typeof value === 'object') {
    return value;
  }
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (error) {
    return {};
  }
}

/**
 * Walk up from the package directory by the number of segments in its name to
 * reach the node_modules tree that holds it.
 * @param {string} name
 * @param {string} dir
 * @returns {string}
 */
function packageRoot(name, dir) {
  let root = dir;
  name.split('/').forEach(() => {
    root = path.dirname(root);
  });
  return root;
}

/**
 * @param {string|object} value Value of DOCSFW_NODE_GLOBAL_PACKAGES.
 * @returns {Array<object>} Entries used by the resolution hooks.
 */
function buildEntries(value) {
  const packages = parsePackages(value);
  return Object.keys(packages).reduce((entries, name) => {
    const dir = packages[name];
    if (typeof dir !== 'string' || !dir) {
      return entries;
    }
    const resolvedDir = path.resolve(dir);
    const root = packageRoot(name, resolvedDir);
    const parentPath = path.join(root, PINNED_PARENT_FILE);
    entries.push({
      name,
      dir: resolvedDir,
      root,
      parentPath,
      parentURL: pathToFileURL(parentPath).href,
    });
    return entries;
  }, []);
}

/**
 * @param {Array<object>} entries
 * @param {string} request Specifier to resolve.
 * @returns {object|null} The pinned entry the specifier belongs to.
 */
function findEntry(entries, request) {
  if (typeof request !== 'string' || !request) {
    return null;
  }
  if (request.startsWith('.') || path.isAbsolute(request)) {
    return null;
  }
  for (let i = 0; i < entries.length; i += 1) {
    const entry = entries[i];
    if (request === entry.name || request.startsWith(`${entry.name}/`)) {
      return entry;
    }
  }
  return null;
}

/**
 * @param {string} target
 * @param {string} directory
 * @returns {boolean} Whether the target sits in the directory or below it.
 */
function isUnderDirectory(target, directory) {
  if (typeof target !== 'string' || !target) {
    return false;
  }
  const resolved = path.resolve(target);
  const base = path.resolve(directory);
  if (resolved === base) {
    return true;
  }
  const prefix = base.endsWith(path.sep) ? base : `${base}${path.sep}`;
  return resolved.startsWith(prefix);
}

/**
 * Rewrite the specifier into a path below the pinned directory. Used only where
 * the package name cannot be resolved from a node_modules tree, because this
 * form bypasses the exports definition of package.json.
 * @param {object} entry
 * @param {string} request
 * @returns {string}
 */
function directoryRequest(entry, request) {
  if (request === entry.name) {
    return entry.dir;
  }
  return path.join(entry.dir, request.slice(entry.name.length + 1));
}

/**
 * @param {object} resolved Result of an ES module resolve hook.
 * @param {string} directory Pinned package directory.
 * @returns {boolean}
 */
function isPinnedResult(resolved, directory) {
  if (!resolved || typeof resolved.url !== 'string' || !resolved.url.startsWith('file:')) {
    return false;
  }
  try {
    return isUnderDirectory(fileURLToPath(resolved.url), directory);
  } catch (error) {
    return false;
  }
}

/**
 * Body of the ES module resolve hook. The same function serves the in-thread
 * hook of module.registerHooks() and the off-thread hook of module.register(),
 * so it accepts both a synchronous and an asynchronous nextResolve.
 * @param {Array<object>} entries
 * @param {string} specifier
 * @param {object} context
 * @param {Function} nextResolve
 * @returns {object|Promise<object>}
 */
function resolveEsm(entries, specifier, context, nextResolve) {
  const fallback = () => nextResolve(specifier, context);
  const conditions = (context && context.conditions) || [];
  // require() の解決は docsfw-prefer-global-modules.js が担当する。
  // CommonJS の既定実装は parentURL を見ないため、ここで固定しても効果がない。
  if (conditions.indexOf('require') !== -1) {
    return fallback();
  }
  const entry = findEntry(entries, specifier);
  if (!entry) {
    return fallback();
  }
  const pinnedContext = Object.assign({}, context, { parentURL: entry.parentURL });
  const verify = (resolved) => (isPinnedResult(resolved, entry.dir) ? resolved : fallback());
  let result;
  try {
    result = nextResolve(specifier, pinnedContext);
  } catch (error) {
    return fallback();
  }
  if (result && typeof result.then === 'function') {
    return result.then(verify, fallback);
  }
  return verify(result);
}

module.exports = {
  PINNED_PARENT_FILE,
  parsePackages,
  packageRoot,
  buildEntries,
  findEntry,
  isUnderDirectory,
  directoryRequest,
  isPinnedResult,
  resolveEsm,
};
