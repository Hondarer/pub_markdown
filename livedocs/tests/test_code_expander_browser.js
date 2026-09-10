// 実行: node livedocs/tests/test_code_expander_browser.js (docsfw ルートから)
// 一時サイトだけを生成し、MkDocs 上のコード ブロック開閉を検証する。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const puppeteer = require(path.join(root, 'bin/node_modules/puppeteer'));
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-code-expander-'));
const python = process.env.PYTHON || path.join(root, 'livedocs/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const longLine = `long-line-${'x'.repeat(240)}`;

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {encoding: 'utf8', timeout: 30000, ...options});
  assert.equal(result.status, 0, result.stderr || String(result.error));
  return result.stdout;
}

(async function () {
  let browser;
  let server;
  try {
    run(python, ['-', root, temporary], {input: String.raw`
import pathlib, sys
root, target = map(pathlib.Path, sys.argv[1:])
sys.path.insert(0, str(root / 'livedocs/bin'))
from vendor_assets import (resolve_node_components, vendor_mermaid,
                           vendor_own_assets, vendor_plantuml)
docs = target / 'docs'
docs.mkdir()
fence = chr(96) * 3
long_line = ${JSON.stringify(longLine)}
md = '\n\n'.join([
    '# Test',
    fence + 'c\n' + long_line + '\nshort\ncode\n' + fence,
    fence + 'c\n' + long_line + '\nline2\nline3\nline4\nline5\nline6\nline7\n' + fence,
    fence + 'mermaid\nflowchart LR\n    A --> B\n' + fence,
    '<figure class="docsfw-figure docsfw-diagram-source-host" markdown="1">\n\n' +
        fence + 'plantuml\n@startuml\ncaption 図の見出し\nAlice -> Bob : Hello\n@enduml\n' + fence +
        '\n\n<figcaption class="docsfw-caption" markdown="span">図の見出し</figcaption>\n\n</figure>',
])
(docs / 'index.md').write_text(md, encoding='utf-8')
vendor_own_assets(str(docs / 'assets'))
resolved = resolve_node_components()['paths']
vendor_plantuml(str(docs / 'assets'), resolved['plantumlCore'])
vendor_mermaid(str(docs / 'assets'), resolved['mermaidJs'])
(docs / 'assets' / 'diagram-test-delay.js').write_text("""
window.docsfwDiagramTest = {};
window.docsfwDiagramTest.mermaid = new Promise(resolve => { window.docsfwDiagramTest.resolveMermaid = resolve; });
window.docsfwDiagramTest.plantuml = new Promise(resolve => { window.docsfwDiagramTest.resolvePlantuml = resolve; });
const originalPlantuml = window.docsfwLoadPlantuml;
window.docsfwLoadPlantuml = async function () {
  await window.docsfwDiagramTest.plantuml;
  return originalPlantuml();
};
const originalMermaidRender = window.mermaid.render.bind(window.mermaid);
window.mermaid.render = async function (...args) {
  await window.docsfwDiagramTest.mermaid;
  return originalMermaidRender(...args);
};
""", encoding='utf-8')
(target / 'mkdocs.yml').write_text("""site_name: Test
theme:
  name: material
  language: ja
  font: false
  features:
    - content.code.copy
  palette:
    - scheme: default
    - scheme: slate
markdown_extensions:
  - pymdownx.highlight
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: docsfw-mermaid
          format: !!python/name:pymdownx.superfences.fence_div_format
        - name: plantuml
          class: docsfw-plantuml
          format: !!python/name:pymdownx.superfences.fence_div_format
extra_css:
  - assets/docsfw-diagrams.css
  - assets/docsfw-pandoc-style.css
  - assets/docsfw-livedocs.css
  - assets/docsfw-code-expander.css
extra_javascript:
  - assets/docsfw-code-expander.js
  - assets/docsfw-plantuml-loader.js
  - assets/mermaid/mermaid.min.js
  - assets/diagram-test-delay.js
  - assets/docsfw-diagrams.js
  - assets/docsfw-svg-download.js
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
    browser = await puppeteer.launch({
      headless: true,
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/local/bin/chrome',
      args: ['--no-sandbox', '--disable-crash-reporter'],
    });
    const noScriptPage = await browser.newPage();
    await noScriptPage.setJavaScriptEnabled(false);
    await noScriptPage.goto(url, {waitUntil: 'networkidle0'});
    const initialStyles = await noScriptPage.$$eval('.docsfw-plantuml, .docsfw-mermaid', blocks =>
      blocks.map(block => {
        const style = getComputedStyle(block);
        const hostStyle = getComputedStyle(block.closest('figure') || block);
        return {
          align: style.textAlign,
          background: style.backgroundColor,
          paddingLeft: style.paddingLeft,
          family: style.fontFamily,
          lineHeight: style.lineHeight,
          marginTop: style.marginTop,
          marginBottom: style.marginBottom,
          figure: !!block.closest('figure'),
          border: style.border,
          borderRadius: style.borderRadius,
          fontSize: style.fontSize,
          hostBorderStyle: hostStyle.borderStyle,
        };
      }));
    assert(initialStyles.every(style => style.align === 'left' && style.background !== 'rgba(0, 0, 0, 0)' &&
      parseFloat(style.paddingLeft) > 0 && (style.figure ?
        style.marginTop === '0px' && style.marginBottom === '0px' :
        parseFloat(style.marginTop) > 0 && parseFloat(style.marginBottom) > 0) &&
      (style.figure ? style.border.includes('none') && style.hostBorderStyle === 'solid' :
        style.border.includes('solid') && style.borderRadius === '3px') &&
      /mono|Consolas|Menlo/i.test(style.family)), JSON.stringify(initialStyles));
    await noScriptPage.close();
    const page = await browser.newPage();
    await page.setViewport({width: 1848, height: 900});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url, {waitUntil: 'networkidle0'});
    const initialStates = await page.$$eval('.docsfw-plantuml, .docsfw-mermaid', blocks => blocks.map(block => {
      const source = block.querySelector('.docsfw-diagram-source');
      const blockStyle = getComputedStyle(block);
      const sourceStyle = getComputedStyle(source);
      const codeStyle = getComputedStyle(source.querySelector('code'));
      return {
        kind: block.classList.contains('docsfw-plantuml') ? 'plantuml' : 'mermaid',
        busy: block.getAttribute('aria-busy'),
        hasSource: !!source,
        align: sourceStyle.textAlign,
        margin: sourceStyle.margin,
        background: sourceStyle.backgroundColor !== 'rgba(0, 0, 0, 0)' ?
          sourceStyle.backgroundColor : codeStyle.backgroundColor,
        hatch: blockStyle.backgroundImage,
        opacity: blockStyle.opacity,
        blockWidth: block.getBoundingClientRect().width,
        hostWidth: block.closest('.docsfw-svg-dl-host').getBoundingClientRect().width,
        figure: !!block.closest('figure'),
        caption: block.closest('figure') ? block.closest('figure').querySelector('figcaption').textContent : '',
        sourceHost: !!(block.closest('figure') &&
          block.closest('figure').classList.contains('docsfw-diagram-source-host')),
      };
    }));
    assert(initialStates.every(item => item.busy === 'true' && item.hasSource && item.align === 'left'),
      JSON.stringify(initialStates));
    const initialPlantuml = initialStates.find(item => item.kind === 'plantuml');
    assert(initialPlantuml.figure && initialPlantuml.sourceHost && initialPlantuml.caption === '図の見出し',
      JSON.stringify(initialStates));
    assert(initialStates.every(item => item.margin === '0px' && item.background !== 'rgba(0, 0, 0, 0)'),
      JSON.stringify(initialStates));
    assert(initialStates.every(item => item.hatch === 'none' && item.opacity === '1' &&
      (item.figure ? item.blockWidth < item.hostWidth && item.hostWidth - item.blockWidth < 20 :
        Math.abs(item.blockWidth - item.hostWidth) < 1)),
      JSON.stringify(initialStates));
    await page.evaluate(() => window.docsfwDiagramTest.resolveMermaid());
    await page.waitForSelector('.docsfw-mermaid > svg');
    const whilePlantuml = await page.$eval('.docsfw-plantuml', block => ({
      busy: block.getAttribute('aria-busy'),
      hasSource: !!block.querySelector('.docsfw-diagram-source'),
      hatch: getComputedStyle(block).backgroundImage,
      opacity: getComputedStyle(block).opacity,
    }));
    assert.equal(whilePlantuml.busy, 'true');
    assert.equal(whilePlantuml.hasSource, true);
    assert.equal(whilePlantuml.hatch, 'none');
    assert.equal(whilePlantuml.opacity, '1');
    await page.evaluate(() => window.docsfwDiagramTest.resolvePlantuml());
    await page.waitForFunction(() => [...document.querySelectorAll('.docsfw-plantuml, .docsfw-mermaid')]
      .every(block => block.dataset.docsfwState === 'done'), {timeout: 60000});
    assert.equal(await page.$eval('.docsfw-plantuml', block =>
      block.closest('figure').classList.contains('docsfw-diagram-source-host')), false);
    const downloadRendering = await page.evaluate(async () => {
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
    assert(downloadRendering.every(item => item.busy === null && item.hatch === 'none' && item.opacity === '1'),
      JSON.stringify(downloadRendering));
    const info = await page.evaluate(() => {
      const wrappers = [...document.querySelectorAll('.code-expander-wrapper')];
      const toolbars = [...document.querySelectorAll('.code-expander-toolbar')];
      const mermaidWrap = document.querySelector('.docsfw-mermaid .code-expander-wrapper');
      return {
        wrapperCount: wrappers.length,
        toolbarCount: toolbars.length,
        mermaidWrapped: !!mermaidWrap,
        shortHasToolbar: !!(wrappers[0] && wrappers[0].parentElement.querySelector(':scope > .code-expander-toolbar')),
        longHasToolbar: !!(wrappers[1] && wrappers[1].parentElement.querySelector(':scope > .code-expander-toolbar')),
        restHiddenAfterCollapse: null,
        hintText: toolbars.length ? document.querySelector('.code-expander-hint').textContent : '',
      };
    });
    assert.equal(info.wrapperCount, 2, JSON.stringify(info));
    assert.equal(info.toolbarCount, 1);
    assert.equal(info.shortHasToolbar, false);
    assert.equal(info.longHasToolbar, true);
    assert.equal(info.mermaidWrapped, false);
    const diagramTools = await page.evaluate(async () => {
      const results = [];
      let copiedText = '';
      Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {
        writeText(text) { copiedText = text; return Promise.resolve(); },
      }});
      for (const block of document.querySelectorAll('.docsfw-plantuml, .docsfw-mermaid')) {
        const host = block.closest('.docsfw-svg-dl-host');
        const initialSvg = !!block.querySelector(':scope > svg');
        const svg = block.querySelector(':scope > svg');
        const svgRect = svg.getBoundingClientRect();
        const blockRect = block.getBoundingClientRect();
        const centered = Math.abs((svgRect.left + svgRect.width / 2) -
          (blockRect.left + blockRect.width / 2)) < 1;
        const diagramWidth = host.getBoundingClientRect().width;
        const imageCopyLabel = host.querySelector('.docsfw-diagram-copy').title;
        host.querySelector('.docsfw-diagram-toggle').click();
        await new Promise(resolve => setTimeout(resolve, 0));
        const source = block.querySelector('.docsfw-diagram-source');
        const sourceHost = !block.closest('figure') ||
          block.closest('figure').classList.contains('docsfw-diagram-source-host');
        const sourceCopyLabel = host.querySelector('.docsfw-diagram-copy').title;
        host.querySelector('.docsfw-diagram-copy').click();
        await new Promise(resolve => setTimeout(resolve, 0));
        results.push({
          actions: host.querySelectorAll('.docsfw-diagram-action').length,
          initialSvg,
          centered,
          source: source.textContent,
          expected: block.dataset.docsfwSource,
          copied: copiedText,
          align: getComputedStyle(source).textAlign,
          margin: getComputedStyle(source).margin,
          background: (() => {
            const sourceBackground = getComputedStyle(source).backgroundColor;
            return sourceBackground !== 'rgba(0, 0, 0, 0)' ? sourceBackground :
              getComputedStyle(source.querySelector('code')).backgroundColor;
          })(),
          lineHeight: getComputedStyle(source.querySelector('code')).lineHeight,
          border: getComputedStyle(source).border,
          borderRadius: getComputedStyle(source).borderRadius,
          paddingLeft: getComputedStyle(source.querySelector('code')).paddingLeft,
          family: getComputedStyle(source.querySelector('code')).fontFamily,
          fontSize: getComputedStyle(source.querySelector('code')).fontSize,
          hostBorderStyle: getComputedStyle(host).borderStyle,
          sourceWidth: host.getBoundingClientRect().width,
          diagramWidth,
          downloadLabel: host.querySelector('.docsfw-svg-dl').title,
          copyLabel: sourceCopyLabel,
          imageCopyLabel,
          sourceHost,
        });
      }
      return results;
    });
    assert(diagramTools.every(item => item.actions === 3 && item.initialSvg && item.centered),
      JSON.stringify(diagramTools));
    assert(diagramTools.every(item => item.source === item.expected && item.copied === item.expected),
      JSON.stringify(diagramTools));
    assert(diagramTools.every(item => item.align === 'left'), JSON.stringify(diagramTools));
    assert(diagramTools.every(item => item.sourceHost), JSON.stringify(diagramTools));
    assert(diagramTools.every(item => item.downloadLabel === 'SVG をダウンロード' &&
      item.imageCopyLabel === '画像をコピー' && item.copyLabel === 'ソースをコピー'), JSON.stringify(diagramTools));
    assert(diagramTools.every(item => item.margin === '0px' && Math.abs(item.sourceWidth - item.diagramWidth) < 1),
      JSON.stringify(diagramTools));
    assert(diagramTools.every(item => item.background ===
      initialStates.find(initial => initial.kind === (item.expected.startsWith('@start') ? 'plantuml' : 'mermaid')).background),
    JSON.stringify({initialStates, diagramTools}));
    assert(diagramTools.every(item => item.lineHeight ===
      initialStyles[item.expected.startsWith('@start') ? 1 : 0].lineHeight),
    JSON.stringify({initialStyles, diagramTools}));
    assert(diagramTools.every(item => {
      const initial = initialStyles[item.expected.startsWith('@start') ? 1 : 0];
      return item.border === initial.border && item.borderRadius === initial.borderRadius &&
        item.paddingLeft === '16px' && item.family === initial.family && item.fontSize === initial.fontSize &&
        (initial.figure ? item.hostBorderStyle === 'solid' && item.border.includes('none') :
          item.hostBorderStyle === 'none' && item.border.includes('solid'));
    }), JSON.stringify({initialStyles, diagramTools}));
    const mermaidCopy = await page.evaluate(async () => {
      const block = document.querySelector('.docsfw-mermaid');
      const host = block.closest('.docsfw-svg-dl-host');
      let copied;
      let expectedRatio;
      let requestedTheme = '';
      window.ClipboardItem = function (items) { this.items = items; };
      Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {
        write(items) {
          return Promise.resolve(items[0].items['image/png']).then(async blob => {
            const bitmap = await createImageBitmap(blob);
            copied = {type: blob.type, size: blob.size, width: bitmap.width, height: bitmap.height};
            bitmap.close();
          }).catch(error => {
            copied = {error: String(error)};
          });
        },
      }});
      const originalRender = window.docsfwDiagramTools.renderSvg;
      window.docsfwDiagramTools.renderSvg = function (target, selectedTheme) {
        requestedTheme = selectedTheme;
        return originalRender.call(this, target, selectedTheme).then(text => {
          const svg = new DOMParser().parseFromString(text, 'image/svg+xml').documentElement;
          const box = svg.getAttribute('viewBox').trim().split(/[ ,]+/).map(Number);
          expectedRatio = box[2] / box[3];
          return text;
        });
      };
      host.querySelector('.docsfw-diagram-toggle').click();
      await new Promise(resolve => setTimeout(resolve, 0));
      host.querySelector('.docsfw-diagram-copy').click();
      for (let i = 0; i < 100 && !copied; i += 1) {
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      let downloaded;
      const originalUrl = URL.createObjectURL;
      URL.createObjectURL = function (blob) {
        if (blob.type === 'image/svg+xml') { downloaded = blob; }
        return originalUrl(blob);
      };
      host.querySelector('.docsfw-svg-dl').click();
      for (let i = 0; i < 100 && !downloaded; i += 1) {
        await new Promise(resolve => setTimeout(resolve, 20));
      }
      URL.createObjectURL = originalUrl;
      return {copied, requestedTheme, expectedRatio, downloaded: {
        type: downloaded.type,
        hasForeignObject: (await downloaded.text()).includes('<foreignObject'),
      }};
    });
    assert.equal(mermaidCopy.requestedTheme, 'default');
    assert.equal(mermaidCopy.copied.type, 'image/png', JSON.stringify(mermaidCopy));
    assert(mermaidCopy.copied.size > 0);
    assert(Math.abs(mermaidCopy.copied.width - mermaidCopy.copied.height * mermaidCopy.expectedRatio) <= 1.1,
      JSON.stringify(mermaidCopy));
    assert.equal(mermaidCopy.downloaded.type, 'image/svg+xml');
    assert.equal(mermaidCopy.downloaded.hasForeignObject, false);
    console.log('PASS: MkDocs PlantUML/Mermaid diagram tools and light-theme PNG copy');
    async function codeAppearance(pageHandle, scheme) {
      await pageHandle.mouse.move(0, 0);
      await pageHandle.evaluate(selected => {
        document.documentElement.setAttribute('data-md-color-scheme', selected);
        document.body.setAttribute('data-md-color-scheme', selected);
      }, scheme);
      const read = () => pageHandle.evaluate(() => {
        const wrapper = document.querySelectorAll('.code-expander-wrapper')[1];
        const shell = wrapper.parentElement;
        const first = wrapper.querySelector('.code-first');
        const rest = wrapper.querySelector('.code-rest');
        const firstCode = first.querySelector('code');
        const restCode = rest.querySelector('code');
        const toolbar = shell.querySelector('.code-expander-toolbar');
        const button = toolbar.querySelector('.code-expander-btn');
        const arrow = button.querySelector('.code-expander-arrow');
        const hint = wrapper.querySelector('.code-expander-hint');
        const shellStyle = getComputedStyle(shell);
        const firstStyle = getComputedStyle(first);
        const restStyle = getComputedStyle(rest);
        const firstCodeStyle = getComputedStyle(firstCode);
        const restCodeStyle = getComputedStyle(restCode);
        const firstRect = first.getBoundingClientRect();
        const restRect = rest.getBoundingClientRect();
        const toolbarRect = toolbar.getBoundingClientRect();
        const number = value => parseFloat(value);
        return {
          lineHeight: firstCodeStyle.lineHeight,
          paddingTop: number(firstStyle.paddingTop) + number(firstCodeStyle.paddingTop),
          paddingRight: number(firstStyle.paddingRight) + number(firstCodeStyle.paddingRight),
          paddingBottom: number(restStyle.paddingBottom) + number(restCodeStyle.paddingBottom),
          paddingLeft: number(firstStyle.paddingLeft) + number(firstCodeStyle.paddingLeft),
          splitPaddingBottom: number(firstStyle.paddingBottom) + number(firstCodeStyle.paddingBottom),
          splitPaddingTop: number(restStyle.paddingTop) + number(restCodeStyle.paddingTop),
          firstHeight: firstRect.height,
          restHeight: restRect.height,
          gap: restRect.top - firstRect.bottom,
          toolbarHeight: toolbarRect.height,
          buttonLineHeight: getComputedStyle(button).lineHeight,
          restDisplay: restStyle.display,
          hintDisplay: getComputedStyle(hint).display,
          marginTop: shellStyle.marginTop,
          marginBottom: shellStyle.marginBottom,
          borderBottomColor: getComputedStyle(toolbar).borderBottomColor,
          borderTopColor: getComputedStyle(hint).borderTopColor,
          buttonFamily: getComputedStyle(button).fontFamily,
          bodyFamily: getComputedStyle(document.body).fontFamily,
          buttonColor: getComputedStyle(button).color,
          arrowColor: getComputedStyle(arrow).color,
          hintColor: getComputedStyle(hint).color,
          controlBackground: getComputedStyle(toolbar).backgroundColor,
          hintBackground: getComputedStyle(hint).backgroundColor,
        };
      });
      const before = await read();
      await pageHandle.hover('.code-expander-btn');
      const afterHoverColor = await pageHandle.$eval('.code-expander-btn', button => getComputedStyle(button).color);
      return {...before, afterHoverColor};
    }

    function assertAppearanceGeometry(info, scheme, expanded) {
      assert.equal(info.lineHeight, '19px', JSON.stringify(info));
      assert.equal(info.paddingTop, 11, JSON.stringify(info));
      assert.equal(info.paddingRight, 16, JSON.stringify(info));
      assert.equal(info.paddingBottom, 11, JSON.stringify(info));
      assert.equal(info.paddingLeft, 16, JSON.stringify(info));
      assert.equal(info.splitPaddingBottom, 0, JSON.stringify(info));
      assert.equal(info.splitPaddingTop, 0, JSON.stringify(info));
      assert.equal(info.marginTop, '15px', JSON.stringify(info));
      assert.equal(info.marginBottom, '15px', JSON.stringify(info));
      assert.equal(info.borderBottomColor,
        scheme === 'default' ? 'rgb(221, 221, 221)' : 'rgba(255, 255, 255, 0.12)');
      assert.equal(info.borderTopColor, info.borderBottomColor);
      assert.equal(info.buttonFamily, info.bodyFamily);
      assert.equal(info.buttonColor, info.afterHoverColor);
      assert.equal(info.buttonLineHeight, '22px');
      assert.equal(info.toolbarHeight, 31);
      assert.ok(Math.abs(info.firstHeight - 106) < 0.01, JSON.stringify(info));
      if (expanded) {
        assert.notEqual(info.restDisplay, 'none');
        assert.equal(info.hintDisplay, 'none');
        assert.ok(Math.abs(info.restHeight - 49) < 0.01, JSON.stringify(info));
        assert.ok(Math.abs(info.gap) < 0.01, JSON.stringify(info));
      } else {
        assert.equal(info.restDisplay, 'none');
        assert.equal(info.hintDisplay, 'block');
      }
    }

    function compositeColor(foreground, background) {
      const parse = value => value.match(/[\d.]+/g).map(Number);
      const fg = parse(foreground);
      const bg = parse(background);
      const alpha = fg.length === 4 ? fg[3] : 1;
      return fg.slice(0, 3).map((channel, index) => channel * alpha + bg[index] * (1 - alpha));
    }

    function assertVisualColorNear(pandocColor, mkdocsColor, pandocBackground, mkdocsBackground, label) {
      const pandoc = compositeColor(pandocColor, pandocBackground);
      const mkdocs = compositeColor(mkdocsColor, mkdocsBackground);
      assert.ok(pandoc.every((channel, index) => Math.abs(channel - mkdocs[index]) <= 3),
        label + ' ' + JSON.stringify({pandocColor, mkdocsColor, pandocBackground, mkdocsBackground}));
    }

    const mkdocsExpandedAppearance = {};
    for (const scheme of ['default', 'slate']) {
      mkdocsExpandedAppearance[scheme] = await codeAppearance(page, scheme);
      assertAppearanceGeometry(mkdocsExpandedAppearance[scheme], scheme, true);
    }
    assert.notEqual(mkdocsExpandedAppearance.slate.buttonColor, mkdocsExpandedAppearance.default.buttonColor);
    assert.notEqual(mkdocsExpandedAppearance.slate.arrowColor, mkdocsExpandedAppearance.default.arrowColor);

    const restDisplayExpanded = await page.evaluate(() => {
      const rest = document.querySelector('.code-rest');
      return rest ? rest.style.display : 'missing';
    });
    assert.equal(restDisplayExpanded, '');
    await page.click('.code-expander-btn');
    const collapsed = await page.evaluate(() => {
      const rest = document.querySelector('.code-rest');
      const hint = document.querySelector('.code-expander-hint');
      const first = document.querySelector('.code-first code');
      return {
        rest: rest.style.display,
        hint: hint.style.display,
        firstLines: first.textContent.split('\n').filter(Boolean).length,
        hintText: hint.textContent,
      };
    });
    assert.equal(collapsed.rest, 'none');
    assert.equal(collapsed.hint, '');
    assert.equal(collapsed.firstLines, 5);
    assert.match(collapsed.hintText, /2.*7/);
    for (const scheme of ['default', 'slate']) {
      assertAppearanceGeometry(await codeAppearance(page, scheme), scheme, false);
    }
    await page.waitForFunction(() => document.querySelector('.md-code__button[data-md-type="copy"][data-clipboard-text]'));
    const copiedSource = await page.evaluate(() => {
      const buttons = [...document.querySelectorAll('.md-code__button[data-md-type="copy"]')];
      const long = buttons.find(b => (b.getAttribute('data-clipboard-text') || '').includes('line7'));
      return long ? long.getAttribute('data-clipboard-text') : '';
    });
    assert.match(copiedSource, /line7/);
    assert.match(copiedSource, /long-line-/);
    await page.waitForFunction(() => {
      const wrap = document.querySelector('.code-expander-wrapper');
      return !!(wrap && [...wrap.children].some((child) => child.classList.contains('md-code__nav')));
    });

    async function copyPin(pageHandle, wrapperIndex, selector) {
      return pageHandle.evaluate((index, sel) => {
        const wrap = document.querySelectorAll('.code-expander-wrapper')[index];
        const scroll = wrap && wrap.querySelector('.code-expander-scroll');
        const chip = wrap && wrap.querySelector(sel);
        const pre = wrap && wrap.querySelector('pre');
        if (!wrap || !scroll || !chip || !pre) {
          return {missing: true};
        }
        const wrapRect = wrap.getBoundingClientRect();
        const chipRect = chip.getBoundingClientRect();
        const preRect = pre.getBoundingClientRect();
        return {
          missing: false,
          parentIsWrapper: chip.parentElement === wrap,
          wrapRight: wrapRect.right,
          chipRight: chipRect.right,
          chipTop: chipRect.top,
          preRight: preRect.right,
          overflow: scroll.scrollWidth - scroll.clientWidth,
          scrollLeft: scroll.scrollLeft,
        };
      }, wrapperIndex, selector);
    }

    function assertPinned(info, label) {
      assert.equal(info.missing, false, label + ' ' + JSON.stringify(info));
      assert.equal(info.parentIsWrapper, true, label + ' parent ' + JSON.stringify(info));
      assert.ok(info.overflow > 40, label + ' overflow ' + JSON.stringify(info));
      assert.ok(info.preRight > info.wrapRight + 40, label + ' content wider ' + JSON.stringify(info));
      const gap = info.wrapRight - info.chipRight;
      assert.ok(gap >= 0 && gap <= 12, label + ' visible right ' + JSON.stringify(info));
    }

    async function assertStaysOnScroll(pageHandle, wrapperIndex, selector, label) {
      const before = await copyPin(pageHandle, wrapperIndex, selector);
      assertPinned(before, label);
      await pageHandle.evaluate((index) => {
        const wrap = document.querySelectorAll('.code-expander-wrapper')[index];
        wrap.querySelector('.code-expander-scroll').scrollLeft = 120;
      }, wrapperIndex);
      const after = await copyPin(pageHandle, wrapperIndex, selector);
      assert.equal(after.scrollLeft, 120, label + ' scrolled ' + JSON.stringify(after));
      assert.ok(Math.abs(after.chipRight - before.chipRight) <= 1, label + ' stayed ' + JSON.stringify({before, after}));
      await pageHandle.evaluate((index) => {
        const wrap = document.querySelectorAll('.code-expander-wrapper')[index];
        wrap.querySelector('.code-expander-scroll').scrollLeft = 0;
      }, wrapperIndex);
    }

    await assertStaysOnScroll(page, 0, '.md-code__nav', 'mkdocs short');
    await assertStaysOnScroll(page, 1, '.md-code__nav', 'mkdocs long');

    async function hoverLongChrome(pageHandle, selector) {
      const wrap = (await pageHandle.$$('.code-expander-wrapper'))[1];
      const inside = await wrap.$(selector);
      if (inside) {
        await inside.hover();
        return;
      }
      const sibling = await wrap.evaluateHandle((el, sel) => el.parentElement.querySelector(sel), selector);
      await sibling.asElement().hover();
    }
    async function navOpacityAfterHover(selector) {
      await hoverLongChrome(page, selector);
      await new Promise((resolve) => setTimeout(resolve, 200));
      return page.evaluate(() => {
        const wrap = document.querySelectorAll('.code-expander-wrapper')[1];
        const nav = wrap.querySelector('.md-code__nav') || wrap.parentElement.querySelector('.md-code__nav');
        return nav ? getComputedStyle(nav).opacity : 'missing';
      });
    }
    assert.equal(await navOpacityAfterHover('.code-expander-toolbar'), '0');
    assert.equal(await navOpacityAfterHover('.code-expander-hint'), '0');
    assert.equal(await navOpacityAfterHover('.code-expander-scroll'), '1');
    for (const width of [1700, 2100]) {
      await page.setViewport({width, height: 900});
      assert.equal(
        await page.evaluate(() => getComputedStyle(document.documentElement).fontSize),
        '20px',
        'html font-size at ' + width,
      );
    }
    assert.deepEqual(errors, []);
    console.log('PASS: MkDocs code expander wrap, threshold, collapse hint, full copy, mermaid skipped, copy hover on code only');

    const htmlStyle = fs.readFileSync(path.join(root, 'styles/html/html-style.css'), 'utf8');
    const template = fs.readFileSync(path.join(root, 'styles/html/html-template.html'), 'utf8');
    const markerAt = template.indexOf('コードブロック エキスパンダーとコピー');
    const styleStart = template.indexOf('<style>', markerAt);
    const styleEnd = template.indexOf('</style>', styleStart) + '</style>'.length;
    const scriptStart = template.indexOf('<script>', styleEnd);
    const scriptEnd = template.indexOf('</script>', scriptStart) + '</script>'.length;
    const expanderCss = template.slice(styleStart, styleEnd);
    const expanderJs = template.slice(scriptStart, scriptEnd).replace(/\$\$/g, '$');
    const pandocHtml = '<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>' +
      htmlStyle + '</style>' + expanderCss + '</head><body><main id="docsfw-content">' +
      '<pre><code>' + longLine + '\nshort\ncode\n</code></pre>' +
      '<div class="sourceCode"><pre><code>' + longLine +
      '\nline2\nline3\nline4\nline5\nline6\nline7\n</code></pre></div>' +
      '</main>' + expanderJs + '</body></html>';
    const pandocServer = http.createServer((request, response) => {
      response.setHeader('Content-Type', 'text/html; charset=utf-8');
      response.end(pandocHtml);
    });
    await new Promise((resolve) => pandocServer.listen(0, '127.0.0.1', resolve));
    const pandocPage = await browser.newPage();
    await pandocPage.setViewport({width: 1848, height: 900});
    await pandocPage.goto('http://127.0.0.1:' + pandocServer.address().port + '/', {waitUntil: 'networkidle0'});
    for (const scheme of ['default', 'slate']) {
      const pandocAppearance = await codeAppearance(pandocPage, scheme);
      assertAppearanceGeometry(pandocAppearance, scheme, true);
      const mkdocsAppearance = mkdocsExpandedAppearance[scheme];
      assert.equal(pandocAppearance.lineHeight, mkdocsAppearance.lineHeight);
      assert.equal(pandocAppearance.firstHeight, mkdocsAppearance.firstHeight);
      assert.equal(pandocAppearance.restHeight, mkdocsAppearance.restHeight);
      assert.equal(pandocAppearance.gap, mkdocsAppearance.gap);
      assert.equal(pandocAppearance.borderBottomColor, mkdocsAppearance.borderBottomColor);
      if (scheme === 'default') {
        assertVisualColorNear(pandocAppearance.buttonColor, mkdocsAppearance.buttonColor,
          pandocAppearance.controlBackground, mkdocsAppearance.controlBackground, scheme + ' button');
        assertVisualColorNear(pandocAppearance.arrowColor, mkdocsAppearance.arrowColor,
          pandocAppearance.controlBackground, mkdocsAppearance.controlBackground, scheme + ' arrow');
        assertVisualColorNear(pandocAppearance.hintColor, mkdocsAppearance.hintColor,
          pandocAppearance.hintBackground, mkdocsAppearance.hintBackground, scheme + ' hint');
      } else {
        assert.notEqual(pandocAppearance.buttonColor, mkdocsExpandedAppearance.default.buttonColor);
        assert.notEqual(pandocAppearance.arrowColor, mkdocsExpandedAppearance.default.arrowColor);
      }
    }
    await pandocPage.click('.code-expander-btn');
    for (const scheme of ['default', 'slate']) {
      assertAppearanceGeometry(await codeAppearance(pandocPage, scheme), scheme, false);
    }
    await pandocPage.setViewport({width: 800, height: 600});
    async function copyOpacityAfterHover(selector) {
      await hoverLongChrome(pandocPage, selector);
      await new Promise((resolve) => setTimeout(resolve, 200));
      return pandocPage.evaluate(() => {
        const wrap = document.querySelectorAll('.code-expander-wrapper')[1];
        return getComputedStyle(wrap.querySelector('.docsfw-code-copy')).opacity;
      });
    }
    assert.equal(await copyOpacityAfterHover('.code-expander-toolbar'), '0');
    assert.equal(await copyOpacityAfterHover('.code-expander-hint'), '0');
    assert.equal(await copyOpacityAfterHover('.code-expander-scroll'), '1');
    await assertStaysOnScroll(pandocPage, 0, '.docsfw-code-copy', 'pandoc short');
    await assertStaysOnScroll(pandocPage, 1, '.docsfw-code-copy', 'pandoc long');
    await pandocPage.close();
    await new Promise((resolve) => pandocServer.close(resolve));
    console.log('PASS: Pandoc/MkDocs code metrics, themes, expander colors, and copy hover');
  } finally {
    if (browser) await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
    fs.rmSync(temporary, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
