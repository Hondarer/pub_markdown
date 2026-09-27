/*!
 * docsfw-tokenize.js
 * CJK bigram + ASCII word tokenizer.
 * Shared by Node (build-search-index.mjs) and browser (docsfw-search.js).
 *
 * Node:    const tokenize = require('./docsfw-tokenize.js');
 * Browser: loads as <script src="docsfw-tokenize.js"> → window.docsfwTokenize
 */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.docsfwTokenize = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  /**
   * Returns true if the character is in a CJK range.
   * Covers Hiragana/Katakana, CJK Unified Ideographs (incl. Extension A),
   * Compatibility Ideographs, Halfwidth/Fullwidth Forms, etc.
   */
  function isCjk(ch) {
    var cp = ch.charCodeAt(0);
    return (cp >= 0x3040 && cp <= 0x9FFF)   // Hiragana, Katakana, CJK Unif.
        || (cp >= 0xF900 && cp <= 0xFAFF)   // CJK Compatibility Ideographs
        || (cp >= 0xFF00 && cp <= 0xFFEF);  // Halfwidth/Fullwidth Forms
  }

  /**
   * Tokenize a string.
   * - CJK runs  → overlapping 2-grams (single char → uni-gram)
   * - ASCII/num runs → split on non-word boundaries, lowercase
   *
   * @param {string} text
   * @returns {string[]}
   */
  function tokenize(text) {
    if (!text) { return []; }

    var tokens = [];
    var len = text.length;
    var i = 0;

    while (i < len) {
      var ch = text[i];

      if (isCjk(ch)) {
        // Collect CJK run
        var runStart = i;
        while (i < len && isCjk(text[i])) {
          i++;
        }
        var run = text.slice(runStart, i);
        if (run.length === 1) {
          tokens.push(run);
        } else {
          for (var j = 0; j < run.length - 1; j++) {
            tokens.push(run.slice(j, j + 2));
          }
        }
      } else if (/[a-zA-Z0-9_-]/.test(ch)) {
        // Collect ASCII/numeric run
        var wordStart = i;
        while (i < len && /[a-zA-Z0-9_-]/.test(text[i]) && !isCjk(text[i])) {
          i++;
        }
        var word = text.slice(wordStart, i).toLowerCase();
        if (word.length > 0) { tokens.push(word); }
      } else {
        i++;
      }
    }

    return tokens;
  }

  return tokenize;
}));
