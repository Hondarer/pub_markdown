// 全文検索の結果を、今開いている詳細度のページに限る。
// 通常版と詳細版は 1 つの索引に入るため、相手の URL は一覧から外す。
(function () {
  "use strict";

  function variants() {
    return window.__DOCSFW_VARIANTS__ || [];
  }

  function currentVariant() {
    var known = variants();
    var parts = window.location.pathname.split("/").filter(Boolean);
    if (parts.length && known.indexOf(parts[0]) >= 0) {
      return parts[0];
    }
    return null;
  }

  function sameVariant(href, variant) {
    try {
      var url = new URL(href, window.location.href);
      var parts = url.pathname.split("/").filter(Boolean);
      return parts.length > 0 && parts[0] === variant;
    } catch (error) {
      return true;
    }
  }

  function filterLinks(root, variant) {
    var links = root.querySelectorAll("a[href]");
    Array.prototype.forEach.call(links, function (link) {
      var hide = !sameVariant(link.getAttribute("href"), variant);
      var item = link.closest("li") || link;
      if (hide) {
        item.setAttribute("hidden", "");
      } else {
        item.removeAttribute("hidden");
      }
    });
  }

  function resultText(visible) {
    var strings = window.__DOCSFW_SEARCH_RESULT__;
    if (!strings) {
      return null;
    }
    if (visible === 0) {
      return strings.none;
    }
    if (visible === 1) {
      return strings.one;
    }
    return String(strings.other || "").replace("#", String(visible));
  }

  function updateCount(root) {
    var list = root.querySelector(".md-search-result__list");
    var meta = root.querySelector(".md-search-result__meta");
    if (!list || !meta) {
      return;
    }
    var items = list.querySelectorAll(":scope > li");
    if (!items.length) {
      return;
    }
    var visible = 0;
    Array.prototype.forEach.call(items, function (item) {
      if (!item.hasAttribute("hidden")) {
        visible += 1;
      }
    });
    var text = resultText(visible);
    if (text && meta.textContent !== text) {
      meta.textContent = text;
    }
  }

  function apply() {
    var variant = currentVariant();
    if (!variant) {
      return;
    }
    var result = document.querySelector(".md-search-result");
    if (result) {
      filterLinks(result, variant);
      updateCount(result);
    }
    var suggest = document.querySelector(".md-search__suggest");
    if (suggest) {
      filterLinks(suggest, variant);
    }
  }

  function start() {
    var search = document.querySelector(".md-search");
    if (!search || search.getAttribute("data-docsfw-variant-search") === "1") {
      return;
    }
    search.setAttribute("data-docsfw-variant-search", "1");
    var observer = new MutationObserver(apply);
    observer.observe(search, {childList: true, subtree: true, attributes: true});
    apply();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
