'use strict';

// 図の共通資産と、file:// と単一 HTML で使う自己完結フレームを作る。
// フレーム HTML はエンジン本体を埋め込み、別のローカル JavaScript を読まない。
const fs = require('fs');
const path = require('path');
const COMMON_DIR = path.join(__dirname, '..', 'styles', 'browser');
const MERMAID_FRAME = 'docsfw-mermaid-frame.html';
const PLANTUML_FRAME = 'docsfw-plantuml-frame.html';

// Mermaid は iframe の DOM で文字寸法を測る。親ページの iframe 幅は
// documentElement.clientWidth (下限 320px)、高さは 4000px。
// フレーム内のフォントと測定要素は、HTTP / file:// / srcdoc でこの CSS に揃える。
const MEASURE_CSS = [
  'html, body { margin: 0; padding: 0; background: transparent; }',
  'body {',
  '  font-family: "trebuchet ms", verdana, arial, sans-serif;',
  '  font-size: 16px;',
  '  line-height: normal;',
  '}',
  '.docsfw-diagram-measure { position: absolute; left: 0; top: 0; }',
].join('\n');

function writeChanged(destination, content) {
  const data = Buffer.isBuffer(content) ? content : Buffer.from(content, 'utf8');
  if (fs.existsSync(destination) && fs.readFileSync(destination).equals(data)) { return; }
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.writeFileSync(destination, data);
}

function escapeForInlineScript(text) {
  return text.replace(/<\/script/gi, '<\\/script');
}

function validRequest(source) {
  return [
    'function validRequest(data) {',
    '  return !!data && data.kind === "render" && typeof data.requestId === "string" && data.requestId &&',
    '    typeof data.source === "string" && typeof data.dark === "boolean" && typeof data.portable === "boolean";',
    '}',
  ].join('\n');
}

function mermaidDriver() {
  return [
    validRequest(),
    'var host = document.createElement("div");',
    'host.className = "docsfw-diagram-measure";',
    'document.body.appendChild(host);',
    'function post(message) { parent.postMessage(message, "*"); }',
    'function whenFontsReady() {',
    '  if (document.fonts && document.fonts.ready) { return document.fonts.ready; }',
    '  return Promise.resolve();',
    '}',
    'function afterLayout() {',
    '  return new Promise(function (resolve) { requestAnimationFrame(function () { resolve(); }); });',
    '}',
    'window.addEventListener("message", function (event) {',
    '  if (event.source !== parent) { return; }',
    '  var data = event.data;',
    '  if (!validRequest(data)) { return; }',
    '  whenFontsReady().then(afterLayout).then(function () {',
    '    host.replaceChildren();',
    '    window.mermaid.initialize({',
    '      startOnLoad: false,',
    '      theme: data.dark ? "dark" : "default",',
    '      securityLevel: "loose",',
    '      htmlLabels: !data.portable',
    '    });',
    '    return window.mermaid.render("docsfw-m-" + data.requestId, data.source, host);',
    '  }).then(function (result) {',
    '    post({ kind: "result", requestId: data.requestId, svg: result && result.svg ? result.svg : "" });',
    '  }, function (error) {',
    '    post({ kind: "result", requestId: data.requestId, error: String((error && error.message) || error) });',
    '  });',
    '});',
    'whenFontsReady().then(function () {',
    '  if (!window.mermaid || typeof window.mermaid.render !== "function") {',
    '    post({ kind: "init-error", error: "Mermaid の描画エンジンを読み込めません。" });',
    '    return;',
    '  }',
    '  post({ kind: "ready" });',
    '}, function (error) {',
    '  post({ kind: "init-error", error: String((error && error.message) || error) });',
    '});',
  ].join('\n');
}

function writeMermaidFrame(mermaidJs, outputDir) {
  if (!mermaidJs || !fs.existsSync(mermaidJs)) {
    throw new Error('mermaid.min.js がありません。bin_internal/resolve-node-components.js の解決結果を確認してください。');
  }
  const source = fs.readFileSync(mermaidJs, 'utf8');
  const html = '<!doctype html><html><head><meta charset="utf-8"><style>\n' + MEASURE_CSS +
    '\n</style></head><body>\n<script>\n' + escapeForInlineScript(source) +
    '\n</script>\n<script>\n' + mermaidDriver() + '\n</script>\n</body></html>\n';
  writeChanged(path.join(outputDir, MERMAID_FRAME), html);
}

