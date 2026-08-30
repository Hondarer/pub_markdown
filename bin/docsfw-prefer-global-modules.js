'use strict';

/**
 * Prepend globally resolved node_modules roots so require() prefers them
 * over a leftover local framework/docsfw/bin/node_modules tree.
 */
const Module = require('module');
const path = require('path');

const roots = String(process.env.DOCSFW_NODE_GLOBAL_ROOTS || '')
  .split(path.delimiter)
  .map((entry) => entry.trim())
  .filter(Boolean);

if (!roots.length) {
  return;
}

const original = Module._nodeModulePaths;
Module._nodeModulePaths = function docsfwPreferGlobalModulePaths(from) {
  return roots.concat(original.call(this, from));
};
