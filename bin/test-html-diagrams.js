'use strict';

// 局所生成した HTML を Edge / Chrome で開き、実エンジンと再描画競合を検証する。
const assert = require('assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const { pathToFileURL } = require('url');
const { execFileSync } = require('child_process');
const puppeteer = require('puppeteer');
const { buildBrowserAssets } = require('./build-browser-assets');
const { buildBrowserLaunchOptions } = require('./browser-launch-options');
const root = path.resolve(__dirname, '..');
const output = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-diagrams-'));
const assets = path.join(output, 'assets');
const source = `---
title: 図とテーマの検証
lang: ja
---

# テーマの検証

[リンク](#テスト) と \`inline code\`、==ハイライト==。

| 名前 | 値 |
| --- | --- |
| 表 | 123 |

> 引用です。

> [!NOTE]
> 注意書きです。

\`\`\`c
int main(void) {
  // comment
  const char *text = "Hello";
  int result = 0;
  result += 1;
  return result;
}
\`\`\`

\`\`\`mermaid
flowchart LR
  A[開始] --> B[完了]
\`\`\`
CodeBlock: Mermaid の図 {#fig:flow}

\`\`\`plantuml
@startuml
Alice -> Bob : Hello
@enduml
\`\`\`
CodeBlock: シーケンスの図 {#fig:sequence}

\`\`\`plantuml
@startuml
class A
class B
A --> B
@enduml
\`\`\`

\`\`\`plantuml
@startuml
Alice -> Bob : <&person> <:smile:>
@enduml
\`\`\`

\`\`\`plantuml
@startsalt
{
  [OK]
}
@endsalt
\`\`\`

\`\`\`mermaid
not a diagram <script>alert("bad")</script>
\`\`\`

\`\`\`mermaid
sequenceDiagram
  Alice->>Bob: after error
\`\`\`
`;

function generate() {
  const resolved = JSON.parse(execFileSync(process.execPath, [path.join(__dirname, 'resolve-node-components.js')], { encoding: 'utf8' }));
  buildBrowserAssets(resolved.paths.plantumlCore, assets);
  fs.copyFileSync(resolved.paths.mermaidJs, path.join(assets, 'mermaid.min.js'));
  for (const name of ['html-style.css', 'docsfw-ui.css', 'docsfw-nav.js']) {
    fs.copyFileSync(path.join(root, 'styles/html', name), path.join(assets, name));
  }
  fs.writeFileSync(path.join(output, 'sample.md'), source);
  for (const [template, filename, embed] of [
    ['html-template.html', 'normal.html', false],
    ['html-simple-template.html', 'simple.html', false],
    ['html-template.html', 'standalone.html', true],
  ]) {
    // 既存の CDN 依存はこの局所テストから除く。共通資産は実ファイルを使用する。
    const content = fs.readFileSync(path.join(root, 'styles/html', template), 'utf8')
      .replace(/<script\b[^>]*src=['"]https?:[^>]*>\s*<\/script>/g, '')
      .replace(/<link\b[^>]*href=['"]https?:[^>]*>/g, '');
    const temporaryTemplate = path.join(output, template);
    fs.writeFileSync(temporaryTemplate, content);
    const args = ['sample.md', '-s', '-t', 'html', '--toc', '--template', temporaryTemplate,
      '-c', 'assets/html-style.css', '-M', 'mermaid-js=assets/mermaid.min.js',
      '-M', 'docsfw-ui-enable=true', '-M', 'search-base=assets/'];
    for (const filter of ['codeblock-caption-line', 'plantuml', 'mermaid', 'admonition', 'html-browser']) {
      args.push('--lua-filter', path.join(__dirname, 'pandoc-filters', filter + '.lua'));
    }
    if (embed) { args.push('--embed-resources'); }
    args.push('-o', filename);
    execFileSync('pandoc', args, { cwd: output, stdio: 'pipe', timeout: 120000 });
    const html = fs.readFileSync(path.join(output, filename), 'utf8');
    assert(html.includes('class="docsfw-mermaid"'));
    assert(html.includes('class="docsfw-plantuml"'));
    assert(!/<img[^>]+(?:puml_|mermaid_)/.test(html));
    assert(html.includes('id="fig:sequence"'));
    assert(html.includes('id="fig:flow"'));
  }
  assert(!fs.readdirSync(output).some(name => /^puml_|^mermaid_/.test(name)));
  fs.writeFileSync(path.join(output, 'clip.html'), `<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<script src="assets/docsfw-plantuml-loader.js"></script>
<script src="assets/docsfw-diagrams.js"></script>
</head>
<body data-md-color-scheme="default">
<div class="docsfw-plantuml">@startmindmap
* test
** test2
** test3
@endmindmap</div>
</body></html>
`);
  // 狭い画面の配色ボタン確認は、PlantUML の再描画と重ねない。
  fs.writeFileSync(path.join(output, 'theme-mobile.html'), `<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="assets/html-style.css">
<script src="assets/docsfw-theme.js"></script>
</head>
<body>
<div class="navbar navbar-static-top"><div class="navbar-inner"><div class="container">
<span class="doc-title">配色</span>
<ul class="nav pull-right doc-info"></ul>
</div></div></div>
</body></html>
`);
}

async function settled(page) {
  await page.waitForFunction(() => [...document.querySelectorAll('.docsfw-mermaid, .docsfw-plantuml')]
    .every(block => block.dataset.docsfwState === 'done' &&
      block.dataset.docsfwTheme === (document.body.dataset.mdColorScheme === 'slate' ? 'dark' : 'default')),
  { timeout: 60000 }).catch(async error => {
    console.error(await page.evaluate(() => ({ theme: document.body.dataset.mdColorScheme,
      blocks: [...document.querySelectorAll('.docsfw-mermaid, .docsfw-plantuml')].map(el => ({
        state: el.dataset.docsfwState, theme: el.dataset.docsfwTheme, source: el.dataset.docsfwSource.slice(0,90) })) })));
    throw error;
  });
}

async function exercise(page, url, name) {
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);
  await page.goto(url, { waitUntil: 'load' });
  assert(await page.$$eval('.docsfw-plantuml', nodes => nodes.some(el => el.getBoundingClientRect().top > innerHeight)));
  await settled(page);
  const errors = await page.$$eval('.docsfw-diagram--error', nodes => nodes.map(el => el.textContent));
  assert.equal(errors.length, 2, JSON.stringify(errors));
  assert.equal(await page.$$eval('.docsfw-plantuml > svg', nodes => nodes.length), 3);
  assert.equal(await page.$$eval('.docsfw-mermaid > svg', nodes => nodes.length), 2);
  assert(await page.$eval('.docsfw-diagram--error', el => el.textContent.includes('Salt')));
  if (name === 'normal') {
    await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'dark' }]);
    await page.waitForFunction(() => document.body.dataset.mdColorScheme === 'slate');
    await settled(page);
    assert.equal(await page.$eval('body', el => el.dataset.mdColorScheme), 'slate');
    await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);
    await page.waitForFunction(() => document.body.dataset.mdColorScheme === 'default');
    await settled(page);
  }
  const light = await page.$eval('.docsfw-plantuml > svg', svg => svg.outerHTML);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(output, name + '-light.png'), fullPage: true });
  await page.locator('#docsfw-theme-toggle').click();
  await settled(page);
  const dark = await page.$eval('.docsfw-plantuml > svg', svg => svg.outerHTML);
  assert.notEqual(light, dark);
  assert.equal(await page.$eval('body', el => getComputedStyle(el).backgroundColor), 'rgb(30, 33, 41)');
  assert.equal(await page.$eval('body', el => el.dataset.mdColorScheme), 'slate');
  await page.screenshot({ path: path.join(output, name + '-dark.png'), fullPage: true });
  // 保存時に古い SVG を閉じ込めていないことを確認する。
  const exported = await page.evaluate(async () => {
    let saved;
    const original = URL.createObjectURL;
    URL.createObjectURL = blob => { saved = blob; return original(blob); };
    document.querySelector('.plantuml-figure .docsfw-svg-dl').click();
    URL.createObjectURL = original;
    return saved.text();
  });
  const displayed = await page.$eval('.docsfw-plantuml > svg', svg => new XMLSerializer().serializeToString(svg));
  assert.equal(exported, displayed);
  await page.reload({ waitUntil: 'load' });
  assert.equal(await page.$eval('body', el => el.dataset.mdColorScheme), 'slate');
  await settled(page);
  // 狭い画面の見た目だけ撮る。390px で PlantUML を再描画すると TeaVM が戻らず、
  // 続く setViewport が CDP 待ちで落ちるため、配色切替は mobileTheme() で見る。
  await page.setViewport({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(output, name + '-mobile.png') });
  console.log(name + ': rendering, themes, persistence, SVG download passed');
}

