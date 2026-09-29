'use strict';

// 実行: node tests/test_lazy_nav_browser.js (docsfw ルートから)。
// 両発行方式の局所 fixture で、遅延生成と DOM 破棄を実ブラウザーで確認する。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {pathToFileURL} = require('node:url');
const http = require('node:http');
const root = path.resolve(__dirname, '..');
const resolved = JSON.parse(execFileSync(process.execPath,
  [path.join(root, 'bin_internal/resolve-node-components.js')], {encoding: 'utf8'}));
const puppeteer = require(resolved.paths.puppeteer);
const {buildBrowserLaunchOptions} = require('../bin_internal/browser-launch-options');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-lazy-nav-'));
const python = process.env.PYTHON || path.join(root, 'livedocs/.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

function pandocFixture() {
  const tree = {title: 'Home', url: 'index.html', children: Array.from({length: 12}, (_, i) => ({
    title: `Section ${i}`, url: `s${i}/index.html`, path: `s${i}/`, children: [
      {title: 'Nested', url: `s${i}/nested/index.html`, path: `s${i}/nested/`, children: [
        {title: 'Deep', url: `s${i}/nested/deep.html`}
      ]}, ...Array.from({length: 100}, (_, j) => ({title: j === 99 ? '日本語 <img src=x onerror=alert(1)> & "quoted"' : `Page ${j}`, url: `s${i}/p${j}.html`}))
    ]
  }))};
  const css = ['html-style.css', 'docsfw-ui.css'].map(file =>
    fs.readFileSync(path.join(root, 'styles/html', file), 'utf8')).join('\n');
  const html = `<!doctype html><html lang="ja"><head><style>${css}</style></head><body>
    <button id="docsfw-hamburger"></button><button id="docsfw-nav-backdrop"></button>
    <aside id="docsfw-primary-sidebar"><div class="well"><div id="docsfw-home-container"></div>
      <div id="docsfw-tree"></div></div></aside>
    <aside id="TOC"><div class="well"><div id="docsfw-page-toc"><a href="#heading">Heading</a></div></div></aside>
    <main id="docsfw-content"><h1 id="heading">Heading</h1></main>
    <script>window.__DOCSFW_NAV_ENABLED__=true; window.__DOCSFW_CURRENT__='s0/p0.html';
      window.__DOCSFW_NAV__=${JSON.stringify(tree)};</script>
    <script src="${pathToFileURL(path.join(root, 'styles/html/docsfw-nav.js'))}"></script>
    </body></html>`;
  const target = path.join(temporary, 'pandoc.html');
  fs.writeFileSync(target, html);
  return pathToFileURL(target).href;
}

function mkdocsFixture() {
  execFileSync(python, ['-', root, temporary], {encoding: 'utf8', input: String.raw`
import pathlib, shutil, sys
root, target = map(pathlib.Path, sys.argv[1:])
site = target / 'mkdocs'
docs = site / 'docs'
docs.mkdir(parents=True)
for variant in ('ja', 'ja-details'):
    base = docs / variant
    base.mkdir()
    (base / 'index.md').write_text('# Home\n', encoding='utf-8')
    for i in range(12 if variant == 'ja' else 1):
        section = base / f's{i}'
        section.mkdir()
        (section / 'index.md').write_text(f'# Section {i}\n', encoding='utf-8')
        nested = section / 'nested'
        nested.mkdir()
        (nested / 'index.md').write_text('# Nested\n', encoding='utf-8')
        (nested / 'deep.md').write_text('# Deep\n', encoding='utf-8')
        for j in range(10 if variant == 'ja' else 1):
            (section / f'p{j}.md').write_text(
                f'# Page {j}\n\n## Heading\n\n本文\n', encoding='utf-8')
shutil.copytree(root / 'livedocs/theme', site / 'theme')
assets = docs / 'assets'
assets.mkdir()
for file in ('docsfw-responsive-nav.js', 'docsfw-livedocs.css', 'docsfw-pandoc-style.css'):
    shutil.copyfile(root / 'livedocs/assets' / file, assets / file)
(site / 'mkdocs.yml').write_text('''site_name: Test
plugins: []
theme:
  name: material
  custom_dir: theme
  font: false
  features:
    - navigation.indexes
    - toc.follow
extra:
  livedocs_variants: [ja, ja-details]
  livedocs_variant: ja
  livedocs_site_name: Test
extra_css:
  - assets/docsfw-livedocs.css
  - assets/docsfw-pandoc-style.css
extra_javascript:
  - assets/docsfw-responsive-nav.js
''', encoding='utf-8')
`});
  execFileSync(python, ['-m', 'mkdocs', 'build', '--strict', '-f',
    path.join(temporary, 'mkdocs/mkdocs.yml')], {encoding: 'utf8', stdio: 'pipe'});
}

(async () => {
  let browser, server;
  try {
    const pandocUrl = pandocFixture();
    mkdocsFixture();
    server = http.createServer((request, response) => {
      let pathname = new URL(request.url, 'http://localhost').pathname;
      if (pathname.endsWith('/')) pathname += 'index.html';
      const file = path.join(temporary, 'mkdocs/site', decodeURIComponent(pathname));
      if (!fs.existsSync(file)) { response.writeHead(404).end(); return; }
      const types = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css'};
      response.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
      response.end(fs.readFileSync(file));
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const executablePath = process.env.PUPPETEER_EXECUTABLE_PATH || (process.platform === 'win32'
      ? 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' : undefined);
    browser = await puppeteer.launch(buildBrowserLaunchOptions({headless: true, executablePath}));
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    await page.setViewport({width: 1500, height: 900});
    await page.goto(pandocUrl);
    await page.waitForSelector('.docsfw-flat-nav .docsfw-current');
    const initialPandoc = await page.$$eval('#docsfw-tree *', nodes => nodes.length);
    assert(initialPandoc < 1000, `Pandoc initial DOM: ${initialPandoc}`);
    assert.equal(await page.$$('.docsfw-nav-panel').then(nodes => nodes.length), 0);
    const sectionToggle = '.docsfw-flat-nav > ul > li:nth-child(2) .docsfw-nav-toggle';
    await page.$eval(sectionToggle, button => button.click());
    assert.equal(await page.$$eval('.docsfw-flat-nav > ul > li:nth-child(2) > ul > li', n => n.length), 101);
    assert.equal(await page.$$('.docsfw-flat-nav img').then(n => n.length), 0);
    assert.match(await page.$eval('.docsfw-flat-nav > ul > li:nth-child(2) > ul > li:last-child a', n => n.textContent), /日本語 <img/);
    // 動的に追加した孫の操作と、親を閉じたあとの状態復元。
    const nestedToggle = '.docsfw-flat-nav > ul > li:nth-child(2) > ul > li:first-child button';
    await page.$eval(nestedToggle, button => button.click());
    await page.$eval(sectionToggle, button => button.click());
    assert.equal(await page.$$eval('.docsfw-flat-nav > ul > li:nth-child(2) > ul *', n => n.length), 0);
    await page.$eval(sectionToggle, button => button.click());
    assert.equal(await page.$eval(nestedToggle, button => button.getAttribute('aria-expanded')), 'true');
    await page.setViewport({width: 900, height: 900});
    await page.waitForSelector('.docsfw-nav-panel');
    assert.equal(await page.$$('.docsfw-nav-panel').then(n => n.length), 1);
    assert.equal(await page.$$('.docsfw-flat-nav').then(n => n.length), 0);
    await page.$eval('.docsfw-nav-back', button => button.click());
    assert.equal(await page.$$('.docsfw-nav-panel').then(n => n.length), 1);
    assert.equal(await page.$eval('#docsfw-page-toc', toc => toc.isConnected), true);
    await page.setViewport({width: 1500, height: 900});
    await page.waitForSelector('.docsfw-flat-nav .docsfw-current');
    await page.setViewport({width: 900, height: 900});
    await page.waitForFunction(() => document.getElementById('docsfw-primary-sidebar').classList.contains('docsfw-child-panel-active'));
    await page.setViewport({width: 1500, height: 900});

    await page.goto(`http://127.0.0.1:${server.address().port}/ja/s0/p0/`);
    await page.waitForSelector('#docsfw-nav-data');
    const initialMkdocs = await page.$$eval('.md-sidebar--primary *', nodes => nodes.length);
    assert(initialMkdocs < 1500, `MkDocs initial DOM: ${initialMkdocs}`);
    assert.equal(await page.$eval('.md-sidebar--primary .md-nav__list > li:nth-child(3) > nav > ul', n => n.children.length), 0);
    assert.equal(await page.$eval('#docsfw-nav-data', n => JSON.parse(n.textContent).length), 13);
    const mkSection = await page.evaluate(() => {
      const input = document.querySelector('.md-sidebar--primary .md-nav__list > li:nth-child(3) > input');
      return input.id;
    });
    const mkNested = await page.evaluate(id => {
      const toggle = document.getElementById(id);
      document.getElementById(id + '_label').click();
      return toggle.parentNode.querySelector(':scope > nav > ul > li > input').id;
    }, mkSection);
    await page.evaluate(id => {
      const toggle = document.getElementById(id);
      toggle.checked = true; toggle.dispatchEvent(new Event('change', {bubbles: true}));
    }, mkNested);
    await page.evaluate(id => {
      const toggle = document.getElementById(id);
      toggle.checked = false; toggle.dispatchEvent(new Event('change', {bubbles: true}));
    }, mkSection);
    assert.equal(await page.evaluate(id => !!document.getElementById(id), mkNested), false);
    await page.focus(`#${mkSection}_label`);
    await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(id => document.getElementById(id).checked, mkNested), true);
    await page.focus(`#${mkNested}_label`);
    await page.keyboard.press('Space');
    assert.equal(await page.evaluate(id => document.getElementById(id).checked, mkNested), false);
    await page.setViewport({width: 900, height: 900});
    await page.waitForSelector('.docsfw-combined-toc');
    // 現在経路を閉じても、統合目次は DOM に残る。
    await page.evaluate(() => {
      const link = document.querySelector('.md-sidebar--primary a.md-nav__link--active[href]');
      const toggle = link.closest('nav').parentNode.querySelector(':scope > input');
      toggle.checked = false; toggle.dispatchEvent(new Event('change', {bubbles: true}));
    });
    assert.equal(await page.$eval('.docsfw-combined-toc nav', toc => toc.isConnected), true);
    await page.setViewport({width: 1500, height: 900});
    await page.waitForSelector('.md-sidebar--secondary nav.md-nav--secondary');
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({initialPandocElements: initialPandoc, initialMkdocsElements: initialMkdocs,
      fixtureLeavesPerSection: {pandoc: 100, mkdocs: 10}, checks: 'expand/collapse/restore/resize/current/toc/keyboard passed'}));
  } finally {
    if (browser) await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
    const absolute = path.resolve(temporary);
    if (absolute.startsWith(path.resolve(os.tmpdir()) + path.sep) &&
        path.basename(absolute).startsWith('docsfw-lazy-nav-')) fs.rmSync(absolute, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
