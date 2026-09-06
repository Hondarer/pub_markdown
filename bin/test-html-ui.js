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
`;

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
    }]
  }) + ';\n');

  const template = fs.readFileSync(path.join(root, 'styles/html/html-template.html'), 'utf8')
    .replace(/<script\b[^>]*src=['"]https?:[^>]*>\s*<\/script>/g, '')
    .replace(/<link\b[^>]*href=['"]https?:[^>]*>/g, '');
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
    await page.screenshot({ path: path.join(output, 'wide.png'), fullPage: false });

    await page.setViewport({ width: 1400, height: 900 });
    await page.waitForFunction(() => getComputedStyle(document.querySelector('#docsfw-hamburger')).display !== 'none');
    await page.click('#docsfw-hamburger');
    await new Promise(resolve => setTimeout(resolve, 300));
    const drawer = await dimensions(page, '#docsfw-primary-sidebar');
    assert.equal(Math.round(drawer.top), 60);
    assert.equal(Math.round(drawer.width), 320);
    assert.equal(await page.$eval('#docsfw-primary-sidebar', node => Math.round(node.getBoundingClientRect().left)), 0);
    assert(await page.$eval('#docsfw-page-toc', node => !!node.closest('.docsfw-flat-nav')));
    await page.screenshot({ path: path.join(output, 'drawer.png'), fullPage: false });
    await page.click('#docsfw-nav-backdrop');
    assert.equal(await page.$eval('#docsfw-hamburger', node => node.getAttribute('aria-expanded')), 'false');

    await page.setViewport({ width: 1100, height: 900 });
    await page.click('#docsfw-hamburger');
    await new Promise(resolve => setTimeout(resolve, 300));
    assert(await page.$eval('.docsfw-nav-panel.docsfw-panel-active', node => node.dataset.panelKey !== 'root'));
    assert.equal((await dimensions(page, '.docsfw-panel-title')).display, 'flex');
    assert(await page.$eval('#docsfw-page-toc', node => !!node.closest('.docsfw-nav-panel.docsfw-panel-active')));
    await page.screenshot({ path: path.join(output, 'panel.png'), fullPage: false });
    await page.click('.docsfw-nav-back');
    assert(await page.$eval('.docsfw-nav-panel.docsfw-panel-active', node => node.dataset.panelKey === 'root'));
    await page.keyboard.press('Escape');

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