async function race(page) {
  await page.goto('about:blank');
  await page.setContent('<body data-md-color-scheme="default"><main id="docsfw-content"><div class="docsfw-plantuml">@startuml\nA -> B\n@enduml</div></main></body>');
  await page.evaluate(() => {
    window.calls = [];
    window.docsfwLoadPlantuml = async () => ({ renderToString(source, ok, fail, options) {
      window.calls.push(options.dark);
      setTimeout(() => ok('<svg xmlns="http://www.w3.org/2000/svg"><text>' + options.dark + '</text></svg>'), 100);
    } });
  });
  await page.addScriptTag({ path: path.join(root, 'styles/browser/docsfw-diagrams.js') });
  await page.waitForFunction(() => window.calls.length === 1);
  await page.evaluate(() => { document.body.dataset.mdColorScheme = 'slate'; });
  await settled(page);
  assert.deepEqual(await page.evaluate(() => window.calls), [false, true]);
  assert.equal(await page.$eval('.docsfw-plantuml svg', el => el.textContent), 'true');
  console.log('theme change during rendering: passed');
}

async function sequentialAfterDomReady(page) {
  await page.goto('about:blank');
  await page.setContent('<body data-md-color-scheme="default"><main style="padding-top: 2000px">' +
    ['A', 'B', 'C'].map(name => '<div class="docsfw-plantuml">@startuml\n' + name + ' -> X\n@enduml</div>').join('') +
    '</main></body>');
  await page.evaluate(() => {
    window.calls = [];
    window.activeCalls = 0;
    window.maxActiveCalls = 0;
    window.docsfwLoadPlantuml = async () => ({ renderToString(source, ok) {
      window.calls.push(source.find(line => line.includes(' -> ')).split(' ')[0]);
      window.activeCalls += 1;
      window.maxActiveCalls = Math.max(window.maxActiveCalls, window.activeCalls);
      setTimeout(() => {
        window.activeCalls -= 1;
        ok('<svg xmlns="http://www.w3.org/2000/svg"></svg>');
      }, 20);
    } });
  });
  await page.addScriptTag({ path: path.join(root, 'styles/browser/docsfw-diagrams.js') });
  await settled(page);
  const result = await page.evaluate(() => ({
    calls: window.calls,
    maxActiveCalls: window.maxActiveCalls,
    scrollY: window.scrollY,
    firstTop: document.querySelector('.docsfw-plantuml').getBoundingClientRect().top
  }));
  assert.deepEqual(result.calls, ['A', 'B', 'C']);
  assert.equal(result.maxActiveCalls, 1);
  assert.equal(result.scrollY, 0);
  assert(result.firstTop > 600, JSON.stringify(result));
  console.log('offscreen PlantUML sequential rendering after DOM ready: passed');
}

