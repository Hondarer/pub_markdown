'use strict';

function isMicrosoftEdgeExecutable(executablePath) {
  return process.platform === 'win32' &&
    /(^|[\\/])msedge\.exe$/i.test(executablePath || '');
}

function buildBrowserLaunchOptions(options = {}) {
  const args = [...(options.args || [])];
  const executablePath = options.executablePath || process.env.PUPPETEER_EXECUTABLE_PATH;

  // Edge が互換性再起動すると、Puppeteer は最初のプロセスの正常終了を
  // ブラウザー起動失敗として扱う。最初のプロセスをそのまま自動操作対象にする。
  if (isMicrosoftEdgeExecutable(executablePath) &&
      !args.includes('--edge-skip-compat-layer-relaunch')) {
    args.push('--edge-skip-compat-layer-relaunch');
  }

  return { ...options, args };
}

module.exports = {
  buildBrowserLaunchOptions,
  isMicrosoftEdgeExecutable,
};
