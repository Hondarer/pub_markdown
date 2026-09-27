/**
 * puppeteer-rsvg-convert  (STDIN→STDOUT, 正確版)
 *  ⊳ pandoc 互換: -f png -a --dpi-x N --dpi-y N のみ想定
 *  ⊳ 入力:  SVG (text)  via STDIN
 *  ⊳ 出力:  PNG (binary) via STDOUT
 *
 *  環境変数 PUB_MARKDOWN_BROWSER_WS_FILE が設定されている場合、
 *  共有ブラウザインスタンスに接続して再利用する。
 */
const puppeteer = require('puppeteer');
const minimist  = require('minimist');
const fs        = require('fs');
const crypto    = require('crypto');
const sharp     = require('sharp');
const { buildBrowserLaunchOptions } = require('./browser-launch-options');

/* ── 1. オプション解析 ─────────────────────────────────────────────── */
const argv  = minimist(process.argv.slice(2), {
  string : ['f','dpi-x','dpi-y'],
  default: {f:'png','dpi-x':96,'dpi-y':96}
});
if (argv.f !== 'png') { console.error('PNG 以外は未対応'); process.exit(1); }
const dpiX = +argv['dpi-x'] || 96;
const dpiY = +argv['dpi-y'] || 96;
/* 指定 DPI を 1.5 倍して描画 */
const scale = Math.max(dpiX, dpiY) * 1.5 / 96;
const RETRY_DELAY_MS = 3000;

/* ── 2. STDIN 取得 ────────────────────────────────────────────────── */
const readStdin = () => new Promise(res => {
  let d=''; process.stdin.setEncoding('utf8');
  process.stdin.on('data', c=>d+=c);
  process.stdin.on('end', ()=>res(d));
});

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function summarizeSvg(svgText) {
  const sha1 = crypto.createHash('sha1').update(svgText).digest('hex');
  const titleMatch = svgText.match(/<title[^>]*>(.*?)<\/title>/is);
  const rootIdMatch = svgText.match(/<svg\b[^>]*\bid="([^"]+)"/i);
  return {
    sha1,
    title: titleMatch ? titleMatch[1].replace(/\s+/g, ' ').trim() : '',
    rootId: rootIdMatch ? rootIdMatch[1] : '',
  };
}

function describeFailure({ sourceFile, svgSummary, width, height, scaleValue }) {
  const parts = [
    `[rsvg-convert] screenshot failed`,
    `source=${sourceFile || '(unknown)'}`,
    `svg_sha1=${svgSummary.sha1}`,
    `size=${width}x${height}`,
    `scale=${scaleValue}`,
  ];
  if (svgSummary.title) parts.push(`title=${JSON.stringify(svgSummary.title)}`);
  if (svgSummary.rootId) parts.push(`svg_id=${JSON.stringify(svgSummary.rootId)}`);
  return parts.join(' ');
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
    } catch (_) {
      // ファイルが読めない・接続失敗時はフォールバック
    }
  }
  const browser = await puppeteer.launch(buildBrowserLaunchOptions({ args: ['--no-sandbox'] }));
  return { browser, shared: false };
}

(async () => {
  const svgText = (await readStdin()).trim();
  if (!svgText) { console.error('STDIN が空です'); process.exit(2); }
  const sourceFile = process.env.SOURCE_FILE || '';
  const svgSummary = summarizeSvg(svgText);

  /* ── 3. Puppeteer 起動 or 共有ブラウザ接続 ─────────────────────── */
  const { browser, shared } = await getBrowser();
  const page = await browser.newPage();

  try {
    /* 3-A. 仮に大きめ viewport を張っておく（計測用） */
    await page.setViewport({width: 4096, height: 4096, deviceScaleFactor: 1});
    await page.setContent(`<html><body style="margin:0">${svgText}</body></html>`,
                          {waitUntil:'load'});   // <img>, 外部 CSS 等も読み込ませる

    /* ── 4. サイズ決定ロジック (ブラウザ側で実行) ─────────────────── */
    const {w,h} = await page.evaluate(() => {
      const svg = document.querySelector('svg');
      /* ① width/height 属性 (単位付含む) を優先 */
      const parseUnit = v => {
        if (!v) return null;
        const m = String(v).trim().match(/^([+-]?\d*\.?\d+)([a-z%]*)$/i);
        if (!m) return null;
        const num = parseFloat(m[1]);
        const unit = m[2] || 'px';
        /* SVG CSS 仕様: 1pt=1.25px, 1pc=15px, 1mm≈3.7795px, 1cm=10mm */
        const conv = {px:1, pt:1.25, pc:15, mm:3.7795275591, cm:37.795275591,
                      in:96, '%':null};
        return conv[unit] ? num*conv[unit] : null;   // % は計算できないので無視
      };
      const wAttr = parseUnit(svg.getAttribute('width'));
      const hAttr = parseUnit(svg.getAttribute('height'));
      if (wAttr && hAttr) return {w:wAttr, h:hAttr};

      /* ② viewBox の幅高 */
      const vb = svg.getAttribute('viewBox');
      if (vb) {
        const p = vb.split(/[\s,]+/).map(Number);
        if (p.length === 4 && p.every(n=>!isNaN(n))) return {w:p[2], h:p[3]};
      }

      /* ③ 最終手段: レイアウト後の実ピクセル矩形 */
      const r = svg.getBoundingClientRect();
      return {w:r.width, h:r.height};
    });

    const width  = Math.max(1, Math.ceil(w));
    const height = Math.max(1, Math.ceil(h));

    /* ── 5. 実 viewport へ張り直し & deviceScaleFactor 反映 ─────────── */
    await page.setViewport({width, height, deviceScaleFactor: scale});
    /* レイアウト再計算を待つ */
    await page.evaluate(() => new Promise(r => requestAnimationFrame(()=>r())));

    /* ── 6. PNG 出力 → STDOUT ──────────────────────────────────────── */
    let buf;
    try {
      buf = await page.screenshot({type:'png', omitBackground:true});
    } catch (firstError) {
      // 一過性の CDP 失敗を想定し、ユーザーへ通知せず 1 回だけ再試行する。
      await sleep(RETRY_DELAY_MS);
      await page.evaluate(() => new Promise(r => requestAnimationFrame(()=>r())));
      try {
        buf = await page.screenshot({type:'png', omitBackground:true});
      } catch (retryError) {
        console.error(describeFailure({
          sourceFile,
          svgSummary,
          width,
          height,
          scaleValue: scale,
        }));
        retryError.cause = firstError;
        throw retryError;
      }
    }
    /* ── 7. sharp によるパレット減色再エンコード ──────────────────────── */
    try {
      buf = await sharp(buf).png({
        palette         : true,  // libimagequant による減色 (pngquant 相当)
        quality         : 90,    // 減色品質 (0-100)
        effort          : 10,    // 最適化強度 (1-10)
        compressionLevel: 9,     // zlib 圧縮レベル (0-9)
      }).toBuffer();
    } catch (sharpErr) {
      /* 再エンコード失敗時はスクリーンショット buf をそのまま使用して続行 */
      console.error('[rsvg-convert] sharp re-encode failed, using raw screenshot:', sharpErr.message);
    }

    process.stdout.write(buf);
  } finally {
    /* 共有ブラウザの場合はページを閉じて切断。専用ブラウザの場合はブラウザごと閉じる */
    await page.close();
    if (shared) {
      browser.disconnect();
    } else {
      await browser.close();
    }
  }

})().catch(err => { console.error(err); process.exit(3); });
