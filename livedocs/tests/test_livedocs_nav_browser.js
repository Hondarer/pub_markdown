// 実行: node livedocs/tests/test_livedocs_nav_browser.js (docsfw ルートから)
// ドロワーを開いたときに現在文書が中央へ表示されることと、3 ペインから
// 連続一覧ドロワーの幅 (1300px) へ縮めたあとも下端 12px が残ることを検証する。
// 3 列表示では、左右ナビのスクロール終端に Pandoc と同じ 12px が残ることを
// 検証する。
// ドロワー内のページ内目次は、Material の 960px 境界をまたいでも文字の
// 開始位置が動かず、各階層が Pandoc と同じ位置になることも検証する。
// 板 (スライド パネル) になる幅では、どの階層の板を見ていてもページ内目次が
// その板の一覧の続きに並ぶことと、上位の板へ戻してから開き直したドロワーが
// 横へずれないことも検証する。
// 見出しのアンカーへ移動したとき、目次の現在項目がその見出しになることも
// 検証する。
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
  return Array.from({length: 40}, (_, index) =>
    '## Heading ' + (index + 1) + '\n\n本文です。\n' +
    (index === 0 ? '\n### Nested heading\n\n子見出しです。\n' : '')
  ).join('\n');
}

(async function () {
  let browser;
  let server;
  try {
    run(python, ['-', root, temporary], {input: String.raw`
import pathlib, sys
root, target = map(pathlib.Path, sys.argv[1:])
sys.path.insert(0, str(root / 'livedocs/bin'))
from vendor_assets import vendor_own_assets, vendor_theme
docs = target / 'docs'
docs.mkdir()
md = ${JSON.stringify('# Drawer margin\n\n' + headings())}
(docs / 'index.md').write_text(md, encoding='utf-8')
section = docs / 'section'
section.mkdir()
(section / 'index.md').write_text(
    '# Section\n\n## Section overview\n\n本文です。\n\n## Section details\n\n本文です。\n',
    encoding='utf-8')
for index in range(50):
    body = f'# Page {index:02d}\n\n本文です。\n'
    if index == 25:
        body += '\n## Current page heading\n\nページ内目次の確認です。\n'
    (section / f'page-{index:02d}.md').write_text(
        body, encoding='utf-8'
    )
vendor_own_assets(str(docs / 'assets'))
vendor_theme(str(target))
(target / 'mkdocs.yml').write_text("""site_name: Test
theme:
  name: material
  custom_dir: theme
  font: false
  palette:
    scheme: default
  features:
    - navigation.indexes
markdown_extensions:
  - toc:
      permalink: true
      toc_depth: 3
extra_css:
  - assets/docsfw-livedocs.css
  - assets/docsfw-pandoc-style.css
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
        const rootList = document.querySelector('.md-nav--primary > .md-nav__list');
        const toc = document.querySelector('.docsfw-combined-toc');
        const links = document.querySelectorAll('.docsfw-combined-toc a');
        const last = links[links.length - 1];
        const wrapRect = wrap.getBoundingClientRect();
        const rootListRect = rootList ? rootList.getBoundingClientRect() : null;
        const lastRect = last ? last.getBoundingClientRect() : null;
        return {
          innerHeight: window.innerHeight,
          wrapBottom: wrapRect.bottom,
          wrapTop: wrapRect.top,
          gapWrap: window.innerHeight - wrapRect.bottom,
          rootListBottom: rootListRect ? rootListRect.bottom : null,
          gapRootList: rootListRect ? window.innerHeight - rootListRect.bottom : null,
          lastBottom: lastRect ? lastRect.bottom : null,
          contentBottomGap: lastRect ? window.innerHeight - lastRect.bottom : null,
          lastCount: links.length,
          inlineHeight: wrap.style.height,
          rootListPaddingBottom: rootList ? getComputedStyle(rootList).paddingBottom : null,
          tocMarginTop: toc ? getComputedStyle(toc).marginTop : null,
        };
      });
    }

    function assertDrawerEnd(data, label, checksContinuousList = false) {
      assert.ok(data.lastCount > 0, label + ' toc ' + JSON.stringify(data));
      assert.ok(Math.abs(data.gapWrap) <= 1.5,
        label + ' wrap gap ' + JSON.stringify(data));
      if (checksContinuousList) {
        assert.ok(Math.abs(data.gapRootList) <= 1.5,
          label + ' list gap ' + JSON.stringify(data));
      }
      assert.ok(data.lastBottom <= data.innerHeight + 1,
        label + ' last item ' + JSON.stringify(data));
      assert.equal(data.tocMarginTop, checksContinuousList ? '12px' : '0px',
        label + ' toc margin ' + JSON.stringify(data));
    }

    function assertContinuousListBottomPadding(data, label) {
      assert.equal(data.rootListPaddingBottom, '12px', label + ' list padding ' + JSON.stringify(data));
      assert.ok(Math.abs(data.contentBottomGap - 12) <= 1.5,
        label + ' content gap ' + JSON.stringify(data));
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

    async function bodyStartMetrics(targetPage) {
      return targetPage.evaluate(() => {
        const header = document.querySelector('.md-header').getBoundingClientRect();
        const headerInner = document.querySelector('.md-header__inner').getBoundingClientRect();
        const drawerIcon = document.querySelector('.md-header__button[for="__drawer"] svg')
          .getBoundingClientRect();
        const headerTitle = document.querySelector('.md-header__title').getBoundingClientRect();
        const mainNode = document.querySelector('.md-main__inner');
        const innerNode = document.querySelector('.md-content__inner');
        const main = mainNode.getBoundingClientRect();
        const content = innerNode.getBoundingClientRect();
        return {
          headerBottom: header.bottom,
          headerInnerLeft: headerInner.left,
          drawerIconLeft: drawerIcon.left,
          headerTitleLeft: headerTitle.left,
          mainTop: main.top,
          mainMarginTop: getComputedStyle(mainNode).marginTop,
          contentPaddingTop: getComputedStyle(innerNode).paddingTop,
          contentLeft: content.left,
          contentRight: content.right,
        };
      });
    }

    const layoutPage = await browser.newPage();
    for (const width of [360, 767, 768, 900, 922, 929, 930, 1100, 1219, 1220, 1399, 1400, 1700]) {
      await layoutPage.setViewport({width, height: 900});
      await layoutPage.goto(url, {waitUntil: 'domcontentloaded'});
      const metrics = await bodyStartMetrics(layoutPage);
      assert.equal(metrics.mainMarginTop, '0px', width + 'px main margin ' + JSON.stringify(metrics));
      assert.equal(metrics.contentPaddingTop, '0px', width + 'px content padding ' + JSON.stringify(metrics));
      assert.ok(Math.abs(metrics.mainTop - metrics.headerBottom) <= 1,
        width + 'px content start ' + JSON.stringify(metrics));
      if (width <= 767) {
        assert.ok(Math.abs(metrics.contentLeft - 20) <= 1,
          width + 'px content left ' + JSON.stringify(metrics));
        assert.ok(Math.abs(metrics.contentRight - (width - 20)) <= 1,
          width + 'px content right ' + JSON.stringify(metrics));
      } else if (width <= 929) {
        assert.ok(Math.abs(metrics.contentLeft - 30) <= 1,
          width + 'px content left ' + JSON.stringify(metrics));
        assert.ok(Math.abs(metrics.contentRight - (width - 30)) <= 1,
          width + 'px content right ' + JSON.stringify(metrics));
        const headerLeft = Math.max(0, (width - 902) / 2);
        assert.ok(Math.abs(metrics.headerInnerLeft - headerLeft) <= 1,
          width + 'px header left ' + JSON.stringify(metrics));
        assert.ok(Math.abs(metrics.drawerIconLeft - (headerLeft + 16)) <= 1,
          width + 'px drawer icon left ' + JSON.stringify(metrics));
        assert.ok(Math.abs(metrics.headerTitleLeft - (headerLeft + 72)) <= 1,
          width + 'px header title left ' + JSON.stringify(metrics));
      }
    }
    await layoutPage.close();

    async function drawerTocTextPositions(targetPage) {
      return targetPage.evaluate(() => {
        const drawer = document.querySelector('.md-sidebar--primary').getBoundingClientRect();
        const links = Array.from(document.querySelectorAll('.docsfw-combined-toc a.md-nav__link'));
        const position = text => {
          const link = links.find(node => node.textContent.trim() === text);
          const range = document.createRange();
          range.selectNodeContents(link);
          return range.getBoundingClientRect().left - drawer.left;
        };
        return {topLevel: position('Heading 1'), nested: position('Nested heading')};
      });
    }

    async function drawerTocBoundaryMetrics(targetPage) {
      return targetPage.evaluate(() => {
        const toc = document.querySelector('.docsfw-combined-toc');
        const previous = toc.previousElementSibling;
        const lastLink = previous.querySelector(
          ':scope > a.md-nav__link, :scope > .md-nav__container > a.md-nav__link'
        );
        const title = toc.querySelector('.md-nav__title');
        const tocStyle = getComputedStyle(toc);
        return {
          marginTop: parseFloat(tocStyle.marginTop),
          gap: toc.getBoundingClientRect().top - lastLink.getBoundingClientRect().bottom,
          titleGap: title.getBoundingClientRect().top - toc.getBoundingClientRect().top -
            parseFloat(tocStyle.borderTopWidth),
        };
      });
    }

    const tocPositionPage = await browser.newPage();
    for (const width of [959, 960, 1219, 1220, 1399]) {
      await tocPositionPage.setViewport({width, height: 900});
      await tocPositionPage.goto(url, {waitUntil: 'domcontentloaded'});
      await tocPositionPage.click('label.md-header__button[for="__drawer"]');
      await tocPositionPage.waitForSelector('.docsfw-combined-toc');
      const positions = await drawerTocTextPositions(tocPositionPage);
      const expected = width < 1220
        ? {topLevel: 16, nested: 32}
        : {topLevel: 24, nested: 40};
      assert.deepEqual(positions, expected,
        width + 'px drawer toc positions ' + JSON.stringify(positions));
      const boundary = await drawerTocBoundaryMetrics(tocPositionPage);
      const expectedMargin = width < 1220 ? 0 : 12;
      assert.ok(Math.abs(boundary.marginTop - expectedMargin) <= 0.01,
        width + 'px drawer toc margin ' + JSON.stringify(boundary));
      if (width >= 1220) {
        assert.ok(Math.abs(boundary.gap - 12) <= 1,
          width + 'px drawer toc boundary gap ' + JSON.stringify(boundary));
        assert.ok(Math.abs(boundary.titleGap - 12) <= 1,
          width + 'px drawer toc title gap ' + JSON.stringify(boundary));
      }
    }
    await tocPositionPage.close();

    async function wideSidebarEndMetrics(targetPage, sidebarSelector, lastLinkText) {
      return targetPage.evaluate(async ({sidebarSelector, lastLinkText}) => {
        const wrap = document.querySelector(sidebarSelector + ' .md-sidebar__scrollwrap');
        const inner = document.querySelector(sidebarSelector + ' .md-sidebar__inner');
        const link = Array.from(inner.querySelectorAll('a.md-nav__link'))
          .find(node => node.textContent.trim() === lastLinkText);
        const pageScrollBefore = window.scrollY;
        wrap.scrollTop = wrap.scrollHeight;
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const wrapRect = wrap.getBoundingClientRect();
        const linkRect = link.getBoundingClientRect();
        return {
          found: !!link,
          paddingBottom: getComputedStyle(inner).paddingBottom,
          bottomGap: wrapRect.bottom - linkRect.bottom,
          pageScrollBefore,
          pageScrollAfter: window.scrollY,
        };
      }, {sidebarSelector, lastLinkText});
    }

    function assertWideSidebarEnd(data, label) {
      assert.ok(data.found, label + ' last link ' + JSON.stringify(data));
      assert.equal(data.paddingBottom, '12px', label + ' padding ' + JSON.stringify(data));
      assert.ok(Math.abs(data.bottomGap - 12.5) <= 1.5,
        label + ' bottom gap ' + JSON.stringify(data));
      assert.equal(data.pageScrollAfter, data.pageScrollBefore,
        label + ' page scroll ' + JSON.stringify(data));
    }

    const widePage = await browser.newPage();
    for (const width of [1400, 1700]) {
      await widePage.setViewport({width, height: 900});
      await widePage.goto(url, {waitUntil: 'domcontentloaded'});
      await widePage.waitForSelector('.md-sidebar--secondary .md-sidebar__scrollwrap');
      await widePage.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight / 2));
      assertWideSidebarEnd(
        await wideSidebarEndMetrics(widePage, '.md-sidebar--secondary', 'Heading 40'),
        width + 'px right sidebar'
      );

      await widePage.goto(url + 'section/page-25/', {waitUntil: 'domcontentloaded'});
      await widePage.waitForSelector('.md-sidebar--primary .md-sidebar__scrollwrap');
      assertWideSidebarEnd(
        await wideSidebarEndMetrics(widePage, '.md-sidebar--primary', 'Page 49'),
        width + 'px left sidebar'
      );
    }
    await widePage.close();

    const narrowRootPage = await browser.newPage();
    await narrowRootPage.setViewport({width: 520, height: 900});
    await narrowRootPage.goto(url, {waitUntil: 'domcontentloaded'});
    const narrowRootMetrics = await narrowRootPage.evaluate(() => {
      const root = document.querySelector('.md-nav--primary');
      const title = root.querySelector(':scope > .md-nav__title');
      const logoNode = root.querySelector(':scope > .md-nav__title .md-logo svg');
      const logo = logoNode.getBoundingClientRect();
      const item = root.querySelector(':scope > .md-nav__list > .md-nav__item--nested');
      const sidebar = document.querySelector('.md-sidebar--primary');
      const row = item.querySelector(':scope > .md-nav__container').getBoundingClientRect();
      const icon = item.querySelector(':scope > .md-nav__container .md-nav__icon');
      const iconRect = icon.getBoundingClientRect();
      const iconLabel = icon.parentElement.getBoundingClientRect();
      const rowStyle = getComputedStyle(item.querySelector(':scope > .md-nav__container'));
      return {
        logoWidth: logo.width,
        logoHeight: logo.height,
        logoFill: getComputedStyle(logoNode).fill,
        titleBackground: getComputedStyle(title).backgroundColor,
        titleColor: getComputedStyle(title).color,
        itemHeight: item.getBoundingClientRect().height,
        rowHeight: row.height,
        rowMinHeight: rowStyle.minHeight,
        rowPadding: rowStyle.padding,
        iconColor: getComputedStyle(icon).color,
        iconWidth: iconRect.width,
        iconHeight: iconRect.height,
        iconLabelHeight: iconLabel.height,
        sidebarBorderTop: getComputedStyle(sidebar).borderTopWidth,
        sidebarBorderRight: getComputedStyle(sidebar).borderRightWidth,
      };
    });
    assert.deepEqual(narrowRootMetrics, {
      logoWidth: 24,
      logoHeight: 24,
      logoFill: 'rgb(119, 119, 119)',
      titleBackground: 'rgb(234, 234, 234)',
      titleColor: 'rgb(119, 119, 119)',
      itemHeight: 49,
      rowHeight: 48,
      rowMinHeight: '48px',
      rowPadding: '12px 16px',
      iconColor: 'rgba(0, 0, 0, 0.54)',
      iconWidth: 18,
      iconHeight: 18,
      iconLabelHeight: 18,
      sidebarBorderTop: '1px',
      sidebarBorderRight: '1px',
    });
    await narrowRootPage.evaluate(() => {
      document.documentElement.setAttribute('data-md-color-scheme', 'slate');
      document.body.setAttribute('data-md-color-scheme', 'slate');
    });
    assert.deepEqual(await narrowRootPage.$eval('.md-nav--primary > .md-nav__title', title => {
      const logo = title.querySelector('.md-logo svg');
      return {
        titleColor: getComputedStyle(title).color,
        logoFill: getComputedStyle(logo).fill,
      };
    }), {
      titleColor: 'rgba(255, 255, 255, 0.87)',
      logoFill: 'rgba(255, 255, 255, 0.87)',
    });
    assert.equal(
      await narrowRootPage.$eval(
        '.md-nav--primary > .md-nav__list > .docsfw-combined-toc',
        node => getComputedStyle(node).display !== 'none'
      ),
      true
    );
    await narrowRootPage.close();

    async function narrowTocMetrics() {
      return page.evaluate(() => {
        const toc = document.querySelector('.docsfw-combined-toc');
        const title = toc && toc.querySelector('.md-nav__title');
        return {
          marginTop: toc ? getComputedStyle(toc).marginTop : null,
          titlePadding: title ? getComputedStyle(title).padding : null,
        };
      });
    }

    async function narrowPanelCursorMetrics() {
      return page.evaluate(() => {
        const panel = document.querySelector('.md-nav--primary .md-nav[data-md-level="1"]');
        const title = panel && panel.querySelector(':scope > .md-nav__title');
        const icon = title && title.querySelector(':scope > .md-nav__icon');
        return {
          titleCursor: title ? getComputedStyle(title).cursor : null,
          iconCursor: icon ? getComputedStyle(icon).cursor : null,
          linkDecoration: title && title.querySelector(':scope > a')
            ? getComputedStyle(title.querySelector(':scope > a')).textDecorationLine : null,
        };
      });
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
    assert.deepEqual(await narrowTocMetrics(), {
      marginTop: '0px', titlePadding: '12px 16px',
    });
    await page.hover('.md-nav--primary .md-nav[data-md-level="1"] > .md-nav__title > a');
    assert.deepEqual(await narrowPanelCursorMetrics(), {
      titleCursor: 'default', iconCursor: 'pointer', linkDecoration: 'none',
    });

    /* 板になる幅では、表示中の板の一覧の続きにページ内目次が並ぶ。
       navigation.indexes の索引ページは、現在ページのリンクが 1 つ上の一覧に
       あるまま、その節自身の板が開いた状態で始まる。板を戻っても目次が
       表示中の板へ付いてくることを、初期表示と根の板の双方で確認する。 */
    await page.evaluateOnNewDocument(() => {
      window.__docsfwVisiblePanel = function () {
        var nav = document.querySelector('.md-sidebar--primary nav.md-nav--primary');
        for (;;) {
          var list = nav.querySelector(':scope > .md-nav__list');
          if (!list) return nav;
          var child = null;
          for (var i = 0; i < list.children.length; i++) {
            var toggle = list.children[i].querySelector(':scope > input.md-nav__toggle');
            var panel = list.children[i].querySelector(':scope > nav.md-nav');
            if (toggle && panel && toggle.checked && toggle.id !== '__toc') child = panel;
          }
          if (!child) return nav;
          nav = child;
        }
      };
    });

    async function panelTocPlacement() {
      return page.evaluate(() => {
        const panel = window.__docsfwVisiblePanel();
        const list = panel.querySelector(':scope > .md-nav__list');
        const toc = document.querySelector('.docsfw-combined-toc');
        const links = toc ? toc.querySelectorAll('a[href^="#"]') : [];
        const rect = links.length ? links[0].getBoundingClientRect() : null;
        const bounds = panel.getBoundingClientRect();
        const title = panel.querySelector(':scope > .md-nav__title');
        return {
          panelTitle: title ? title.textContent.trim() : 'root',
          inVisiblePanel: !!toc && toc.parentElement === list,
          linkCount: links.length,
          firstLinkInPanel: !!rect && rect.width > 0 &&
            rect.left >= bounds.left - 1 && rect.right <= bounds.right + 1,
        };
      });
    }

    async function goBackOnePanel() {
      await page.evaluate(() => {
        const panel = window.__docsfwVisiblePanel();
        const back = panel.querySelector(':scope > .md-nav__title > label.md-nav__icon');
        if (back) back.click();
      });
      await new Promise(resolve => setTimeout(resolve, 200));
    }

    function assertTocFollowsPanel(data, label) {
      assert.ok(data.inVisiblePanel, label + ' toc panel ' + JSON.stringify(data));
      assert.ok(data.linkCount > 0, label + ' toc links ' + JSON.stringify(data));
      assert.ok(data.firstLinkInPanel, label + ' toc position ' + JSON.stringify(data));
    }

    await page.setViewport({width: 1100, height: 900});
    await page.goto(url + 'section/', {waitUntil: 'domcontentloaded'});
    await openDrawer();
    const sectionPanelToc = await panelTocPlacement();
    assert.equal(sectionPanelToc.panelTitle, 'Section', 'index panel ' +
      JSON.stringify(sectionPanelToc));
    assertTocFollowsPanel(sectionPanelToc, 'index panel');
    await goBackOnePanel();
    const rootPanelToc = await panelTocPlacement();
    assert.equal(rootPanelToc.panelTitle, 'Test', 'root panel ' + JSON.stringify(rootPanelToc));
    assertTocFollowsPanel(rootPanelToc, 'root panel');

    /* 上位の板へ戻してからドロワーを閉じ、開き直しても中身が横へずれない。
       表示していない板は translateX で右へ退避しているため、そこにある
       現在ページの行へスクロールすると .md-sidebar__scrollwrap が横へ動き、
       overflow-x: hidden で戻す手段が無くなる。 */
    await page.setViewport({width: 1100, height: 900});
    await page.goto(url + 'section/page-25/', {waitUntil: 'domcontentloaded'});
    await openDrawer();
    await goBackOnePanel();
    await page.click('label.md-header__button[for="__drawer"]');
    await new Promise(resolve => setTimeout(resolve, 300));
    await openDrawer();
    const reopened = await page.evaluate(() => {
      const sidebar = document.querySelector('.md-sidebar--primary');
      const wrap = sidebar.querySelector('.md-sidebar__scrollwrap');
      const primary = sidebar.querySelector('nav.md-nav--primary');
      return {
        scrollLeft: Math.round(wrap.scrollLeft),
        offset: Math.round(
          primary.getBoundingClientRect().left - sidebar.getBoundingClientRect().left),
      };
    });
    assert.deepEqual(reopened, {scrollLeft: 0, offset: 0},
      'reopened drawer ' + JSON.stringify(reopened));

    /* 見出しのアンカーへ移動したとき、目次の現在項目がその見出しになる。
       Material は見出しの上端が判定線より上にあるかどうかで現在項目を決める。
       判定線が着地位置より上にあると、1 つ前の見出しが現在項目のまま残る。 */
    async function anchoredTocMetrics() {
      return page.evaluate(() => {
        const toc = document.querySelector('.docsfw-combined-toc') ||
          document.querySelector('.md-sidebar--secondary nav.md-nav--secondary');
        const target = document.getElementById('heading-20');
        const header = document.querySelector('.md-header').getBoundingClientRect();
        return {
          active: Array.from(toc.querySelectorAll('a.md-nav__link--active'))
            .map(node => node.textContent.trim()),
          targetTop: Math.round(target.getBoundingClientRect().top),
          headerBottom: Math.round(header.bottom),
        };
      });
    }

    for (const width of [1100, 1500]) {
      await page.setViewport({width, height: 900});
      await page.goto(url, {waitUntil: 'domcontentloaded'});
      await page.waitForSelector('.md-sidebar--primary');
      await page.goto(url + '#heading-20', {waitUntil: 'domcontentloaded'});
      await new Promise(resolve => setTimeout(resolve, 600));
      const anchored = await anchoredTocMetrics();
      assert.deepEqual(anchored.active, ['Heading 20'],
        width + 'px anchor active ' + JSON.stringify(anchored));
      assert.ok(anchored.targetTop > anchored.headerBottom,
        width + 'px anchor landing ' + JSON.stringify(anchored));
    }

    await page.setViewport({width: 1800, height: 900});
    await page.goto(url, {waitUntil: 'domcontentloaded'});
    await page.waitForSelector('.md-sidebar--primary .md-sidebar__scrollwrap');
    await new Promise(resolve => setTimeout(resolve, 300));
    await page.setViewport({width: 1300, height: 900});
    await new Promise(resolve => setTimeout(resolve, 400));
    await openDrawerAndScrollEnd();
    const resizedEnd = await drawerEndMetrics();
    assertDrawerEnd(resizedEnd, 'resize 1800 to 1300', true);
    assertContinuousListBottomPadding(resizedEnd, 'resize 1800 to 1300');

    await page.setViewport({width: 1300, height: 900});
    await page.goto(url, {waitUntil: 'domcontentloaded'});
    await page.waitForSelector('.md-sidebar--primary .md-sidebar__scrollwrap');
    await new Promise(resolve => setTimeout(resolve, 300));
    await openDrawerAndScrollEnd();
    const reloadedEnd = await drawerEndMetrics();
    assertDrawerEnd(reloadedEnd, 'reload 1300', true);
    assertContinuousListBottomPadding(reloadedEnd, 'reload 1300');

    await page.setViewport({width: 1800, height: 900});
    await page.goto(url, {waitUntil: 'domcontentloaded'});
    await page.waitForSelector('.md-sidebar--primary .md-sidebar__scrollwrap');
    await new Promise(resolve => setTimeout(resolve, 300));
    await page.setViewport({width: 1100, height: 900});
    await new Promise(resolve => setTimeout(resolve, 400));
    await openDrawerAndScrollEnd();
    assertDrawerEnd(await drawerEndMetrics(), 'resize 1800 to 1100');

    console.log('PASS: MkDocs wide sidebars keep a 12px bottom gap; drawer toc keeps ' +
      'Pandoc text positions across breakpoints, centers the current page, keeps a 12px ' +
      'content bottom gap and symmetric 12px medium toc spacing, merges the page toc into ' +
      'every panel, extends drawer ' +
      'scrollbars to the viewport bottom, reopens without shifting and marks the ' +
      'anchored heading as current');
  } finally {
    if (browser) await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
    fs.rmSync(temporary, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
