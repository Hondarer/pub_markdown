/**
 * browser-server.js
 *
 * 共有ブラウザインスタンスを起動し、WebSocket エンドポイントをファイルに書き出す。
 * pub_markdown_core.sh から起動され、ビルド全体で 1 つのブラウザを使い回す。
 *
 * 使い方:
 *   node browser-server.js <ws-endpoint-file>
 *
 * 停止:
 *   SIGTERM または SIGINT で終了し、ブラウザを閉じてエンドポイントファイルを削除する。
 */
const puppeteer = require('puppeteer');
const fs        = require('fs');
const http      = require('http');

const wsFile = process.argv[2];
if (!wsFile) {
  console.error('Usage: node browser-server.js <ws-endpoint-file>');
  process.exit(1);
}

const START_TIMEOUT_SEC = Number.parseInt(process.env.PUB_MARKDOWN_BROWSER_START_TIMEOUT_SEC || '30', 10);
const START_TIMEOUT_MS = Number.isFinite(START_TIMEOUT_SEC) && START_TIMEOUT_SEC > 0
  ? START_TIMEOUT_SEC * 1000
  : 30000;
const READY_POLL_INTERVAL_MS = 50;

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function getJsonVersionUrl(wsEndpoint) {
  const endpointUrl = new URL(wsEndpoint);
  return new URL(`http://${endpointUrl.host}/json/version`);
}

function fetchJsonVersion(jsonVersionUrl) {
  return new Promise((resolve, reject) => {
    const req = http.get(jsonVersionUrl, { timeout: 200 }, res => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', chunk => {
        body += chunk;
      });
      res.on('end', () => {
        if (res.statusCode !== 200) {
          reject(new Error(`/json/version returned status ${res.statusCode}`));
          return;
        }
        try {
          resolve(JSON.parse(body));
        } catch (err) {
          reject(err);
        }
      });
    });

    req.on('timeout', () => {
      req.destroy(new Error('/json/version request timed out'));
    });
    req.on('error', reject);
  });
}

async function waitForDevToolsReady(wsEndpoint) {
  const deadline = Date.now() + START_TIMEOUT_MS;
  const jsonVersionUrl = getJsonVersionUrl(wsEndpoint);
  let lastError = null;

  while (Date.now() < deadline) {
    try {
      const version = await fetchJsonVersion(jsonVersionUrl);
      if (version.webSocketDebuggerUrl) {
        return;
      }
      lastError = new Error('/json/version did not include webSocketDebuggerUrl');
    } catch (err) {
      lastError = err;
    }
    await sleep(READY_POLL_INTERVAL_MS);
  }

  const detail = lastError ? `: ${lastError.message}` : '';
  throw new Error(`DevTools WebSocket was not ready within ${START_TIMEOUT_MS}ms${detail}`);
}

(async () => {
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  let shuttingDown = false;

  // シャットダウン処理
  const cleanup = async () => {
    shuttingDown = true;
    try { fs.unlinkSync(wsFile); } catch (_) {}
    try { await browser.close(); } catch (_) {}
    process.exit(0);
  };

  process.on('SIGTERM', cleanup);
  process.on('SIGINT',  cleanup);

  // ブラウザプロセスが予期せず終了した場合
  browser.on('disconnected', () => {
    if (shuttingDown) {
      return;
    }
    try { fs.unlinkSync(wsFile); } catch (_) {}
    process.exit(1);
  });

  const wsEndpoint = browser.wsEndpoint();
  try {
    await waitForDevToolsReady(wsEndpoint);
  } catch (err) {
    shuttingDown = true;
    try { await browser.close(); } catch (_) {}
    throw err;
  }

  // WebSocket エンドポイントをファイルに書き出す
  fs.writeFileSync(wsFile, wsEndpoint, 'utf8');
})().catch(err => {
  console.error('browser-server.js:', err);
  try { fs.unlinkSync(wsFile); } catch (_) {}
  process.exit(2);
});
