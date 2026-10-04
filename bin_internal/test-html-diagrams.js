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
const diagramsScript = path.join(root, 'styles/browser/docsfw-diagrams.js');
const output = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-diagrams-'));
const downloads = path.join(output, 'downloads');
const downloadBehavior = { policy: 'allow', downloadPath: downloads };

function stubFrame(options = {}) {
  const delay = options.delayMs || 0;
  const hang = !!options.hang;
  const fail = options.fail || '';
  const initError = options.initError || '';
  const svg = options.svg || '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40" viewBox="0 0 80 40"></svg>';
  return `<!doctype html><meta charset="utf-8"><body><script>
    var released = ${options.hold ? 'false' : 'true'};
    var waiting = [];
    function emit(data) { parent.postMessage(data, '*'); }
    window.addEventListener('message', function (event) {
      if (event.source !== parent) return;
      var data = event.data || {};
      if (data.kind === 'release') {
        released = true;
        waiting.splice(0).forEach(function (send) { send(); });
        return;
      }
      if (data.kind !== 'render' || typeof data.requestId !== 'string' || typeof data.source !== 'string' ||
          typeof data.dark !== 'boolean' || typeof data.portable !== 'boolean') return;
      emit({ kind: 'started', requestId: data.requestId, source: data.source, dark: data.dark, portable: data.portable });
      var send = function () {
        setTimeout(function () {
          ${hang ? '' : fail
            ? `emit({ kind: 'result', requestId: data.requestId, error: ${JSON.stringify(fail)} });`
            : `emit({ kind: 'result', requestId: data.requestId, svg: ${JSON.stringify(svg)} });
          ${options.lateSvg ? `setTimeout(function () { emit({ kind: 'result', requestId: data.requestId, svg: ${JSON.stringify(options.lateSvg)} }); }, 50);` : ''}`}
        }, ${delay});
      };
      if (released) send(); else waiting.push(send);
    });
    ${initError ? `emit({ kind: 'init-error', error: ${JSON.stringify(initError)} });` : 'emit({ kind: "ready" });'}
  </script></body>`;
}
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
  for (const [name, width] of [['small', 120], ['wide', 2400]]) {
    fs.writeFileSync(path.join(output, name + '.drawio.svg'),
      '<svg xmlns="http://www.w3.org/2000/svg" width="' + width + '" height="60" viewBox="0 0 ' + width + ' 60"><rect width="100%" height="100%" fill="lightblue"/></svg>');
  }
  const resolved = JSON.parse(execFileSync(process.execPath, [path.join(__dirname, 'resolve-node-components.js')], { encoding: 'utf8' }));
  buildBrowserAssets(resolved.paths.plantumlCore, assets, resolved.paths.mermaidJs);
  for (const name of ['html-style.css', 'docsfw-ui.css', 'docsfw-nav.js']) {
    fs.copyFileSync(path.join(root, 'styles/html', name), path.join(assets, name));
  }
  fs.writeFileSync(path.join(output, 'sample.md'), source + '\n' +
    '![小さい draw.io 図](small.drawio.svg){#fig:drawio-small}\n\n' +
    '![大きい draw.io 図](wide.drawio.svg){#fig:drawio-wide}\n');
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
      '-c', 'assets/html-style.css', '-M', 'mermaid-js=assets/docsfw-mermaid-frame.html',
      '-M', 'docsfw-ui-enable=true', '-M', 'search-base=assets/'];
    for (const filter of ['codeblock-caption-line', 'plantuml', 'mermaid', 'admonition', 'html-browser']) {
      args.push('--lua-filter', path.join(__dirname, 'pandoc-filters', filter + '.lua'));
    }
    if (embed) { args.push('--embed-resources', '-M', 'docsfw-embed-frames=true'); }
    args.push('-o', filename);
    execFileSync('pandoc', args, { cwd: output, stdio: 'pipe', timeout: 120000 });
    const html = fs.readFileSync(path.join(output, filename), 'utf8');
    assert(html.includes('class="docsfw-mermaid"'));
    assert(html.includes('class="docsfw-plantuml"'));
    assert.equal((html.match(/class="docsfw-diagram-source"/g) || []).length, 7);
    assert(!/<img[^>]+(?:puml_|mermaid_)/.test(html));
    assert(html.includes('id="fig:sequence"'));
    assert(html.includes('id="fig:flow"'));
    assert(!html.includes('docsfw-plantuml-loader.js'), filename);
    assert(!html.includes('src="assets/mermaid.min.js"'), filename);
    if (embed) {
      assert(html.includes('type="text/plain"'), filename);
      assert(html.includes('id="docsfw-mermaid-frame"'), filename);
      assert(html.includes('id="docsfw-plantuml-frame"'), filename);
      assert(html.includes('DOCSFW_FRAME_SCRIPT_END_7f3a9c'), filename);
      assert(!html.includes('<script src="assets/docsfw-mermaid-frame.html"></script>'), filename);
    } else {
      assert(!html.includes('id="docsfw-mermaid-frame"'), filename);
    }
  }
  assert(!fs.readdirSync(output).some(name => /^puml_|^mermaid_/.test(name)));
  fs.writeFileSync(path.join(output, 'clip.html'), `<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<link rel="stylesheet" href="assets/docsfw-diagrams.css">
<script defer src="assets/docsfw-diagrams.js"></script>
</head>
<body data-md-color-scheme="default">
<div class="docsfw-plantuml">@startmindmap
* test
** test2
** test3
@endmindmap</div>
</body></html>
`);
  fs.writeFileSync(path.join(output, 'measure.html'), `<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<link rel="stylesheet" href="assets/docsfw-diagrams.css">
<script defer src="assets/docsfw-diagrams.js"></script>
</head>
<body data-md-color-scheme="default">
<div class="docsfw-mermaid">flowchart LR
  A["日本語の長いラベルが折り返しと寸法を確認します"] --> B["1行目<br/>2行目"]
  click A "https://example.com/docsfw" "詳細"
</div>
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
  await page.evaluateOnNewDocument(() => {
    window.__docsfwRaf = 0;
    const tick = () => { window.__docsfwRaf += 1; requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
  const moduleRequests = [];
  const recordModule = request => {
    if (request.resourceType() === 'script' && request.frame() !== page.mainFrame()) {
      moduleRequests.push(request.url());
    }
  };
  page.on('request', recordModule);
  await page.goto(url, { waitUntil: 'load' });
  await settled(page);
  const imageSizes = await page.$$eval('figure[id^="fig:drawio-"]', figures => figures.map(figure => {
    const image = figure.querySelector('img');
    const frame = image.closest('.docsfw-image-frame');
    const style = getComputedStyle(image);
    const width = image.getBoundingClientRect().width;
    const contentWidth = width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) -
      parseFloat(style.borderLeftWidth) - parseFloat(style.borderRightWidth);
    return { id: figure.id, naturalWidth: image.naturalWidth, contentWidth,
      frameFullWidth: !!frame && Math.abs(frame.getBoundingClientRect().width - figure.getBoundingClientRect().width) < 1,
      fits: width <= frame.getBoundingClientRect().width + 1,
      captionOutside: figure.querySelector('figcaption').getBoundingClientRect().top >= frame.getBoundingClientRect().bottom };
  }));
  assert.equal(imageSizes.length, 2);
  assert(imageSizes.every(item => item.frameFullWidth && item.fits && item.captionOutside), JSON.stringify(imageSizes));
  assert(Math.abs(imageSizes[0].contentWidth - 120) < 1, JSON.stringify(imageSizes));
  assert(imageSizes[1].contentWidth < imageSizes[1].naturalWidth, JSON.stringify(imageSizes));
  const errors = await page.$$eval('.docsfw-diagram--error', nodes => nodes.map(el => el.textContent));
  assert.equal(errors.length, 2, JSON.stringify(errors));
  assert.equal(await page.$$eval('.docsfw-plantuml > svg', nodes => nodes.length), 3);
  page.off('request', recordModule);
  assert(moduleRequests.some(url => url.startsWith('blob:')), 'PlantUML module must load from a Blob URL');
  assert(!moduleRequests.some(url => url.startsWith('data:')), 'PlantUML must not import a data URL');
  assert.equal(await page.$$eval('.docsfw-mermaid > svg', nodes => nodes.length), 2);
  const parentApis = await page.evaluate(() => ({
    mermaid: typeof window.mermaid,
    plantuml: typeof window.docsfwLoadPlantuml,
    raf: window.__docsfwRaf,
  }));
  assert.equal(parentApis.mermaid, 'undefined', name);
  assert.equal(parentApis.plantuml, 'undefined', name);
  assert(parentApis.raf > 5, name + ' parent raf ' + parentApis.raf);
  const measured = await page.$eval('.docsfw-mermaid > svg', svg => {
    const box = svg.viewBox.baseVal;
    return { text: svg.textContent, width: box.width, height: box.height };
  });
  assert(measured.text.includes('開始'), name + ' ' + measured.text);
  assert(measured.width > 0 && measured.height > 0, JSON.stringify(measured));
  assert(await page.$eval('.docsfw-diagram--error', el => el.textContent.includes('Salt')));
  assert.equal(await page.$$eval('.plantuml-figure .docsfw-diagram-toolbar', nodes => nodes.length), 1);
  assert.equal(await page.$$eval('.plantuml-figure .docsfw-diagram-action', nodes => nodes.length), 3);
  const captionedWidths = await page.evaluate(async () => {
    const results = [];
    for (const block of document.querySelectorAll('.mermaid-figure > .docsfw-mermaid, .plantuml-figure > .docsfw-plantuml')) {
      const host = block.closest('figure');
      const toggle = host.querySelector('.docsfw-diagram-toggle');
      const captionOutside = () => getComputedStyle(host.querySelector('.docsfw-diagram-toolbar')).borderStyle === 'none' &&
        getComputedStyle(host).borderStyle === 'none' &&
        getComputedStyle(block).borderStyle === 'solid' &&
        host.querySelector('figcaption').getBoundingClientRect().top >= block.getBoundingClientRect().bottom;
      const diagramCaptionOutside = captionOutside();
      const diagramWidth = host.getBoundingClientRect().width;
      toggle.click();
      await new Promise(resolve => setTimeout(resolve, 0));
      const sourceWidth = host.getBoundingClientRect().width;
      const sourceCaptionOutside = captionOutside();
      toggle.click();
      await new Promise(resolve => setTimeout(resolve, 0));
      results.push({ diagramWidth, sourceWidth, captionOutside: diagramCaptionOutside && sourceCaptionOutside });
    }
    return results;
  });
  assert(captionedWidths.length === 2 && captionedWidths.every(item =>
    item.captionOutside && Math.abs(item.diagramWidth - item.sourceWidth) < 1), JSON.stringify(captionedWidths));
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
  // ソース表示は原文を保って左寄せになり、コピー対象も原文になる。
  const sourceResult = await page.evaluate(async () => {
    const block = document.querySelector('.plantuml-figure .docsfw-plantuml');
    const expected = block.dataset.docsfwSource;
    let copied = '';
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
      writeText(text) { copied = text; return Promise.resolve(); },
    } });
    block.closest('.docsfw-svg-dl-host').querySelector('.docsfw-diagram-toggle').click();
    await new Promise(resolve => setTimeout(resolve, 0));
    const source = block.querySelector('.docsfw-diagram-source');
    block.closest('.docsfw-svg-dl-host').querySelector('.docsfw-diagram-copy').click();
    await new Promise(resolve => setTimeout(resolve, 0));
    return {
      expected,
      shown: source.textContent,
      copied,
      align: getComputedStyle(source).textAlign,
      lineHeight: getComputedStyle(source).lineHeight,
    };
  });
  assert.equal(sourceResult.shown, sourceResult.expected);
  assert.equal(sourceResult.copied, sourceResult.expected);
  assert(!sourceResult.expected.includes('skinparam backgroundColor transparent'));
  assert.equal(sourceResult.align, 'left');
  assert.equal(sourceResult.lineHeight, '19px');
  await page.click('.plantuml-figure .docsfw-diagram-toggle');
  await page.waitForSelector('.plantuml-figure .docsfw-plantuml > svg');

  // ダーク表示中も、ダウンロードと画像コピーはライトテーマの結果を使う。
  const exported = await page.evaluate(async () => {
    let savedResolve;
    const savedPromise = new Promise(resolve => { savedResolve = resolve; });
    const original = URL.createObjectURL;
    URL.createObjectURL = blob => { savedResolve(blob); return original(blob); };
    document.querySelector('.plantuml-figure .docsfw-svg-dl').click();
    const saved = await savedPromise;
    URL.createObjectURL = original;
    return saved.text();
  });
  const displayed = await page.$eval('.docsfw-plantuml > svg', svg => new XMLSerializer().serializeToString(svg));
  const expectedLight = await page.evaluate(async () => {
    const block = document.querySelector('.plantuml-figure .docsfw-plantuml');
    const text = await window.docsfwDiagramTools.renderSvg(block, 'default');
    const svg = new DOMParser().parseFromString(text, 'image/svg+xml').documentElement;
    if (!svg.getAttribute('xmlns')) { svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg'); }
    return new XMLSerializer().serializeToString(svg);
  });
  assert.equal(exported, expectedLight);
  assert.notEqual(exported, displayed);

  const copiedImage = await page.evaluate(async () => {
    const originalRender = window.docsfwDiagramTools.renderSvg;
    let requestedTheme = '';
    let expectedRatio;
    window.docsfwDiagramTools.renderSvg = function (block, selectedTheme) {
      requestedTheme = selectedTheme;
      return originalRender.call(this, block, selectedTheme).then(text => {
        const svg = new DOMParser().parseFromString(text, 'image/svg+xml').documentElement;
        const box = svg.getAttribute('viewBox').trim().split(/[ ,]+/).map(Number);
        expectedRatio = box[2] / box[3];
        return text;
      });
    };
    window.ClipboardItem = function (items) { this.items = items; };
    let copied;
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
      write(items) {
        return Promise.resolve(items[0].items['image/png']).then(async blob => {
          const bitmap = await createImageBitmap(blob);
          copied = { type: blob.type, size: blob.size, width: bitmap.width, height: bitmap.height };
          bitmap.close();
        });
      },
    } });
    document.querySelector('.plantuml-figure .docsfw-diagram-copy').click();
    for (let i = 0; i < 100 && !copied; i += 1) {
      await new Promise(resolve => setTimeout(resolve, 20));
    }
    return { requestedTheme, expectedRatio, copied };
  });
  assert.equal(copiedImage.requestedTheme, 'default');
  assert.equal(copiedImage.copied.type, 'image/png');
  assert(copiedImage.copied.size > 0);
  assert(Math.abs(copiedImage.copied.width - copiedImage.copied.height * copiedImage.expectedRatio) <= 1.1,
    JSON.stringify(copiedImage));
  if (name === 'normal') {
    const mermaidImage = await page.evaluate(async () => {
      const block = document.querySelector('.docsfw-mermaid');
      const host = block.closest('.docsfw-svg-dl-host');
      let copied;
      let expectedRatio;
      const originalRender = window.docsfwDiagramTools.renderSvg;
      window.docsfwDiagramTools.renderSvg = function (target, selectedTheme) {
        return originalRender.call(this, target, selectedTheme).then(text => {
          const svg = new DOMParser().parseFromString(text, 'image/svg+xml').documentElement;
          const box = svg.getAttribute('viewBox').trim().split(/[ ,]+/).map(Number);
          expectedRatio = box[2] / box[3];
          return text;
        });
      };
      window.ClipboardItem = function (items) { this.items = items; };
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
        write(items) {
          return Promise.resolve(items[0].items['image/png']).then(async blob => {
            const bitmap = await createImageBitmap(blob);
            copied = { width: bitmap.width, height: bitmap.height };
            bitmap.close();
          });
        },
      } });
      host.querySelector('.docsfw-diagram-copy').click();
      for (let i = 0; i < 100 && !copied; i += 1) {
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      return { copied, expectedRatio };
    });
    assert(Math.abs(mermaidImage.copied.width - mermaidImage.copied.height * mermaidImage.expectedRatio) <= 1.1,
      JSON.stringify(mermaidImage));
  }
  const copyFailure = await page.evaluate(async () => {
    const button = document.querySelector('.plantuml-figure .docsfw-diagram-copy');
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
      write() { return Promise.reject(new Error('clipboard denied')); },
    } });
    button.click();
    for (let i = 0; i < 50 && !button.getAttribute('aria-label').includes('できません'); i += 1) {
      await new Promise(resolve => setTimeout(resolve, 20));
    }
    return {
      label: button.getAttribute('aria-label'),
      actions: [...button.closest('.docsfw-diagram-toolbar').querySelectorAll('button')]
        .map(action => ({ type: action.type, label: action.getAttribute('aria-label') })),
    };
  });
  assert(copyFailure.label.includes('コピーできませんでした'));
  assert(copyFailure.actions.every(action => action.type === 'button' && action.label));
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
  await page.evaluate(srcdoc => {
    window.calls = [];
    window.addEventListener('message', event => {
      if (event.data && event.data.kind === 'started') window.calls.push(event.data.dark);
    });
    window.docsfwDiagramFrames = { plantuml: { srcdoc } };
  }, stubFrame({
    delayMs: 100,
    svg: '<svg xmlns="http://www.w3.org/2000/svg"><text>done</text></svg>',
  }));
  await page.addScriptTag({ path: diagramsScript });
  await page.waitForFunction(() => window.calls.length === 1);
  await page.evaluate(() => { document.body.dataset.mdColorScheme = 'slate'; });
  await settled(page);
  assert.deepEqual(await page.evaluate(() => window.calls), [false, true]);
  assert.equal(await page.$eval('.docsfw-plantuml svg', el => el.textContent), 'done');
  console.log('theme change during rendering: passed');
}

async function diagramStateMatrix(page) {
  await page.goto('about:blank');
  await page.setContent('<body data-md-color-scheme="default"><main id="docsfw-content">' +
    '<div class="docsfw-plantuml">@startuml\nA -> B\n@enduml</div>' +
    '<div class="docsfw-mermaid">flowchart LR\nA --> B</div></main></body>');
  await page.addStyleTag({ path: path.join(root, 'styles/html/html-style.css') });
  await page.addStyleTag({ path: path.join(root, 'styles/browser/docsfw-diagrams.css') });
  await page.evaluate((plantumlFrame, mermaidFrame) => {
    window.matrix = {};
    window.matrix.plantuml = new Promise(resolve => { window.matrix.resolvePlantuml = resolve; });
    window.matrix.mermaid = new Promise(resolve => { window.matrix.resolveMermaid = resolve; });
    window.docsfwDiagramTest = { plantuml: window.matrix.plantuml, mermaid: window.matrix.mermaid };
    window.docsfwDiagramFrames = {
      plantuml: { srcdoc: plantumlFrame },
      mermaid: { srcdoc: mermaidFrame },
    };
  }, stubFrame({ svg: '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="120" viewBox="0 0 240 120"></svg>' }),
    stubFrame({ svg: '<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="200" viewBox="0 0 400 200"></svg>' }));
  await page.addScriptTag({ path: diagramsScript });
  await page.addScriptTag({ path: path.join(root, 'styles/browser/docsfw-svg-download.js') });

  async function states() {
    return page.$$eval('.docsfw-plantuml, .docsfw-mermaid', blocks => blocks.map(block => {
      const source = block.querySelector('.docsfw-diagram-source');
      const host = block.closest('.docsfw-svg-dl-host');
      return {
        busy: block.getAttribute('aria-busy'),
        source: !!source,
        svg: !!block.querySelector(':scope > svg'),
        align: source ? getComputedStyle(source).textAlign : '',
        margin: source ? getComputedStyle(source).margin : '',
        background: source ? getComputedStyle(source).backgroundColor : '',
        hatch: getComputedStyle(block).backgroundImage,
        opacity: getComputedStyle(block).opacity,
        width: host.getBoundingClientRect().width,
      };
    }));
  }

  const initial = await states();
  assert(initial.every(item => item.busy === 'true' && item.source && !item.svg && item.align === 'left'),
    JSON.stringify(initial));
  assert(initial.every(item => item.margin === '0px' && item.background !== 'rgba(0, 0, 0, 0)' &&
    item.hatch === 'none' && item.opacity === '1'),
    JSON.stringify(initial));
  await page.evaluate(() => window.matrix.resolvePlantuml());
  await page.waitForSelector('.docsfw-plantuml > svg');
  const rendering = await states();
  assert(rendering[0].svg && rendering[1].source && rendering[1].busy === 'true' &&
    rendering[1].hatch === 'none' && rendering[1].opacity === '1',
    JSON.stringify(rendering));
  await page.evaluate(() => window.matrix.resolveMermaid());
  await page.waitForSelector('.docsfw-mermaid > svg');
  const diagram = await states();
  assert(diagram.every(item => item.svg && item.busy === null), JSON.stringify(diagram));
  const exporting = await page.evaluate(async () => {
    const original = window.docsfwDiagramTools.renderSvg;
    const results = [];
    for (const block of document.querySelectorAll('.docsfw-plantuml, .docsfw-mermaid')) {
      let release;
      window.docsfwDiagramTools.renderSvg = () => new Promise(resolve => { release = resolve; });
      block.closest('.docsfw-svg-dl-host').querySelector('.docsfw-svg-dl').click();
      await new Promise(resolve => setTimeout(resolve, 0));
      results.push({
        busy: block.getAttribute('aria-busy'),
        hatch: getComputedStyle(block).backgroundImage,
        opacity: getComputedStyle(block).opacity,
      });
      release('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"></svg>');
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    window.docsfwDiagramTools.renderSvg = original;
    return results;
  });
  assert(exporting.every(item => item.busy === null && item.hatch === 'none' && item.opacity === '1'),
    JSON.stringify(exporting));
  await page.evaluate(async () => {
    for (const block of document.querySelectorAll('.docsfw-plantuml, .docsfw-mermaid')) {
      await window.docsfwDiagramTools.showSource(block);
    }
  });
  const source = await states();
  assert(source.every((item, index) => item.source && item.align === 'left' && item.margin === '0px' &&
    Math.abs(item.width - diagram[index].width) < 1), JSON.stringify({ diagram, source }));
  console.log('Pandoc PlantUML/Mermaid four-state layout: passed');
}

async function sequentialAfterDomReady(page) {
  await page.goto('about:blank');
  await page.setContent('<body data-md-color-scheme="default"><main style="padding-top: 2000px">' +
    ['A', 'B', 'C'].map(name => '<div class="docsfw-plantuml">@startuml\n' + name + ' -> X\n@enduml</div>').join('') +
    '</main></body>');
  await page.evaluate(srcdoc => {
    window.calls = [];
    window.activeCalls = 0;
    window.maxActiveCalls = 0;
    window.addEventListener('message', event => {
      const data = event.data || {};
      if (data.kind === 'started') {
        window.activeCalls += 1;
        window.maxActiveCalls = Math.max(window.maxActiveCalls, window.activeCalls);
        const match = data.source.match(/^([A-C]) -> /m);
        window.calls.push(match ? match[1] : data.source);
      } else if (data.kind === 'result') {
        window.activeCalls -= 1;
      }
    });
    window.docsfwDiagramFrames = { plantuml: { srcdoc } };
  }, stubFrame({ delayMs: 20 }));
  await page.addScriptTag({ path: diagramsScript });
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
  await page.evaluate((plantumlFrame, mermaidFrame) => {
    window.docsfwDiagramFrames = {
      plantuml: { srcdoc: plantumlFrame },
      mermaid: { srcdoc: mermaidFrame },
    };
  }, stubFrame({ initError: 'engine import failed in sandboxed frame' }),
    stubFrame());
  await page.addScriptTag({ path: diagramsScript });
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

async function initialSourceAlignment(page, url) {
  await page.setJavaScriptEnabled(false);
  await page.goto(url, { waitUntil: 'load' });
  const styles = await page.$$eval('.docsfw-plantuml, .docsfw-mermaid', blocks => blocks.map(block => {
    const source = block.querySelector('.docsfw-diagram-source');
    const style = getComputedStyle(source);
    const figure = block.closest('figure');
    return {
      hasSource: !!source,
      align: style.textAlign,
      background: style.backgroundColor,
      border: style.borderStyle,
      paddingLeft: style.paddingLeft,
      family: style.fontFamily,
      lineHeight: style.lineHeight,
      sourceBorder: style.borderStyle,
      hostBorder: figure ? getComputedStyle(figure).borderStyle : 'none',
      blockBorder: getComputedStyle(block).borderStyle,
    };
  }));
  assert(styles.length > 0);
  assert(styles.every(style => style.hasSource && style.align === 'left' && style.background !== 'rgba(0, 0, 0, 0)' &&
    ((style.hostBorder === 'none' && style.blockBorder === 'solid' && style.sourceBorder === 'none') ||
      (style.hostBorder === 'none' && style.sourceBorder === 'solid')) &&
    parseFloat(style.paddingLeft) > 0 && /mono|Consolas|Menlo/i.test(style.family) &&
    style.lineHeight === '19px'),
  JSON.stringify(styles));
  console.log('source before diagram rendering: styled and left aligned');
}

async function measureDiagram(page, url) {
  await page.goto(url, { waitUntil: 'load' });
  await settled(page);
  const display = await page.$eval('.docsfw-mermaid > svg', svg => {
    const texts = [...svg.querySelectorAll('text, span, foreignObject')].map(node => ({
      text: node.textContent,
      width: node.getBBox ? node.getBBox().width : node.getBoundingClientRect().width,
    }));
    return {
      html: svg.innerHTML,
      width: svg.viewBox.baseVal.width,
      height: svg.viewBox.baseVal.height,
      texts,
    };
  });
  assert(display.html.includes('日本語の長いラベル'), display.html.slice(0, 200));
  assert(display.html.includes('1行目') && display.html.includes('2行目'), display.html.slice(0, 300));
  assert(/foreignObject/i.test(display.html), 'HTML ラベル');
  assert(/example\.com\/docsfw/.test(display.html), 'SVG 内リンク');
  assert(display.width > 0 && display.height > 0, JSON.stringify(display));
  assert(display.texts.some(item => item.text.includes('日本語') && item.width > 0), JSON.stringify(display.texts));
  const portable = await page.evaluate(() => window.docsfwDiagramTools.renderSvg(
    document.querySelector('.docsfw-mermaid'), 'default'));
  assert(!/foreignObject/i.test(portable), portable.slice(0, 300));
  assert(portable.includes('日本語の長いラベル'));
  const parent = await page.evaluate(() => typeof window.mermaid);
  assert.equal(parent, 'undefined');
  console.log('mermaid measurement and portable svg: passed ' + url);
}

function traceOf(page) {
  return page.evaluate(() => window.docsfwDiagramTrace || []);
}

async function gateCases(page) {
  const diagram = '<div class="docsfw-plantuml">@startuml\nA -> B\n@enduml</div>';
  await page.evaluateOnNewDocument(stub => {
    window.docsfwDiagramFrames = { plantuml: { srcdoc: stub } };
  }, stubFrame());
  const loading = path.join(output, 'gate-loading.html');
  fs.writeFileSync(loading, `<!doctype html><meta charset="utf-8"><body data-md-color-scheme="default">${diagram}
<script src="assets/docsfw-diagrams.js"></script></body>`);
  await page.goto(pathToFileURL(loading).href, { waitUntil: 'load' });
  await settled(page);
  let trace = await traceOf(page);
  const scan = trace.find(item => item.event === 'scan');
  const loaded = trace.find(item => item.event === 'content-loaded');
  const paint = trace.find(item => item.event === 'paint-opportunity');
  const frame = trace.find(item => item.event === 'frame-load');
  assert.equal(scan.readyState, 'loading', JSON.stringify(trace));
  assert.notEqual(loaded.readyState, 'loading');
  assert(scan.time < loaded.time && loaded.time <= paint.time && paint.time <= frame.time, JSON.stringify(trace));
  console.log('gate loading: passed');

  const deferred = path.join(output, 'gate-defer.html');
  fs.writeFileSync(deferred, `<!doctype html><head><meta charset="utf-8"><script defer src="assets/docsfw-diagrams.js"></script></head>
<body data-md-color-scheme="default"><script>window.__dcl = 0; document.addEventListener('DOMContentLoaded', function () { window.__dcl = performance.now(); });</script>
${diagram}</body>`);
  await page.goto(pathToFileURL(deferred).href, { waitUntil: 'load' });
  await settled(page);
  const deferredResult = await page.evaluate(() => ({ dcl: window.__dcl, trace: window.docsfwDiagramTrace }));
  assert.equal(deferredResult.trace.find(item => item.event === 'scan').readyState, 'interactive');
  assert(deferredResult.dcl > 0 && deferredResult.trace.find(item => item.event === 'frame-load').time > deferredResult.dcl,
    JSON.stringify(deferredResult));
  console.log('gate interactive before DOMContentLoaded: passed');

  const delayed = path.join(output, 'gate-delayed-defer.html');
  fs.writeFileSync(delayed, `<!doctype html><head><meta charset="utf-8">
<script defer src="assets/docsfw-diagrams.js"></script><script defer src="assets/delayed-toc.js"></script></head>
<body data-md-color-scheme="default">${diagram}<script>
document.addEventListener('DOMContentLoaded', function () { window.__dcl = performance.now(); });
</script></body>`);
  await page.setRequestInterception(true);
  const delayedToc = request => {
    if (!request.url().endsWith('/delayed-toc.js')) { request.continue(); return; }
    setTimeout(() => request.respond({ contentType: 'text/javascript', body:
      'window.__tocPlaced = performance.now();' }), 400);
  };
  page.on('request', delayedToc);
  try {
    await page.goto(pathToFileURL(delayed).href, { waitUntil: 'load' });
    await settled(page);
    const result = await page.evaluate(() => ({
      toc: window.__tocPlaced, dcl: window.__dcl, trace: window.docsfwDiagramTrace,
    }));
    assert(result.toc > result.trace.find(item => item.event === 'scan').time + 200, JSON.stringify(result));
    assert(result.trace.find(item => item.event === 'content-loaded').time >= result.dcl, JSON.stringify(result));
    assert(result.trace.find(item => item.event === 'frame-load').time > result.toc, JSON.stringify(result));
  } finally {
    page.off('request', delayedToc);
    await page.setRequestInterception(false);
  }
  console.log('gate waits for delayed defer and toc placement: passed');

  const done = path.join(output, 'gate-done.html');
  fs.writeFileSync(done, `<!doctype html><meta charset="utf-8"><body data-md-color-scheme="default">${diagram}</body>`);
  await page.goto(pathToFileURL(done).href, { waitUntil: 'load' });
  await page.addScriptTag({ path: diagramsScript });
  await settled(page);
  assert.equal((await traceOf(page)).find(item => item.event === 'content-loaded').readyState, 'complete');
  console.log('gate after DOMContentLoaded: passed');

  const during = path.join(output, 'gate-during.html');
  const script = fs.readFileSync(diagramsScript, 'utf8');
  const encoded = JSON.stringify(script).replace(/</g, '\\u003c');
  fs.writeFileSync(during, `<!doctype html><meta charset="utf-8"><body data-md-color-scheme="default">${diagram}
<script>document.addEventListener('DOMContentLoaded', function () {
  var element = document.createElement('script');
  element.textContent = ${encoded};
  document.body.appendChild(element);
});</script></body>`);
  await page.goto(pathToFileURL(during).href, { waitUntil: 'load' });
  await settled(page);
  console.log('gate re-entry during DOMContentLoaded: passed');
  const withoutTiming = await page.evaluateOnNewDocument(() => {
    const getEntries = performance.getEntriesByType.bind(performance);
    performance.getEntriesByType = type => type === 'navigation' ? [] : getEntries(type);
  });
  try {
    await page.goto(pathToFileURL(during).href, { waitUntil: 'load' });
    await settled(page);
    assert((await traceOf(page)).some(item => item.event === 'frame-load'));
  } finally {
    await page.removeScriptToEvaluateOnNewDocument(withoutTiming.identifier);
  }
  console.log('gate re-entry without navigation timing: passed');
}

async function hiddenAndTheme(page) {
  await page.evaluateOnNewDocument(stub => {
    let hidden = true;
    Object.defineProperty(document, 'hidden', { configurable: true, get() { return hidden; } });
    window.__showDoc = () => { hidden = false; document.dispatchEvent(new Event('visibilitychange')); };
    window.docsfwDiagramFrames = { plantuml: { srcdoc: stub } };
    window.__started = [];
    window.addEventListener('message', event => {
      if (event.data && event.data.kind === 'started') window.__started.push(event.data);
    });
  }, stubFrame());
  const hiddenPage = path.join(output, 'hidden-theme.html');
  fs.writeFileSync(hiddenPage, `<!doctype html><meta charset="utf-8"><body data-md-color-scheme="default">
<div class="docsfw-plantuml">@startuml
A -> B
@enduml</div>
<script src="assets/docsfw-diagrams.js"></script>
</body>`);
  await page.goto(pathToFileURL(hiddenPage).href, { waitUntil: 'load' });
  await page.evaluate(() => {
    document.body.setAttribute('data-md-color-scheme', 'slate');
    const block = document.querySelector('.docsfw-plantuml');
    window.docsfwDiagramTools.showDiagram(block);
    window.docsfwDiagramTools.renderSvg(block, 'default');
  });
  await new Promise(resolve => setTimeout(resolve, 200));
  const before = await page.evaluate(() => ({
    frame: !!document.querySelector('iframe'),
    events: (window.docsfwDiagramTrace || []).map(item => item.event),
  }));
  assert.equal(before.frame, false, JSON.stringify(before));
  assert(!before.events.includes('paint-opportunity'), JSON.stringify(before));
  await page.evaluate(() => window.__showDoc());
  await page.waitForFunction(() => window.__started.some(item => item.portable));
  await settled(page);
  const started = await page.evaluate(() => window.__started);
  assert.equal(started[0].dark, true, JSON.stringify(started));
  assert.equal(started[0].portable, false, JSON.stringify(started));
  assert(started.some(item => item.portable && item.dark === false), JSON.stringify(started));
  console.log('hidden tab and pre-start theme: passed');
}

async function serialAndFailures(page) {
  await page.evaluateOnNewDocument((plantumlFrame, mermaidFrame) => {
    window.docsfwDiagramFrames = {
      plantuml: { srcdoc: plantumlFrame },
      mermaid: { srcdoc: mermaidFrame },
    };
    window.__started = [];
    window.addEventListener('message', event => {
      if (event.data && event.data.kind === 'started') window.__started.push(event.data);
    });
  }, stubFrame({ hold: true }), stubFrame());
  const serialPage = path.join(output, 'serial-queue.html');
  fs.writeFileSync(serialPage, `<!doctype html><meta charset="utf-8"><body data-md-color-scheme="default">
<div class="docsfw-plantuml">@startuml
A -> B
@enduml</div>
<div class="docsfw-mermaid">flowchart LR
A --> B</div>
<script src="assets/docsfw-diagrams.js"></script>
</body>`);
  await page.goto(pathToFileURL(serialPage).href, { waitUntil: 'load' });
  await page.waitForFunction(() => window.__started.length === 1);
  await page.evaluate(() => {
    window.docsfwDiagramTools.renderSvg(document.querySelector('.docsfw-plantuml'), 'default');
  });
  await new Promise(resolve => setTimeout(resolve, 50));
  let started = await page.evaluate(() => window.__started);
  assert.equal(started.length, 1, JSON.stringify(started));
  assert.equal(started[0].portable, false);
  assert(started[0].source.includes('@startuml'));
  await page.evaluate(() => window.postMessage({
    kind: 'result', requestId: 'd1', svg: '<svg id="forged" xmlns="http://www.w3.org/2000/svg"></svg>',
  }, '*'));
  await page.evaluate(() => document.querySelector('iframe').contentWindow.postMessage({ kind: 'release' }, '*'));
  await page.waitForFunction(() => window.__started.some(item => item.portable));
  await settled(page);
  started = await page.evaluate(() => window.__started);
  assert(started.some(item => item.portable), JSON.stringify(started));
  assert.equal(await page.$('#forged'), null);
  assert.equal(await page.$$eval('.docsfw-mermaid > svg', nodes => nodes.length), 1);
  console.log('serial queue, portable request, foreign message: passed');
}

async function timeoutAndLate(page) {
  await page.evaluateOnNewDocument((plantumlFrame, mermaidFrame) => {
    window.docsfwDiagramTimeouts = { init: 2000, render: 400 };
    window.docsfwDiagramFrames = {
      plantuml: { srcdoc: plantumlFrame },
      mermaid: { srcdoc: mermaidFrame },
    };
  }, stubFrame({ hang: true }), stubFrame({
    svg: '<svg xmlns="http://www.w3.org/2000/svg" id="mermaid-ok"></svg>',
  }));
  const timeoutPage = path.join(output, 'timeout-queue.html');
  fs.writeFileSync(timeoutPage, `<!doctype html><meta charset="utf-8"><body data-md-color-scheme="default">
<div class="docsfw-plantuml">@startuml
A -> B
@enduml</div>
<div class="docsfw-mermaid">flowchart LR
A --> B</div>
<script src="assets/docsfw-diagrams.js"></script>
</body>`);
  await page.goto(pathToFileURL(timeoutPage).href, { waitUntil: 'load' });
  await settled(page);
  const result = await page.evaluate(() => ({
    plantuml: document.querySelector('.docsfw-plantuml').innerText,
    mermaid: !!document.querySelector('.docsfw-mermaid > svg'),
  }));
  assert(result.plantuml.includes('タイムアウト'), result.plantuml);
  assert.equal(result.mermaid, true);
  console.log('timeout advances the queue: passed');

  await page.evaluateOnNewDocument(stub => {
    window.docsfwDiagramFrames = { plantuml: { srcdoc: stub } };
  }, stubFrame({
    svg: '<svg xmlns="http://www.w3.org/2000/svg" id="first"></svg>',
    lateSvg: '<svg xmlns="http://www.w3.org/2000/svg" id="late"></svg>',
  }));
  const latePage = path.join(output, 'late-reply.html');
  fs.writeFileSync(latePage, `<!doctype html><meta charset="utf-8"><body data-md-color-scheme="default">
<div class="docsfw-plantuml">@startuml
A -> B
@enduml</div>
<script src="assets/docsfw-diagrams.js"></script>
</body>`);
  await page.goto(pathToFileURL(latePage).href, { waitUntil: 'load' });
  await settled(page);
  await new Promise(resolve => setTimeout(resolve, 80));
  const html = await page.$eval('.docsfw-plantuml', node => node.innerHTML);
  assert(html.includes('id="first"'), html);
  assert(!html.includes('id="late"'), html);
  console.log('late reply ignored: passed');
}

async function missingFrame(page) {
  await page.evaluateOnNewDocument(() => {
    window.docsfwDiagramTimeouts = { init: 700, render: 700 };
  });
  const missingPage = path.join(output, 'missing-frame.html');
  fs.writeFileSync(missingPage, `<!doctype html><meta charset="utf-8"><body data-md-color-scheme="default">
<div class="docsfw-plantuml">@startuml
A -> B
@enduml</div>
<div class="docsfw-mermaid">flowchart LR
A --> B</div>
<script src="${pathToFileURL(diagramsScript).href}"></script>
</body>`);
  await page.goto(pathToFileURL(missingPage).href, { waitUntil: 'load' });
  await settled(page);
  const errors = await page.$$eval('.docsfw-diagram--error', nodes => nodes.map(node => node.textContent));
  assert.equal(errors.length, 2, JSON.stringify(errors));
  assert(errors.every(text => text.includes('読み込めません') || text.includes('タイムアウト')), JSON.stringify(errors));
  console.log('missing frame does not stop the queue: passed');
}

async function paintBeforeDiagram(page, base) {
  await page.setViewport({ width: 1440, height: 1100 });
  let held = null;
  await page.setRequestInterception(true);
  page.on('request', request => {
    if (!held && /docsfw-(?:mermaid|plantuml)-frame\.html/.test(request.url())) {
      held = request;
      return;
    }
    request.continue();
  });
  await page.goto(base + '/normal.html', { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelector('iframe.docsfw-diagram-frame'), { timeout: 10000 });
  const atFrame = await page.evaluate(() => {
    const toc = document.getElementById('docsfw-page-toc');
    const body = document.getElementById('docsfw-content') || document.querySelector('main') || document.body;
    return {
      tocHeight: toc ? toc.getBoundingClientRect().height : 0,
      tocHidden: !!(toc && toc.hidden),
      bodyHeight: body.getBoundingClientRect().height,
      svg: !!document.querySelector('.docsfw-mermaid > svg, .docsfw-plantuml > svg'),
      trace: (window.docsfwDiagramTrace || []).map(item => item.event),
    };
  });
  assert(atFrame.bodyHeight > 0, JSON.stringify(atFrame));
  assert(atFrame.tocHeight > 0 && !atFrame.tocHidden, JSON.stringify(atFrame));
  assert.equal(atFrame.svg, false);
  assert(atFrame.trace.indexOf('content-loaded') < atFrame.trace.indexOf('paint-opportunity'));
  assert(atFrame.trace.indexOf('paint-opportunity') < atFrame.trace.indexOf('frame-load'));
  await page.screenshot({ path: path.join(output, 'before-diagram.png') });
  await held.continue();
  await settled(page);
  console.log('body and toc before diagram frame: passed');
}

async function parentResponsiveness(page, base) {
  await page.goto(base + '/measure.html', { waitUntil: 'load' });
  await settled(page);
  const frame = page.frames().find(item => item.url().endsWith('/docsfw-mermaid-frame.html'));
  assert(frame, '実 Mermaid フレーム');
  // 実エンジンの呼出し中に同期処理を加え、親の応答を確実に観測できる時間を作る。
  const patched = await frame.evaluate(() => {
    const render = window.mermaid.render;
    window.mermaid.render = async function (...args) {
      parent.postMessage({ kind: 'test-busy' }, '*');
      // 通知を配送してから同期処理へ入り、通知の IPC バッファリングを測定から除く。
      await new Promise(resolve => setTimeout(resolve, 100));
      window.__busyStarted = Date.now();
      const end = performance.now() + 1500;
      while (performance.now() < end) { /* フレーム内の重い同期処理 */ }
      window.__busyEnded = Date.now();
      parent.postMessage({ kind: 'test-idle' }, '*');
      return render.apply(this, args);
    };
    return window.mermaid.render !== render;
  });
  assert(patched, 'Mermaid render の負荷計測フック');
  await page.evaluate(() => {
    window.__busy = false;
    window.addEventListener('message', event => {
      if (event.data.kind === 'test-busy') window.__busy = true;
      if (event.data.kind === 'test-idle') window.__busy = false;
    });
    const button = document.createElement('button');
    button.id = 'response-probe';
    button.textContent = '応答確認';
    button.style.cssText = 'position:fixed;top:0;left:0;z-index:9999';
    button.onclick = () => { window.__clickedAt = Date.now(); };
    document.body.appendChild(button);
    window.__export = window.docsfwDiagramTools.renderSvg(document.querySelector('.docsfw-mermaid'), 'dark');
  });
  await page.waitForFunction(() => window.__busy);
  await new Promise(resolve => setTimeout(resolve, 250));
  await page.click('#response-probe');
  await page.evaluate(() => window.__export);
  const interval = await frame.evaluate(() => ({ start: window.__busyStarted, end: window.__busyEnded }));
  const clickedAt = await page.evaluate(() => window.__clickedAt);
  assert(interval.end - interval.start >= 1500, JSON.stringify(interval));
  assert(clickedAt >= interval.start, JSON.stringify({ clickedAt, interval }));
  const result = { clickedAt, interval, responsive: clickedAt < interval.end };
  fs.writeFileSync(path.join(output, 'parent-responsiveness.json'), JSON.stringify(result, null, 2));
  // プロセス分離はブラウザーに依存するため、描画中に応答しない環境も計測結果として残す。
  console.log('parent input during Mermaid execution: ' +
    (result.responsive ? 'responsive' : 'blocked until frame execution finished'));
}

async function runTests() {
  console.log('Artifacts: ' + output);
  generate();
  const executablePath = process.env.PUPPETEER_EXECUTABLE_PATH || (process.platform === 'win32' ?
    ['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe'].find(fs.existsSync) : undefined);
  // 既定と個別のコンテキストで、利用者のダウンロード フォルダーへ保存しない。
  // see: https://pptr.dev/api/puppeteer.downloadbehavior
  const launch = () => puppeteer.launch(buildBrowserLaunchOptions({
    headless: true, executablePath, downloadBehavior,
  }));
  const clipBrowser = await launch();
  try {
    const clipPage = await clipBrowser.newPage();
    clipPage.on('pageerror', error => console.error('Browser:', error.message.slice(0,500)));
    await clipPage.setViewport({ width: 800, height: 600 });
    await clip(clipPage, pathToFileURL(path.join(output, 'clip.html')).href);
    await mobileTheme(clipPage, pathToFileURL(path.join(output, 'theme-mobile.html')).href);
    const sourcePage = await clipBrowser.newPage();
    await initialSourceAlignment(sourcePage, pathToFileURL(path.join(output, 'normal.html')).href);
    await sourcePage.close();
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
      const context = await browser.createBrowserContext({ downloadBehavior });
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
    const base = 'http://127.0.0.1:' + server.address().port;
    await exercise(page, base + '/normal.html', 'http');
    await diagramStateMatrix(page);
    await race(page);
    await sequentialAfterDomReady(page);
    await engineFailure(page);
    const schedule = await browser.newPage();
    await schedule.setViewport({ width: 1440, height: 1100 });
    await gateCases(schedule);
    await hiddenAndTheme(await browser.newPage());
    await serialAndFailures(await browser.newPage());
    await timeoutAndLate(await browser.newPage());
    await missingFrame(await browser.newPage());
    await measureDiagram(await browser.newPage(), pathToFileURL(path.join(output, 'measure.html')).href);
    await measureDiagram(await browser.newPage(), base + '/measure.html');
    await paintBeforeDiagram(await browser.newPage(), base);
    await parentResponsiveness(await browser.newPage(), base);
  } finally {
    await browser.close();
    server.close();
  }
}

async function main() {
  fs.mkdirSync(downloads);
  try {
    await runTests();
  } finally {
    // HTML とスクリーンショットは残し、ダウンロード ファイルだけ削除する。
    fs.rmSync(downloads, { recursive: true, force: true });
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
