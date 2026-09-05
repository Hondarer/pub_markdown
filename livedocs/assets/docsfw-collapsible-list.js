// Pandoc HTML の collapsible-list と同じ開閉・履歴復元を本文へ適用する。
(function () {
  "use strict";

  function initialize() {
    var containers = document.querySelectorAll('.collapsible-list');
    containers.forEach(function (container) {
      container.querySelectorAll('li').forEach(function (li) {
        if (li.querySelector(':scope > details')) return;
        var children = Array.from(li.children).filter(function (node) {
          return node.tagName === 'UL' || node.tagName === 'OL';
        });
        if (!children.length) return;
        var details = document.createElement('details');
        var summary = document.createElement('summary');
        Array.from(li.childNodes).forEach(function (node) {
          if (children.indexOf(node) === -1) summary.appendChild(node);
        });
        details.appendChild(summary);
        children.forEach(function (node) { details.appendChild(node); });
        li.appendChild(details);
      });
    });

    var all = Array.from(document.querySelectorAll('.collapsible-list details'));
    var key = 'collapsible-state:' + window.location.pathname;
    var state = null;
    try {
      var navigation = performance.getEntriesByType('navigation');
      var backForward = navigation.length ? navigation[0].type === 'back_forward' :
        performance.navigation && performance.navigation.type === 2;
      if (backForward) state = JSON.parse(sessionStorage.getItem(key));
      if (!state || typeof state !== 'object' || Array.isArray(state)) state = null;
    } catch (error) { state = null; }

    all.forEach(function (details, index) {
      if (details.dataset.docsfwCollapsibleInitialized) return;
      details.dataset.docsfwCollapsibleInitialized = 'true';
      var container = details.closest('.collapsible-list');
      var limit = parseInt(container.getAttribute('data-open-level'), 10);
      var level = 1;
      for (var parent = details.parentElement; parent && parent !== container; parent = parent.parentElement) {
        if (parent.tagName === 'DETAILS') level++;
      }
      details.open = state ? state[index] === true : limit < 0 || level <= limit;
      details.addEventListener('toggle', function () {
        var saved = {};
        all.forEach(function (item, position) {
          if (item.open) saved[position] = true;
        });
        try { sessionStorage.setItem(key, JSON.stringify(saved)); } catch (error) { /* 保存不可でも開閉できる。 */ }
      });
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize);
  else initialize();
})();
