// 実行: node livedocs/tests/test_code_expander_browser.js (docsfw ルートから)
// 一時サイトだけを生成し、MkDocs 上のコード ブロック開閉を検証する。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const puppeteer = require(path.join(root, 'bin/node_modules/puppeteer'));
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-code-expander-'));
const python = process.env.PYTHON || path.join(root, 'livedocs/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const longLine = `long-line-${'x'.repeat(240)}`;

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {encoding: 'utf8', timeout: 30000, ...options});
  assert.equal(result.status, 0, result.stderr || String(result.error));
  return result.stdout;
}

(async function () {
  let browser;
  let server;
  try {
    run(python, ['-', root, temporary], {input: String.raw`
import pathlib, sys
root, target = map(pathlib.Path, sys.argv[1:])
sys.path.insert(0, str(root / 'livedocs/bin'))
from vendor_assets import vendor_own_assets
docs = target / 'docs'
docs.mkdir()
fence = chr(96) * 3
long_line = ${JSON.stringify(longLine)}
md = '\n\n'.join([
    '# Test',
    fence + 'c\n' + long_line + '\nshort\ncode\n' + fence,
    fence + 'c\n' + long_line + '\nline2\nline3\nline4\nline5\nline6\nline7\n' + fence,
    fence + 'mermaid\nflowchart LR\n    A --> B\n' + fence,
])
(docs / 'index.md').write_text(md, encoding='utf-8')
vendor_own_assets(str(docs / 'assets'))
(target / 'mkdocs.yml').write_text("""site_name: Test
theme:
  name: material
  font: false
  features:
    - content.code.copy
markdown_extensions:
  - pymdownx.highlight
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: docsfw-mermaid
          format: !!python/name:pymdownx.superfences.fence_div_format
extra_css:
  - assets/docsfw-pandoc-style.css
  - assets/docsfw-livedocs.css
  - assets/docsfw-code-expander.css
extra_javascript:
  - assets/docsfw-code-expander.js
""", encoding='utf-8')
`});
    run(python, ['-m', 'mkdocs', 'build', '--strict', '-f', path.join(temporary, 'mkdocs.yml')]);
    server = http.createServer((request, response) => {
      let pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      if (pathname.endsWith('/')) pathname += 'index.html';
      const file = path.join(temporary, 'site', pathname.replace(/^\//, ''));
      if (!fs.existsSync(file)) { response.writeHead(404); response.end(); return; }
      const types = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css'};
      response.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
      response.end(fs.readFileSync(file));
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const url = `http://127.0.0.1:${server.address().port}/`;
    browser = await puppeteer.launch({
      headless: true,
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/local/bin/chrome',
      args: ['--no-sandbox', '--disable-crash-reporter'],
    });
    const page = await browser.newPage();
    await page.setViewport({width: 800, height: 600});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url, {waitUntil: 'networkidle0'});
    const info = await page.evaluate(() => {
      const wrappers = [...document.querySelectorAll('.code-expander-wrapper')];
      const toolbars = [...document.querySelectorAll('.code-expander-toolbar')];
      const mermaidWrap = document.querySelector('.docsfw-mermaid .code-expander-wrapper');
      return {
        wrapperCount: wrappers.length,
        toolbarCount: toolbars.length,
        mermaidWrapped: !!mermaidWrap,
        shortHasToolbar: !!(wrappers[0] && wrappers[0].parentElement.querySelector(':scope > .code-expander-toolbar')),
        longHasToolbar: !!(wrappers[1] && wrappers[1].parentElement.querySelector(':scope > .code-expander-toolbar')),
        restHiddenAfterCollapse: null,
        hintText: toolbars.length ? document.querySelector('.code-expander-hint').textContent : '',
      };
    });
    assert.equal(info.wrapperCount, 2, JSON.stringify(info));
    assert.equal(info.toolbarCount, 1);
    assert.equal(info.shortHasToolbar, false);
    assert.equal(info.longHasToolbar, true);
    assert.equal(info.mermaidWrapped, false);
    const restDisplayExpanded = await page.evaluate(() => {
      const rest = document.querySelector('.code-rest');
      return rest ? rest.style.display : 'missing';
    });
    assert.equal(restDisplayExpanded, '');
    await page.click('.code-expander-btn');
    const collapsed = await page.evaluate(() => {
      const rest = document.querySelector('.code-rest');
      const hint = document.querySelector('.code-expander-hint');
      const first = document.querySelector('.code-first code');
      return {
        rest: rest.style.display,
        hint: hint.style.display,
        firstLines: first.textContent.split('\n').filter(Boolean).length,
        hintText: hint.textContent,
      };
    });
    assert.equal(collapsed.rest, 'none');
    assert.equal(collapsed.hint, '');
    assert.equal(collapsed.firstLines, 5);
    assert.match(collapsed.hintText, /2.*7/);
    await page.waitForFunction(() => document.querySelector('.md-code__button[data-md-type="copy"][data-clipboard-text]'));
    const copiedSource = await page.evaluate(() => {
      const buttons = [...document.querySelectorAll('.md-code__button[data-md-type="copy"]')];
      const long = buttons.find(b => (b.getAttribute('data-clipboard-text') || '').includes('line7'));
      return long ? long.getAttribute('data-clipboard-text') : '';
    });
    assert.match(copiedSource, /line7/);
    assert.match(copiedSource, /long-line-/);
    await page.waitForFunction(() => {
      const wrap = document.querySelector('.code-expander-wrapper');
      return !!(wrap && [...wrap.children].some((child) => child.classList.contains('md-code__nav')));
    });

    async function copyPin(pageHandle, wrapperIndex, selector) {
      return pageHandle.evaluate((index, sel) => {
        const wrap = document.querySelectorAll('.code-expander-wrapper')[index];
        const scroll = wrap && wrap.querySelector('.code-expander-scroll');
        const chip = wrap && wrap.querySelector(sel);
        const pre = wrap && wrap.querySelector('pre');
        if (!wrap || !scroll || !chip || !pre) {
          return {missing: true};
        }
        const wrapRect = wrap.getBoundingClientRect();
        const chipRect = chip.getBoundingClientRect();
        const preRect = pre.getBoundingClientRect();
        return {
          missing: false,
          parentIsWrapper: chip.parentElement === wrap,
          wrapRight: wrapRect.right,
          chipRight: chipRect.right,
          chipTop: chipRect.top,
          preRight: preRect.right,
          overflow: scroll.scrollWidth - scroll.clientWidth,
          scrollLeft: scroll.scrollLeft,
        };
      }, wrapperIndex, selector);
    }

    function assertPinned(info, label) {
      assert.equal(info.missing, false, label + ' ' + JSON.stringify(info));
      assert.equal(info.parentIsWrapper, true, label + ' parent ' + JSON.stringify(info));
      assert.ok(info.overflow > 40, label + ' overflow ' + JSON.stringify(info));
      assert.ok(info.preRight > info.wrapRight + 40, label + ' content wider ' + JSON.stringify(info));
      const gap = info.wrapRight - info.chipRight;
      assert.ok(gap >= 0 && gap <= 12, label + ' visible right ' + JSON.stringify(info));
    }

    async function assertStaysOnScroll(pageHandle, wrapperIndex, selector, label) {
      const before = await copyPin(pageHandle, wrapperIndex, selector);
      assertPinned(before, label);
      await pageHandle.evaluate((index) => {
        const wrap = document.querySelectorAll('.code-expander-wrapper')[index];
        wrap.querySelector('.code-expander-scroll').scrollLeft = 120;
      }, wrapperIndex);
      const after = await copyPin(pageHandle, wrapperIndex, selector);
      assert.equal(after.scrollLeft, 120, label + ' scrolled ' + JSON.stringify(after));
      assert.ok(Math.abs(after.chipRight - before.chipRight) <= 1, label + ' stayed ' + JSON.stringify({before, after}));
      await pageHandle.evaluate((index) => {
        const wrap = document.querySelectorAll('.code-expander-wrapper')[index];
        wrap.querySelector('.code-expander-scroll').scrollLeft = 0;
      }, wrapperIndex);
    }

    await assertStaysOnScroll(page, 0, '.md-code__nav', 'mkdocs short');
    await assertStaysOnScroll(page, 1, '.md-code__nav', 'mkdocs long');

    async function hoverLongChrome(pageHandle, selector) {
      const wrap = (await pageHandle.$$('.code-expander-wrapper'))[1];
      const inside = await wrap.$(selector);
      if (inside) {
        await inside.hover();
        return;
      }
      const sibling = await wrap.evaluateHandle((el, sel) => el.parentElement.querySelector(sel), selector);
      await sibling.asElement().hover();
    }
    async function navOpacityAfterHover(selector) {
      await hoverLongChrome(page, selector);
      await new Promise((resolve) => setTimeout(resolve, 200));
      return page.evaluate(() => {
        const wrap = document.querySelectorAll('.code-expander-wrapper')[1];
        const nav = wrap.querySelector('.md-code__nav') || wrap.parentElement.querySelector('.md-code__nav');
        return nav ? getComputedStyle(nav).opacity : 'missing';
      });
    }
    assert.equal(await navOpacityAfterHover('.code-expander-toolbar'), '0');
    assert.equal(await navOpacityAfterHover('.code-expander-hint'), '0');
    assert.equal(await navOpacityAfterHover('.code-expander-scroll'), '1');
    assert.deepEqual(errors, []);
    console.log('PASS: MkDocs code expander wrap, threshold, collapse hint, full copy, mermaid skipped, copy hover on code only');

    const htmlStyle = fs.readFileSync(path.join(root, 'styles/html/html-style.css'), 'utf8');
    const template = fs.readFileSync(path.join(root, 'styles/html/html-template.html'), 'utf8');
    const markerAt = template.indexOf('コードブロック エキスパンダーとコピー');
    const styleStart = template.indexOf('<style>', markerAt);
    const styleEnd = template.indexOf('</style>', styleStart) + '</style>'.length;
    const scriptStart = template.indexOf('<script>', styleEnd);
    const scriptEnd = template.indexOf('</script>', scriptStart) + '</script>'.length;
    const expanderCss = template.slice(styleStart, styleEnd);
    const expanderJs = template.slice(scriptStart, scriptEnd).replace(/\$\$/g, '$');
    const pandocHtml = '<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>' +
      htmlStyle + '</style>' + expanderCss + '</head><body><main id="docsfw-content">' +
      '<pre><code>' + longLine + '\nshort\ncode\n</code></pre>' +
      '<pre><code>' + longLine + '\nline2\nline3\nline4\nline5\nline6\nline7\n</code></pre>' +
      '</main>' + expanderJs + '</body></html>';
    const pandocServer = http.createServer((request, response) => {
      response.setHeader('Content-Type', 'text/html; charset=utf-8');
      response.end(pandocHtml);
    });
    await new Promise((resolve) => pandocServer.listen(0, '127.0.0.1', resolve));
    const pandocPage = await browser.newPage();
    await pandocPage.setViewport({width: 800, height: 600});
    await pandocPage.goto('http://127.0.0.1:' + pandocServer.address().port + '/', {waitUntil: 'networkidle0'});
    await pandocPage.click('.code-expander-btn');
    async function copyOpacityAfterHover(selector) {
      await hoverLongChrome(pandocPage, selector);
      await new Promise((resolve) => setTimeout(resolve, 200));
      return pandocPage.evaluate(() => {
        const wrap = document.querySelectorAll('.code-expander-wrapper')[1];
        return getComputedStyle(wrap.querySelector('.docsfw-code-copy')).opacity;
      });
    }
    assert.equal(await copyOpacityAfterHover('.code-expander-toolbar'), '0');
    assert.equal(await copyOpacityAfterHover('.code-expander-hint'), '0');
    assert.equal(await copyOpacityAfterHover('.code-expander-scroll'), '1');
    await assertStaysOnScroll(pandocPage, 0, '.docsfw-code-copy', 'pandoc short');
    await assertStaysOnScroll(pandocPage, 1, '.docsfw-code-copy', 'pandoc long');
    await pandocPage.close();
    await new Promise((resolve) => pandocServer.close(resolve));
    console.log('PASS: Pandoc copy hover on code only');
  } finally {
    if (browser) await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
    fs.rmSync(temporary, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
