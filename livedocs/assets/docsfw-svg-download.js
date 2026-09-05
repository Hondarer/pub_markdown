// 本文中の SVG へ「SVG をダウンロード」ボタンを重ねる。
//
// 静的発行 (Pandoc) の ../../styles/html/html-template.html にある同名の処理を
// 動的発行へ移植したもの。静的発行は PlantUML も draw.io も
// <img src="*.svg"> のため画像だけを対象にすればよいが、動的発行は
// PlantUML と Mermaid をブラウザー上でインライン描画するため、
// 描画済みの <svg> も直列化してダウンロード対象にする。
//
// ボタンの見た目は assets/docsfw-livedocs.css の .docsfw-svg-dl* が持つ。

(function () {
  "use strict";

  var DIAGRAM_SELECTOR = "div.docsfw-plantuml, div.docsfw-mermaid";
  var ICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"'
    + ' stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    + '<path d="M12 4v11"/><path d="M7 10l5 5 5-5"/><path d="M4 20h16"/></svg>';
  var SVG_NAMESPACE = "http://www.w3.org/2000/svg";
  // Windows のファイル名に使えない文字と、パス区切りを置き換える。
  var UNSAFE_NAME = /[\\/:*?"<>|]/g;

  var isJa = (document.documentElement.lang || "").toLowerCase().indexOf("ja") === 0;
  var counters = {};

  /** 本文のルート要素を返す。 */
  function contentRoot() {
    return document.querySelector("article.md-content__inner") ||
      document.querySelector(".md-typeset");
  }

  /** ページの識別子。キャプションを持たない図のファイル名に使う。 */
  function pageSlug() {
    var segments = window.location.pathname.split("/").filter(function (part) {
      return part && part !== "index.html";
    });
    if (segments.length === 0) {
      return "index";
    }
    var last = segments[segments.length - 1].replace(/\.html$/i, "");
    try {
      return decodeURIComponent(last);
    } catch (error) {
      return last;
    }
  }

  /** ファイル名として安全な文字列にする。 */
  function safeName(text) {
    return text.replace(UNSAFE_NAME, "_").replace(/\s+/g, " ").trim();
  }

  /** 図のダウンロード ファイル名を決める。 */
  function diagramName(block) {
    var figure = block.closest("figure");
    var caption = figure ? figure.querySelector("figcaption") : null;
    var text = caption ? safeName(caption.textContent) : "";
    if (text) {
      return text + ".svg";
    }
    var kind = block.classList.contains("docsfw-plantuml") ? "plantuml" : "mermaid";
    counters[kind] = (counters[kind] || 0) + 1;
    return pageSlug() + "-" + kind + counters[kind] + ".svg";
  }

  /**
   * ボタンの基準要素を決める。
   *
   * figure があれば figure、なければ対象を包む要素を新たに作る。
   * 画像は静的発行と同じ span、図はブロック要素のため div で包む。
   */
  function resolveHost(target, wrapperTag, wrapperClass) {
    var figure = target.closest("figure");
    if (figure) {
      figure.classList.add("docsfw-svg-dl-host");
      return figure;
    }
    var host = document.createElement(wrapperTag);
    host.className = wrapperClass + " docsfw-svg-dl-host";
    target.parentNode.insertBefore(host, target);
    host.appendChild(target);
    return host;
  }

  /** ダウンロード リンクを組み立てる。 */
  function createLink(name) {
    var link = document.createElement("a");
    link.className = "docsfw-svg-dl";
    link.setAttribute("download", name);
    var label = isJa ? "SVG をダウンロード: " + name : "Download SVG: " + name;
    link.title = label;
    link.setAttribute("aria-label", label);
    link.innerHTML = ICON;
    return link;
  }

  /** Blob URL を経由して保存を強制する。 */
  function saveBlob(blob, name) {
    var url = URL.createObjectURL(blob);
    var temporary = document.createElement("a");
    temporary.href = url;
    temporary.setAttribute("download", name);
    document.body.appendChild(temporary);
    temporary.click();
    document.body.removeChild(temporary);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  /** 画像ファイルとして参照している SVG にボタンを付ける。 */
  function attachToImage(img) {
    var src = img.getAttribute("src") || "";
    // data:, http(s): などスキーム付きの src は対象外
    if (/^[a-z][a-z0-9+.\-]*:/i.test(src)) { return; }
    var path = src.split("#")[0].split("?")[0];
    if (!/\.svg$/i.test(path)) { return; }
    if (img.closest(".docsfw-svg-dl-host")) { return; }

    var name;
    try { name = decodeURIComponent(path.split("/").pop()); }
    catch (error) { name = path.split("/").pop(); }

    var host = resolveHost(img, "span", "docsfw-svg-dl-wrap");
    var link = createLink(name);
    link.href = src;
    host.appendChild(link);

    // download 属性が無視されて SVG が表示される環境があるため、
    // http(s) では Blob URL を経由して保存を強制する
    link.addEventListener("click", function (event) {
      if (window.location.protocol !== "http:" && window.location.protocol !== "https:") { return; }
      event.preventDefault();
      // 資格情報入り URL では相対 src の fetch が TypeError になるため、資格情報を除去する
      var fetchSrc = src;
      try {
        var resolved = new URL(src, window.location.href);
        resolved.username = "";
        resolved.password = "";
        fetchSrc = resolved.href;
      } catch (error) { /* 解析不可ならそのまま */ }
      fetch(fetchSrc).then(function (response) {
        if (!response.ok) { throw new Error("HTTP " + response.status); }
        return response.blob();
      }).then(function (blob) {
        saveBlob(new Blob([blob], { type: "application/octet-stream" }), name);
      }).catch(function () {
        // 取得に失敗した場合は従来のリンク挙動にフォールバックする
        window.location.href = src;
      });
    });
  }

  /** インライン描画した図にボタンを付ける。 */
  function attachToDiagram(block) {
    var svg = block.querySelector(":scope > svg");
    if (!svg) { return; }
    if (block.closest(".docsfw-svg-dl-host")) { return; }

    var name = diagramName(block);
    var host = resolveHost(block, "div", "docsfw-svg-dl-block");
    var link = createLink(name);
    link.href = "#";
    host.appendChild(link);

    link.addEventListener("click", function (event) {
      event.preventDefault();
      var clone = svg.cloneNode(true);
      if (!clone.getAttribute("xmlns")) {
        clone.setAttribute("xmlns", SVG_NAMESPACE);
      }
      var text = new XMLSerializer().serializeToString(clone);
      saveBlob(new Blob([text], { type: "image/svg+xml" }), name);
    });
  }

  /** 現時点の本文を走査してボタンを付ける。 */
  function scan(root) {
    root.querySelectorAll("img").forEach(attachToImage);
    root.querySelectorAll(DIAGRAM_SELECTOR).forEach(attachToDiagram);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var root = contentRoot();
    if (!root) { return; }
    scan(root);

    // PlantUML と Mermaid は非同期に描画されるため、<svg> の挿入を監視する。
    // 描画側のスクリプトへ呼び出しを埋め込まないことで、読み込み順に依存しない。
    if (typeof MutationObserver !== "function") { return; }
    new MutationObserver(function () {
      root.querySelectorAll(DIAGRAM_SELECTOR).forEach(attachToDiagram);
    }).observe(root, { childList: true, subtree: true });
  });
})();
