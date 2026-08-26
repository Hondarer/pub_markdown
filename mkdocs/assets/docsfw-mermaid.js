// Mermaid をブラウザー上でレンダリングする。
//
// docsfw の HTML 出力と同じく、同梱した mermaid.min.js に描画させる。
// サイズ正規化は styles/html/html-template.html の normalizeMermaidSvgSize と
// 同じ処理で、viewBox から得た実寸を 0.875 倍して width / height に設定する。
//
// Material 標準の Mermaid 連携は CDN から mermaid を取得するため使用しない。
// クラス名を docsfw-mermaid とすることで Material 側の処理と競合させない。

(function () {
  "use strict";

  var BLOCK_SELECTOR = "div.docsfw-mermaid";
  var MULTIPLY_SVG = 0.875;

  /** mermaid が出力した SVG の表示サイズを補正する。 */
  function normalizeSvgSize() {
    var svgs = document.querySelectorAll(BLOCK_SELECTOR + " svg");
    Array.prototype.forEach.call(svgs, function (svg) {
      // ネストされたアイコン svg は mermaid が個別にサイズを設定済みのため対象外とする。
      if (svg.parentNode && svg.parentNode.closest && svg.parentNode.closest("svg")) {
        return;
      }

      var width = 0;
      var height = 0;
      if (svg.viewBox && svg.viewBox.baseVal &&
          svg.viewBox.baseVal.width > 0 && svg.viewBox.baseVal.height > 0) {
        width = svg.viewBox.baseVal.width;
        height = svg.viewBox.baseVal.height;
      } else {
        var viewBox = svg.getAttribute("viewBox");
        var parts = viewBox ? viewBox.trim().split(/\s+/) : [];
        if (parts.length === 4) {
          width = parseFloat(parts[2]);
          height = parseFloat(parts[3]);
        }
      }

      if (!(width > 0) || !(height > 0)) {
        return;
      }

      var displayWidth = width * MULTIPLY_SVG;
      var displayHeight = height * MULTIPLY_SVG;
      svg.setAttribute("width", displayWidth + "px");
      svg.setAttribute("height", displayHeight + "px");
      svg.style.width = displayWidth + "px";
      svg.style.height = "auto";
      svg.style.maxWidth = "100%";
    });
  }

  /** Material のカラー スキームに対応する mermaid のテーマ名を返す。 */
  function currentTheme() {
    return document.body.getAttribute("data-md-color-scheme") === "slate" ? "dark" : "default";
  }

  function render() {
    if (!window.mermaid) {
      return;
    }

    var blocks = document.querySelectorAll(BLOCK_SELECTOR);
    if (blocks.length === 0) {
      return;
    }

    Array.prototype.forEach.call(blocks, function (block) {
      if (block.dataset.docsfwSource === undefined) {
        block.dataset.docsfwSource = block.textContent;
      } else {
        // 再描画のため、元のソースへ戻してから mermaid に渡す。
        block.textContent = block.dataset.docsfwSource;
        block.removeAttribute("data-processed");
      }
    });

    window.mermaid.initialize({
      startOnLoad: false,
      theme: currentTheme(),
      securityLevel: "loose"
    });
    window.mermaid.run({
      querySelector: BLOCK_SELECTOR,
      postRenderCallback: normalizeSvgSize
    }).then(normalizeSvgSize).catch(function (error) {
      console.error("mermaid のレンダリングに失敗しました", error);
    });
  }

  /** カラー スキームの切り替えで描画し直す。 */
  function watchColorScheme() {
    var previous = currentTheme();
    var observer = new MutationObserver(function () {
      var current = currentTheme();
      if (current === previous) {
        return;
      }
      previous = current;
      render();
    });
    observer.observe(document.body, { attributes: true, attributeFilter: ["data-md-color-scheme"] });
  }

  function initialize() {
    render();
    watchColorScheme();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }

  // Material のインスタント ローディングでページが差し替わったときに再描画する。
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(render);
  }
})();