function plantumlDriver() {
  return [
    'let enginePromise;',
    'function loadEngine() {',
    '  if (!enginePromise) {',
    '    const bytes = Uint8Array.from(atob(ENGINE_BASE64), function (c) { return c.charCodeAt(0); });',
    '    const url = URL.createObjectURL(new Blob([bytes], { type: "text/javascript" }));',
    '    enginePromise = import(url);',
    '  }',
    '  return enginePromise;',
    '}',
    validRequest(),
    'function post(message) { parent.postMessage(message, "*"); }',
    'loadEngine().then(function (engine) {',
    '  window.addEventListener("message", function (event) {',
    '    if (event.source !== parent) { return; }',
    '    const data = event.data;',
    '    if (!validRequest(data)) { return; }',
    '    engine.renderToString(data.source.split("\\n"), function (svg) {',
    '      post({ kind: "result", requestId: data.requestId, svg: svg });',
    '    }, function (error) {',
    '      post({ kind: "result", requestId: data.requestId, error: String((error && error.message) || error) });',
    '    }, { dark: data.dark });',
    '  });',
    '  post({ kind: "ready" });',
    '}, function (error) {',
    '  post({ kind: "init-error", error: String((error && error.message) || error) });',
    '});',
  ].join('\n');
}

function writePlantumlFrame(sourceDir, outputDir) {
  const engineSource = fs.readFileSync(path.join(sourceDir, 'plantuml.js'));
  // 先読みしたアイコンも内部ローダーの完了表へ登録しないと、同名ファイルを再取得する。
  // 更新時に黙って file:// 対応を失わないよう、利用する内部契約を検査する。
  // see: https://unpkg.com/@plantuml/core@1.2026.7/plantuml.js
  if (!engineSource.includes('__pl_script_state')) {
    throw new Error('@plantuml/core のローダー契約が変わりました。アイコンの埋め込み処理を確認してください。');
  }
  const engine = engineSource.toString('base64');
  const libraries = ['viz-global.js', 'emoji.js', 'openiconic.js']
    .map(name => fs.readFileSync(path.join(sourceDir, name), 'utf8')).join('\n;\n');
  const license = fs.readFileSync(path.join(sourceDir, 'LICENSE'), 'utf8');
  // ローカル ES モジュールの外部読み込みは file:// で CORS に阻まれる。
  // Blob URL の自己完結したモジュールと classic script を使い、import の相対参照を残さない。
  // see: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules
  // iPhone の Edge では data URL の import でページが停止し、Blob URL では描画できた。
  // see: https://github.com/Hondarer/plantuml-core-test/blob/main/docs/13.html
  const driver = plantumlDriver().replace('ENGINE_BASE64', JSON.stringify(engine));
  const html = '<!doctype html><html><head><meta charset="utf-8"></head><body>\n' +
    '<!--\n' + license.replace(/--/g, '- -').replace(/\*\//g, '* /') + '\n-->\n' +
    '<script>\n' + escapeForInlineScript(libraries) + '\n;\n' +
    'window.__pl_script_state = window.__pl_script_state || Object.create(null);\n' +
    '["emoji.js", "openiconic.js"].forEach(function (name) { window.__pl_script_state[name] = { state: "loaded" }; });\n' +
    '</script>\n' +
    '<script type="module">\n' + driver + '\n</script>\n' +
    '</body></html>\n';
  writeChanged(path.join(outputDir, PLANTUML_FRAME), html);
  writeChanged(path.join(outputDir, 'docsfw-plantuml-LICENSE.txt'), license);
}

function buildBrowserAssets(sourceDir, outputDir, mermaidJs) {
  for (const name of fs.readdirSync(COMMON_DIR)) {
    writeChanged(path.join(outputDir, name), fs.readFileSync(path.join(COMMON_DIR, name)));
  }
  writeChanged(path.join(outputDir, 'docsfw-theme.js'), fs.readFileSync(path.join(__dirname, '..', 'styles', 'html', 'docsfw-theme.js')));
  writePlantumlFrame(sourceDir, outputDir);
  if (mermaidJs) { writeMermaidFrame(mermaidJs, outputDir); }
}

module.exports = { buildBrowserAssets, writeMermaidFrame, writePlantumlFrame, MERMAID_FRAME, PLANTUML_FRAME };

if (require.main === module) {
  const args = process.argv.slice(2);
  if (args[0] === '--mermaid' && args.length === 3) {
    writeMermaidFrame(args[1], args[2]);
  } else if (args.length === 2 || args.length === 3) {
    buildBrowserAssets(args[0], args[1], args[2]);
  } else {
    console.error('Usage: node build-browser-assets.js <plantuml-core-dir> <output-dir> [mermaid-js]');
    console.error('       node build-browser-assets.js --mermaid <mermaid-js> <output-dir>');
    process.exitCode = 1;
  }
}
