'use strict';

const assert = require('assert');
const {
  buildBrowserLaunchOptions,
  isMicrosoftEdgeExecutable,
} = require('./browser-launch-options');

const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

assert.strictEqual(isMicrosoftEdgeExecutable(edgePath), process.platform === 'win32');
assert.strictEqual(isMicrosoftEdgeExecutable('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'), false);

const launchOptions = buildBrowserLaunchOptions({
  args: ['--no-sandbox'],
  executablePath: edgePath,
});
if (process.platform === 'win32') {
  assert.deepStrictEqual(launchOptions.args, ['--no-sandbox', '--edge-skip-compat-layer-relaunch']);
} else {
  assert.deepStrictEqual(launchOptions.args, ['--no-sandbox']);
}

console.log('browser launch option tests passed.');
