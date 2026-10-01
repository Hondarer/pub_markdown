'use strict';

// 実行: node bin_test/test_page_libraries_browser.js (docsfw ルートから)。
// 局所 MkDocs サイトと Pandoc HTML で、必要時読み込みと実描画を検証する。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const resolved = JSON.parse(execFileSync(process.execPath,
  [path.join(root, 'bin_internal/resolve-node-components.js')], {encoding: 'utf8'}));
const puppeteer = require(resolved.paths.puppeteer);
const {buildBrowserLaunchOptions} = require('../bin_internal/browser-launch-options');
const python = process.env.PYTHON || path.join(root, 'livedocs/.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-page-libraries-'));
const heavy = /mermaid\.min\.js|docsfw-plantuml-loader\.js|tex-mml-chtml\.js/;

function generate() {
  execFileSync(python, ['-X', 'utf8', '-', root, temporary, JSON.stringify(resolved)], {encoding: 'utf8', input: String.raw`
import json, pathlib, sys, subprocess
root, target = map(pathlib.Path, sys.argv[1:3])
sys.path.insert(0, str(root / 'livedocs/bin'))
from vendor_assets import (vendor_own_assets, vendor_theme, vendor_header_icons,
    vendor_favicon_icons, generate_mkdocs_yml,
    vendor_plantuml, vendor_mermaid, node_child_env)
docs = target / 'src'
assets = docs / 'assets'
assets.mkdir(parents=True)
resolved = json.loads(sys.argv[3])
vendor_own_assets(str(assets))
vendor_plantuml(str(assets), resolved['paths']['plantumlCore'], env=node_child_env(resolved))
vendor_mermaid(str(assets), resolved['paths']['mermaidJs'])
vendor_header_icons(str(assets)); vendor_favicon_icons(str(assets))
vendor_theme(str(target))
fence = chr(96) * 3
mermaid = fence + 'mermaid\nflowchart LR\nA --> B\n' + fence
plantuml = fence + 'plantuml\n@startuml\nAlice -> Bob : Hello\n@enduml\n' + fence
pages = {'index': '# 本文\n\n図・数式なし。',
    'code': '# コード\n\n' + fence + 'text\nmermaid plantuml $x+y$\n' + fence,
    'mermaid': '# Mermaid\n\n' + mermaid + '\n\n' + mermaid,
    'plantuml': '# PlantUML\n\n' + plantuml + '\n\n' + plantuml,
    'mixed': '# 混在\n\n' + plantuml + '\n\n' + mermaid + '\n\n' + plantuml + '\n\n' + mermaid,
    'math': '# 数式\n\n$x^2+y^2=z^2$\n\n$$\n\\frac{1}{2}\n$$'}
for name, text in pages.items():
    (docs / (name + '.md')).write_text(text, encoding='utf-8')
generate_mkdocs_yml(str(target), False, site_name='表示性能の局所検証')
config = target / 'mkdocs.yml'
# ステージング・索引の運用 hook はこの局所 fixture の対象外。
config.write_text(config.read_text(encoding='utf-8').split('\nhooks:')[0], encoding='utf-8')
subprocess.run([sys.executable, '-X', 'utf8', '-m', 'mkdocs', 'build', '--strict', '-f', str(config)], check=True)
`});
  const site = path.join(temporary, 'site');
  for (const template of ['html-template.html', 'html-simple-template.html']) {
    const cleaned = fs.readFileSync(path.join(root, 'styles/html', template), 'utf8')
      .replace(/<script\b[^>]*src=['"]https?:[^>]*>\s*<\/script>/g, '')
      .replace(/<link\b[^>]*href=['"]https?:[^>]*>/g, '');
    const tempTemplate = path.join(temporary, template);
    fs.writeFileSync(tempTemplate, cleaned);
    for (const name of ['index', 'code', 'math']) {
      const output = path.join(site, template.replace('.html', '-' + name + '.html'));
      execFileSync('pandoc', [path.join(temporary, 'src', name + '.md'), '-s', '-t', 'html5',
        '-M', 'pagetitle=Test',
        '--template', tempTemplate, '--defaults', path.join(root, 'bin_internal/pandoc-defaults/math-mathjax.yaml'),
        '--lua-filter', path.join(root, 'bin_internal/pandoc-filters/html-browser.lua'), '-o', output]);
      const html = fs.readFileSync(output, 'utf8');
      assert.equal(html.includes('cdn.jsdelivr.net/npm/mathjax'), name === 'math', template + ' ' + name);
    }
  }
  return site;
}

async function diagramsSettled(page) {
  await page.waitForFunction(() => [...document.querySelectorAll('.docsfw-mermaid, .docsfw-plantuml')]
    .every(block => block.dataset.docsfwState === 'done'), {timeout: 60000});
}

(async function () {
  let browser, server;
  try {
    const site = generate();
    server = http.createServer((request, response) => {
      let pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      if (pathname.endsWith('/')) pathname += 'index.html';
      const file = path.resolve(site, '.' + pathname);
      if (!file.startsWith(site + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        response.writeHead(404); response.end(); return;
      }
      response.setHeader('Content-Type', ({'.html': 'text/html; charset=utf-8', '.js': 'text/javascript',
        '.css': 'text/css', '.svg': 'image/svg+xml'})[path.extname(file)] || 'application/octet-stream');
      response.end(fs.readFileSync(file));
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const url = 'http://127.0.0.1:' + server.address().port + '/';
    browser = await puppeteer.launch(buildBrowserLaunchOptions({headless: true,
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH, args: ['--no-sandbox']}));
    const errors = [];
    for (const [name, expected] of (process.argv.includes('--math-only') ? [] : [['', []], ['code/', []], ['mermaid/', ['mermaid.min.js']],
      ['plantuml/', ['docsfw-plantuml-loader.js']], ['mixed/', ['docsfw-plantuml-loader.js', 'mermaid.min.js']]])) {
      const page = await browser.newPage();
      page.on('pageerror', error => errors.push(error.message));
      const requests = [];
      page.on('request', request => { if (heavy.test(request.url())) requests.push(new URL(request.url()).pathname.split('/').pop()); });
      await page.goto(url + name);
      if (expected.length) {
        await page.waitForSelector('.docsfw-mermaid, .docsfw-plantuml', {timeout: 10000})
          .catch(async error => { console.error(await page.$eval('body', node => node.innerText)); throw error; });
      }
      await diagramsSettled(page);
      assert.deepEqual(requests, expected, name + ': 必要なライブラリを 1 回だけ読む');
      if (expected.length) {
        const count = await page.$$eval('.docsfw-diagram-toolbar', nodes => nodes.length);
        assert.equal(count, name === 'mixed/' ? 4 : 2);
        await page.evaluate(() => document.body.setAttribute('data-md-color-scheme', 'slate'));
        await page.waitForFunction(() => [...document.querySelectorAll('.docsfw-mermaid, .docsfw-plantuml')]
          .every(block => block.dataset.docsfwTheme === 'dark'), {timeout: 60000});
        assert.deepEqual(requests, expected, '配色変更で再取得しない');
      }
      console.log('MkDocs ' + (name || 'index/') + ': ' + (requests.join(', ') || '大きなライブラリの要求 0 回'));
      await page.close();
    }
    if (!process.argv.includes('--math-only')) {
      const failed = await browser.newPage();
      const requests = [];
      failed.on('pageerror', error => errors.push(error.message));
      await failed.setRequestInterception(true);
      failed.on('request', request => {
        if (/mermaid\.min\.js/.test(request.url())) {
          requests.push(request.url());
          request.respond({status: 404, body: 'missing'});
        } else request.continue();
      });
      await failed.goto(url + 'mixed/');
      await diagramsSettled(failed);
      assert.equal(requests.length, 1, '失敗したライブラリを図ごとに再取得しない');
      assert.equal(await failed.$$eval('.docsfw-mermaid.docsfw-diagram--error pre', nodes => nodes.length), 2);
      assert.equal(await failed.$$eval('.docsfw-plantuml > svg', nodes => nodes.length), 2);
      console.log('MkDocs 読み込み失敗: 元ソースを残し、他の図の描画を継続');
      await failed.close();
    }
    // 初回が通常ページでも、Material の通知後に初めて図を読み込める。
    if (!process.argv.includes('--math-only')) {
      const page = await browser.newPage();
      const requests = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => { if (heavy.test(request.url())) requests.push(request.url()); });
      await page.goto(url);
      await page.evaluate(() => {
        window.pageChanged = [];
        window.document$ = {subscribe(callback) { window.pageChanged.push(callback); }};
      });
      await page.addScriptTag({path: path.join(root, 'styles/browser/docsfw-diagrams.js')});
      await page.addScriptTag({path: path.join(root, 'livedocs/assets/docsfw-mathjax.js')});
      await page.evaluate(() => {
        document.querySelector('article').innerHTML = '<div class="docsfw-mermaid">flowchart LR\nA --> B</div>';
        window.pageChanged.forEach(callback => callback());
      });
      await diagramsSettled(page);
      assert.equal(requests.length, 1);
      await page.evaluate(() => {
        document.querySelector('article').innerHTML = '<div class="docsfw-plantuml">@startuml\nA -> B\n@enduml</div>';
        window.pageChanged.forEach(callback => callback());
      });
      await diagramsSettled(page);
      assert.equal(requests.length, 2);
      console.log('MkDocs ページ差し替え: 後から必要になる図も正常に描画');
      await page.close();
    }

    // 配布物の指定がない環境では、読み込みと組版の制御を API fixture で検証する。
    {
      const math = await browser.newPage();
      const mathRequests = [];
      const mathLogs = [];
      math.on('console', message => { if (message.type() === 'error') mathLogs.push(message.text()); });
      await math.setRequestInterception(true);
      math.on('request', request => {
        if (/tex-mml-chtml\.js/.test(request.url())) {
          mathRequests.push(request.url());
          const stub = `Object.assign(window.MathJax, {
            startup: {promise: Promise.resolve(), output: {clearCache() {}}},
            texReset() {}, typesetClear() {},
            async typesetPromise(nodes) { for (const node of nodes) {
              node.innerHTML = '<mjx-container>数式</mjx-container>';
            } }
          });`;
          request.respond({status: 200, contentType: 'text/javascript',
            body: process.env.DOCSFW_TEST_MATHJAX_SCRIPT ? fs.readFileSync(process.env.DOCSFW_TEST_MATHJAX_SCRIPT) : stub});
        } else request.continue();
      });
      math.on('pageerror', error => errors.push(error.message));
      await math.goto(url + 'math/');
      await math.waitForFunction(() => document.querySelectorAll('mjx-container').length === 2, {timeout: 60000})
        .catch(async error => { console.error(mathLogs, await math.$eval('article', node => node.innerHTML)); throw error; });
      assert.equal(mathRequests.length, 1);
      assert.equal(await math.$$eval('mjx-merror', nodes => nodes.length), 0);
      assert.equal(await math.$$eval('mjx-container mjx-container', nodes => nodes.length), 0, '重複した組版がない');
      await math.goto(url);
      const before = mathRequests.length;
      await math.evaluate(() => {
        window.mathChanged = [];
        window.document$ = {subscribe(callback) { window.mathChanged.push(callback); }};
      });
      await math.addScriptTag({path: path.join(root, 'livedocs/assets/docsfw-mathjax.js')});
      await math.evaluate(() => {
        document.querySelector('article').innerHTML = String.raw`<span class="arithmatex">\(x+1\)</span><div class="arithmatex">\[x+2\]</div>`;
        for (let i = 0; i < 3; i++) window.mathChanged.forEach(callback => callback());
      });
      await math.waitForFunction(() => document.querySelectorAll('mjx-container').length === 2, {timeout: 60000});
      assert.equal(mathRequests.length, before + 1);
      await math.evaluate(() => {
        document.querySelector('article').innerHTML = String.raw`<span class="arithmatex">\(y+1\)</span>`;
        window.mathChanged.forEach(callback => callback());
      });
      await math.waitForFunction(() => document.querySelectorAll('mjx-container').length === 1 &&
        !document.querySelector('mjx-container mjx-container'), {timeout: 60000});
      assert.equal(mathRequests.length, before + 1, 'ページ差し替えで MathJax を再取得しない');
      await math.evaluate(() => {
        document.querySelector('article').innerHTML = '<p>数式のないページ</p>';
        window.mathChanged.forEach(callback => callback());
      });
      await math.waitForFunction(() => !window.MathJax.startup.document ||
        Array.from(window.MathJax.startup.document.math).length === 0);
      assert.deepEqual(mathLogs, []);
      console.log('MkDocs MathJax: ' + (process.env.DOCSFW_TEST_MATHJAX_SCRIPT ? '実エンジン' : 'API fixture') +
        'で数式、重複通知、ページ差し替え、不要な組版状態の解放を確認');
      await math.close();
    }
    assert.deepEqual(errors, []);
    console.log('Pandoc 標準・簡易テンプレート: 数式ページだけ MathJax を含む');
  } finally {
    if (browser) await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
    assert(path.resolve(temporary).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(temporary, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
