/* Pandoc HTML と共通のレスポンシブ ナビゲーション配置を適用する。 */
(function () {
  'use strict';

  var wideLayout = window.matchMedia('(min-width: 1400px)');
  var toc = null;
  var originalParent = null;
  var originalNextSibling = null;
  var combinedContainer = null;

  function resolveElements() {
    var nextToc = document.querySelector('.md-sidebar--secondary nav.md-nav--secondary');
    if (nextToc && nextToc !== toc) {
      toc = nextToc;
      originalParent = toc.parentNode;
      originalNextSibling = toc.nextSibling;
      combinedContainer = null;
    }
  }

  function getCombinedContainer() {
    var primaryInner = document.querySelector('.md-sidebar--primary .md-sidebar__inner');
    if (!primaryInner) { return null; }
    if (!combinedContainer || !combinedContainer.isConnected) {
      combinedContainer = document.createElement('div');
      combinedContainer.className = 'docsfw-combined-toc';
      primaryInner.appendChild(combinedContainer);
    }
    return combinedContainer;
  }

  function placeToc() {
    resolveElements();
    if (!toc) { return; }

    if (wideLayout.matches) {
      if (originalParent && toc.parentNode !== originalParent) {
        originalParent.insertBefore(toc, originalNextSibling);
      }
      if (combinedContainer) {
        combinedContainer.remove();
        combinedContainer = null;
      }
      return;
    }

    var target = getCombinedContainer();
    if (target && toc.parentNode !== target) {
      target.appendChild(toc);
    }
  }

  function init() {
    if (!toc || !toc.isConnected) {
      toc = null;
      originalParent = null;
      originalNextSibling = null;
      combinedContainer = null;
    }
    placeToc();
  }

  if (wideLayout.addEventListener) {
    wideLayout.addEventListener('change', placeToc);
  } else {
    wideLayout.addListener(placeToc);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  if (window.document$ && typeof window.document$.subscribe === 'function') {
    window.document$.subscribe(init);
  }
}());