async function engineFailure(page) {
  await page.goto('about:blank');
  await page.setContent('<body data-md-color-scheme="default"><main>' +
    '<div class="docsfw-plantuml">@startuml\nA -> B\n@enduml</div>' +
    '<div class="docsfw-plantuml">@startuml\nC -> D\n@enduml</div>' +
    '<div class="docsfw-mermaid">flowchart LR\n  A[start] --> B[end]</div>' +
    '</main></body>');
  await page.evaluate(() => {
    // 隠し iframe 側の engine import が失敗した状況を模す。
    window.docsfwLoadPlantuml = () => Promise.reject(new Error('engine import failed in sandboxed frame'));
    window.mermaid = {
      initialize() {},
      async render(id, source, host) {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        host.appendChild(svg);
        return { svg: svg.outerHTML, bindFunctions: undefined };
      },
    };
  });
  await page.addScriptTag({ path: path.join(root, 'styles/browser/docsfw-diagrams.js') });
  await settled(page);
  const result = await page.evaluate(() => ({
    plantumlErrors: [...document.querySelectorAll('.docsfw-plantuml')].map(el => ({
      hasErrorClass: el.classList.contains('docsfw-diagram--error'),
      message: el.querySelector('p')?.textContent || '',
      source: el.querySelector('pre')?.textContent || '',
    })),
    mermaidSvgCount: document.querySelectorAll('.docsfw-mermaid > svg').length,
  }));
  assert.equal(result.plantumlErrors.length, 2);
  for (const entry of result.plantumlErrors) {
    assert(entry.hasErrorClass, JSON.stringify(result));
    assert(entry.message.includes('engine import failed in sandboxed frame'), JSON.stringify(result));
    assert(entry.source.includes('@startuml'), JSON.stringify(result));
  }
  // PlantUML の engine 障害は Mermaid の描画や他の PlantUML 図の完了を妨げない。
  assert.equal(result.mermaidSvgCount, 1, JSON.stringify(result));
  console.log('plantuml engine load failure: isolated per diagram, no hang: passed');
}

