// 数式が必要になったときだけ MathJax を読み込む。
// 図のエンジンは親ページで評価せず、docsfw-diagrams.js がフレーム HTML を iframe で読む。
(function () {
  "use strict";

  var base = new URL(".", document.currentScript.src);
  var pending = new Map();
  window.docsfwLoadScript = function (url) {
    var absolute = new URL(url, base).href;
    if (!pending.has(absolute)) {
      pending.set(absolute, new Promise(function (resolve, reject) {
        var script = document.createElement("script");
        script.src = absolute;
        script.onload = resolve;
        script.onerror = function () { reject(new Error("ライブラリを読み込めません: " + absolute)); };
        document.head.appendChild(script);
      }));
    }
    return pending.get(absolute);
  };

  window.docsfwDiagramFrameUrl = function (kind) {
    return new URL("docsfw-" + kind + "-frame.html", base).href;
  };
})();
