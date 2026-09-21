'use strict';

/**
 * Pin the packages that resolve-node-components.js adopted from a global
 * node_modules tree to the exact directory it selected. Packages it did not
 * adopt keep the standard Node.js resolution, so a version rejected by the
 * declared semver range never takes effect at require() time.
 */
const Module = require('module');
const path = require('path');

function parsePackages(value) {
  if (!value) {
    return {};
  }
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (error) {
    return {};
  }
}

const packages = parsePackages(process.env.DOCSFW_NODE_GLOBAL_PACKAGES);
const names = Object.keys(packages);

function mapRequest(request) {
  if (typeof request !== 'string' || !request) {
    return request;
  }
  if (request.startsWith('.') || path.isAbsolute(request)) {
    return request;
  }
  for (let i = 0; i < names.length; i += 1) {
    const name = names[i];
    if (request === name) {
      return packages[name];
    }
    if (request.startsWith(`${name}/`)) {
      return path.join(packages[name], request.slice(name.length + 1));
    }
  }
  return request;
}

if (names.length) {
  const original = Module._resolveFilename;
  Module._resolveFilename = function docsfwResolveFilename(request) {
    const args = Array.prototype.slice.call(arguments);
    args[0] = mapRequest(request);
    return original.apply(this, args);
  };
}
