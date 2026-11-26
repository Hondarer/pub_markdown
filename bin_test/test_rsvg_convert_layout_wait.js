'use strict';

// rsvg-convert.js の単体実行および共有ブラウザー並列実行 (背面タブ発生時) で
// requestAnimationFrame 停止によるタイムアウトが起きず、有効な PNG が出力されること、
// ならびに build-browser-assets.js の Mermaid フレーム内 afterLayout() が
// タイムアウト付きフォールバックを持つことを検証する。
const assert = require('assert/strict');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const BIN_INTERNAL = path.resolve(__dirname, '..', 'bin_internal');
const RSVG_CONVERT = path.join(BIN_INTERNAL, 'rsvg-convert.js');
const BROWSER_SERVER = path.join(BIN_INTERNAL, 'browser-server.js');
const SAMPLE_SVG = path.resolve(__dirname, '..', 'styles', 'html', 'docsfw-pandoc-icon.svg');
const { writeMermaidFrame, MERMAID_FRAME } = require(path.join(BIN_INTERNAL, 'build-browser-assets'));

const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function runRsvgConvert(svgBuffer, env = {}, args = ['-f', 'png', '--dpi-x', '96', '--dpi-y', '96']) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [RSVG_CONVERT, ...args], {
      env: { ...process.env, ...env },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    const stdoutChunks = [];
    const stderrChunks = [];
    const timer = setTimeout(() => {
      child.kill('SIGKILL');
      reject(new Error('rsvg-convert.js timed out after 30s'));
    }, 30000);

    child.stdout.on('data', chunk => stdoutChunks.push(chunk));
    child.stderr.on('data', chunk => stderrChunks.push(chunk));
    child.on('error', err => {
      clearTimeout(timer);
      reject(err);
    });
    child.on('close', code => {
      clearTimeout(timer);
      resolve({
        code,
        stdout: Buffer.concat(stdoutChunks),
        stderr: Buffer.concat(stderrChunks).toString('utf8'),
      });
    });

    child.stdin.end(svgBuffer);
  });
}

function waitForFileNonEmpty(filePath, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;
    const poll = () => {
      try {
        if (fs.existsSync(filePath)) {
          const content = fs.readFileSync(filePath, 'utf8').trim();
          if (content) {
            resolve(content);
            return;
          }
        }
      } catch (_) {}
      if (Date.now() >= deadline) {
        reject(new Error(`Timed out waiting for ${filePath}`));
        return;
      }
      setTimeout(poll, 100);
    };
    poll();
  });
}

async function testStandaloneConversion(svgBuffer) {
  const res = await runRsvgConvert(svgBuffer, { PUB_MARKDOWN_BROWSER_WS_FILE: '' });
  assert.equal(res.code, 0, `standalone failed: ${res.stderr}`);
  assert(res.stdout.length > PNG_SIGNATURE.length, 'PNG output is empty');
  assert(res.stdout.subarray(0, 8).equals(PNG_SIGNATURE), 'Output is not a PNG');
  console.log(`standalone rsvg-convert: passed (${res.stdout.length} bytes)`);
}

async function testSharedBrowserParallelConversion(svgBuffer) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-rsvg-test-'));
  const wsFile = path.join(tmpDir, 'browser.ws');
  const server = spawn(process.execPath, [BROWSER_SERVER, wsFile], {
    stdio: ['ignore', 'ignore', 'pipe'],
  });
  let serverErr = '';
  server.stderr.on('data', chunk => { serverErr += chunk.toString('utf8'); });

  try {
    await waitForFileNonEmpty(wsFile, 30000);
    // 複数プロセスで同時に共有ブラウザーへ接続し、背面タブが発生する状況で変換する。
    const parallelCount = 6;
    const tasks = Array.from({ length: parallelCount }, () =>
      runRsvgConvert(svgBuffer, { PUB_MARKDOWN_BROWSER_WS_FILE: wsFile })
    );
    const results = await Promise.all(tasks);
    for (let i = 0; i < results.length; i += 1) {
      const res = results[i];
      assert.equal(res.code, 0, `parallel[${i}] failed: ${res.stderr}`);
      assert(res.stdout.subarray(0, 8).equals(PNG_SIGNATURE), `parallel[${i}] output is not PNG`);
    }
    console.log(`shared browser parallel (${parallelCount}x) rsvg-convert: passed`);
  } finally {
    server.kill('SIGTERM');
    await new Promise(resolve => {
      const killTimer = setTimeout(() => { server.kill('SIGKILL'); resolve(); }, 5000);
      server.once('exit', () => { clearTimeout(killTimer); resolve(); });
    });
    fs.rmSync(tmpDir, { recursive: true, force: true });
    if (serverErr && process.env.DEBUG) {
      console.error(serverErr);
    }
  }
}

function testMermaidFrameAfterLayoutFallback() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-frame-test-'));
  try {
    const fakeMermaid = path.join(tmpDir, 'mermaid.min.js');
    fs.writeFileSync(fakeMermaid, 'window.mermaid = { initialize: function () {}, render: function () { return Promise.resolve({ svg: "<svg/>" }); } };\n', 'utf8');
    writeMermaidFrame(fakeMermaid, tmpDir);
    const html = fs.readFileSync(path.join(tmpDir, MERMAID_FRAME), 'utf8');
    assert(html.includes('function afterLayout()'), 'afterLayout not found');
    assert(html.includes('document.hidden'), 'document.hidden fallback not found');
    assert(html.includes('setTimeout(finish, 200)'), 'timeout fallback not found');
    assert(html.includes('getBoundingClientRect()'), 'sync reflow not found');
    console.log('mermaid frame afterLayout fallback: passed');
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

(async () => {
  const svgBuffer = fs.readFileSync(SAMPLE_SVG);
  testMermaidFrameAfterLayoutFallback();
  await testStandaloneConversion(svgBuffer);
  await testSharedBrowserParallelConversion(svgBuffer);
})().catch(err => {
  console.error(err);
  process.exit(1);
});
