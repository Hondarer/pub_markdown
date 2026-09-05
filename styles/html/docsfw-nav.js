/*!
 * docsfw-nav.js
 * 1. Renders the global navigation tree from window.__DOCSFW_NAV__ into #docsfw-tree.
 * 2. Places the page-local TOC on the right at wide widths and in the combined
 *    navigation drawer below 1400px.
 * 3. Tracks the current heading in the page-local TOC.
 * 4. Appends a permalink anchor to each heading in the page body.
 * 5. Controls the off-canvas drawer (#docsfw-hamburger / #docsfw-nav-backdrop).
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
  // Place the page-local TOC for the current viewport
  // ---------------------------------------------------------------------------

  /**
   * Place #docsfw-page-toc in the right sidebar or the combined drawer.
   * The same element is moved so heading tracking survives viewport changes.
   */
  function placePageToc(wideLayout) {
    var sep     = document.querySelector('.docsfw-toc-separator');
    var pageToc = document.getElementById('docsfw-page-toc');
    var secondary = document.getElementById('TOC');
    var primary = document.getElementById('docsfw-primary-sidebar');

    if (!pageToc) {
      if (sep) { sep.remove(); }
      if (secondary) { secondary.hidden = true; }
      return;
    }

    if (!pageToc.querySelector('a[href^="#"]')) {
      pageToc.hidden = true;
      if (secondary) { secondary.hidden = true; }
      if (sep) { sep.hidden = true; }
      return;
    }

    pageToc.removeAttribute('hidden');
    if (secondary) { secondary.hidden = false; }

    if (wideLayout && secondary) {
      var secondaryWell = secondary.querySelector('.well');
      if (secondaryWell && pageToc.parentNode !== secondaryWell) {
        secondaryWell.appendChild(pageToc);
      }
      if (sep) { sep.hidden = true; }
      return;
    }

    var currentNode = document.getElementById('docsfw-current-node');
    if (currentNode && currentNode.tagName === 'DETAILS') {
      var inner = currentNode.querySelector(':scope > div');
      if (inner) {
        currentNode.insertBefore(pageToc, inner);
      } else {
        currentNode.appendChild(pageToc);
      }
    } else if (currentNode) {
      currentNode.appendChild(pageToc);
    } else if (primary) {
      var primaryWell = primary.querySelector('.well');
      if (primaryWell) { primaryWell.appendChild(pageToc); }
    }

    if (sep) { sep.hidden = false; }
  }

  function normalizeTocLinks() {
    var pageToc = document.getElementById('docsfw-page-toc');
    if (!pageToc) { return; }
    var tocLinks = pageToc.querySelectorAll('a');
    for (var li = 0; li < tocLinks.length; li++) {
      tocLinks[li].textContent = tocLinks[li].textContent;
    }
  }

  /**
   * Append a permalink anchor to every heading in the page body, matching the
   * "\u00B6" that mkdocs Material renders from its toc permalink option.
   * Headings without an id have no anchor target, so they are skipped; that
   * includes the page title, which the template emits as a plain <H1>.
   */
  function initHeaderLinks() {
    var content = document.getElementById('docsfw-content');
    if (!content) { return; }

    var headings = content.querySelectorAll('h1[id], h2[id], h3[id], h4[id], h5[id], h6[id]');
    for (var i = 0; i < headings.length; i++) {
      var heading = headings[i];
      if (heading.querySelector('a.headerlink')) { continue; }
      var link = document.createElement('a');
      link.className = 'headerlink';
      link.setAttribute('href', '#' + heading.id);
      link.setAttribute('title', 'Permanent link');
      link.textContent = '\u00B6';
      heading.appendChild(link);
    }
  }

  function initTocTracking() {
    var pageToc = document.getElementById('docsfw-page-toc');
    var content = document.getElementById('docsfw-content');
    if (!pageToc || !content) { return; }

    var links = Array.prototype.slice.call(pageToc.querySelectorAll('a[href^="#"]'));
    var entries = links.map(function (link) {
      var hash = link.getAttribute('href').slice(1);
      var id;
      try { id = decodeURIComponent(hash); } catch (_error) { id = hash; }
      return { link: link, heading: document.getElementById(id) };
    }).filter(function (entry) { return !!entry.heading; });

    if (!entries.length) { return; }

    var activeLink = null;
    var scheduled = false;

    function revealInSidebar(link) {
      var sidebar = link.closest('.docsfw-primary-sidebar, .docsfw-secondary-sidebar');
      if (!sidebar) { return; }
      var sidebarRect = sidebar.getBoundingClientRect();
      var linkRect = link.getBoundingClientRect();
      if (linkRect.top < sidebarRect.top || linkRect.bottom > sidebarRect.bottom) {
        sidebar.scrollTop += linkRect.top - sidebarRect.top - sidebar.clientHeight / 2;
      }
    }

    /* Mark every heading up to and including the current one as passed, so the
       TOC dims what the reader already scrolled through. Same semantics as
       mkdocs Material's md-nav__link--passed; see docs/livedocs-design.md. */
    function activate(link, index) {
      if (activeLink === link) { return; }
      for (var i = 0; i < links.length; i++) {
        links[i].classList.toggle('docsfw-toc-active', links[i] === link);
        if (links[i] === link) {
          links[i].setAttribute('aria-current', 'location');
        } else {
          links[i].removeAttribute('aria-current');
        }
      }
      for (var j = 0; j < entries.length; j++) {
        entries[j].link.classList.toggle('docsfw-toc-passed', j <= index);
      }
      activeLink = link;
      revealInSidebar(link);
    }

    function update() {
      scheduled = false;
      var selectedIndex = 0;
      for (var i = 0; i < entries.length; i++) {
        if (entries[i].heading.getBoundingClientRect().top <= 32) {
          selectedIndex = i;
        } else {
          break;
        }
      }
      activate(entries[selectedIndex].link, selectedIndex);
    }

    function scheduleUpdate() {
      if (!scheduled) {
        scheduled = true;
        window.requestAnimationFrame(update);
      }
    }

    window.addEventListener('scroll', scheduleUpdate, { passive: true });
    window.addEventListener('hashchange', scheduleUpdate);
    update();
  }

  // ---------------------------------------------------------------------------
  // Mobile off-canvas drawer
  // ---------------------------------------------------------------------------

  function initHamburger() {
    var btn      = document.getElementById('docsfw-hamburger');
    var backdrop = document.getElementById('docsfw-nav-backdrop');
    var sidebar  = document.getElementById('docsfw-primary-sidebar');

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
    // Runs before the branching below, so the anchors are added on every path.
    initHeaderLinks();

    var container = document.getElementById('docsfw-tree');
    var nav       = window.__DOCSFW_NAV__;
    var current   = window.__DOCSFW_CURRENT__;
    var wideLayout = window.matchMedia('(min-width: 1400px)');
    var onLayoutChange = function (event) { placePageToc(event.matches); };
    if (wideLayout.addEventListener) {
      wideLayout.addEventListener('change', onLayoutChange);
    } else {
      wideLayout.addListener(onLayoutChange);
    }

    if (!container) {
      placePageToc(wideLayout.matches);
      normalizeTocLinks();
      initTocTracking();
      initHamburger();
      return;
    }

    if (!nav) {
      // nav-tree.js not yet generated (first build); hide tree and keep the
      // page-local TOC available in the responsive layout.
      container.style.display = 'none';
      placePageToc(wideLayout.matches);
      normalizeTocLinks();
      initTocTracking();
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
          '<a href="' + esc(href(nav.url)) + '"' + homeCls + '> ' + esc(nav.title || 'Home') + '</a>' +
        '</div>'
      );
    }

    var homeContainer = document.getElementById('docsfw-home-container');
    if (homeContainer) { homeContainer.innerHTML = homeHtml; }
    container.innerHTML = renderNode(nav, current, true);

    placePageToc(wideLayout.matches);
    normalizeTocLinks();
    initTocTracking();

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
