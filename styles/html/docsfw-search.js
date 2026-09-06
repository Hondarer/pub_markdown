/*!
 * Pandoc HTML のヘッダー検索。MiniSearch と索引は初回操作時に読み込む。
 */
(function () {
  'use strict';

  var base = window.__DOCSFW_BASE__ == null ? '' : String(window.__DOCSFW_BASE__);
  var isJa = (document.documentElement.lang || 'ja').toLowerCase().indexOf('ja') === 0;
  var mobile = window.matchMedia('(max-width: 59.984375em)');
  var miniSearch = null;
  var loading = false;
  var queue = [];
  var input;
  var results;
  var container;
  var lastQuery = '';
  var debounceTimer;
  var selectedIndex = -1;

  var text = isJa ? {
    open: '検索を開く', back: '検索を閉じる', label: 'ドキュメント検索', placeholder: '検索…',
    loading: '検索インデックスを読み込んでいます…', unavailable: '検索インデックスを読み込めませんでした。',
    emptyBefore: '「', emptyAfter: '」に一致するページは見つかりませんでした。',
    moreBefore: '他 ', moreAfter: ' 件（検索語を絞ると絞り込めます）'
  } : {
    open: 'Open search', back: 'Close search', label: 'Document search', placeholder: 'Search…',
    loading: 'Loading the search index…', unavailable: 'The search index could not be loaded.',
    emptyBefore: 'No pages matched “', emptyAfter: '”.', moreBefore: '', moreAfter: ' more results'
  };

  function esc(value) {
    return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function loadScript(url, done) {
    var script = document.createElement('script');
    script.src = url;
    script.onload = function () { done(null); };
    script.onerror = function () { done(new Error('Failed to load ' + url)); };
    document.head.appendChild(script);
  }

  function loadSequence(urls, done) {
    var index = 0;
    function next(error) {
      if (error || index === urls.length) { done(error || null); return; }
      loadScript(base + urls[index++], next);
    }
    next(null);
  }

  function ensureLoaded(done) {
    if (miniSearch) { done(null); return; }
    queue.push(done);
    if (loading) { return; }
    loading = true;
    setStatus(text.loading, 'status');
    loadSequence(['minisearch.min.js', 'docsfw-tokenize.js', 'search-index.js'], function (error) {
      if (!error) {
        try {
          if (!window.MiniSearch || !window.docsfwTokenize || !window.__DOCSFW_INDEX__) {
            throw new Error('Missing search data');
          }
          var data = typeof window.__DOCSFW_INDEX__ === 'string' ? window.__DOCSFW_INDEX__ :
            JSON.stringify(window.__DOCSFW_INDEX__);
          miniSearch = window.MiniSearch.loadJSON(data, {
            fields: ['title', 'headings', 'text'], storeFields: ['url', 'title'],
            tokenize: window.docsfwTokenize, processTerm: function (term) { return term; }
          });
        } catch (caught) { error = caught; }
      }
      loading = false;
      if (error) { setStatus(text.unavailable, 'alert'); }
      var waiting = queue.slice(); queue = [];
      for (var i = 0; i < waiting.length; i++) { waiting[i](error); }
    });
  }

  function setExpanded(expanded) {
    input.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    results.classList.toggle('visible', expanded);
  }

  function setStatus(message, role) {
    results.innerHTML = '<div class="docsfw-result-empty" role="' + role + '">' + esc(message) + '</div>';
    setExpanded(true);
  }

  function items() { return Array.prototype.slice.call(results.querySelectorAll('.docsfw-result-item')); }

  function select(index, focus) {
    var options = items();
    if (!options.length) { selectedIndex = -1; input.removeAttribute('aria-activedescendant'); return; }
    selectedIndex = Math.max(0, Math.min(index, options.length - 1));
    for (var i = 0; i < options.length; i++) {
      options[i].setAttribute('aria-selected', i === selectedIndex ? 'true' : 'false');
    }
    input.setAttribute('aria-activedescendant', options[selectedIndex].id);
    if (focus) { options[selectedIndex].focus(); }
  }

  function render(hits, query) {
    selectedIndex = -1;
    if (!hits.length) {
      setStatus(text.emptyBefore + query + text.emptyAfter, 'status');
      return;
    }
    var html = '';
    var limit = Math.min(hits.length, 20);
    for (var i = 0; i < limit; i++) {
      var url = hits[i].url || '';
      var title = hits[i].title || url;
      html += '<a class="docsfw-result-item" id="docsfw-result-' + i + '" role="option" aria-selected="false" href="' +
        esc(base + url) + '"><span class="docsfw-result-title">' + esc(title) + '</span>' +
        '<span class="docsfw-result-url">' + esc(url) + '</span></a>';
    }
    if (hits.length > limit) {
      html += '<div class="docsfw-result-empty">' + text.moreBefore + (hits.length - limit) + text.moreAfter + '</div>';
    }
    results.innerHTML = html;
    setExpanded(true);
  }

  function search(query) {
    if (!query.trim()) { setExpanded(false); lastQuery = ''; return; }
    if (query === lastQuery && miniSearch) { return; }
    lastQuery = query;
    ensureLoaded(function (error) {
      if (error || query !== lastQuery) { return; }
      render(miniSearch.search(query, {
        boost: { title: 5, headings: 3 }, fuzzy: 0.1, prefix: true
      }), query);
    });
  }

  function closeSearch(restoreFocus) {
    document.body.classList.remove('docsfw-search-open');
    setExpanded(false);
    if (restoreFocus && mobile.matches) {
      var opener = container.querySelector('.docsfw-search-icon');
      if (opener) { opener.focus(); }
    }
  }

  function openSearch() {
    document.dispatchEvent(new CustomEvent('docsfw:search-open'));
    document.body.classList.add('docsfw-search-open');
    input.focus();
    if (input.value.trim()) { search(input.value); }
  }

  function onKeydown(event) {
    var options = items();
    if (event.key === 'Escape') {
      event.preventDefault(); closeSearch(true);
    } else if (event.key === 'ArrowDown' && options.length) {
      event.preventDefault(); select(selectedIndex < 0 ? 0 : selectedIndex + 1, true);
    } else if (event.key === 'ArrowUp' && options.length) {
      event.preventDefault();
      if (document.activeElement !== input && selectedIndex <= 0) { selectedIndex = -1; input.focus(); }
      else { select(selectedIndex < 0 ? options.length - 1 : selectedIndex - 1, true); }
    } else if (event.key === 'Enter' && document.activeElement === input && options.length) {
      event.preventDefault(); window.location.href = options[Math.max(0, selectedIndex)].href;
    }
  }

  function build() {
    container = document.getElementById('docsfw-search-container');
    if (!container) { return; }
    container.innerHTML =
      '<button type="button" class="docsfw-search-icon" aria-label="' + esc(text.open) + '">' +
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 3a6.5 6.5 0 0 1 5.18 10.43L21.25 20 20 21.25l-6.57-6.57A6.5 6.5 0 1 1 9.5 3m0 2a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9Z"/></svg></button>' +
      '<div class="docsfw-search-form"><button type="button" class="docsfw-search-back" aria-label="' + esc(text.back) + '">' +
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11v2H7.8l5.6 5.6L12 20l-8-8 8-8 1.4 1.4L7.8 11H20Z"/></svg></button>' +
        '<input type="search" id="docsfw-search-input" autocomplete="off" role="combobox" aria-autocomplete="list" ' +
          'aria-expanded="false" aria-controls="docsfw-search-results" aria-label="' + esc(text.label) +
          '" placeholder="' + esc(text.placeholder) + '"></div>' +
      '<div id="docsfw-search-results" role="listbox"></div>' +
      '<div class="docsfw-search-backdrop"></div>';
    input = document.getElementById('docsfw-search-input');
    results = document.getElementById('docsfw-search-results');

    container.querySelector('.docsfw-search-icon').addEventListener('click', openSearch);
    container.querySelector('.docsfw-search-back').addEventListener('click', function () { closeSearch(true); });
    container.querySelector('.docsfw-search-backdrop').addEventListener('click', function () { closeSearch(true); });
    input.addEventListener('focus', function () { if (input.value.trim()) { search(input.value); } });
    input.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      if (!input.value.trim()) { lastQuery = ''; setExpanded(false); return; }
      debounceTimer = setTimeout(function () { search(input.value); }, 200);
    });
    input.addEventListener('keydown', onKeydown);
    results.addEventListener('keydown', onKeydown);
    results.addEventListener('click', function (event) {
      if (event.target.closest && event.target.closest('.docsfw-result-item')) { closeSearch(false); }
    });
    document.addEventListener('click', function (event) {
      if (!mobile.matches && !container.contains(event.target)) { setExpanded(false); }
    });
    document.addEventListener('docsfw:drawer-open', function () { closeSearch(false); });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && document.body.classList.contains('docsfw-search-open')) { closeSearch(true); }
    });
    var onLayout = function () { closeSearch(false); };
    if (mobile.addEventListener) { mobile.addEventListener('change', onLayout); } else { mobile.addListener(onLayout); }
  }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', build); }
  else { build(); }
}());
