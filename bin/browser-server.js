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
const path      = require('path');

const wsFile = process.argv[2];
if (!wsFile) {
  console.error('Usage: node browser-server.js <ws-endpoint-file>');
  process.exit(1);
}

(async () => {
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  const wsEndpoint = browser.wsEndpoint();

  // WebSocket エンドポイントをファイルに書き出す
  fs.writeFileSync(wsFile, wsEndpoint, 'utf8');

  // シャットダウン処理
  const cleanup = async () => {
    try { fs.unlinkSync(wsFile); } catch (_) {}
    try { await browser.close(); } catch (_) {}
    process.exit(0);
  };

  process.on('SIGTERM', cleanup);
  process.on('SIGINT',  cleanup);

  // ブラウザプロセスが予期せず終了した場合
  browser.on('disconnected', () => {
    try { fs.unlinkSync(wsFile); } catch (_) {}
    process.exit(1);
  });
})().catch(err => {
  console.error('browser-server.js:', err);
  try { fs.unlinkSync(wsFile); } catch (_) {}
  process.exit(2);
});
