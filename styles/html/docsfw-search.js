/*!
 * docsfw-search.js
 * Full-text search UI for pub_markdown HTML output.
 *
 * Lazy-loads heavy assets on first user interaction:
 *   1. minisearch.min.js   (MiniSearch UMD bundle)
 *   2. docsfw-tokenize.js  (shared CJK bigram tokenizer)
 *   3. search-index.js     (pre-built index + doc list)
 *
 * Globals consumed:
 *   window.__DOCSFW_BASE__     - relative path to html root (e.g. "../../")
 *   window.__DOCSFW_CURRENT__  - this page's path relative to html root
 *   window.__DOCSFW_INDEX__    - MiniSearch serialized index (object, from search-index.js)
 *   window.__DOCSFW_DOCS__     - [{id, url, title}, ...] (from search-index.js)
 *
 * Rendered into:
 *   #docsfw-search-container   - input box injected here
 *   #docsfw-search-results     - result overlay rendered here
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  var _ms          = null;   // MiniSearch instance (null until loaded)
  var _loading     = false;  // loading in progress
  var _loadQueue   = [];     // callbacks waiting for load
  var _input       = null;   // <input> element
  var _results     = null;   // result overlay element
  var _lastQuery   = '';

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  var base = (window.__DOCSFW_BASE__ != null) ? String(window.__DOCSFW_BASE__) : '';

  function esc(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function loadScript(url, cb) {
    var s = document.createElement('script');
    s.src = url;
    s.onload = cb;
    s.onerror = function () {
      console.error('[docsfw-search] Failed to load: ' + url);
      cb();
    };
    document.head.appendChild(s);
  }

  // ---------------------------------------------------------------------------
  // Lazy asset loading
  // ---------------------------------------------------------------------------

  /**
   * Load MiniSearch + tokenizer + index, then call cb(err).
   * Safe to call multiple times; queues callbacks if already loading.
   */
  function ensureLoaded(cb) {
    if (_ms) { cb(null); return; }
    _loadQueue.push(cb);
    if (_loading) { return; }
    _loading = true;

    setStatus('loading');

    loadScript(base + 'minisearch.min.js', function () {
      loadScript(base + 'docsfw-tokenize.js', function () {
        loadScript(base + 'search-index.js', function () {
          var err = null;
          try {
            var MiniSearch = window.MiniSearch;
            var tokenize   = window.docsfwTokenize;
            var indexData  = window.__DOCSFW_INDEX__;

            if (!MiniSearch || !tokenize || !indexData) {
              throw new Error('Missing search assets');
            }

            // window.__DOCSFW_INDEX__ is a JSON string (set by search-index.js).
            // MiniSearch.loadJSON() accepts a JSON string directly.
            var indexStr = typeof indexData === 'string'
              ? indexData
              : JSON.stringify(indexData); // fallback for unexpected object form

            _ms = MiniSearch.loadJSON(indexStr, {
              fields:      ['title', 'headings', 'text'],
              storeFields: ['url', 'title'],
              tokenize:    tokenize,
              processTerm: function (term) { return term; },
            });
          } catch (e) {
            err = e;
            console.error('[docsfw-search] Init error:', e);
          }

          setStatus(null);

          var queue = _loadQueue.slice();
          _loadQueue = [];
          for (var i = 0; i < queue.length; i++) {
            queue[i](err);
          }
        });
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Result overlay
  // ---------------------------------------------------------------------------

  function showOverlay() {
    if (_results) { _results.classList.add('visible'); }
  }

  function hideOverlay() {
    if (_results) { _results.classList.remove('visible'); }
  }

  function setStatus(type) {
    if (!_results) { return; }
    if (type === 'loading') {
      _results.innerHTML = '<div class="docsfw-result-loading">検索インデックスを読み込んでいます...</div>';
      showOverlay();
    } else if (type === null) {
      hideOverlay();
      _results.innerHTML = '';
    }
  }

  function renderResults(hits, query) {
    if (!_results) { return; }
    if (hits.length === 0) {
      _results.innerHTML =
        '<div class="docsfw-result-empty">「' + esc(query) + '」に一致するページは見つかりませんでした。</div>';
    } else {
      var html = '';
      var limit = Math.min(hits.length, 20);
      for (var i = 0; i < limit; i++) {
        var h = hits[i];
        var url  = h.url  || '';
        var title = h.title || url;
        var fullUrl = base + url;
        html +=
          '<div class="docsfw-result-item" data-href="' + esc(fullUrl) + '">' +
            '<div class="docsfw-result-title">' + esc(title) + '</div>' +
            '<div class="docsfw-result-url">'   + esc(url)   + '</div>' +
          '</div>';
      }
      if (hits.length > 20) {
        html +=
          '<div class="docsfw-result-empty">他 ' + (hits.length - 20) + ' 件（検索語を絞ると絞り込めます）</div>';
      }
      _results.innerHTML = html;
    }
    showOverlay();
  }

  // ---------------------------------------------------------------------------
  // Search
  // ---------------------------------------------------------------------------

  var _debounceTimer = null;

  function doSearch(query) {
    if (!query || !query.trim()) {
      hideOverlay();
      _lastQuery = '';
      return;
    }
    if (query === _lastQuery) { return; }
    _lastQuery = query;

    ensureLoaded(function (err) {
      if (err || !_ms) { return; }
      if (query !== _lastQuery) { return; } // stale

      var hits = _ms.search(query, {
        boost:       { title: 5, headings: 3 },
        fuzzy:       0.1,
        prefix:      true,
      });
      renderResults(hits, query);
    });
  }

  function onInput() {
    var q = _input ? _input.value : '';
    clearTimeout(_debounceTimer);
    if (!q.trim()) { hideOverlay(); return; }
    _debounceTimer = setTimeout(function () { doSearch(q); }, 200);
  }

  // ---------------------------------------------------------------------------
  // Build UI
  // ---------------------------------------------------------------------------

  function buildUI() {
    var container = document.getElementById('docsfw-search-container');
    _results      = document.getElementById('docsfw-search-results');
    if (!container || !_results) { return; }

    // Input
    _input = document.createElement('input');
    _input.type        = 'search';
    _input.id          = 'docsfw-search-input';
    _input.placeholder = '検索...';
    _input.autocomplete = 'off';
    _input.setAttribute('aria-label', 'ドキュメント検索');

    _input.addEventListener('input', onInput);

    _input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        hideOverlay();
        _input.blur();
      } else if (e.key === 'Enter') {
        // Navigate to first result
        var first = _results.querySelector('.docsfw-result-item');
        if (first) { window.location.href = first.getAttribute('data-href'); }
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        var items = _results.querySelectorAll('.docsfw-result-item');
        if (items.length > 0) { items[0].focus(); }
      }
    });

    container.appendChild(_input);

    // Keyboard navigation in results
    _results.addEventListener('click', function (e) {
      var item = e.target.closest('.docsfw-result-item');
      if (item) { window.location.href = item.getAttribute('data-href'); }
    });

    _results.addEventListener('keydown', function (e) {
      var items = Array.prototype.slice.call(_results.querySelectorAll('.docsfw-result-item'));
      var idx = items.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (idx + 1 < items.length) { items[idx + 1].focus(); }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (idx > 0) { items[idx - 1].focus(); } else { _input.focus(); }
      } else if (e.key === 'Enter' && idx >= 0) {
        window.location.href = items[idx].getAttribute('data-href');
      } else if (e.key === 'Escape') {
        hideOverlay();
        _input.focus();
      }
    });

    // Close overlay when clicking outside
    document.addEventListener('click', function (e) {
      if (!container.contains(e.target) && !_results.contains(e.target)) {
        hideOverlay();
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Entry point
  // ---------------------------------------------------------------------------

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildUI);
  } else {
    buildUI();
  }
}());
