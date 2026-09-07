// 実行: node livedocs/tests/test_livedocs_nav_item_browser.js (docsfw ルートから)
// 約 1220px 未満のドロワー板見出しで、"<" アイコンは常に上位フォルダーへ戻り、
// フォルダー名はインデックス ページ (navigation.indexes) があるときだけ実リンクに
// なることを、theme/partials/nav-item.html の上書きに対して検証する。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const puppeteer = require(path.join(root, 'bin/node_modules/puppeteer'));
const {buildBrowserLaunchOptions} = require(path.join(root, 'bin/browser-launch-options'));
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-nav-item-'));
const python = process.env.PYTHON || path.join(root, 'livedocs/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const themeDir = path.join(root, 'livedocs', 'theme');

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {encoding: 'utf8', timeout: 60000, ...options});
  assert.equal(result.status, 0, result.stderr || String(result.error));
  return result.stdout;
}

async function openDrawer(page) {
  await page.waitForFunction(() => {
    const button = document.querySelector('label.md-header__button[for="__drawer"]');
    return button && getComputedStyle(button).display !== 'none';
  });
  await page.click('label.md-header__button[for="__drawer"]');
  await page.waitForSelector('.md-sidebar--primary');
  await new Promise(resolve => setTimeout(resolve, 200));
}

// title で始まるテキストを持つ、板 (li.md-nav__item--nested) を開く。
// index を持つ節は実リンク <a> とトグル用 label が兄弟で並び、
// index を持たない節はラベル自身がトグルを兼ねる。
function openSection(page, title) {
  return page.evaluate((sectionTitle) => {
    const items = Array.from(document.querySelectorAll('.md-sidebar--primary li.md-nav__item--nested'));
    for (const li of items) {
      const link = li.querySelector(':scope > .md-nav__container > a') ||
        li.querySelector(':scope > label.md-nav__link');
      if (link && link.textContent.trim().startsWith(sectionTitle)) {
        const toggle = li.querySelector(':scope > .md-nav__container > label[for]') ||
          li.querySelector(':scope > label.md-nav__link[for]');
        if (!toggle) { return 'no-toggle'; }
        toggle.click();
        return 'opened';
      }
    }
    return 'not-found';
  }, title);
}

// 開いた板の見出し (.md-nav__title) を調べ、戻るアイコンと索引リンクの
// 構造を報告する。索引が無ければ href は null になる。
function inspectPanelTitle(page, title) {
  return page.evaluate((sectionTitle) => {
    const items = Array.from(document.querySelectorAll('.md-sidebar--primary li.md-nav__item--nested'));
    for (const li of items) {
      const link = li.querySelector(':scope > .md-nav__container > a') ||
        li.querySelector(':scope > label.md-nav__link');
      if (link && link.textContent.trim().startsWith(sectionTitle)) {
        const nav = li.querySelector(':scope > nav.md-nav');
        if (!nav) { return {found: false}; }
        const panelTitle = nav.querySelector(':scope > .md-nav__title');
        const icon = panelTitle && panelTitle.querySelector(':scope > label.md-nav__icon');
        const anchor = panelTitle && panelTitle.querySelector(':scope > a');
        const checkbox = document.getElementById(icon ? icon.getAttribute('for') : '');
        return {
          found: true,
          hasIcon: !!icon,
          iconChecked: checkbox ? checkbox.checked : null,
          href: anchor ? anchor.getAttribute('href') : null,
          text: panelTitle ? panelTitle.textContent.trim() : null,
        };
      }
    }
    return {found: false};
  }, title);
}

// 開いた板の見出しの中で、アイコン (戻る) か索引リンク (フォルダー名) を押す。
function clickPanelTitle(page, title, target) {
  return page.evaluate((sectionTitle, which) => {
    const items = Array.from(document.querySelectorAll('.md-sidebar--primary li.md-nav__item--nested'));
    for (const li of items) {
      const link = li.querySelector(':scope > .md-nav__container > a') ||
        li.querySelector(':scope > label.md-nav__link');
      if (link && link.textContent.trim().startsWith(sectionTitle)) {
        const nav = li.querySelector(':scope > nav.md-nav');
        const panelTitle = nav && nav.querySelector(':scope > .md-nav__title');
        if (!panelTitle) { return 'no-title'; }
        const element = which === 'icon' ?
          panelTitle.querySelector(':scope > label.md-nav__icon') :
          panelTitle.querySelector(':scope > a');
        if (!element) { return 'no-target'; }
        element.click();
        return 'clicked';
      }
    }
    return 'not-found';
  }, title, target);
}

