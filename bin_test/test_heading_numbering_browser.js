'use strict';

// 実行: node bin_test/test_heading_numbering_browser.js
// Chromium のレイアウト結果で CSS が表示する番号も確認する。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {execFileSync} = require('node:child_process');
const {pathToFileURL} = require('node:url');
const root = path.resolve(__dirname, '..');
const resolved = JSON.parse(execFileSync(process.execPath,
  [path.join(root, 'bin_internal/resolve-node-components.js')], {encoding: 'utf8'}));
const puppeteer = require(resolved.paths.puppeteer);
const {buildBrowserLaunchOptions} = require('../bin_internal/browser-launch-options');
const python = process.env.BIN_TEST_PYTHON || path.join(root, 'livedocs/.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-heading-'));

function generate() {
  execFileSync(python, ['-X', 'utf8', '-c', `
import sys, pathlib, shutil, subprocess
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / 'bin_test'))
from test_heading_numbering import render, postprocess
root, target = map(pathlib.Path, sys.argv[1:])
source = (root / 'docs/sample/heading.md').read_text(encoding='utf-8')
source += '\\n\\n## Reset parent\\n\\n###### Skip level\\n'
source += '\\n\\n##### Numeric parent\\n\\n'
source += '\\n\\n'.join('###### Letter ' + str(i) for i in range(1, 28))
for template in ('html-template.html', 'html-simple-template.html'):
    output = render(source, target, template)
    postprocess(output)
docs = target / 'src'
docs.mkdir()
(docs / 'index.md').write_text(source, encoding='utf-8')
shutil.copyfile(root / 'livedocs/assets/docsfw-pandoc-style.css', docs / 'style.css')
config = target / 'mkdocs.yml'
hook = (root / 'livedocs/bin/livedocs_heading_numbering_hook.py').as_posix()
config.write_text('site_name: Heading test\\ndocs_dir: src\\nsite_dir: site\\n'
    'theme:\\n  name: material\\n  font: false\\nextra_css: [style.css]\\n'
    'markdown_extensions:\\n  - toc:\\n      toc_depth: 6\\nhooks:\\n  - "' + hook + '"\\n', encoding='utf-8')
subprocess.run([sys.executable, '-m', 'mkdocs', 'build', '--strict', '-f', str(config)], check=True)
plain = subprocess.check_output(['pandoc', '-t', 'html', '--wrap=none'], input=source, encoding='utf-8')
(target / 'plain.html').write_text(plain, encoding='utf-8')
`, root, temporary], {stdio: 'inherit'});
}

async function headingNames(page) {
  // CSS カウンターはレイアウト後に確定する。
  await page.screenshot();
  const session = await page.createCDPSession();
  const snapshot = await session.send('DOMSnapshot.captureSnapshot', {computedStyles: []});
  await session.detach();
  const {nodes, layout} = snapshot.documents[0];
  const headings = new Map();
  nodes.nodeName.forEach((name, index) => {
    if (/^H[1-6]$/.test(snapshot.strings[name])) headings.set(index, '');
  });
  layout.nodeIndex.forEach((index, row) => {
    let ancestor = index;
    while (ancestor >= 0 && !headings.has(ancestor)) ancestor = nodes.parentIndex[ancestor];
    if (ancestor >= 0 && layout.text[row] >= 0) {
      headings.set(ancestor, headings.get(ancestor) + snapshot.strings[layout.text[row]]);
    }
  });
  return [...headings.values()].map(text => text.trim().replace(/\s+/g, ' '));
}

(async () => {
  let browser;
  let passed = false;
  try {
    generate();
    browser = await puppeteer.launch(buildBrowserLaunchOptions({headless: true,
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH, args: ['--no-sandbox']}));
    const page = await browser.newPage();
    // Pandoc の実体番号を基準に CSS 採番・目次を比較する。
    await page.goto(pathToFileURL(path.join(temporary, 'html-simple-template.html.html')).href);
    const expected = (await headingNames(page)).filter(s => s !== '見出しのサンプル');
    await page.goto(pathToFileURL(path.join(temporary, 'site/index.html')).href);
    const actual = (await headingNames(page)).filter(s => s !== '見出しのサンプル');
    // 失敗時に残す一時ディレクトリで、表示を目視確認できるようにする。
    await page.screenshot({path: path.join(temporary, 'mkdocs.png'), fullPage: true});
    assert.deepEqual(actual, expected, 'MkDocs 本文の CSS 採番');
    const toc = await page.$eval('.md-nav--secondary',
      nav => [...nav.querySelectorAll('.md-nav__link .md-ellipsis')]
        .map(n => n.textContent.trim().replace(/\s+/g, ' ')));
    assert.deepEqual(toc, expected, 'MkDocs 目次と本文の採番');
    const example = fs.readFileSync(path.join(root, 'docs/mpe-heading-numbering.md'), 'utf8')
      .match(/```css\r?\n([\s\S]*?)```/)[1];
    const plain = fs.readFileSync(path.join(temporary, 'plain.html'), 'utf8');
    await page.setContent('<style>' + example + '</style><div class="markdown-preview">' + plain + '</div>');
    assert.deepEqual((await headingNames(page)).slice(1), expected, 'MPE style.less 掲載例の CSS 採番');
    console.log('PASS: Pandoc / MkDocs 本文・目次 / MPE CSS、連続・リセット・階層飛ばし・27番目');
    passed = true;
  } finally {
    if (browser) await browser.close();
    const absolute = path.resolve(temporary);
    if (!passed) {
      console.error('Visual fixture: ' + absolute);
    } else if (absolute.startsWith(path.resolve(os.tmpdir()) + path.sep) &&
        path.basename(absolute).startsWith('docsfw-heading-')) {
      fs.rmSync(absolute, {recursive: true, force: true});
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
