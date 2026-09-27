#!/usr/bin/env node
/**
 * build-search-index.mjs
 *
 * Walks a pub_markdown HTML output directory, extracts content from each page,
 * builds a MiniSearch full-text index (with CJK bigram tokenization), and
 * writes search-index.js to the html root.
 *
 * The output file sets two globals used by docsfw-search.js:
 *   window.__DOCSFW_INDEX__  - serialized MiniSearch index (plain JS object)
 *   window.__DOCSFW_DOCS__   - [{id, url, title}, ...] for lightweight listing
 *
 * Usage: node build-search-index.mjs <html-root>
 */

import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { createRequire } from 'node:module';
import MiniSearch from 'minisearch';

const require = createRequire(import.meta.url);
const tokenize = require('./docsfw-tokenize.js');

// ---------------------------------------------------------------------------
// Argument
// ---------------------------------------------------------------------------

const htmlRoot = process.argv[2];
if (!htmlRoot) {
  process.stderr.write('Usage: node build-search-index.mjs <html-root>\n');
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Files to exclude from indexing (our own generated assets)
// ---------------------------------------------------------------------------

const SKIP_NAMES = new Set([
  'search-index.js',
  'nav-tree.js',
  'minisearch.min.js',
  'docsfw-search.js',
  'docsfw-nav.js',
  'docsfw-tokenize.js',
  'docsfw-ui.css',
  'html-style.css',
  'mermaid.min.js',
]);

// ---------------------------------------------------------------------------
// HTML utilities
// ---------------------------------------------------------------------------

/**
 * Strip HTML tags and decode basic entities.
 * @param {string} html
 * @returns {string}
 */
function htmlToText(html) {
  return html
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, ' ')
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/&#\d+;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Extract text from <title>...</title>.
 * @param {string} html
 * @returns {string}
 */
function extractTitle(html) {
  const m = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  return m ? htmlToText(m[1]) : '';
}

/**
 * Extract the main content block.
 * Uses <main id="docsfw-content"> when available (added by our template),
 * falls back to <body> for pages generated before the template update.
 * @param {string} html
 * @returns {string}
 */
function extractMain(html) {
  const mainM = html.match(/<main\s[^>]*id="docsfw-content"[^>]*>([\s\S]*?)<\/main>/i);
  if (mainM) { return mainM[1]; }
  const bodyM = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  return bodyM ? bodyM[1] : html;
}

/**
 * Extract text from h1-h3 headings in a content block.
 * @param {string} contentHtml
 * @returns {string}
 */
function extractHeadings(contentHtml) {
  const parts = [];
  const re = /<h[1-3][^>]*>([\s\S]*?)<\/h[1-3]>/gi;
  let m;
  while ((m = re.exec(contentHtml)) !== null) {
    const t = htmlToText(m[1]);
    if (t) { parts.push(t); }
  }
  return parts.join(' ');
}

// ---------------------------------------------------------------------------
// Walk HTML files
// ---------------------------------------------------------------------------

/**
 * Recursively yield relative paths of all *.html files under dir.
 * @param {string} dir
 * @yields {string} relative path from htmlRoot (POSIX separators)
 */
function* walkHtml(dir) {
  const entries = readdirSync(dir).sort();
  for (const entry of entries) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      yield* walkHtml(full);
    } else if (entry.endsWith('.html') && !SKIP_NAMES.has(entry)) {
      yield relative(htmlRoot, full).replace(/\\/g, '/');
    }
  }
}

// ---------------------------------------------------------------------------
// Build index
// ---------------------------------------------------------------------------

/** Maximum text characters to index per page (keeps index size manageable). */
const MAX_TEXT_CHARS = 30000;

const docs = [];
let id = 0;

for (const relPath of walkHtml(htmlRoot)) {
  const absPath = join(htmlRoot, relPath);
  let html;
  try {
    html = readFileSync(absPath, 'utf8');
  } catch (e) {
    process.stderr.write(`Warning: cannot read ${absPath}: ${e.message}\n`);
    continue;
  }

  const title    = extractTitle(html);
  const mainHtml = extractMain(html);
  const headings = extractHeadings(mainHtml);
  let   text     = htmlToText(mainHtml);
  if (text.length > MAX_TEXT_CHARS) { text = text.slice(0, MAX_TEXT_CHARS); }

  docs.push({ id, url: relPath, title, headings, text });
  id++;
}

process.stdout.write(`  Indexing ${docs.length} pages...\n`);

const miniSearch = new MiniSearch({
  fields:       ['title', 'headings', 'text'],
  storeFields:  ['url', 'title'],
  tokenize,
  processTerm:  (term) => term,
  searchOptions: {
    boost:  { title: 5, headings: 3, text: 1 },
    fuzzy:  0.1,
  },
});

miniSearch.addAll(docs);

// ---------------------------------------------------------------------------
// Write output
// ---------------------------------------------------------------------------

// MiniSearch.loadJSON() requires a JSON string (it calls JSON.parse internally).
// We store the serialized index as a JS string literal so the browser can pass
// window.__DOCSFW_INDEX__ directly to MiniSearch.loadJSON() without re-stringify.
// JSON.stringify(str) wraps the JSON string in double quotes and escapes internal quotes.
const indexJson = JSON.stringify(JSON.stringify(miniSearch));

// Slim doc list for potential use in nav / future features.
const docsJson = JSON.stringify(
  docs.map((d) => ({ id: d.id, url: d.url, title: d.title }))
);

const output =
  `/* docsfw search-index.js - auto-generated by build-search-index.mjs, do not edit */\n` +
  `window.__DOCSFW_INDEX__ = ${indexJson};\n` +
  `window.__DOCSFW_DOCS__ = ${docsJson};\n`;

const outPath = join(htmlRoot, 'search-index.js');
writeFileSync(outPath, output, 'utf8');

const kbSize = (output.length / 1024).toFixed(0);
process.stdout.write(`  Written: search-index.js (${kbSize} KB)\n`);
