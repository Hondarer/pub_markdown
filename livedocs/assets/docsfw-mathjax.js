// MathJax の設定。pymdownx.arithmatex の generic 出力に合わせる。
//
// docsfw の静的発行は pandoc の MathJax 出力を使用し、\(...\) と \[...\] を数式として扱う。
// 同じ書式を mkdocs でも扱えるようにする。

window.MathJax = window.MathJax || {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex"
  },
  startup: { typeset: false }
};

(function () {
  "use strict";
  var ready;
  var queue = Promise.resolve();
  var processed = new WeakSet();
  var previous = [];

  function initialize() {
    // MathJax の組版も、前のページの組版が終わってから開始する。
    queue = queue.then(async function () {
      var content = document.querySelector("article.md-content__inner") || document.querySelector(".md-typeset");
      var removed = previous.filter(function (node) { return !node.isConnected; });
      if (removed.length && window.MathJax.typesetClear) {
        window.MathJax.typesetClear(removed);
      }
      previous = previous.filter(function (node) { return node.isConnected; });
      var nodes = content ? Array.from(content.querySelectorAll(".arithmatex")).filter(function (node) {
        return !processed.has(node);
      }) : [];
      // 初期表示と document$ の通知が重なっても、組版済みの数式は再処理しない。
      if (!nodes.length) { return; }
      if (!window.MathJax.typesetPromise) {
        // 静的発行と同じ MathJax 3。数式がないページでは取得しない。
        if (!ready) { ready = window.docsfwLoadScript("https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"); }
        await ready;
      }
      await window.MathJax.startup.promise;
      nodes = nodes.filter(function (node) { return node.isConnected; });
      if (!nodes.length) { return; }
      window.MathJax.startup.output.clearCache();
      if (!previous.length) { window.MathJax.texReset(); }
      await window.MathJax.typesetPromise(nodes);
      nodes.forEach(function (node) { processed.add(node); previous.push(node); });
    }).catch(function (error) {
      // 読み込みに失敗しても、本文と数式の元ソースは表示できる。
      console.error("MathJax:", error);
    });
  }

  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", initialize); }
  else { initialize(); }
  // Material のインスタント ローディングでも、必要になった時点で読み込む。
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(initialize);
  }
})();
