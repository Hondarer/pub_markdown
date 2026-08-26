// MathJax の設定。pymdownx.arithmatex の generic 出力に合わせる。
//
// docsfw は pandoc の --mathjax を使用し、\(...\) と \[...\] を数式として扱う。
// 同じ書式を mkdocs でも扱えるようにする。

window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex"
  }
};

// Material のインスタント ローディングでページが差し替わったときに組版し直す。
if (window.document$ && typeof window.document$.subscribe === "function") {
  window.document$.subscribe(function () {
    if (window.MathJax && window.MathJax.typesetPromise) {
      window.MathJax.startup.output.clearCache();
      window.MathJax.typesetClear();
      window.MathJax.texReset();
      window.MathJax.typesetPromise();
    }
  });
}
