'use strict';

// Pandoc HTML のヘッダー、検索、ドロワーを実ブラウザーで局所検証する。
const assert = require('assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const { pathToFileURL } = require('url');
const puppeteer = require('puppeteer');
const { buildBrowserLaunchOptions } = require('./browser-launch-options');

const root = path.resolve(__dirname, '..');
const output = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-ui-'));
const source = `---
title: Look & Feel 同期
lang: ja
author: 発行者
date: 2026-09-06
---

# 同期の確認

全文検索とナビゲーションを確認します。

## 子見出し

本文です。
` + Array.from({length: 35}, (_, i) => '\n## Section ' + i + '\n\n' + '本文のスクロール確認。'.repeat(70) + '\n').join('');

function prepare() {
  const resolved = JSON.parse(execFileSync(process.execPath,
    [path.join(__dirname, 'resolve-node-components.js')], { encoding: 'utf8' }));
  for (const name of ['html-style.css', 'docsfw-ui.css', 'docsfw-nav.js', 'docsfw-search.js', 'docsfw-theme.js']) {
    fs.copyFileSync(path.join(root, 'styles/html', name), path.join(output, name));
  }
  fs.copyFileSync(path.join(__dirname, 'docsfw-tokenize.js'), path.join(output, 'docsfw-tokenize.js'));
  fs.copyFileSync(resolved.paths.minisearchJs, path.join(output, 'minisearch.min.js'));
  fs.writeFileSync(path.join(output, 'sample.md'), source);
  fs.writeFileSync(path.join(output, 'nav-tree.js'), 'window.__DOCSFW_NAV__=' + JSON.stringify({
    title: 'sample-site', url: 'index.html', children: [{
      title: 'ガイド', url: 'guide/index.html', path: 'guide/', children: [
        { title: 'Look & Feel 同期', url: 'guide/current.html', children: [] },
        { title: '別ページ', url: 'guide/other.html', children: [] }
      ]
    }, {title: '閉じた分類', url: null, children: [
      {title: '隠れたページ', url: 'other/page.html', children: []}
    ]}]
  }) + ';\n');

  const template = fs.readFileSync(path.join(root, 'styles/html/html-template.html'), 'utf8')
    .replace(/<script\b[^>]*src=['"]https?:[^>]*>\s*<\/script>/g, '')
    .replace(/<link\b[^>]*href=['"]https?:[^>]*>/g, '')
    // Retain the legacy selector conflict without a network dependency.
    .replace('<head>', '<head><style>body{margin:0}.container{margin:auto}#TOC{top:0;overflow-y:scroll}.toc{margin-top:10px}</style>');
  fs.writeFileSync(path.join(output, 'template.html'), template);
  execFileSync('pandoc', ['sample.md', '-s', '-t', 'html', '--toc', '--template', 'template.html',
    '-c', 'html-style.css', '-M', 'docsfw-browser-base=', '-M', 'docsfw-ui-enable=true',
    '-M', 'docsfw-drawer-enable=true', '-M', 'docsfw-nav-enable=true',
    '-M', 'docsfw-search-enable=true', '-M', 'docsfw-asset-base=',
    '-M', 'search-current=guide/current.html', '-M', 'homelink=index.html',
    '-M', 'docsfw-site-name=sample-site', '-M', 'docsfw-variant=ja', '-o', 'current.html'],
  { cwd: output, stdio: 'pipe' });
  execFileSync(process.execPath, [path.join(__dirname, 'build-search-index.mjs'), output], { stdio: 'pipe' });
  return resolved;
}

async function dimensions(page, selector) {
  return page.$eval(selector, element => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return { top: rect.top, width: rect.width, height: rect.height, display: style.display };
  });
}

async function main() {
  const resolved = prepare();
  process.stdout.write('Artifacts: ' + output + '\n');
  const options = buildBrowserLaunchOptions({ puppeteer, puppeteerExecutablePath: resolved.paths.puppeteer });
  const browser = await puppeteer.launch(options);
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewport({ width: 1700, height: 900 });
    await page.goto(pathToFileURL(path.join(output, 'current.html')).href);
    await page.waitForSelector('.docsfw-flat-nav');

    assert.equal((await dimensions(page, '.docsfw-header')).height, 48);
    assert(['flex', 'inline-flex'].includes((await dimensions(page, '.docsfw-logo')).display));
    assert.equal((await dimensions(page, '#docsfw-hamburger')).display, 'none');
    assert(await page.$eval('#docsfw-page-toc', node => !!node.closest('#TOC')));
    assert.equal(await page.$eval('#docsfw-search-input', node => node.placeholder), '検索');
    assert.equal((await dimensions(page, '.docsfw-search-form')).height, 36);
    assert.equal((await dimensions(page, '.docsfw-search-form')).width, 234);
    assert.equal((await dimensions(page, '.docsfw-search-form')).top, 6);
    assert.equal(await page.$eval('.docsfw-logo', node => node.getBoundingClientRect().left), 60.5);
    assert.equal(await page.$eval('.doc-title', node => node.getBoundingClientRect().left), 124.5);
    assert.equal(await page.$eval('.doc-title', node => getComputedStyle(node).color), 'rgba(0, 0, 0, 0.87)');
    assert.equal(await page.$eval('.docsfw-current', node => getComputedStyle(node).fontWeight), '400');
    assert.equal(await page.$eval('.docsfw-nav-ancestor > .docsfw-nav-row > a', node => getComputedStyle(node).color), 'rgb(26, 95, 170)');
    assert.equal(await page.$eval('.docsfw-nav-ancestor > .docsfw-nav-row > .docsfw-nav-toggle', node => getComputedStyle(node).color), 'rgb(26, 95, 170)');
    assert.deepEqual(await page.$eval('.docsfw-search-form', node => {
      const style = getComputedStyle(node, '::before');
      return {width: style.width, height: style.height, left: style.left};
    }), {width: '24px', height: '24px', left: '10px'});
    await page.focus('#docsfw-search-input');
    assert.equal(await page.$eval('#docsfw-search-input', node => getComputedStyle(node).boxShadow), 'rgb(74, 144, 217) 0px 0px 0px 1px');
    await page.$eval('#docsfw-search-input', node => node.blur());
    assert((await dimensions(page, '.docsfw-home-link a')).height > 0);
    assert.equal(await page.$eval('.docsfw-home-link a', node => node.getAttribute('href')), 'index.html');
    const toggles = await page.$$('.docsfw-nav-toggle');
    assert.equal(await toggles[0].evaluate(node => node.getAttribute('aria-expanded')), 'true');
    assert.equal(await toggles[1].evaluate(node => node.getAttribute('aria-expanded')), 'false');
    await toggles[1].hover();
    assert.equal(await toggles[1].evaluate(node => getComputedStyle(node).color), 'rgb(26, 95, 170)');
    await toggles[1].focus();
    assert.equal(await toggles[1].evaluate(node => getComputedStyle(node).color), 'rgb(26, 95, 170)');
    assert.equal(await toggles[1].evaluate(node => getComputedStyle(node).outlineStyle), 'none');
    await page.keyboard.press('Enter');
    assert.equal(await toggles[1].evaluate(node => document.getElementById(node.getAttribute('aria-controls')).hidden), false);
    await page.keyboard.press('Space');
    assert.equal(await toggles[1].evaluate(node => node.getAttribute('aria-expanded')), 'false');
    // position: sticky はスクロールで自然配置が閾値 (60px) を超えるまで固定されない。
    // margin-top: -10px を含む自然配置は 70px で、固定後 (60px) と異なるのが正しい
    // (下の scrollTo(0, 700) 後の同じアサーションと比較)。
    assert.equal((await dimensions(page, '#TOC')).top, 70);
    assert.equal(Math.round((await dimensions(page, '#TOC')).width * 100) / 100, 306.22);
    assert.equal(Math.round(await page.$eval('#TOC', node => node.getBoundingClientRect().right) * 100) / 100, 1643.11);
    assert.equal(Math.round((await dimensions(page, '#docsfw-primary-sidebar')).width * 100) / 100, 351.22);
    assert.equal(Math.round(await page.$eval('#docsfw-primary-sidebar', node => node.getBoundingClientRect().right) * 100) / 100, 408.11);
    await page.evaluate(() => scrollTo(0, 700));
    await new Promise(resolve => setTimeout(resolve, 100));
    assert.equal((await dimensions(page, '#TOC')).top, 60);
    assert.equal(await page.$eval('#TOC', node => node.scrollHeight > node.clientHeight), true);
    await page.$eval('#TOC', node => { node.scrollTop = 200; });
    assert.equal(await page.evaluate(() => scrollY), 700);
    assert.equal((await dimensions(page, '.docsfw-toc-title')).top, 60);
    await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
    await new Promise(resolve => setTimeout(resolve, 100));
    assert(await page.$eval('#TOC', node => node.scrollTop > 200));
    assert(await page.$eval('#docsfw-page-toc .docsfw-toc-active', node => {
      const bounds = document.querySelector('#TOC').getBoundingClientRect();
      const rect = node.getBoundingClientRect();
      return rect.top >= bounds.top && rect.bottom <= bounds.bottom;
    }));
    await page.evaluate(() => { document.documentElement.setAttribute('data-md-color-scheme', 'slate'); });
    assert.equal(await page.$eval('.doc-title', node => getComputedStyle(node).color), 'rgba(255, 255, 255, 0.87)');
    await page.evaluate(() => { document.documentElement.setAttribute('data-md-color-scheme', 'default'); scrollTo(0, 0); });
    for (const width of [1399, 1400, 1700]) {
      await page.setViewport({width, height:900});
      await page.waitForFunction(wide => !!document.querySelector('#docsfw-page-toc').closest('#TOC') === wide, {}, width >= 1400);
    }
    await page.screenshot({ path: path.join(output, 'wide.png'), fullPage: false });

    // 中間 3 列 (1400px〜1624px) は、3 列 PC (1625px 以上) と同じくハンバーガーを
    // 隠し、ページ内目次が右の列になるが、左右列は 240px/210px と狭い。
    await page.setViewport({ width: 1500, height: 900 });
    await page.waitForFunction(() => getComputedStyle(document.querySelector('#docsfw-hamburger')).display === 'none');
    assert(await page.$eval('#docsfw-page-toc', node => !!node.closest('#TOC')));
    const midSidebarWidth = (await dimensions(page, '#docsfw-primary-sidebar')).width;
    await page.setViewport({ width: 1700, height: 900 });
    await page.waitForFunction(() => getComputedStyle(document.querySelector('#docsfw-hamburger')).display === 'none');
    const wideSidebarWidth = (await dimensions(page, '#docsfw-primary-sidebar')).width;
    assert(midSidebarWidth < wideSidebarWidth);

    // ページ上部へ戻るボタン: 下スクロール中は出さず、上スクロールで表示する。
    assert.equal(await page.$eval('#docsfw-top', node => node.hidden), true);
    await page.evaluate(() => scrollTo(0, 3000));
    await new Promise(resolve => setTimeout(resolve, 100));
    assert.equal(await page.$eval('#docsfw-top', node => node.hidden), true);
    await page.evaluate(() => scrollTo(0, 2900));
    await page.waitForFunction(() => {
      const node = document.getElementById('docsfw-top');
      return !node.hidden && getComputedStyle(node).opacity === '1';
    });
    assert.equal(await page.$eval('#docsfw-top', node => node.tagName), 'BUTTON');
    assert.equal(await page.$eval('#docsfw-top', node => node.getAttribute('aria-label')), 'ページトップへ戻る');
    assert.equal(await page.$eval('#docsfw-top-label', node => node.textContent), 'ページトップへ戻る');
    assert.equal(await page.$eval('#docsfw-top', node => node.getAttribute('title') || ''), '');
    assert.deepEqual(await page.$eval('#docsfw-top', node => {
      const style = getComputedStyle(node);
      return {
        top: style.top,
        fontSize: style.fontSize,
        paddingTop: style.paddingTop,
        paddingRight: style.paddingRight,
        paddingBottom: style.paddingBottom,
        paddingLeft: style.paddingLeft,
        borderRadius: style.borderRadius
      };
    }), {
      top: '76px',
      fontSize: '14px',
      paddingTop: '8px',
      paddingRight: '16px',
      paddingBottom: '8px',
      paddingLeft: '16px',
      borderRadius: '32px'
    });
    assert.equal(await page.$eval('#docsfw-top svg', node => getComputedStyle(node).width), '24px');
    await page.screenshot({ path: path.join(output, 'back-to-top.png'), fullPage: false });
    await page.setViewport({ width: 1700, height: 800 });
    await page.waitForFunction(() => document.getElementById('docsfw-top').hidden);
    await page.evaluate(() => scrollTo(0, 3000));
    await new Promise(resolve => setTimeout(resolve, 50));
    await page.evaluate(() => scrollTo(0, 2800));
    await page.waitForFunction(() => {
      const node = document.getElementById('docsfw-top');
      return !node.hidden && getComputedStyle(node).opacity === '1';
    });
    const topBox = await page.$eval('#docsfw-top', node => {
      const rect = node.getBoundingClientRect();
      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
    });
    await page.mouse.move(topBox.x, topBox.y);
    await page.waitForFunction(() =>
      getComputedStyle(document.getElementById('docsfw-top')).backgroundColor === 'rgb(0, 85, 128)');
    assert.equal(await page.$eval('#docsfw-top', node => getComputedStyle(node).color), 'rgb(255, 255, 255)');
    await page.mouse.click(topBox.x, topBox.y);
    assert.equal(await page.$eval('#docsfw-top', node => node.hidden), true);
    await page.waitForFunction(() => scrollY < 5);
    assert.equal(await page.$eval('#docsfw-content h1', node => document.activeElement === node), true);

    await page.setViewport({ width: 1300, height: 900 });
    await page.waitForFunction(() => getComputedStyle(document.querySelector('#docsfw-hamburger')).display !== 'none');
    await page.click('#docsfw-hamburger');
    await new Promise(resolve => setTimeout(resolve, 300));
    const drawer = await dimensions(page, '#docsfw-primary-sidebar');
    assert.equal(Math.round(drawer.top), 60);
    assert.equal(Math.round(drawer.width), 320);
    assert.equal(await page.$eval('#docsfw-primary-sidebar', node => Math.round(node.getBoundingClientRect().left)), 0);
    assert(await page.$eval('#docsfw-page-toc', node => !!node.closest('.docsfw-flat-nav')));

    // ドロワー表示中でも、ホイールで本文をスクロールできる (MkDocs Material と同じ)。
    assert.equal(await page.evaluate(() => scrollY), 0);
    await page.mouse.move(1000, 400);
    await page.mouse.wheel({ deltaY: 1500 });
    await new Promise(resolve => setTimeout(resolve, 100));
    assert(await page.evaluate(() => scrollY) > 0);

    // ドロワーへ移設したページ内目次でも、読了部が薄い色になる。
    await page.waitForSelector('#docsfw-page-toc a.docsfw-toc-passed');
    assert(await page.$eval('#docsfw-page-toc', node => !!node.closest('.docsfw-flat-nav')));
    assert.equal(await page.$eval('#docsfw-page-toc a.docsfw-toc-passed', node => getComputedStyle(node).color), 'rgb(117, 117, 117)');
    await page.evaluate(() => scrollTo(0, 0));

    // 垂直スクロール バーは見出しの下から始まる。ドロワー自体はスクロールさせない。
    assert(await page.$eval('#docsfw-primary-sidebar', node => node.scrollHeight === node.clientHeight));
    assert.equal(Math.round((await dimensions(page, '.docsfw-drawer-body')).top), 105);
    assert(await page.$eval('.docsfw-drawer-body', node => node.scrollHeight > node.clientHeight));
    await page.screenshot({ path: path.join(output, 'drawer.png'), fullPage: false });
    await page.click('#docsfw-nav-backdrop');
    assert.equal(await page.$eval('#docsfw-hamburger', node => node.getAttribute('aria-expanded')), 'false');
    await page.waitForFunction(() => document.querySelector('#docsfw-nav-backdrop').getBoundingClientRect().width === 0);

    await page.setViewport({ width: 1100, height: 900 });
    await page.click('#docsfw-hamburger');
    await new Promise(resolve => setTimeout(resolve, 300));
    assert(await page.$eval('.docsfw-nav-panel.docsfw-panel-active', node => node.dataset.panelKey !== 'root'));
    assert.equal((await dimensions(page, '.docsfw-panel-title')).display, 'block');
    assert.equal((await dimensions(page, '.docsfw-panel-title')).height, 112);
    assert.equal((await dimensions(page, '.docsfw-panel-title')).top, 60);
    assert(await page.$eval('#docsfw-page-toc', node => !!node.closest('.docsfw-nav-panel.docsfw-panel-active')));
    // 垂直スクロールバーは見出しの下から始まる。ドロワー自体はスクロールさせない。
    assert(await page.$eval('#docsfw-primary-sidebar', node => node.scrollHeight === node.clientHeight));
    const panelBody = '.docsfw-nav-panel.docsfw-panel-active > .docsfw-panel-body';
    assert.equal(Math.round((await dimensions(page, panelBody)).top), 172);
    assert(await page.$eval(panelBody, node => node.scrollHeight > node.clientHeight));
    await page.screenshot({ path: path.join(output, 'panel.png'), fullPage: false });

    // 見出しのフォルダー名は、インデックス ページ (node.url) があれば実リンクになる。
    const guideTitleLink = await page.$eval('.docsfw-nav-panel.docsfw-panel-active .docsfw-panel-title-text',
      node => ({ tag: node.tagName, href: node.getAttribute('href') }));
    assert.equal(guideTitleLink.tag, 'A');
    assert.equal(guideTitleLink.href, 'guide/index.html');

    await page.click('.docsfw-nav-panel.docsfw-panel-active .docsfw-nav-back');
    assert(await page.$eval('.docsfw-nav-panel.docsfw-panel-active', node => node.dataset.panelKey === 'root'));

    // インデックス ページを持たないフォルダーでは、フォルダー名はリンクにならない。
    await page.click('button.docsfw-nav-forward[aria-label="閉じた分類を開く"]');
    await new Promise(resolve => setTimeout(resolve, 200));
    assert.equal(await page.$eval('.docsfw-nav-panel.docsfw-panel-active .docsfw-panel-title-text', node => node.tagName), 'SPAN');
    await page.click('.docsfw-nav-panel.docsfw-panel-active .docsfw-nav-back');
    assert(await page.$eval('.docsfw-nav-panel.docsfw-panel-active', node => node.dataset.panelKey === 'root'));

    await page.keyboard.press('Escape');
    await page.waitForFunction(() => document.querySelector('#docsfw-nav-backdrop').getBoundingClientRect().width === 0);

    await page.setViewport({ width: 900, height: 900 });
    await page.click('.docsfw-search-icon');
    assert(await page.$eval('body', body => body.classList.contains('docsfw-search-open')));
    await page.type('#docsfw-search-input', '全文検索');
    await page.waitForSelector('.docsfw-result-item');
    await page.keyboard.press('ArrowDown');
    assert(await page.$eval('.docsfw-result-item', node => node.getAttribute('aria-selected') === 'true'));
    await page.screenshot({ path: path.join(output, 'search.png'), fullPage: false });
    await page.keyboard.press('Escape');
    assert(!await page.$eval('body', body => body.classList.contains('docsfw-search-open')));

    assert.deepEqual(errors, []);
    process.stdout.write('Pandoc header, drawer, panel navigation, and search: passed\n');
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