async function clip(page, url) {
  await page.goto(url, { waitUntil: 'load' });
  const block = await page.$('.docsfw-plantuml');
  await block.scrollIntoView();
  await page.waitForFunction(el => el.dataset.docsfwState === 'done', { timeout: 90000 }, block);
  const mindmap = await page.evaluate(() => {
    const svg = document.querySelector('.docsfw-plantuml > svg');
    if (!svg) { return null; }
    const box = svg.viewBox.baseVal;
    const rects = [...svg.querySelectorAll('rect')];
    const minX = Math.min(...rects.map(r => parseFloat(r.getAttribute('x'))));
    const minY = Math.min(...rects.map(r => parseFloat(r.getAttribute('y'))));
    const maxStroke = Math.max(...rects.map(r => parseFloat(r.getAttribute('stroke-width') || 0)));
    return { x: box.x, y: box.y, minX, minY, maxStroke };
  });
  assert(mindmap, 'mindmap svg missing');
  assert(mindmap.x <= mindmap.minX - mindmap.maxStroke / 2, JSON.stringify(mindmap));
  assert(mindmap.y <= mindmap.minY - mindmap.maxStroke / 2, JSON.stringify(mindmap));
  await page.screenshot({ path: path.join(output, 'clip-mindmap.png') });
  console.log('plantuml mindmap viewBox padding: passed');
}

async function mobileTheme(page, url) {
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);
  await page.setViewport({ width: 390, height: 844 });
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForSelector('#docsfw-theme-toggle');
  const before = await page.$eval('body', el => el.dataset.mdColorScheme);
  await page.locator('#docsfw-theme-toggle').click();
  await page.waitForFunction(prev => document.body.dataset.mdColorScheme !== prev, { timeout: 10000 }, before);
  const after = await page.$eval('body', el => el.dataset.mdColorScheme);
  assert.notEqual(after, before);
  assert.ok(after === 'slate' || after === 'default', after);
  console.log('narrow viewport theme toggle: passed');
}

async function main() {
  console.log('Artifacts: ' + output);
  generate();
  const executablePath = process.env.PUPPETEER_EXECUTABLE_PATH || (process.platform === 'win32' ?
    ['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync) : undefined);
  const launch = () => puppeteer.launch(buildBrowserLaunchOptions({ headless: true, executablePath }));
  const clipBrowser = await launch();
  try {
    const clipPage = await clipBrowser.newPage();
    clipPage.on('pageerror', error => console.error('Browser:', error.message.slice(0,500)));
    await clipPage.setViewport({ width: 800, height: 600 });
    await clip(clipPage, pathToFileURL(path.join(output, 'clip.html')).href);
    await mobileTheme(clipPage, pathToFileURL(path.join(output, 'theme-mobile.html')).href);
  } finally { await clipBrowser.close(); }
  const browser = await launch();
  const server = http.createServer((req, res) => {
    const file = path.join(output, decodeURIComponent(req.url.split('?')[0]));
    if (!file.startsWith(output + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404); res.end(); return; }
    res.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : 'text/html');
    fs.createReadStream(file).pipe(res);
  });
  try {
    for (const name of ['normal', 'simple', 'standalone']) {
      if (process.env.DOCSFW_TEST_ONLY && name !== process.env.DOCSFW_TEST_ONLY) { continue; }
      const context = await browser.createBrowserContext();
      try {
        const page = await context.newPage();
        page.on('pageerror', error => console.error('Browser:', error.message.slice(0,500)));
        await page.setViewport({ width: 1440, height: 1100 });
        await page.setOfflineMode(true);
        await exercise(page, pathToFileURL(path.join(output, name + '.html')).href, name);
      } finally { await context.close(); }
    }
    if (process.env.DOCSFW_TEST_ONLY) { return; }
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 1100 });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    await exercise(page, 'http://127.0.0.1:' + server.address().port + '/normal.html', 'http');
    await race(page);
    await sequentialAfterDomReady(page);
    await engineFailure(page);
  } finally {
    await browser.close();
    server.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
