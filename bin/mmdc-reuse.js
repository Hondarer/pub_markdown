/**
 * mmdc-reuse.js
 *
 * 共有ブラウザインスタンスを使用して Mermaid 図を SVG にレンダリングする。
 * mmdc (mermaid-cli) の代替として、既存のブラウザインスタンスに接続することで
 * ブラウザの起動コストを削減する。
 *
 * 使い方:
 *   node mmdc-reuse.js -i <input.mmd> -o <output.svg> [-b transparent]
 *
 * 環境変数:
 *   PUB_MARKDOWN_BROWSER_WS_FILE - 共有ブラウザの WebSocket エンドポイントファイルパス
 */
const puppeteer = require('puppeteer');
const fs        = require('fs');
const path      = require('path');
const minimist  = require('minimist');

const argv = minimist(process.argv.slice(2), {
  string: ['i', 'o', 'b'],
  default: { b: 'white' }
});

if (!argv.i || !argv.o) {
  console.error('Usage: node mmdc-reuse.js -i <input.mmd> -o <output.svg> [-b transparent]');
  process.exit(1);
}

/* ── Mermaid ライブラリのブラウザバンドルを探す ──────────────────── */
function findMermaidBundle() {
  const candidates = [
    () => {
      const dir = path.dirname(require.resolve('mermaid/package.json'));
      return path.join(dir, 'dist', 'mermaid.min.js');
    },
    () => {
      const dir = path.dirname(require.resolve('@mermaid-js/mermaid-cli/package.json'));
      return path.join(dir, 'node_modules', 'mermaid', 'dist', 'mermaid.min.js');
    },
    () => path.join(__dirname, 'node_modules', 'mermaid', 'dist', 'mermaid.min.js'),
    () => path.join(__dirname, 'node_modules', '@mermaid-js', 'mermaid-cli', 'node_modules', 'mermaid', 'dist', 'mermaid.min.js'),
  ];

  for (const candidate of candidates) {
    try {
      const p = candidate();
      if (fs.existsSync(p)) return p;
    } catch (_) {}
  }
  return null;
}

/* ── 共有ブラウザ接続 or 新規起動 ────────────────────────────────── */
async function getBrowser() {
  const wsFile = process.env.PUB_MARKDOWN_BROWSER_WS_FILE;
  if (wsFile) {
    try {
      const wsEndpoint = fs.readFileSync(wsFile, 'utf8').trim();
      if (wsEndpoint) {
        const browser = await puppeteer.connect({ browserWSEndpoint: wsEndpoint });
        return { browser, shared: true };
      }
    } catch (_) {}
  }
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  return { browser, shared: false };
}

(async () => {
  const inputFile  = argv.i;
  const outputFile = argv.o;
  const background = argv.b || 'white';

  // 入力ファイル読み込み
  const diagramCode = fs.readFileSync(inputFile, 'utf8');

  // Mermaid バンドルのパスを取得
  const mermaidBundlePath = findMermaidBundle();
  if (!mermaidBundlePath) {
    console.error('Error: mermaid library bundle not found');
    process.exit(2);
  }

  const { browser, shared } = await getBrowser();
  const page = await browser.newPage();

  try {
    // 基本的な HTML ページを設定
    const bgStyle = background === 'transparent' ? 'transparent' : background;
    await page.setContent(`<!DOCTYPE html>
<html><head><style>body { background: ${bgStyle}; margin: 0; }</style></head>
<body><div id="mermaid-container"></div></body></html>`, { waitUntil: 'load' });

    // Mermaid ライブラリを読み込み
    await page.addScriptTag({ path: mermaidBundlePath });

    // Mermaid でダイアグラムをレンダリング
    const svgContent = await page.evaluate(async (code) => {
      /* global mermaid */
      mermaid.initialize({
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'loose',
      });
      const { svg } = await mermaid.render('mermaid-diagram', code);
      return svg;
    }, diagramCode);

    // SVG を出力ファイルに書き込み
    fs.writeFileSync(outputFile, svgContent, 'utf8');
  } finally {
    await page.close();
    if (shared) {
      browser.disconnect();
    } else {
      await browser.close();
    }
  }
})().catch(err => { console.error(err); process.exit(3); });
