/**
 * puppeteer-rsvg-convert  (STDIN→STDOUT, 正確版)
 *  ⊳ pandoc 互換: -f png -a --dpi-x N --dpi-y N のみ想定
 *  ⊳ 入力:  SVG (text)  via STDIN
 *  ⊳ 出力:  PNG (binary) via STDOUT
 */
const puppeteer = require('puppeteer');
const minimist  = require('minimist');

/* ── 1. オプション解析 ─────────────────────────────────────────────── */
const argv  = minimist(process.argv.slice(2), {
  string : ['f','dpi-x','dpi-y'],
  default: {f:'png','dpi-x':96,'dpi-y':96}
});
if (argv.f !== 'png') { console.error('PNG 以外は未対応'); process.exit(1); }
const dpiX = +argv['dpi-x'] || 96;
const dpiY = +argv['dpi-y'] || 96;
/* 指定 DPI を 3 倍して描画 */
const scale = Math.max(dpiX, dpiY) * 3 / 96;

/* ── 2. STDIN 取得 ────────────────────────────────────────────────── */
const readStdin = () => new Promise(res => {
  let d=''; process.stdin.setEncoding('utf8');
  process.stdin.on('data', c=>d+=c);
  process.stdin.on('end', ()=>res(d));
});
(async () => {
  const svgText = (await readStdin()).trim();
  if (!svgText) { console.error('STDIN が空です'); process.exit(2); }

  /* ── 3. Puppeteer 起動 ─────────────────────────────────────────── */
  const browser = await puppeteer.launch({args:['--no-sandbox']});
  const page    = await browser.newPage();

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
  const buf = await page.screenshot({type:'png', omitBackground:true});
  await browser.close();
  process.stdout.write(buf);

})().catch(err => { console.error(err); process.exit(3); });
