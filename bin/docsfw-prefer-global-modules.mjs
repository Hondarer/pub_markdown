/**
 * Off-thread ES module resolve hook for docsfw-prefer-global-modules.js.
 *
 * Node.js 22.15 and later run the hook of module.registerHooks() on the same
 * thread, so this file is used only where that API is missing and the pinning
 * has to be registered through module.register().
 */

import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const pinned = require('./docsfw-pinned-packages.js');

let entries = [];

/**
 * @param {object} data Payload passed to module.register().
 */
export function initialize(data) {
  entries = pinned.buildEntries(data && data.packages);
}

/**
 * @param {string} specifier
 * @param {object} context
 * @param {Function} nextResolve
 * @returns {object|Promise<object>}
 */
export function resolve(specifier, context, nextResolve) {
  return pinned.resolveEsm(entries, specifier, context, nextResolve);
}