(async function () {
  let browser;
  let server;
  try {
    run(python, ['-', root, temporary], {input: String.raw`
import pathlib, sys
root, target = map(pathlib.Path, sys.argv[1:])
docs = target / 'docs'
(docs / 'guide').mkdir(parents=True)
(docs / 'other').mkdir(parents=True)
(docs / 'index.md').write_text('# Home\n', encoding='utf-8')
(docs / 'guide' / 'index.md').write_text('# Guide Index\n', encoding='utf-8')
(docs / 'guide' / 'page.md').write_text('# Guide Page\n', encoding='utf-8')
(docs / 'other' / 'page.md').write_text('# Other Page\n', encoding='utf-8')
(docs / 'other' / 'second.md').write_text('# Other Second\n', encoding='utf-8')
`});
    const themeDirYaml = JSON.stringify(themeDir.split(path.sep).join('/'));
    fs.writeFileSync(path.join(temporary, 'mkdocs.yml'), `site_name: Test
theme:
  name: material
  custom_dir: ${themeDirYaml}
  font: false
  features:
    - navigation.indexes
`);
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
    await page.setViewport({width: 1000, height: 900});

    // --- インデックス付きの節 (Guide): アイコンは戻る、フォルダー名は実リンク。
    await page.goto(url, {waitUntil: 'domcontentloaded'});
    await openDrawer(page);
    assert.equal(await openSection(page, 'Guide'), 'opened', 'Guide の板を開けなかった');
    await new Promise(resolve => setTimeout(resolve, 150));
    const guideInfo = await inspectPanelTitle(page, 'Guide');
    assert.ok(guideInfo.found, 'Guide の板見出しが見つからない');
    assert.ok(guideInfo.hasIcon, 'Guide の板見出しに戻るアイコンが無い');
    assert.ok(guideInfo.href && /guide\/?(index\.html)?$/.test(guideInfo.href),
      'Guide の板見出しがインデックス ページへのリンクになっていない: ' + guideInfo.href);

    // アイコンをクリック → 戻る (チェックボックスが外れる)。
    assert.equal(await clickPanelTitle(page, 'Guide', 'icon'), 'clicked');
    await new Promise(resolve => setTimeout(resolve, 150));
    const afterBack = await inspectPanelTitle(page, 'Guide');
    assert.equal(afterBack.iconChecked, false, 'アイコン クリックで上位フォルダーへ戻らなかった');

    // 再度開いて、今度はフォルダー名をクリック → インデックス ページへ実際に遷移する。
    assert.equal(await openSection(page, 'Guide'), 'opened');
    await new Promise(resolve => setTimeout(resolve, 150));
    await Promise.all([
      page.waitForNavigation({waitUntil: 'domcontentloaded'}),
      clickPanelTitle(page, 'Guide', 'link'),
    ]);
    assert.match(page.url(), /\/guide\/?$/, 'フォルダー名クリックでインデックス ページへ遷移しなかった: ' + page.url());
    const guideHeading = await page.$eval('h1', node => node.textContent.trim());
    assert.equal(guideHeading, 'Guide Index');

    // --- インデックス無しの節 (Other): アイコンは戻る、フォルダー名はリンクにならない。
    await page.goto(url, {waitUntil: 'domcontentloaded'});
    await openDrawer(page);
    assert.equal(await openSection(page, 'Other'), 'opened', 'Other の板を開けなかった');
    await new Promise(resolve => setTimeout(resolve, 150));
    const otherInfo = await inspectPanelTitle(page, 'Other');
    assert.ok(otherInfo.found, 'Other の板見出しが見つからない');
    assert.ok(otherInfo.hasIcon, 'Other の板見出しに戻るアイコンが無い');
    assert.equal(otherInfo.href, null, 'インデックス ページが無いのにフォルダー名がリンクになっている');

    const otherLinkClick = await clickPanelTitle(page, 'Other', 'link');
    assert.equal(otherLinkClick, 'no-target', 'インデックス ページが無いのにフォルダー名クリックで何か起きた');

    assert.equal(await clickPanelTitle(page, 'Other', 'icon'), 'clicked');
    await new Promise(resolve => setTimeout(resolve, 150));
    const otherAfterBack = await inspectPanelTitle(page, 'Other');
    assert.equal(otherAfterBack.iconChecked, false, 'Other でもアイコン クリックで上位フォルダーへ戻らなかった');

    console.log('PASS: drawer panel title splits back icon from index link (MkDocs)');
  } finally {
    if (browser) await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
    fs.rmSync(temporary, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
