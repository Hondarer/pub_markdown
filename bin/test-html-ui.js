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
        ...Array.from({length: 24}, (_, index) => ({
          title: '前のページ ' + index, url: 'guide/before-' + index + '.html', children: []
        })),
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
    return {
      top: rect.top,
      bottom: rect.bottom,
      width: rect.width,
      height: rect.height,
      display: style.display,
    };
  });
}

function assertNear(actual, expected, tolerance, label) {
  assert.ok(Math.abs(actual - expected) <= tolerance,
    label + ': expected ' + expected + ' +/- ' + tolerance + ', actual ' + actual);
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

    const drawerLogoPage = await browser.newPage();
    await drawerLogoPage.setViewport({ width: 1100, height: 900 });
    await drawerLogoPage.goto(pathToFileURL(path.join(output, 'current.html')).href);
    await drawerLogoPage.waitForSelector('.docsfw-flat-nav');
    await drawerLogoPage.click('#docsfw-hamburger');
    await drawerLogoPage.waitForFunction(() => document.body.classList.contains('docsfw-nav-open'));
    if (await drawerLogoPage.$eval('.docsfw-nav-panel.docsfw-panel-active', node => node.dataset.panelKey !== 'root')) {
      await drawerLogoPage.$eval('.docsfw-nav-panel.docsfw-panel-active .docsfw-nav-back', node => node.click());
      await drawerLogoPage.waitForFunction(() =>
        document.querySelector('.docsfw-nav-panel.docsfw-panel-active').dataset.panelKey === 'root');
    }
    for (const scheme of ['default', 'slate']) {
      await drawerLogoPage.evaluate(value => {
        document.documentElement.setAttribute('data-md-color-scheme', value);
      }, scheme);
      const logo = await drawerLogoPage.$eval('.docsfw-drawer-title', title => {
        const svg = title.querySelector('.docsfw-drawer-logo svg');
        const rect = svg.getBoundingClientRect();
        return {
          titleColor: getComputedStyle(title).color,
          fill: getComputedStyle(svg).fill,
          width: rect.width,
          height: rect.height,
        };
      });
      assert.equal(logo.fill, logo.titleColor, scheme + ' ' + JSON.stringify(logo));
      assert.deepEqual({width: logo.width, height: logo.height}, {width: 24, height: 24});
    }
    await drawerLogoPage.close();

    const tocClickPage = await browser.newPage();
    for (const width of [1500, 1700]) {
      await tocClickPage.setViewport({width, height: 900});
      await tocClickPage.goto(pathToFileURL(path.join(output, 'current.html')).href);
      await tocClickPage.waitForSelector('#docsfw-page-toc a[href^="#"]');
      const hrefs = await tocClickPage.$$eval('#docsfw-page-toc a[href^="#"]', links =>
        links.map(link => link.getAttribute('href')));
      let checked = 0;
      for (const href of hrefs) {
        const metric = await tocClickPage.evaluate(async targetHref => {
          const link = Array.from(document.querySelectorAll('#docsfw-page-toc a[href^="#"]'))
            .find(node => node.getAttribute('href') === targetHref);
          link.click();
          await new Promise(resolve => setTimeout(resolve, 20));
          const id = decodeURIComponent(targetHref.slice(1));
          const target = document.getElementById(id);
          const active = document.querySelector('#docsfw-page-toc a.docsfw-toc-active');
          const anchorLine = parseFloat(getComputedStyle(document.documentElement)
            .getPropertyValue('--docsfw-anchor-line'));
          return {
            hash: decodeURIComponent(location.hash),
            targetTop: target.getBoundingClientRect().top,
            anchorLine,
            activeHref: active && active.getAttribute('href'),
            ariaCurrent: link.getAttribute('aria-current'),
          };
        }, href);
        if (metric.targetTop > metric.anchorLine) continue;
        checked++;
        assert.equal(metric.hash, href, width + 'px hash ' + JSON.stringify(metric));
        assert.equal(metric.activeHref, href, width + 'px active ' + JSON.stringify(metric));
        assert.equal(metric.ariaCurrent, 'location', width + 'px aria-current ' + JSON.stringify(metric));
      }
      assert(checked > 10, width + 'px checked links: ' + checked);
    }
    await tocClickPage.close();

    async function drawerSelectionMetrics(targetPage, selectedSelector) {
      return targetPage.evaluate(selector => {
        const selected = document.querySelector(selector);
        const panelLayout = matchMedia('(max-width: 76.234375em)').matches;
        const container = panelLayout
          ? document.querySelector(
            '.docsfw-nav-panel.docsfw-panel-active > .docsfw-panel-body')
          : document.querySelector('.docsfw-drawer-body');
        const selectedRect = selected.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        return {
          text: selected.textContent.trim(),
          visible: selectedRect.top >= containerRect.top - 1 &&
            selectedRect.bottom <= containerRect.bottom + 1,
          centerDifference: Math.abs(
            (selectedRect.top + selectedRect.bottom) / 2 -
            (containerRect.top + containerRect.bottom) / 2),
          scrollTop: container.scrollTop,
          scrollLeft: container.scrollLeft,
          pageScrollY: window.scrollY,
        };
      }, selectedSelector);
    }

    const drawerFollowPage = await browser.newPage();
    const currentFile = pathToFileURL(path.join(output, 'current.html'));
    for (const width of [1100, 1300]) {
      await drawerFollowPage.setViewport({width, height: 900});
      currentFile.hash = 'section-20';
      await drawerFollowPage.goto(currentFile.href);
      await drawerFollowPage.waitForSelector(
        '#docsfw-page-toc a.docsfw-toc-active[href="#section-20"]');
      const pageScrollY = await drawerFollowPage.evaluate(() => window.scrollY);
      await drawerFollowPage.$eval('#docsfw-hamburger', node => node.click());
      await drawerFollowPage.waitForFunction(() =>
        document.body.classList.contains('docsfw-nav-open'));
      const selector = width < 1220
        ? '#docsfw-page-toc a.docsfw-toc-active[href="#section-20"]'
        : '.docsfw-flat-nav .docsfw-current';
      const opened = await drawerSelectionMetrics(drawerFollowPage, selector);
      assert.equal(opened.visible, true,
        width + 'px opened drawer selection ' + JSON.stringify(opened));
      assert.ok(opened.centerDifference <= 2,
        width + 'px opened drawer center ' + JSON.stringify(opened));
      assert.ok(opened.scrollTop > 0,
        width + 'px opened drawer scroll ' + JSON.stringify(opened));
      assert.equal(opened.scrollLeft, 0,
        width + 'px opened drawer horizontal scroll ' + JSON.stringify(opened));
      assert.equal(opened.pageScrollY, pageScrollY,
        width + 'px opened drawer page scroll ' + JSON.stringify(opened));

      await drawerFollowPage.evaluate(() =>
        document.getElementById('section-25').scrollIntoView());
      await drawerFollowPage.waitForSelector(
        '#docsfw-page-toc a.docsfw-toc-active[href="#section-25"]');
      const followed = await drawerSelectionMetrics(drawerFollowPage,
        '#docsfw-page-toc a.docsfw-toc-active[href="#section-25"]');
      assert.equal(followed.visible, true,
        width + 'px followed toc selection ' + JSON.stringify(followed));
      assert.equal(followed.scrollLeft, 0,
        width + 'px followed toc horizontal scroll ' + JSON.stringify(followed));
    }
    await drawerFollowPage.close();

    for (const width of [730, 1302, 1770]) {
      await page.setViewport({ width, height: 900 });
      const content = await page.$eval('.docsfw-main-content', node => {
        const rect = node.getBoundingClientRect();
        const heading = node.querySelector('h1').getBoundingClientRect();
        return { top: heading.top, left: rect.left, right: rect.right };
      });
      assert.ok(Math.abs(content.top - 88) <= 1,
        width + 'px content top ' + JSON.stringify(content));
      if (width <= 767) {
        assert.ok(Math.abs(content.left - 20) <= 1,
          width + 'px content left ' + JSON.stringify(content));
        assert.ok(Math.abs(content.right - (width - 20)) <= 1,
          width + 'px content right ' + JSON.stringify(content));
      }
    }
    await page.setViewport({ width: 1700, height: 900 });

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
    }), {width: '20px', height: '20px', left: '10px'});
    assert.equal(await page.$eval('.docsfw-logo-icon--light', node => getComputedStyle(node).width), '24px');
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
    // 本文上端を MkDocs とそろえたため、ナビゲーションも初期表示から
    // position: sticky の固定位置 (60px) に達する。
    assert.equal((await dimensions(page, '#TOC')).top, 60);
    assertNear((await dimensions(page, '#TOC')).width, 306.22, 1, 'wide TOC width');
    assertNear(await page.$eval('#TOC', node => node.getBoundingClientRect().right),
      1643.11, 1, 'wide TOC right');
    assertNear((await dimensions(page, '#docsfw-primary-sidebar')).width,
      351.22, 1, 'wide primary sidebar width');
    assertNear(await page.$eval('#docsfw-primary-sidebar', node => node.getBoundingClientRect().right),
      408.11, 1, 'wide primary sidebar right');
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
    assert.notEqual(await page.$eval('#docsfw-hamburger', node => document.activeElement === node), true);
    const drawer = await dimensions(page, '#docsfw-primary-sidebar');
    assert.equal(Math.round(drawer.top), 60);
    assert.equal(Math.round(drawer.width), 320);
    assert.equal(await page.$eval('#docsfw-primary-sidebar', node => Math.round(node.getBoundingClientRect().left)), 0);
    assert.deepEqual(await page.$eval('#docsfw-primary-sidebar', node => ({
      top: getComputedStyle(node).borderTopWidth,
      right: getComputedStyle(node).borderRightWidth,
    })), {top: '1px', right: '1px'});
    assert(await page.$eval('#docsfw-page-toc', node => !!node.closest('.docsfw-flat-nav')));
    assert.deepEqual(await page.$eval('.docsfw-drawer-title', node => {
      const title = getComputedStyle(node);
      const tree = getComputedStyle(document.querySelector('#docsfw-tree'));
      return {
        fontFamilyMatchesTree: title.fontFamily === tree.fontFamily,
        fontSize: title.fontSize,
        lineHeight: title.lineHeight,
      };
    }), {fontFamilyMatchesTree: true, fontSize: '14px', lineHeight: '21px'});
    for (const width of [1220, 1300, 1399]) {
      await page.setViewport({ width, height: 900 });
      const boundary = await page.$eval('#docsfw-page-toc', node => {
        const previous = node.previousElementSibling.getBoundingClientRect();
        const toc = node.getBoundingClientRect();
        const title = node.querySelector('.docsfw-toc-title').getBoundingClientRect();
        const style = getComputedStyle(node);
        return {
          marginTop: style.marginTop,
          gap: Math.round((toc.top - previous.bottom) * 100) / 100,
          titleGap: Math.round((title.top - toc.top - parseFloat(style.borderTopWidth)) * 100) / 100,
        };
      });
      assert.deepEqual(boundary, {marginTop: '12px', gap: 12, titleGap: 12},
        width + 'px drawer toc boundary ' + JSON.stringify(boundary));
    }
    await page.setViewport({ width: 1300, height: 900 });

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
    assert.equal(Math.round((await dimensions(page, '.docsfw-drawer-body')).top), 106);
    assert(await page.$eval('.docsfw-drawer-body', node => node.scrollHeight > node.clientHeight));
    assert.equal(Math.round((await dimensions(page, '.docsfw-drawer-body')).bottom), 900);
    assert.equal(await page.$eval('.docsfw-drawer-body', node => getComputedStyle(node).paddingBottom), '12px');
    await page.screenshot({ path: path.join(output, 'drawer.png'), fullPage: false });
    await page.click('#docsfw-nav-backdrop');
    assert.equal(await page.$eval('#docsfw-hamburger', node => node.getAttribute('aria-expanded')), 'false');
    await page.waitForFunction(() => document.querySelector('#docsfw-nav-backdrop').getBoundingClientRect().width === 0);

    await page.setViewport({ width: 1100, height: 900 });
    await page.click('#docsfw-hamburger');
    await new Promise(resolve => setTimeout(resolve, 300));
    assert.equal(await page.$eval('#docsfw-page-toc', node => getComputedStyle(node).marginTop), '0px');
    assert(await page.$eval('.docsfw-nav-panel.docsfw-panel-active', node => node.dataset.panelKey !== 'root'));
    assert.equal((await dimensions(page, '.docsfw-panel-title')).display, 'block');
    assert.equal((await dimensions(page, '.docsfw-panel-title')).height, 112);
    assert.equal((await dimensions(page, '.docsfw-panel-title')).top, 61);
    assert.deepEqual(await page.$eval('.docsfw-nav-panel.docsfw-panel-active .docsfw-panel-title', node => {
      const title = getComputedStyle(node);
      const text = node.querySelector('.docsfw-panel-title-text');
      const textStyle = getComputedStyle(text);
      const backStyle = getComputedStyle(node.querySelector('.docsfw-nav-back'));
      return {
        color: title.color,
        textColor: textStyle.color,
        backColor: backStyle.color,
        textHeight: text.getBoundingClientRect().height,
        textMarginTop: textStyle.marginTop,
        whiteSpace: textStyle.whiteSpace,
        overflow: textStyle.overflow,
        textOverflow: textStyle.textOverflow,
      };
    }), {
      color: 'rgba(0, 0, 0, 0.54)',
      textColor: 'rgba(0, 0, 0, 0.54)',
      backColor: 'rgba(0, 0, 0, 0.54)',
      textHeight: 21,
      textMarginTop: '0px',
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
    });
    await page.hover('.docsfw-nav-panel.docsfw-panel-active .docsfw-panel-title-text');
    assert.equal(await page.$eval('.docsfw-nav-panel.docsfw-panel-active .docsfw-panel-title-text',
      node => getComputedStyle(node).textDecorationLine), 'none');
    assert(await page.$eval('#docsfw-page-toc', node => !!node.closest('.docsfw-nav-panel.docsfw-panel-active')));
    assert.deepEqual(await page.$eval('#docsfw-page-toc.docsfw-combined-toc', node => {
      const title = node.querySelector('.docsfw-toc-title');
      return {
        marginTop: getComputedStyle(node).marginTop,
        padding: getComputedStyle(node).padding,
        titleHeight: title.getBoundingClientRect().height,
        titlePadding: getComputedStyle(title).padding,
      };
    }), {marginTop: '0px', padding: '12px 0px 0px', titleHeight: 45, titlePadding: '12px 16px'});
    assert.deepEqual(await page.$$eval('#docsfw-page-toc.docsfw-combined-toc a', nodes =>
      nodes.slice(0, 3).map(node => ({
        height: node.getBoundingClientRect().height,
        padding: getComputedStyle(node).padding,
        lineHeight: getComputedStyle(node).lineHeight,
        marginTop: getComputedStyle(node).marginTop,
        borderTopWidth: getComputedStyle(node).borderTopWidth,
        itemBorderTopWidth: getComputedStyle(node.parentElement).borderTopWidth,
      }))
    ), [
      {height: 45, padding: '12px 16px', lineHeight: '21px', marginTop: '0px',
        borderTopWidth: '0px', itemBorderTopWidth: '1px'},
      {height: 45, padding: '12px 16px', lineHeight: '21px', marginTop: '0px',
        borderTopWidth: '0px', itemBorderTopWidth: '1px'},
      {height: 45, padding: '12px 16px', lineHeight: '21px', marginTop: '0px',
        borderTopWidth: '0px', itemBorderTopWidth: '1px'},
    ]);
    // 垂直スクロールバーは見出しの下から始まる。ドロワー自体はスクロールさせない。
    assert(await page.$eval('#docsfw-primary-sidebar', node => node.scrollHeight === node.clientHeight));
    const panelBody = '.docsfw-nav-panel.docsfw-panel-active > .docsfw-panel-body';
    assert.equal(Math.round((await dimensions(page, panelBody)).top), 173);
    assert(await page.$eval(panelBody, node => node.scrollHeight > node.clientHeight));
    await page.screenshot({ path: path.join(output, 'panel.png'), fullPage: false });

    // 板の末尾では、最後の行が画面下端に接する。MkDocs の板もこの値にそろえる。
    const panelBottomGap = await page.evaluate(selector => {
      const body = document.querySelector(selector);
      body.scrollTop = body.scrollHeight;
      const links = document.querySelectorAll('#docsfw-page-toc.docsfw-combined-toc a');
      const last = links[links.length - 1];
      return window.innerHeight - last.getBoundingClientRect().bottom;
    }, panelBody);
    assert(Math.abs(panelBottomGap) <= 1, 'panel bottom gap ' + panelBottomGap);
    await page.evaluate(selector => { document.querySelector(selector).scrollTop = 0; }, panelBody);

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
    assert.equal(await page.$eval('#docsfw-hamburger', node => document.activeElement === node), true);
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.body.classList.contains('docsfw-nav-open'));
    assert.equal(await page.$eval('#docsfw-hamburger', node => document.activeElement === node), true);
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
