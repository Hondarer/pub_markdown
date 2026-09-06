/*!
 * Pandoc HTML の文書ツリー、ページ内目次、階層式ドロワーを制御する。
 * MkDocs Material と同じ 1625px / 76.234375em の境界を使用する。
 */
(function () {
  'use strict';

  var wideLayout = window.matchMedia('(min-width: 1625px)');
  var panelLayout = window.matchMedia('(max-width: 76.234375em)');
  var base = window.__DOCSFW_BASE__ == null ? '' : String(window.__DOCSFW_BASE__);
  var current = window.__DOCSFW_CURRENT__ == null ? '' : String(window.__DOCSFW_CURRENT__);
  var panels = {};
  var currentPanelKey = 'root';
  var activePanelKey = 'root';
  var panelSequence = 0;
  var branchSequence = 0;
  var isJa = (document.documentElement.lang || 'ja').toLowerCase().indexOf('ja') === 0;

  function esc(value) {
    return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function href(url) { return base + url; }

  function chevron(direction) {
    var path = direction === 'back' ? 'M15.4 7.4 10.8 12l4.6 4.6L14 18l-6-6 6-6 1.4 1.4Z' :
      'm8.6 16.6 4.6-4.6-4.6-4.6L10 6l6 6-6 6-1.4-1.4Z';
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + path + '"/></svg>';
  }

  function isAncestorOrEqual(node) {
    if (!current) { return false; }
    if (node.url && node.url === current) { return true; }
    var prefix = '';
    if (node.url && /\/index\.html$/.test(node.url)) { prefix = node.url.replace(/index\.html$/, ''); }
    else if (node.path) { prefix = node.path; }
    return !!prefix && current.indexOf(prefix) === 0;
  }

  function rowContent(node, currentId) {
    var title = esc(node.title || '(no title)');
    var selected = node.url && node.url === current;
    var cls = selected ? ' class="docsfw-current" aria-current="page"' : '';
    var id = selected && currentId ? ' id="docsfw-current-node"' : '';
    if (node.url) { return '<a' + id + ' href="' + esc(href(node.url)) + '"' + cls + '>' + title + '</a>'; }
    return '<span' + id + (selected ? ' class="docsfw-current"' : '') + '>' + title + '</span>';
  }

  function renderFlatNode(node) {
    var children = node.children || [];
    var expanded = containsCurrent(node);
    var ancestor = expanded && !(node.url && node.url === current);
    var branchId = 'docsfw-branch-' + (++branchSequence);
    var html = '<li class="docsfw-nav-item' + (ancestor ? ' docsfw-nav-ancestor' : '') +
      '"><div class="docsfw-nav-row">' + rowContent(node, true);
    if (children.length) {
      html += '<button type="button" class="docsfw-nav-toggle" aria-controls="' + branchId +
        '" aria-expanded="' + expanded + '" aria-label="' + esc(node.title || '') +
        '">' + chevron('forward') + '</button>';
    }
    html += '</div>';
    if (children.length) {
      html += '<ul id="' + branchId + '" class="docsfw-nav-list"' + (expanded ? '' : ' hidden') + '>';
      for (var i = 0; i < children.length; i++) { html += renderFlatNode(children[i]); }
      html += '</ul>';
    }
    return html + '</li>';
  }

  function containsCurrent(node) {
    if (node.url && node.url === current) { return true; }
    return (node.children || []).some(containsCurrent);
  }

  function revealCurrent() {
    if (!wideLayout.matches) { return; }
    var selected = document.querySelector('.docsfw-flat-nav .docsfw-current');
    var sidebar = document.getElementById('docsfw-primary-sidebar');
    if (!selected || !sidebar) { return; }
    var rect = selected.getBoundingClientRect();
    var bounds = sidebar.getBoundingClientRect();
    if (rect.top < bounds.top + 33 || rect.bottom > bounds.bottom) {
      sidebar.scrollTop += rect.top - bounds.top - sidebar.clientHeight / 2;
    }
  }

  function allocatePanel(node, parentKey) {
    var key = 'panel-' + (++panelSequence);
    panels[key] = { key: key, node: node, parent: parentKey };
    if (isAncestorOrEqual(node)) { currentPanelKey = key; }
    return key;
  }

  function registerPanels(nodes, parentKey) {
    for (var i = 0; i < nodes.length; i++) {
      var children = nodes[i].children || [];
      if (children.length) {
        var key = allocatePanel(nodes[i], parentKey);
        registerPanels(children, key);
      }
    }
  }

  function childPanelKey(node, parentKey) {
    var keys = Object.keys(panels);
    for (var i = 0; i < keys.length; i++) {
      var panel = panels[keys[i]];
      if (panel.node === node && panel.parent === parentKey) { return panel.key; }
    }
    return '';
  }

  function renderPanelRows(nodes, parentKey) {
    var html = '<ul class="docsfw-nav-list">';
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      var children = node.children || [];
      var target = children.length ? childPanelKey(node, parentKey) : '';
      html += '<li class="docsfw-nav-item"><div class="docsfw-nav-row">' + rowContent(node, false);
      if (target) {
        var label = isJa ? esc(node.title || '') + 'を開く' : 'Open ' + esc(node.title || '');
        html += '<button type="button" class="docsfw-nav-forward" data-panel-target="' + target +
          '" aria-label="' + label + '">' + chevron('forward') + '</button>';
      }
      html += '</div></li>';
    }
    return html + '</ul>';
  }

  function renderPanel(panel) {
    var root = panel.key === 'root';
    var classes = 'docsfw-nav-panel' + (panel.key === activePanelKey ? ' docsfw-panel-active' : '');
    var html = '<section class="' + classes + '" data-panel-key="' + panel.key + '"' +
      (panel.key === activePanelKey ? '' : ' hidden') + '>';
    if (!root) {
      var backLabel = isJa ? '前の階層へ戻る' : 'Back to previous level';
      html += '<div class="docsfw-panel-title"><button type="button" class="docsfw-nav-back" data-panel-target="' +
        esc(panel.parent) + '" aria-label="' + backLabel + '">' + chevron('back') + '</button>' +
        '<span class="docsfw-panel-title-text">' + esc(panel.node.title || '') + '</span></div>';
    }
    if (root && panel.node.url) {
      html += '<div class="docsfw-panel-home docsfw-nav-row">' + rowContent(panel.node, false) + '</div>';
    }
    html += renderPanelRows(panel.node.children || [], panel.key);
    return html + '</section>';
  }

  function renderNavigation(nav) {
    var container = document.getElementById('docsfw-tree');
    if (!container || !nav) { return; }
    var home = document.getElementById('docsfw-home-container');
    if (home && nav.url) {
      var homeClass = nav.url === current ? ' class="docsfw-current" aria-current="page"' : '';
      var homeId = nav.url === current ? ' id="docsfw-current-node"' : '';
      home.innerHTML = '<div class="docsfw-home-link"><a' + homeId + ' href="' + esc(href(nav.url)) + '"' +
        homeClass + '>' + esc(nav.title || 'Home') + '</a></div>';
    }

    var children = nav.children || [];
    branchSequence = 0;
    var flat = '<div class="docsfw-flat-nav"><ul class="docsfw-nav-list">';
    for (var i = 0; i < children.length; i++) { flat += renderFlatNode(children[i]); }
    flat += '</ul></div>';

    panels = { root: { key: 'root', node: nav, parent: '' } };
    panelSequence = 0;
    currentPanelKey = 'root';
    registerPanels(children, 'root');
    activePanelKey = currentPanelKey;
    var panelHtml = '<div class="docsfw-panel-nav">';
    var keys = Object.keys(panels);
    for (var j = 0; j < keys.length; j++) { panelHtml += renderPanel(panels[keys[j]]); }
    panelHtml += '</div>';
    container.innerHTML = flat + panelHtml;
    wirePanelButtons(container);
    var sidebar = document.getElementById('docsfw-primary-sidebar');
    if (sidebar) { sidebar.classList.toggle('docsfw-child-panel-active', activePanelKey !== 'root'); }
  }

  function setActivePanel(key, direction) {
    if (!panels[key]) { return; }
    activePanelKey = key;
    var sidebar = document.getElementById('docsfw-primary-sidebar');
    if (sidebar) { sidebar.classList.toggle('docsfw-child-panel-active', key !== 'root'); }
    var nodes = document.querySelectorAll('.docsfw-nav-panel');
    for (var i = 0; i < nodes.length; i++) {
      var active = nodes[i].getAttribute('data-panel-key') === key;
      nodes[i].classList.toggle('docsfw-panel-active', active);
      nodes[i].hidden = !active;
      nodes[i].classList.remove('docsfw-panel-enter-forward', 'docsfw-panel-enter-back');
      if (active && direction) { nodes[i].classList.add('docsfw-panel-enter-' + direction); }
    }
    placePageToc();
    var heading = document.querySelector('.docsfw-nav-panel.docsfw-panel-active .docsfw-panel-title-text');
    if (heading && direction) { heading.setAttribute('tabindex', '-1'); heading.focus(); }
  }

  function wirePanelButtons(container) {
    container.addEventListener('click', function (event) {
      var toggle = event.target.closest ? event.target.closest('.docsfw-nav-toggle') : null;
      if (toggle) {
        var branch = document.getElementById(toggle.getAttribute('aria-controls'));
        branch.hidden = !branch.hidden;
        toggle.setAttribute('aria-expanded', String(!branch.hidden));
        return;
      }
      var button = event.target.closest ? event.target.closest('[data-panel-target]') : null;
      if (!button) { return; }
      setActivePanel(button.getAttribute('data-panel-target'),
        button.classList.contains('docsfw-nav-back') ? 'back' : 'forward');
    });
  }

  function placePageToc() {
    var pageToc = document.getElementById('docsfw-page-toc');
    var secondary = document.getElementById('TOC');
    if (!pageToc || !pageToc.querySelector('a[href^="#"]')) {
      if (pageToc) { pageToc.hidden = true; }
      if (secondary) { secondary.hidden = true; }
      return;
    }
    pageToc.hidden = false;
    pageToc.classList.remove('docsfw-combined-toc');
    if (wideLayout.matches && secondary) {
      var well = secondary.querySelector('.well');
      if (well) { well.appendChild(pageToc); }
      secondary.hidden = false;
      return;
    }
    if (secondary) { secondary.hidden = true; }
    pageToc.classList.add('docsfw-combined-toc');
    var target = panelLayout.matches ? document.querySelector('.docsfw-nav-panel.docsfw-panel-active') :
      document.querySelector('.docsfw-flat-nav');
    if (!target) { target = document.querySelector('#docsfw-primary-sidebar > .well'); }
    if (target) { target.appendChild(pageToc); }
  }

  function normalizeTocLinks() {
    var toc = document.getElementById('docsfw-page-toc');
    if (!toc) { return; }
    if (!toc.querySelector('.docsfw-toc-title')) {
      var title = document.createElement('div');
      title.className = 'docsfw-toc-title';
      title.textContent = isJa ? '目次' : 'Table of contents';
      toc.insertBefore(title, toc.firstChild);
    }
    var links = toc.querySelectorAll('a');
    for (var i = 0; i < links.length; i++) { links[i].textContent = links[i].textContent; }
  }

  function initHeaderLinks() {
    var content = document.getElementById('docsfw-content');
    if (!content) { return; }
    var headings = content.querySelectorAll('h1[id], h2[id], h3[id], h4[id], h5[id], h6[id]');
    for (var i = 0; i < headings.length; i++) {
      if (headings[i].querySelector('a.headerlink')) { continue; }
      var link = document.createElement('a');
      link.className = 'headerlink'; link.href = '#' + headings[i].id;
      link.title = 'Permanent link'; link.textContent = '\u00B6';
      headings[i].appendChild(link);
    }
  }

  function initTocTracking() {
    var toc = document.getElementById('docsfw-page-toc');
    var content = document.getElementById('docsfw-content');
    if (!toc || !content) { return; }
    var links = Array.prototype.slice.call(toc.querySelectorAll('a[href^="#"]'));
    var entries = links.map(function (link) {
      var hash = link.getAttribute('href').slice(1); var id;
      try { id = decodeURIComponent(hash); } catch (_error) { id = hash; }
      return { link: link, heading: document.getElementById(id) };
    }).filter(function (entry) { return !!entry.heading; });
    if (!entries.length) { return; }
    var scheduled = false;
    var activeIndex = -1;
    function followActiveLink(link) {
      var secondary = document.getElementById('TOC');
      if (!wideLayout.matches || !secondary || !secondary.contains(link)) { return; }
      var bounds = secondary.getBoundingClientRect();
      var title = toc.querySelector('.docsfw-toc-title');
      var visibleTop = bounds.top + (title ? title.getBoundingClientRect().height : 0);
      var linkBounds = link.getBoundingClientRect();
      var targetCenter = (visibleTop + bounds.bottom) / 2;
      var linkCenter = (linkBounds.top + linkBounds.bottom) / 2;
      secondary.scrollTop += linkCenter - targetCenter;
    }
    function update() {
      scheduled = false; var selected = -1;
      for (var i = 0; i < entries.length; i++) {
        if (entries[i].heading.getBoundingClientRect().top <= 84) { selected = i; } else { break; }
      }
      if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 1) {
        selected = entries.length - 1;
      }
      for (var j = 0; j < entries.length; j++) {
        entries[j].link.classList.toggle('docsfw-toc-passed', j <= selected);
        entries[j].link.classList.toggle('docsfw-toc-active', j === selected);
        if (j === selected) { entries[j].link.setAttribute('aria-current', 'location'); }
        else { entries[j].link.removeAttribute('aria-current'); }
      }
      if (selected >= 0 && selected !== activeIndex) { followActiveLink(entries[selected].link); }
      activeIndex = selected;
    }
    window.addEventListener('scroll', function () {
      if (!scheduled) { scheduled = true; window.requestAnimationFrame(update); }
    }, { passive: true });
    window.addEventListener('hashchange', update); update();
  }

  function closeDrawer(restoreFocus) {
    var button = document.getElementById('docsfw-hamburger');
    var sidebar = document.getElementById('docsfw-primary-sidebar');
    document.body.classList.remove('docsfw-nav-open');
    if (button) { button.setAttribute('aria-expanded', 'false'); }
    if (sidebar) { sidebar.setAttribute('aria-hidden', wideLayout.matches ? 'false' : 'true'); }
    if (restoreFocus && button && !wideLayout.matches) { button.focus(); }
  }

  function openDrawer() {
    var button = document.getElementById('docsfw-hamburger');
    var sidebar = document.getElementById('docsfw-primary-sidebar');
    document.dispatchEvent(new CustomEvent('docsfw:drawer-open'));
    document.body.classList.add('docsfw-nav-open');
    if (button) { button.setAttribute('aria-expanded', 'true'); }
    if (sidebar) { sidebar.setAttribute('aria-hidden', 'false'); }
    if (panelLayout.matches) { setActivePanel(currentPanelKey); }
    var selected = document.querySelector(panelLayout.matches ?
      '.docsfw-nav-panel.docsfw-panel-active .docsfw-current' : '.docsfw-flat-nav .docsfw-current');
    if (selected) { selected.scrollIntoView({ block: 'center', behavior: 'auto' }); }
  }

  function initDrawer() {
    var button = document.getElementById('docsfw-hamburger');
    var backdrop = document.getElementById('docsfw-nav-backdrop');
    var sidebar = document.getElementById('docsfw-primary-sidebar');
    if (!button || !sidebar) { return; }
    button.setAttribute('aria-label', isJa ? 'ナビゲーション' : 'Navigation');
    sidebar.setAttribute('aria-label', isJa ? '文書ナビゲーション' : 'Document navigation');
    sidebar.setAttribute('aria-hidden', wideLayout.matches ? 'false' : 'true');
    button.addEventListener('click', function () {
      if (document.body.classList.contains('docsfw-nav-open')) { closeDrawer(true); } else { openDrawer(); }
    });
    if (backdrop) { backdrop.addEventListener('click', function () { closeDrawer(true); }); }
    sidebar.addEventListener('click', function (event) {
      var link = event.target.closest ? event.target.closest('a[href]') : null;
      if (link) { closeDrawer(false); }
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && document.body.classList.contains('docsfw-nav-open')) { closeDrawer(true); }
    });
    document.addEventListener('docsfw:search-open', function () { closeDrawer(false); });
  }

  function loadNavigation(done) {
    if (!window.__DOCSFW_NAV_ENABLED__) { done(null); return; }
    if (window.__DOCSFW_NAV__) { done(window.__DOCSFW_NAV__); return; }
    var script = document.createElement('script'); script.src = base + 'nav-tree.js';
    script.onload = function () { done(window.__DOCSFW_NAV__ || null); };
    script.onerror = function () {
      var container = document.getElementById('docsfw-tree');
      if (container) { container.innerHTML = '<p class="docsfw-nav-unavailable">' +
        (isJa ? '文書一覧を読み込めませんでした。' : 'Document navigation is unavailable.') + '</p>'; }
      done(null);
    };
    document.head.appendChild(script);
  }

  function onLayoutChange() {
    closeDrawer(false);
    if (panelLayout.matches) { setActivePanel(currentPanelKey); }
    placePageToc();
    revealCurrent();
  }

  function init() {
    initHeaderLinks(); normalizeTocLinks(); initTocTracking(); initDrawer(); placePageToc();
    loadNavigation(function (nav) { if (nav) { renderNavigation(nav); } placePageToc(); revealCurrent(); });
    if (wideLayout.addEventListener) {
      wideLayout.addEventListener('change', onLayoutChange); panelLayout.addEventListener('change', onLayoutChange);
    } else {
      wideLayout.addListener(onLayoutChange); panelLayout.addListener(onLayoutChange);
    }
  }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); }
  else { init(); }
}());
