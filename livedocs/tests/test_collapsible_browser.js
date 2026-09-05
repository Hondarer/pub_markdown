// 実行: node livedocs/tests/test_collapsible_browser.js (docsfw ルートから)
// 一時サイトだけを生成し、MkDocs Material 上の開閉と履歴を検証する。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const puppeteer = require(path.join(root, 'bin/node_modules/puppeteer'));
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'docsfw-collapsible-'));
const python = process.env.PYTHON || path.join(root, 'livedocs/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

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
import sys, pathlib, subprocess
root, target = map(pathlib.Path, sys.argv[1:])
sys.path.insert(0, str(root / 'livedocs/bin'))
sys.path.insert(0, str(root / 'livedocs/tests'))
from test_expand_toc import _nested_index
from expand_toc import expand_toc_commands, render_toc, parse_toc_params
from stage_livedocs import convert_collapsible_list_fences
from vendor_assets import vendor_own_assets
docs = target / 'docs'
docs.mkdir()
index = _nested_index()
blocks = ['# Test']
static_blocks = []
sample = (root / 'docs/sample/README.md').read_text(encoding='utf-8')
assert '\n\\toc depth=-1\n' in sample
for level in ('', '0', '1', '2', '-1'):
    command = r'\toc depth=-1' + (' open-level=' + level if level else '')
    blocks.append(expand_toc_commands(command, index, 'c-platform/index.md'))
    attrs = ' open-level=' + level if level else ''
    static_blocks.append('::: {.collapsible-list' + attrs + '}\n' + render_toc(index, 'c-platform/index.md', parse_toc_params(command)) + '\n:::')
blocks.append(convert_collapsible_list_fences('::: {.collapsible-list open-level=1}\n- parent\n    - child\n        - grandchild\n:::'))
static_blocks.append('::: {.collapsible-list open-level=1}\n- parent\n    - child\n        - grandchild\n:::')
blocks.append('- ordinary\n    - child\n\n[Other](other.md)')
(docs / 'index.md').write_text('\n\n'.join(blocks), encoding='utf-8')
(docs / 'other.md').write_text('# Other\n\n[Home](index.md)', encoding='utf-8')
for file in ('api-cheatsheet.md', 'sibling.md', 'functional-spec/index.md', 'functional-spec/argparser.md', 'functional-spec/nested/index.md', 'functional-spec/nested/deep.md'):
    dest = docs / file
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text('# Linked page', encoding='utf-8')
vendor_own_assets(str(docs / 'assets'))
(target / 'mkdocs.yml').write_text('''site_name: Test
theme:
  name: material
  font: false
markdown_extensions: [md_in_html, nl2br]
extra_css:
  - assets/docsfw-pandoc-style.css
  - assets/docsfw-collapsible-list.css
extra_javascript:
  - assets/docsfw-collapsible-list.js
''', encoding='utf-8')
static_html = subprocess.run(['pandoc', '-f', 'markdown', '-t', 'html5', '-L', str(root / 'bin/pandoc-filters/insert-toc.lua')], input='\n\n'.join(static_blocks), capture_output=True, text=True, check=True).stdout
template = (root / 'styles/html/html-template.html').read_text(encoding='utf-8')
start = template.index('<script>', template.index('展開可能リスト (collapsible-list)'))
end = template.index('</script>', start) + len('</script>')
(target / 'reference.html').write_text('<!DOCTYPE html><meta charset="utf-8">' + static_html + template[start:end].replace('$$', '$'), encoding='utf-8')
`});
    run(python, ['-m', 'mkdocs', 'build', '--strict', '-f', path.join(temporary, 'mkdocs.yml')]);
    fs.copyFileSync(path.join(temporary, 'reference.html'), path.join(temporary, 'site/reference.html'));
    server = http.createServer((request, response) => {
      let pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      if (pathname.endsWith('/')) pathname += 'index.html';
      const file = path.join(temporary, 'site', pathname);
      if (!fs.existsSync(file)) { response.writeHead(404); response.end(); return; }
      const types = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css'};
      response.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
      response.end(fs.readFileSync(file));
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const url = `http://127.0.0.1:${server.address().port}/`;
    browser = await puppeteer.launch({headless: true, args: ['--no-sandbox', '--disable-crash-reporter']});
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    const states = () => page.evaluate(() => Array.from(document.querySelectorAll('.collapsible-list')).map(c =>
      Array.from(c.querySelectorAll('details')).map(d => d.open)));
    const initial = [[false, false, false], [false, false, false], [true, false, false], [true, true, false], [true, true, true], [true, false]];
    assert.deepEqual(await states(), initial);
    const reference = await browser.newPage();
    await reference.goto(url + 'reference.html');
    const referenceStates = await reference.evaluate(() => Array.from(document.querySelectorAll('.collapsible-list')).map(c => Array.from(c.querySelectorAll('details')).map(d => d.open)));
    assert.deepEqual(referenceStates, initial);
    await reference.close();
    assert.equal(await page.$eval('article', e => e.querySelectorAll('details').length), 17);
    const first = '.collapsible-list details > summary';
    await page.focus(first);
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('.collapsible-list details').open);
    await page.waitForFunction(() => JSON.parse(sessionStorage.getItem('collapsible-state:/'))['0'] === true);
    // リンクは開閉操作と独立して遷移する。
    await Promise.all([page.waitForNavigation(), page.click('.collapsible-list a[href="api-cheatsheet/"]')]);
    assert.ok(page.url().endsWith('/api-cheatsheet/'));
    await page.goBack();
    assert.equal((await states())[0][0], true);
    await page.reload();
    assert.deepEqual(await states(), initial);
    // 空の保存オブジェクトも全閉状態として復元する。
    await page.evaluate(() => document.querySelectorAll('.collapsible-list details').forEach(d => { d.open = false; }));
    await page.waitForFunction(() => sessionStorage.getItem('collapsible-state:/') === '{}');
    await page.goto(url + 'other/');
    await page.goBack();
    assert.ok((await states()).flat().every(value => !value));
    await page.goForward();
    assert.ok(page.url().endsWith('/other/'));
    await page.goto(url);
    assert.deepEqual(await states(), initial);
    for (const scheme of ['default', 'slate']) {
      await page.evaluate(s => document.body.setAttribute('data-md-color-scheme', s), scheme);
      const style = await page.$eval('.collapsible-list details', d => ({border: getComputedStyle(d).borderWidth, size: getComputedStyle(d).fontSize, parentSize: getComputedStyle(d.parentElement).fontSize}));
      assert.equal(style.border, '0px');
      assert.equal(style.size, style.parentSize);
    }
    await page.addScriptTag({path: path.join(root, 'livedocs/assets/docsfw-collapsible-list.js')});
    assert.deepEqual(await states(), initial);
    assert.equal(await page.$eval('article', e => e.querySelectorAll('details').length), 17);
    const blocked = await browser.newPage();
    await blocked.evaluateOnNewDocument(() => {
      Object.defineProperty(window, 'sessionStorage', {get() { throw new Error('blocked'); }});
    });
    await blocked.goto(url);
    assert.equal(await blocked.$eval('.collapsible-list details', d => d.open), false);
    await blocked.focus(first);
    await blocked.keyboard.press('Enter');
    await blocked.waitForFunction(() => document.querySelector('.collapsible-list details').open);
    assert.deepEqual(errors, []);
    console.log('PASS: MkDocs build, Pandoc parity, sample default, levels, keyboard, links, history, reload, storage, themes, repeated initialization');
  } finally {
    if (browser) await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
    fs.rmSync(temporary, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
