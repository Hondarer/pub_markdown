/*!
 * docsfw-nav.js
 * 1. Renders the global navigation tree from window.__DOCSFW_NAV__ into #docsfw-tree.
 * 2. Merges the page-local TOC (#docsfw-page-toc) into the current page's tree node.
 * 3. Controls the mobile off-canvas drawer (#docsfw-hamburger / #docsfw-nav-backdrop).
 *
 * Dependencies (loaded before this file via <script defer>):
 *   nav-tree.js → window.__DOCSFW_NAV__
 *
 * Globals consumed:
 *   window.__DOCSFW_NAV__      - tree object from generate-nav-tree.py
 *   window.__DOCSFW_BASE__     - relative path from this page to html root (e.g. "../../")
 *   window.__DOCSFW_CURRENT__  - this page's path relative to html root (e.g. "calc/index.html")
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

  function href(url) {
    var base = (window.__DOCSFW_BASE__ != null) ? String(window.__DOCSFW_BASE__) : '';
    return base + url;
  }

  /**
   * Return true if *node* is an ancestor of (or equal to) the current page.
   * For directories with url=null (no index.html), falls back to node.path.
   */
  function isAncestorOrEqual(node, currentUrl) {
    if (!currentUrl) { return false; }
    var url = node.url;
    // Exact match
    if (url && url === currentUrl) { return true; }
    // Derive directory prefix from URL (strip /index.html suffix)
    var dirPrefix = null;
    if (url) {
      var stripped = url.replace(/\/index\.html$/, '/');
      if (stripped !== url) { dirPrefix = stripped; }
    }
    // Fallback: use explicit path field (set for all directory nodes by generate-nav-tree.py)
    if (!dirPrefix) {
      var p = node.path;
      if (p != null && p !== '') { dirPrefix = p; }
    }
    return dirPrefix ? currentUrl.indexOf(dirPrefix) === 0 : false;
  }

  // ---------------------------------------------------------------------------
  // Render tree → HTML string
  // ---------------------------------------------------------------------------

  /**
   * Render a single nav tree node.
   * Adds id="docsfw-current-node" to the element that represents the current page.
   *
   * @param {Object}  node    - { title, url, children }
   * @param {string}  current - current page URL (relative to html root)
   * @param {boolean} isRoot  - true for the virtual root (renders children only)
   * @returns {string} HTML fragment
   */
  function renderNode(node, current, isRoot) {
    var children   = node.children  || [];
    var hasKids    = children.length > 0;
    var isCurrent  = !!(node.url && node.url === current);
    var isAncestor = hasKids && isAncestorOrEqual(node, current);

    if (isRoot) {
      var parts = [];
      for (var i = 0; i < children.length; i++) {
        parts.push(renderNode(children[i], current, false));
      }
      return parts.join('');
    }

    var titleHtml = esc(node.title || '(no title)');
    var currentId = isCurrent ? ' id="docsfw-current-node"' : '';

    if (!hasKids) {
      // Leaf node
      var cls = isCurrent ? ' class="docsfw-current"' : '';
      if (node.url) {
        return '<div' + currentId + '><a href="' + esc(href(node.url)) + '"' + cls + '>' + titleHtml + '</a></div>';
      }
      return '<div' + currentId + '><span' + cls + '>' + titleHtml + '</span></div>';
    }

    // Directory node
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
      '<details' + currentId + openAttr + '>' +
        '<summary>' + summaryInner + '</summary>' +
        '<div>' + childHtml + '</div>' +
      '</details>'
    );
  }

  // ---------------------------------------------------------------------------
  // Merge page-local TOC into the current tree node
  // ---------------------------------------------------------------------------

  /**
   * Move #docsfw-page-toc into the current page's node in the rendered tree.
   *
   * - If the current node is found and there is a page TOC, the TOC is wrapped
   *   in <div class="docsfw-page-toc"> and injected into the node. The separator
   *   <hr class="docsfw-toc-separator"> is also removed (now redundant).
   * - If the current node is not found (page not in tree, or no tree), the page
   *   TOC is shown in place by removing its "hidden" attribute (fallback).
   * - If there is no page TOC at all (page has no headings), only the separator
   *   is removed.
   */
  function mergeTocIntoCurrentNode() {
    var sep     = document.querySelector('.docsfw-toc-separator');
    var pageToc = document.getElementById('docsfw-page-toc');

    if (!pageToc) {
      // No page TOC: remove the separator and stop.
      if (sep) { sep.remove(); }
      return;
    }

    var currentNode = document.getElementById('docsfw-current-node');

    if (!currentNode) {
      // Current page not in tree (or no tree): show TOC in place.
      pageToc.removeAttribute('hidden');
      return;
    }

    // Remove separator — TOC is now part of the tree.
    if (sep) { sep.remove(); }

    // Wrap the TOC content and inject it into the current node.
    var wrapper = document.createElement('div');
    wrapper.className = 'docsfw-page-toc';
    while (pageToc.firstChild) {
      wrapper.appendChild(pageToc.firstChild);
    }

    if (currentNode.tagName === 'DETAILS') {
      // Directory node: insert as a direct child of <details>, immediately
      // before the child-pages <div>. This keeps the page-toc outside the
      // 11px-padded wrapper, so the indicator border aligns with <summary>.
      var inner = currentNode.querySelector(':scope > div');
      if (inner) {
        currentNode.insertBefore(wrapper, inner);
      } else {
        currentNode.appendChild(wrapper);
      }
    } else {
      // Leaf node (<div>): append after the link.
      currentNode.appendChild(wrapper);
    }

    pageToc.remove();
  }

  // ---------------------------------------------------------------------------
  // Mobile off-canvas drawer
  // ---------------------------------------------------------------------------

  function initHamburger() {
    var btn      = document.getElementById('docsfw-hamburger');
    var backdrop = document.getElementById('docsfw-nav-backdrop');
    var sidebar  = document.getElementById('TOC');

    if (!btn) { return; }

    function isOpen() {
      return document.body.classList.contains('docsfw-nav-open');
    }

    function openDrawer() {
      document.body.classList.add('docsfw-nav-open');
      btn.setAttribute('aria-expanded', 'true');
      btn.textContent = '‹'; // ‹
      // Scroll current node into view inside the drawer.
      var cn = document.getElementById('docsfw-current-node');
      if (cn) {
        // Small delay to let CSS transition start, then scroll.
        setTimeout(function () {
          cn.scrollIntoView({ block: 'center', behavior: 'instant' });
        }, 50);
      }
    }

    function closeDrawer() {
      document.body.classList.remove('docsfw-nav-open');
      btn.setAttribute('aria-expanded', 'false');
      btn.textContent = '›'; // ›
    }

    btn.addEventListener('click', function () {
      if (isOpen()) { closeDrawer(); } else { openDrawer(); }
    });

    if (backdrop) {
      backdrop.addEventListener('click', closeDrawer);
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen()) { closeDrawer(); }
    });

    // Close drawer when any link inside the sidebar is clicked.
    if (sidebar) {
      sidebar.addEventListener('click', function (e) {
        var a = e.target.closest ? e.target.closest('a') : null;
        if (a && a.getAttribute('href')) {
          closeDrawer();
        }
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Entry point
  // ---------------------------------------------------------------------------

  function init() {
    var container = document.getElementById('docsfw-tree');
    var nav       = window.__DOCSFW_NAV__;
    var current   = window.__DOCSFW_CURRENT__;

    if (!container) {
      // No tree container: show page TOC in place if it exists.
      var pt = document.getElementById('docsfw-page-toc');
      if (pt) { pt.removeAttribute('hidden'); }
      initHamburger();
      return;
    }

    if (!nav) {
      // nav-tree.js not yet generated (first build); hide tree, show page TOC.
      container.style.display = 'none';
      var pt2 = document.getElementById('docsfw-page-toc');
      if (pt2) { pt2.removeAttribute('hidden'); }
      var sep2 = document.querySelector('.docsfw-toc-separator');
      if (sep2) { sep2.remove(); }
      initHamburger();
      return;
    }

    // Build home link (root index page).
    var homeHtml = '';
    if (nav.url) {
      var isCurrRoot = (nav.url === current);
      var homeCls    = isCurrRoot ? ' class="docsfw-current"' : '';
      var homeId     = isCurrRoot ? ' id="docsfw-current-node"' : '';
      homeHtml = (
        '<div class="docsfw-home-link"' + homeId + '>' +
          '<a href="' + esc(href(nav.url)) + '"' + homeCls + '>🏠 ' + esc(nav.title || 'Home') + '</a>' +
        '</div>'
      );
    }

    container.innerHTML = homeHtml + renderNode(nav, current, true);

    // Merge the page-local TOC into the current node.
    mergeTocIntoCurrentNode();

    // Scroll the current node into view within the sidebar (desktop).
    var currentNode = document.getElementById('docsfw-current-node');
    if (currentNode) {
      currentNode.scrollIntoView({ block: 'center', behavior: 'instant' });
    }

    // Wire up the mobile hamburger.
    initHamburger();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
