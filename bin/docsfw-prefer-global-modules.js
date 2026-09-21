'use strict';

/**
 * Pin the packages that resolve-node-components.js adopted from a global
 * node_modules tree to the exact directory it selected. Packages it did not
 * adopt keep the standard Node.js resolution, so a version rejected by the
 * declared semver range never takes effect at require() time.
 *
 * The same pinning is applied to import, because a bare specifier in an ES
 * module is resolved by the ES module loader alone: it reaches neither this
 * require() hook nor NODE_PATH nor the global node_modules tree.
 */

const Module = require('module');
const { pathToFileURL } = require('url');
const pinned = require('./docsfw-pinned-packages.js');

const entries = pinned.buildEntries(process.env.DOCSFW_NODE_GLOBAL_PACKAGES);

/**
 * Resolve the package name from the node_modules tree that holds the adopted
 * directory.
 *
 * 採用したディレクトリを直接 require すると package.json の exports 定義を通らず、
 * 常に main が読み込まれる。require 用のエントリを持つパッケージでは、
 * ブラウザー向けの UMD などが選ばれて実行時に失敗する。
 * @param {Function} original Saved Module._resolveFilename.
 * @param {object} self
 * @param {object} entry
 * @param {Array} args Arguments of Module._resolveFilename.
 * @returns {string} Resolved file name, or an empty string when not pinned.
 */
function resolveFromRoot(original, self, entry, args) {
  const options = Object.assign({}, args[3], { paths: [entry.root] });
  const resolved = original.call(self, args[0], args[1], args[2], options);
  return pinned.isUnderDirectory(resolved, entry.dir) ? resolved : '';
}

if (entries.length) {
  const original = Module._resolveFilename;
  Module._resolveFilename = function docsfwResolveFilename(request) {
    const args = Array.prototype.slice.call(arguments);
    const entry = pinned.findEntry(entries, request);
    if (!entry) {
      return original.apply(this, args);
    }
    try {
      const resolved = resolveFromRoot(original, this, entry, args);
      if (resolved) {
        return resolved;
      }
    } catch (error) {
      // 名前で解決できない場合は、下のディレクトリへの読み替えで解決する。
    }
    // NODE_PATH のように node_modules 以外へ置かれた採用先は、パッケージ名では解決できない。
    // exports 定義は通らなくなるが、固定そのものは維持する。
    args[0] = pinned.directoryRequest(entry, request);
    return original.apply(this, args);
  };

  if (typeof Module.registerHooks === 'function') {
    // 同一スレッドで動作する解決フック。追加のワーカー スレッドを起こさない。
    Module.registerHooks({
      resolve(specifier, context, nextResolve) {
        return pinned.resolveEsm(entries, specifier, context, nextResolve);
      },
    });
  } else if (typeof Module.register === 'function') {
    Module.register('./docsfw-prefer-global-modules.mjs', pathToFileURL(__filename).href, {
      data: { packages: process.env.DOCSFW_NODE_GLOBAL_PACKAGES },
    });
  }
}
