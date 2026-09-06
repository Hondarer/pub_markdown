// Pandoc HTML のコード ブロック開閉と同じ動きを MkDocs 本文へ付ける。
// ソースの複製元は styles/html/html-template.html。静的発行のテンプレートはここでは変えない。
(function () {
  "use strict";

  var LINE_THRESHOLD = 5;

  function isJapanese() {
    return (document.documentElement.lang || "").toLowerCase().indexOf("ja") === 0;
  }

  function labels() {
    if (isJapanese()) {
      return {
        open: " 開く",
        collapse: " たたむ",
        more: function (rest, total) {
          return "さらに " + rest + " 行 (全 " + total + " 行)";
        }
      };
    }
    return {
      open: " Open",
      collapse: " Collapse",
      more: function (rest, total) {
        return rest + " more lines (" + total + " total)";
      }
    };
  }

  function isBackForwardNavigation() {
    try {
      var navEntries = performance.getEntriesByType("navigation");
      if (navEntries.length > 0) {
        return navEntries[0].type === "back_forward";
      }
      if (performance.navigation) {
        return performance.navigation.type === 2;
      }
    } catch (error) {
      // performance API が利用できない場合は復元しない
    }
    return false;
  }

  function skipPre(pre) {
    if (!pre || pre.closest(".code-expander-wrapper")) {
      return true;
    }
    if (pre.classList.contains("mermaid") || pre.classList.contains("docsfw-mermaid")) {
      return true;
    }
    if (pre.closest(".docsfw-mermaid, .docsfw-plantuml, .mermaid, .highlighttable")) {
      return true;
    }
    return false;
  }

  function splitHtmlAtLine(html, n) {
    var lineCount = 0;
    var inTag = false;
    for (var i = 0; i < html.length; i++) {
      var ch = html[i];
      if (ch === "<") {
        inTag = true;
        continue;
      }
      if (ch === ">") {
        inTag = false;
        continue;
      }
      if (ch === "\n" && !inTag) {
        lineCount++;
        if (lineCount === n) {
          return { first: html.substring(0, i + 1), rest: html.substring(i + 1) };
        }
      }
    }
    return null;
  }

  function createPlainCodeShell(pre) {
    var parentEl = pre.parentNode;
    var shell = document.createElement("div");
    shell.className = "code-copy-shell";
    var preStyle = window.getComputedStyle(pre);
    shell.style.marginTop = preStyle.marginTop;
    shell.style.marginBottom = preStyle.marginBottom;
    shell.style.border = preStyle.border;
    shell.style.borderRadius = preStyle.borderRadius;
    shell.style.backgroundColor = preStyle.backgroundColor;
    shell.style.boxSizing = "border-box";
    parentEl.insertBefore(shell, pre);
    shell.appendChild(pre);
    pre.style.margin = "0";
    pre.style.border = "none";
    pre.style.borderRadius = "0";
    return shell;
  }

  function relocateCopyNav(wrapper, scrollEl) {
    var fromScroll = scrollEl.querySelectorAll(".md-code__nav");
    var onWrapper = [];
    var i;
    for (i = 0; i < wrapper.children.length; i++) {
      if (wrapper.children[i].classList.contains("md-code__nav")) {
        onWrapper.push(wrapper.children[i]);
      }
    }
    if (fromScroll.length === 0 && onWrapper.length <= 1) {
      return;
    }
    var keep = fromScroll.length > 0 ? fromScroll[fromScroll.length - 1] : onWrapper[0];
    if (!keep) {
      return;
    }
    if (keep.parentElement !== wrapper) {
      wrapper.appendChild(keep);
    }
    var child;
    for (i = wrapper.children.length - 1; i >= 0; i--) {
      child = wrapper.children[i];
      if (child.classList.contains("md-code__nav") && child !== keep) {
        wrapper.removeChild(child);
      }
    }
    var leftover = scrollEl.querySelectorAll(".md-code__nav");
    for (var j = 0; j < leftover.length; j++) {
      leftover[j].parentNode.removeChild(leftover[j]);
    }
  }

  function bindFullCopy(shell, wrapper, scrollEl, text) {
    function apply(button) {
      if (!button || button.dataset.docsfwFullCopy === "true") {
        return;
      }
      button.setAttribute("data-clipboard-text", text);
      button.removeAttribute("data-clipboard-target");
      button.dataset.docsfwFullCopy = "true";
    }
    function sync() {
      relocateCopyNav(wrapper, scrollEl);
      shell.querySelectorAll('.md-code__button[data-md-type="copy"]').forEach(apply);
    }
    var observer = new MutationObserver(function () {
      observer.disconnect();
      try {
        sync();
      } finally {
        observer.observe(shell, { childList: true, subtree: true });
      }
    });
    sync();
    observer.observe(shell, { childList: true, subtree: true });
  }

  function initialize() {
    var textLabels = labels();
    var expandableItems = [];
    var expanderStateKey = "code-expander-state:" + window.location.pathname;
    var root = document.querySelector("article.md-content__inner") ||
      document.querySelector(".md-typeset") ||
      document;
    var preBlocks = root.querySelectorAll("pre");

    Array.prototype.forEach.call(preBlocks, function (pre) {
      if (skipPre(pre)) {
        return;
      }
      var codeEl = pre.querySelector("code");
      var text = codeEl ? codeEl.textContent : pre.textContent;
      var lines = text.split("\n");
      var lineCount = (lines.length > 0 && lines[lines.length - 1] === "")
        ? lines.length - 1 : lines.length;
      var highlight = pre.closest(".highlight");
      var shell = highlight || createPlainCodeShell(pre);
      var targetEl = codeEl || pre;
      var split = splitHtmlAtLine(targetEl.innerHTML, LINE_THRESHOLD);
      var expandable = lineCount > LINE_THRESHOLD && split;
      var toggleBtn = null;
      var restPre = null;
      var hintEl = null;
      var restCount = 0;

      if (expandable) {
        var toolbar = document.createElement("div");
        toolbar.className = "code-expander-toolbar";
        toggleBtn = document.createElement("button");
        toggleBtn.type = "button";
        toggleBtn.className = "code-expander-btn";
        toggleBtn.setAttribute("aria-expanded", "false");
        toggleBtn.innerHTML =
          '<span class="code-expander-arrow">▶</span>' +
          '<span class="code-expander-label">' + textLabels.open + "</span>";
        toolbar.appendChild(toggleBtn);
        shell.insertBefore(toolbar, pre);

        restPre = pre.cloneNode(false);
        restPre.className = (restPre.className ? restPre.className + " " : "") + "code-rest";
        restPre.style.display = "none";
        if (codeEl) {
          var restCode = codeEl.cloneNode(false);
          restCode.innerHTML = split.rest;
          restPre.appendChild(restCode);
        } else {
          restPre.innerHTML = split.rest;
        }
        targetEl.innerHTML = split.first;
        pre.className = (pre.className ? pre.className + " " : "") + "code-first";
        restCount = lineCount - LINE_THRESHOLD;

        function setExpanded(opening) {
          restPre.style.display = opening ? "" : "none";
          hintEl.style.display = opening ? "none" : "";
          toggleBtn.setAttribute("aria-expanded", opening ? "true" : "false");
          toggleBtn.querySelector(".code-expander-label").textContent =
            opening ? textLabels.collapse : textLabels.open;
        }

        function isExpanded() {
          return restPre.style.display !== "none";
        }

        hintEl = document.createElement("div");
        hintEl.className = "code-expander-hint";
        hintEl.textContent = textLabels.more(restCount, lineCount);
        hintEl.style.cursor = "pointer";
        hintEl.addEventListener("click", function () {
          if (restPre.style.display === "none") {
            setExpanded(true);
            saveExpanderState();
          }
        });
        toggleBtn.addEventListener("click", function () {
          setExpanded(!isExpanded());
          saveExpanderState();
        });
        expandableItems.push({ setExpanded: setExpanded, isExpanded: isExpanded });
      }

      var wrapper = document.createElement("div");
      wrapper.className = "code-expander-wrapper";
      wrapper.style.overflow = "hidden";
      var scrollEl = document.createElement("div");
      scrollEl.className = "code-expander-scroll";
      shell.insertBefore(wrapper, pre);
      scrollEl.appendChild(pre);
      if (restPre) {
        scrollEl.appendChild(restPre);
      }
      wrapper.appendChild(scrollEl);
      if (hintEl) {
        wrapper.appendChild(hintEl);
      }
      // Material は .md-code__nav を pre 内へ置く。pre は内容幅になるため、
      // 可視領域の右上へ残すよう scroll の外へ移す。
      bindFullCopy(shell, wrapper, scrollEl, text);
    });

    function saveExpanderState() {
      try {
        var state = {};
        expandableItems.forEach(function (item, index) {
          if (item.isExpanded()) {
            state[index] = true;
          }
        });
        sessionStorage.setItem(expanderStateKey, JSON.stringify(state));
      } catch (error) {
        // sessionStorage の書き込みエラーは無視
      }
    }

    if (expandableItems.length === 0) {
      return;
    }
    var restoredFromStorage = false;
    if (isBackForwardNavigation()) {
      try {
        var savedState = sessionStorage.getItem(expanderStateKey);
        if (savedState) {
          var state = JSON.parse(savedState);
          expandableItems.forEach(function (item, index) {
            item.setExpanded(!!state[index]);
          });
          restoredFromStorage = true;
        }
      } catch (error) {
        // sessionStorage の読み込みエラーは無視
      }
    }
    if (!restoredFromStorage) {
      expandableItems.forEach(function (item) {
        item.setExpanded(true);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(initialize);
  }
})();
