// 図・数式が必要になったときだけライブラリを読み込む。
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

  window.docsfwLoadMermaid = async function () {
    // id="mermaid" の見出しも window.mermaid になるため、API を確認する。
    // see: https://html.spec.whatwg.org/multipage/nav-history-apis.html#named-access-on-the-window-object
    if (!window.mermaid || typeof window.mermaid.render !== "function") {
      await window.docsfwLoadScript("mermaid/mermaid.min.js");
    }
    if (!window.mermaid || typeof window.mermaid.render !== "function") {
      throw new Error("Mermaid の描画エンジンを読み込めません。");
    }
    return window.mermaid;
  };

  if (!window.docsfwLoadPlantuml) {
    var loadPlantuml = async function () {
      await window.docsfwLoadScript("docsfw-plantuml-loader.js");
      // ローダーはこの関数を実エンジンの初期化関数で置き換える。
      if (window.docsfwLoadPlantuml === loadPlantuml) {
        throw new Error("PlantUML の描画エンジンを読み込めません。");
      }
      return window.docsfwLoadPlantuml();
    };
    window.docsfwLoadPlantuml = loadPlantuml;
  }
})();
