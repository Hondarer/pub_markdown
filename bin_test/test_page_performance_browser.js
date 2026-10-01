'use strict';

// 実行: node bin_test/test_page_performance_browser.js (docsfw ルートから)。
// 両方式の本文で、図の再描画と新しい要素の追加を区別する。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {pathToFileURL} = require('node:url');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const resolved = JSON.parse(execFileSync(process.execPath,
  [path.join(root, 'bin_internal/resolve-node-components.js')], {encoding: 'utf8'}));
const puppeteer = require(resolved.paths.puppeteer);
const {buildBrowserLaunchOptions} = require('../bin_internal/browser-launch-options');
const svgTools = path.join(root, 'styles/browser/docsfw-svg-download.js');

async function svgMutationScope(page, mode) {
  const host = mode === 'pandoc' ? '<main id="docsfw-content">' : '<article class="md-content__inner">';
  await page.goto('about:blank');
  await page.setContent('<html lang="ja"><body>' + host + '<p>本文</p>'.repeat(1000) +
    '<div class="docsfw-mermaid">flowchart LR\nA --> B</div>'.repeat(40) +
    (mode === 'pandoc' ? '</main>' : '</article>') + '</body></html>');
  await page.evaluate(() => {
    window.fullScans = 0;
    const content = document.querySelector('#docsfw-content, article');
    const query = content.querySelectorAll.bind(content);
    content.querySelectorAll = function (selector) { window.fullScans++; return query(selector); };
    window.docsfwDiagramTools = {getView: () => 'diagram'};
    window.document$ = {subscribe(callback) { window.reinitializeTools = callback; }};
  });
  await page.addScriptTag({path: svgTools});
  assert.equal(await page.evaluate(() => window.fullScans), 2);
  assert.equal(await page.$$eval('.docsfw-diagram-toolbar', nodes => nodes.length), 40);
  await page.evaluate(async () => {
    for (const block of document.querySelectorAll('.docsfw-mermaid')) {
      block.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg"><g><rect width="20" height="20"/></g></svg>';
      block.dispatchEvent(new CustomEvent('docsfw-diagram-viewchange'));
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    window.reinitializeTools();
  });
  assert.equal(await page.evaluate(() => window.fullScans), 2, '再描画で本文全体を検索しない');
  await page.evaluate(() => {
    const content = document.querySelector('#docsfw-content, article');
    const image = document.createElement('img');
    image.src = 'direct.svg';
    content.append(image);
    const block = document.createElement('div');
    block.className = 'docsfw-plantuml';
    content.append(block);
    const section = document.createElement('section');
    section.innerHTML = '<figure><img src="nested.svg"></figure><div class="docsfw-mermaid"></div>';
    content.append(section);
    const detached = document.createElement('div');
    detached.className = 'docsfw-mermaid';
    content.append(detached);
    detached.remove();
  });
  await page.waitForFunction(() => document.querySelectorAll('.docsfw-diagram-toolbar').length === 42 &&
    document.querySelectorAll('a.docsfw-svg-dl').length === 2);
  assert.equal(await page.evaluate(() => window.fullScans), 2);
  await page.evaluate(() => window.reinitializeTools());
  assert.equal(await page.$$eval('.docsfw-diagram-toolbar', nodes => nodes.length), 42);
  // Material のページ差し替えでは、新しい本文を初回だけ検索する。
  if (mode === 'mkdocs') {
    await page.evaluate(() => {
      document.querySelector('article').outerHTML = '<article class="md-content__inner"><img src="new-page.svg"><div class="docsfw-plantuml"></div></article>';
      window.reinitializeTools();
    });
    await page.waitForFunction(() => document.querySelectorAll('.docsfw-diagram-toolbar').length === 1 &&
      document.querySelectorAll('a.docsfw-svg-dl').length === 1);
  }
  console.log(mode + ': SVG 再描画 40 回、本文検索は初回の 2 回だけ。追加要素・ページ差し替えも正常');
}

async function collapsibleWrites(page, mode, temporary) {
  let script;
  if (mode === 'pandoc') {
    const template = fs.readFileSync(path.join(root, 'styles/html/html-template.html'), 'utf8');
    const start = template.indexOf('<script>', template.indexOf('展開可能リスト (collapsible-list)'));
    script = template.slice(start, template.indexOf('</script>', start) + 9).replace(/\$\$/g, '$');
  } else {
    script = '<script src="' + pathToFileURL(path.join(root, 'livedocs/assets/docsfw-collapsible-list.js')) + '"></script>';
  }
  const instrumentation = `<script>
    window.storageWrites = 0; window.toggleEvents = 0;
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function(...args) { window.storageWrites++; return original.apply(this, args); };
    document.addEventListener('toggle', () => window.toggleEvents++, true);
  </script>`;
  const file = path.join(temporary, mode + '.html');
  fs.writeFileSync(file, '<!doctype html><html><head><meta charset="utf-8"></head><body>' +
    '<ul class="collapsible-list" data-open-level="-1">' +
    '<li>親<ul><li>子</li></ul></li>'.repeat(100) + '</ul>' + instrumentation + script + '</body></html>');
  await page.goto(pathToFileURL(file).href);
  await page.waitForFunction(() => window.toggleEvents === 100);
  assert.equal(await page.evaluate(() => window.storageWrites), 0, '初期展開は保存しない');
  const initial = await page.screenshot({fullPage: true});
  await page.evaluate(() => document.querySelectorAll('details').forEach(details => { details.open = false; }));
  await page.waitForFunction(() => window.toggleEvents === 200 && window.storageWrites === 1);
  assert.equal(await page.evaluate(() => sessionStorage.getItem('collapsible-state:' + location.pathname)), '{}');
  await page.evaluate(() => {
    document.querySelectorAll('details').forEach(details => { details.open = true; });
    // toggle の配信を待たずに遷移しても、最新状態が保存される。
    window.dispatchEvent(new PageTransitionEvent('pagehide'));
  });
  await page.waitForFunction(() => window.toggleEvents === 300);
  assert.equal(await page.evaluate(() => window.storageWrites), 2);
  assert.equal(await page.evaluate(() => Object.keys(JSON.parse(sessionStorage.getItem('collapsible-state:' + location.pathname))).length), 100);
  assert.deepEqual(await page.screenshot({fullPage: true}), initial, '開閉後も初期表示と同じ外観');
  if (mode === 'mkdocs') {
    await page.addScriptTag({path: path.join(root, 'livedocs/assets/docsfw-collapsible-list.js')});
    await page.evaluate(() => { document.querySelector('details').open = false; });
    await page.waitForFunction(() => window.storageWrites === 3);
    assert.equal(await page.$$eval('details', nodes => nodes.length), 100);
  }
  await page.evaluate(() => sessionStorage.setItem('collapsible-state:' + location.pathname, '{}'));
  await page.reload();
  await page.waitForFunction(() => window.toggleEvents === 100);
  assert.equal(await page.evaluate(() => window.storageWrites), 0);
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pagehide')));
  assert.equal(await page.evaluate(() => window.storageWrites), 1);
  assert.equal(await page.evaluate(() => Object.keys(JSON.parse(sessionStorage.getItem('collapsible-state:' + location.pathname))).length), 100,
    '再読み込み後に未操作で離れても、現在の初期状態を履歴へ保存する');
  console.log(mode + ': 初期展開 100 項目の保存 0 回、連続変更の保存 1 回。遷移直前と外観も正常');
}

(async function () {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-page-performance-'));
  const browser = await puppeteer.launch(buildBrowserLaunchOptions({headless: true,
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH,
    args: ['--no-sandbox', '--disable-crash-reporter']}));
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    for (const mode of ['pandoc', 'mkdocs']) { await svgMutationScope(page, mode); }
    for (const mode of ['pandoc', 'mkdocs']) { await collapsibleWrites(page, mode, temporary); }
    assert.deepEqual(errors, []);
  } finally {
    await browser.close();
    assert(path.resolve(temporary).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(temporary, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
