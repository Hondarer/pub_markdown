/*!
 * docsfw-nav.js
 * Renders the global navigation tree from window.__DOCSFW_NAV__ into
 * the #docsfw-tree element.
 *
 * Dependencies (loaded before this file via <script defer>):
 *   nav-tree.js   → window.__DOCSFW_NAV__
 *
 * Globals consumed:
 *   window.__DOCSFW_NAV__      - tree object from generate-nav-tree.py
 *   window.__DOCSFW_BASE__     - relative path from this page to html root  (e.g. "../../")
 *   window.__DOCSFW_CURRENT__  - this page's path relative to html root     (e.g. "calc/index.html")
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  function esc(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /**
   * Build the full href for a node URL.
   * __DOCSFW_BASE__ is already the correct relative prefix (e.g. "../../").
   */
  function href(url) {
    var base = (window.__DOCSFW_BASE__ != null) ? String(window.__DOCSFW_BASE__) : '';
    return base + url;
  }

  /** Return true if *nodeUrl* is an ancestor-or-equal of *currentUrl*. */
  function isAncestorOrEqual(nodeUrl, currentUrl) {
    if (!nodeUrl || !currentUrl) { return false; }
    if (nodeUrl === currentUrl) { return true; }
    // A directory node (ends in /index.html) is an ancestor if its directory
    // prefix is a prefix of the currentUrl.
    var dirPrefix = nodeUrl.replace(/\/index\.html$/, '/');
    if (dirPrefix !== nodeUrl) {
      return currentUrl.indexOf(dirPrefix) === 0;
    }
    return false;
  }

  // ---------------------------------------------------------------------------
  // Render tree → HTML string
  // ---------------------------------------------------------------------------

  /**
   * Render a single node.
   *
   * @param {Object}  node        - { title, url, children }
   * @param {string}  current     - current page url (relative to html root)
   * @param {boolean} isRoot      - true for the virtual root (render children only)
   * @returns {string}
   */
  function renderNode(node, current, isRoot) {
    var children  = node.children  || [];
    var hasKids   = children.length > 0;
    var isCurrent = node.url && node.url === current;
    var isAncestor = hasKids && isAncestorOrEqual(node.url, current);

    if (isRoot) {
      // Root: emit children directly
      var parts = [];
      for (var i = 0; i < children.length; i++) {
        parts.push(renderNode(children[i], current, false));
      }
      return parts.join('');
    }

    var titleHtml = esc(node.title || '(no title)');

    if (!hasKids) {
      // Leaf node
      var cls = isCurrent ? ' class="docsfw-current"' : '';
      if (node.url) {
        return '<div><a href="' + esc(href(node.url)) + '"' + cls + '>' + titleHtml + '</a></div>';
      }
      return '<div><span' + cls + '>' + titleHtml + '</span></div>';
    }

    // Directory node: use <details>/<summary>
    var openAttr = (isAncestor || isCurrent) ? ' open' : '';
    var summaryInner;
    if (node.url) {
      var cls2 = isCurrent ? ' class="docsfw-current"' : '';
      summaryInner = '<a href="' + esc(href(node.url)) + '"' + cls2 + '>' + titleHtml + '</a>';
    } else {
      summaryInner = '<span>' + titleHtml + '</span>';
    }

    var childHtml = '';
    for (var j = 0; j < children.length; j++) {
      childHtml += renderNode(children[j], current, false);
    }

    return (
      '<details' + openAttr + '>' +
        '<summary>' + summaryInner + '</summary>' +
        '<div>' + childHtml + '</div>' +
      '</details>'
    );
  }

  // ---------------------------------------------------------------------------
  // Entry point
  // ---------------------------------------------------------------------------

  function init() {
    var container = document.getElementById('docsfw-tree');
    if (!container) { return; }

    var nav     = window.__DOCSFW_NAV__;
    var current = window.__DOCSFW_CURRENT__;

    if (!nav) {
      // nav-tree.js may not exist yet (first build pass); silently skip
      container.style.display = 'none';
      return;
    }

    // If the root itself has a URL, prepend a "Home" link
    var homeHtml = '';
    if (nav.url) {
      var homeCls = (nav.url === current) ? ' class="docsfw-current"' : '';
      homeHtml = '<div class="docsfw-home-link"><a href="' +
                 esc(href(nav.url)) + '"' + homeCls + '>🏠 ' + esc(nav.title || 'Home') + '</a></div>';
    }

    container.innerHTML = homeHtml + renderNode(nav, current, true);
  }

  // Run after DOM is ready (defer attr already provides this, but be safe)
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
