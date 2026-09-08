// 実行: node livedocs/tests/test_livedocs_nav_browser.js (docsfw ルートから)
// ドロワーを開いたときに現在文書が中央へ表示されることと、3 ペインから
// 連続一覧ドロワーの幅 (1300px) へ縮めたあとも下端 12px が残ることを検証する。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const puppeteer = require(path.join(root, 'bin/node_modules/puppeteer'));
const {buildBrowserLaunchOptions} = require(path.join(root, 'bin/browser-launch-options'));
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-nav-drawer-'));
const python = process.env.PYTHON || path.join(root, 'livedocs/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {encoding: 'utf8', timeout: 60000, ...options});
  assert.equal(result.status, 0, result.stderr || String(result.error));
  return result.stdout;
}

function headings() {
  return Array.from({length: 40}, (_, index) => '## Heading ' + (index + 1) + '\n\n本文です。\n').join('\n');
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
md = ${JSON.stringify('# Drawer margin\n\n' + headings())}
(docs / 'index.md').write_text(md, encoding='utf-8')
section = docs / 'section'
section.mkdir()
(section / 'index.md').write_text('# Section\n', encoding='utf-8')
for index in range(50):
    (section / f'page-{index:02d}.md').write_text(
        f'# Page {index:02d}\n\n本文です。\n', encoding='utf-8'
    )
vendor_own_assets(str(docs / 'assets'))
(target / 'mkdocs.yml').write_text("""site_name: Test
theme:
  name: material
  font: false
  features:
    - navigation.indexes
markdown_extensions:
  - toc:
      permalink: true
      toc_depth: 3
extra_css:
  - assets/docsfw-livedocs.css
  - assets/docsfw-header-meta.css
extra_javascript:
  - assets/docsfw-responsive-nav.js
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
    browser = await puppeteer.launch(buildBrowserLaunchOptions({
      headless: true,
      args: ['--no-sandbox', '--disable-crash-reporter'],
    }));
    const page = await browser.newPage();

    async function openDrawer() {
      await page.waitForFunction(() => {
        const button = document.querySelector('label.md-header__button[for="__drawer"]');
        return button && getComputedStyle(button).display !== 'none';
      });
      await page.click('label.md-header__button[for="__drawer"]');
      await page.waitForSelector('.docsfw-combined-toc');
      await new Promise(resolve => setTimeout(resolve, 300));
    }

    async function openDrawerAndScrollEnd() {
      await openDrawer();
      await page.evaluate(() => {
        const lists = Array.from(document.querySelectorAll('.md-sidebar--primary .md-nav__list'));
        for (const list of lists) {
          if (list.scrollHeight > list.clientHeight + 1) {
            list.scrollTop = list.scrollHeight;
          }
        }
        const wrap = document.querySelector('.md-sidebar--primary .md-sidebar__scrollwrap');
        if (wrap) {
          wrap.scrollTop = wrap.scrollHeight;
        }
      });
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    async function drawerEndMetrics() {
      return page.evaluate(() => {
        const wrap = document.querySelector('.md-sidebar--primary .md-sidebar__scrollwrap');
        const links = document.querySelectorAll('.docsfw-combined-toc a');
        const last = links[links.length - 1];
        const wrapRect = wrap.getBoundingClientRect();
        const lastRect = last ? last.getBoundingClientRect() : null;
        return {
          innerHeight: window.innerHeight,
          wrapBottom: wrapRect.bottom,
          wrapTop: wrapRect.top,
          gapWrap: window.innerHeight - wrapRect.bottom,
          lastBottom: lastRect ? lastRect.bottom : null,
          lastCount: links.length,
          inlineHeight: wrap.style.height,
        };
      });
    }

    function assertBottomInset(data, label) {
      assert.ok(data.lastCount > 0, label + ' toc ' + JSON.stringify(data));
      assert.ok(Math.abs(data.gapWrap - 12) <= 1.5, label + ' wrap gap ' + JSON.stringify(data));
      assert.ok(data.lastBottom <= data.innerHeight - 11, label + ' last item ' + JSON.stringify(data));
    }

    async function currentPageMetrics() {
      return page.evaluate(() => {
        const links = Array.from(document.querySelectorAll(
          '.md-sidebar--primary .md-nav__link--active[href]'
        ));
        const active = links.find(link => !link.closest('.docsfw-combined-toc'));
        let scrollContainer = active ? active.parentElement : null;
        while (scrollContainer) {
          const overflow = getComputedStyle(scrollContainer).overflowY;
          if ((overflow === 'auto' || overflow === 'scroll') &&
              scrollContainer.scrollHeight > scrollContainer.clientHeight + 1) break;
          scrollContainer = scrollContainer.parentElement;
        }
        if (!active || !scrollContainer) {
          return {found: !!active, hasScrollContainer: !!scrollContainer};
        }
        const activeRect = active.getBoundingClientRect();
        const containerRect = scrollContainer.getBoundingClientRect();
        return {
          found: true,
          hasScrollContainer: true,
          text: active.textContent.trim(),
          activeCenter: (activeRect.top + activeRect.bottom) / 2,
          containerCenter: (containerRect.top + containerRect.bottom) / 2,
          scrollTop: scrollContainer.scrollTop,
          pageScrollY: window.scrollY,
        };
      });
    }

    function assertCurrentPageCentered(data, label) {
      assert.ok(data.found, label + ' current page ' + JSON.stringify(data));
      assert.ok(data.hasScrollContainer, label + ' scroll container ' + JSON.stringify(data));
      assert.equal(data.text, 'Page 25', label + ' selected link ' + JSON.stringify(data));
      assert.ok(data.scrollTop > 0, label + ' scrollTop ' + JSON.stringify(data));
      assert.ok(Math.abs(data.activeCenter - data.containerCenter) <= 2,
        label + ' center ' + JSON.stringify(data));
      assert.equal(data.pageScrollY, 0, label + ' page scroll ' + JSON.stringify(data));
    }

    await page.setViewport({width: 1300, height: 900});
    await page.goto(url + 'section/page-25/', {waitUntil: 'domcontentloaded'});
    await openDrawer();
    assertCurrentPageCentered(await currentPageMetrics(), 'reload 1300');

    await page.setViewport({width: 1800, height: 900});
    await page.goto(url + 'section/page-25/', {waitUntil: 'domcontentloaded'});
    await page.setViewport({width: 1300, height: 900});
    await new Promise(resolve => setTimeout(resolve, 400));
    await openDrawer();
    assertCurrentPageCentered(await currentPageMetrics(), 'resize 1800 to 1300');

    await page.setViewport({width: 1100, height: 900});
    await page.goto(url + 'section/page-25/', {waitUntil: 'domcontentloaded'});
    await openDrawer();
    assertCurrentPageCentered(await currentPageMetrics(), 'reload 1100');

    await page.setViewport({width: 1800, height: 900});
    await page.goto(url, {waitUntil: 'domcontentloaded'});
    await page.waitForSelector('.md-sidebar--primary .md-sidebar__scrollwrap');
    await new Promise(resolve => setTimeout(resolve, 300));
    await page.setViewport({width: 1300, height: 900});
    await new Promise(resolve => setTimeout(resolve, 400));
    await openDrawerAndScrollEnd();
    assertBottomInset(await drawerEndMetrics(), 'resize 1800 to 1300');

    await page.setViewport({width: 1300, height: 900});
    await page.goto(url, {waitUntil: 'domcontentloaded'});
    await page.waitForSelector('.md-sidebar--primary .md-sidebar__scrollwrap');
    await new Promise(resolve => setTimeout(resolve, 300));
    await openDrawerAndScrollEnd();
    assertBottomInset(await drawerEndMetrics(), 'reload 1300');

    await page.setViewport({width: 1800, height: 900});
    await page.goto(url, {waitUntil: 'domcontentloaded'});
    await page.waitForSelector('.md-sidebar--primary .md-sidebar__scrollwrap');
    await new Promise(resolve => setTimeout(resolve, 300));
    await page.setViewport({width: 1100, height: 900});
    await new Promise(resolve => setTimeout(resolve, 400));
    await openDrawerAndScrollEnd();
    assertBottomInset(await drawerEndMetrics(), 'resize 1800 to 1100');

    console.log('PASS: MkDocs drawer centers current page and keeps 12px bottom inset');
  } finally {
    if (browser) await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
    fs.rmSync(temporary, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
