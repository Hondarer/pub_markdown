// Pandoc HTML と MkDocs の図操作、および画像として配置した SVG の保存を提供する。
(function () {
  "use strict";

  var DIAGRAM_SELECTOR = "div.docsfw-plantuml, div.docsfw-mermaid";
  var SVG_NAMESPACE = "http://www.w3.org/2000/svg";
  var UNSAFE_NAME = /[\\/:*?"<>|]/g;
  var ICON_SOURCE = ["M9.5 7 L5 12 L9.5 17", "M14.5 7 L19 12 L14.5 17"];
  var ICON_DIAGRAM = ["M4 4 h6 v5 H4 z", "M14 15 h6 v5 h-6 z", "M7 9 v6 h10"];
  var ICON_DOWNLOAD = ["M12 4 v11", "M7 10 l5 5 5-5", "M4 20 h16"];
  var ICON_COPY = ["M9 8 h10 v12 H9 z", "M5 16 H4 V4 h10 v1"];
  var ICON_COPIED = ["M5 12 l4 4 10-10"];
  var ICON_ERROR = ["M6 6 l12 12", "M18 6 l-12 12"];
  var isJa = (document.documentElement.lang || "").toLowerCase().indexOf("ja") === 0;
  var counters = {};
  var labels = isJa ? {
    source: "ソースを表示",
    diagram: "図を表示",
    download: "SVG をダウンロード",
    copySource: "ソースをコピー",
    copyImage: "画像をコピー",
    copied: "コピーしました",
    copyError: "コピーできませんでした",
    downloadError: "SVG をダウンロードできませんでした",
  } : {
    source: "Show source",
    diagram: "Show diagram",
    download: "Download SVG",
    copySource: "Copy source",
    copyImage: "Copy image",
    copied: "Copied",
    copyError: "Could not copy",
    downloadError: "Could not download SVG",
  };

  function contentRoot() {
    return document.querySelector("#docsfw-content") || document.querySelector("article.md-content__inner") ||
      document.querySelector(".md-typeset");
  }

  function pageSlug() {
    var segments = window.location.pathname.split("/").filter(function (part) {
      return part && part !== "index.html";
    });
    if (segments.length === 0) { return "index"; }
    var last = segments[segments.length - 1].replace(/\.html$/i, "");
    try { return decodeURIComponent(last); }
    catch (error) { return last; }
  }

  function safeName(text) {
    return text.replace(UNSAFE_NAME, "_").replace(/\s+/g, " ").trim();
  }

  function diagramName(block) {
    var figure = block.closest("figure");
    var caption = figure ? figure.querySelector("figcaption") : null;
    var text = caption ? safeName(caption.textContent) : "";
    if (text) { return text + ".svg"; }
    var kind = block.classList.contains("docsfw-plantuml") ? "plantuml" : "mermaid";
    counters[kind] = (counters[kind] || 0) + 1;
    return pageSlug() + "-" + kind + counters[kind] + ".svg";
  }

  function makeIcon(pathData) {
    var icon = document.createElementNS(SVG_NAMESPACE, "svg");
    icon.setAttribute("viewBox", "0 0 24 24");
    icon.setAttribute("fill", "none");
    icon.setAttribute("stroke", "currentColor");
    icon.setAttribute("stroke-width", "2");
    icon.setAttribute("stroke-linecap", "round");
    icon.setAttribute("stroke-linejoin", "round");
    icon.setAttribute("aria-hidden", "true");
    pathData.forEach(function (data) {
      var path = document.createElementNS(SVG_NAMESPACE, "path");
      path.setAttribute("d", data);
      icon.appendChild(path);
    });
    return icon;
  }

  function setButtonFace(button, label, icon) {
    button.title = label;
    button.setAttribute("aria-label", label);
    button.replaceChildren(makeIcon(icon));
  }

  function createButton(className, label, icon) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "docsfw-diagram-action " + className;
    setButtonFace(button, label, icon);
    return button;
  }

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

  function parseSvg(text) {
    var documentSvg = new DOMParser().parseFromString(text, "image/svg+xml");
    var svg = documentSvg.documentElement;
    if (svg.nodeName.toLowerCase() !== "svg" || documentSvg.querySelector("parsererror")) {
      throw new Error("SVG を解釈できません。");
    }
    if (!svg.getAttribute("xmlns")) { svg.setAttribute("xmlns", SVG_NAMESPACE); }
    return svg;
  }

  function svgBlob(text) {
    return new Blob([new XMLSerializer().serializeToString(parseSvg(text))], { type: "image/svg+xml" });
  }

  function svgToPng(text) {
    var svg;
    try { svg = parseSvg(text); }
    catch (error) { return Promise.reject(error); }
    var viewBox = (svg.getAttribute("viewBox") || "").trim().split(/[ ,]+/).map(Number);
    // Mermaid は width="100%" と実寸の height を併記するため、属性値を
    // 数値化すると縦横比が崩れる。viewBox があれば両辺ともそこから決める。
    var width = viewBox.length === 4 ? viewBox[2] : parseFloat(svg.getAttribute("width"));
    var height = viewBox.length === 4 ? viewBox[3] : parseFloat(svg.getAttribute("height"));
    if (!(width > 0) || !(height > 0)) { return Promise.reject(new Error("図の寸法を取得できません。")); }

    var sourceUrl = URL.createObjectURL(new Blob([
      new XMLSerializer().serializeToString(svg),
    ], { type: "image/svg+xml" }));
    return new Promise(function (resolve, reject) {
      var image = new Image();
      image.onload = function () {
        try {
          var canvas = document.createElement("canvas");
          canvas.width = Math.max(1, Math.ceil(width));
          canvas.height = Math.max(1, Math.ceil(height));
          var context = canvas.getContext("2d");
          if (!context) { throw new Error("Canvas を利用できません。"); }
          context.drawImage(image, 0, 0, canvas.width, canvas.height);
          canvas.toBlob(function (blob) {
            URL.revokeObjectURL(sourceUrl);
            if (blob) { resolve(blob); }
            else { reject(new Error("PNG を生成できません。")); }
          }, "image/png");
        } catch (error) {
          URL.revokeObjectURL(sourceUrl);
          reject(error);
        }
      };
      image.onerror = function () {
        URL.revokeObjectURL(sourceUrl);
        reject(new Error("SVG を画像として読み込めません。"));
      };
      image.src = sourceUrl;
    });
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.cssText = "position:fixed;left:-9999px;top:0";
      document.body.appendChild(textarea);
      textarea.select();
      try {
        if (document.execCommand("copy")) { resolve(); }
        else { reject(new Error("copy command was rejected")); }
      } catch (error) { reject(error); }
      finally { textarea.remove(); }
    });
  }

  function showTemporaryFace(button, label, icon, restore) {
    if (button._docsfwResetTimer) { clearTimeout(button._docsfwResetTimer); }
    setButtonFace(button, label, icon);
    button._docsfwResetTimer = setTimeout(function () {
      button._docsfwResetTimer = null;
      restore();
    }, 1800);
  }

  function attachToImage(img) {
    var src = img.getAttribute("src") || "";
    if (/^[a-z][a-z0-9+.\-]*:/i.test(src)) { return; }
    var path = src.split("#")[0].split("?")[0];
    if (!/\.svg$/i.test(path) || img.closest(".docsfw-svg-dl-host")) { return; }

    var name;
    try { name = decodeURIComponent(path.split("/").pop()); }
    catch (error) { name = path.split("/").pop(); }
    var host = resolveHost(img, "span", "docsfw-svg-dl-wrap");
    var link = document.createElement("a");
    link.className = "docsfw-svg-dl";
    link.setAttribute("download", name);
    link.href = src;
    var label = isJa ? "SVG をダウンロード: " + name : "Download SVG: " + name;
    link.title = label;
    link.setAttribute("aria-label", label);
    link.appendChild(makeIcon(ICON_DOWNLOAD));
    host.appendChild(link);

    link.addEventListener("click", function (event) {
      if (window.location.protocol !== "http:" && window.location.protocol !== "https:") { return; }
      event.preventDefault();
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
      }).catch(function () { window.location.href = src; });
    });
  }

  function attachToDiagram(block) {
    if (block.dataset.docsfwToolsAttached || !window.docsfwDiagramTools) { return; }
    block.dataset.docsfwToolsAttached = "true";
    var name = diagramName(block);
    var host = resolveHost(block, "div", "docsfw-svg-dl-block");
    var toolbar = document.createElement("div");
    toolbar.className = "docsfw-diagram-toolbar";
    var toggle = createButton("docsfw-diagram-toggle", labels.source, ICON_SOURCE);
    var download = createButton("docsfw-svg-dl", labels.download, ICON_DOWNLOAD);
    var copy = createButton("docsfw-diagram-copy", labels.copyImage, ICON_COPY);
    toolbar.append(toggle, download, copy);
    host.appendChild(toolbar);

    function updateView() {
      var source = window.docsfwDiagramTools.getView(block) === "source";
      var sourceVisible = !!block.querySelector(":scope > .docsfw-diagram-source");
      host.classList.toggle("docsfw-diagram-source-host", sourceVisible);
      setButtonFace(toggle, source ? labels.diagram : labels.source, source ? ICON_DIAGRAM : ICON_SOURCE);
      setButtonFace(copy, source ? labels.copySource : labels.copyImage, ICON_COPY);
    }

    toggle.addEventListener("click", function () {
      var source = window.docsfwDiagramTools.getView(block) === "source";
      var operation = source ? window.docsfwDiagramTools.showDiagram(block) :
        window.docsfwDiagramTools.showSource(block);
      operation.then(updateView).catch(function () {});
    });
    block.addEventListener("docsfw-diagram-viewchange", updateView);

    download.addEventListener("click", function () {
      window.docsfwDiagramTools.renderSvg(block, "default").then(function (text) {
        saveBlob(svgBlob(text), name);
      }).catch(function () {
        showTemporaryFace(download, labels.downloadError, ICON_ERROR, function () {
          setButtonFace(download, labels.download, ICON_DOWNLOAD);
        });
      });
    });

    copy.addEventListener("click", function () {
      var source = window.docsfwDiagramTools.getView(block) === "source";
      var operation;
      if (source) {
        operation = copyText(window.docsfwDiagramTools.getSource(block));
      } else if (navigator.clipboard && navigator.clipboard.write && window.ClipboardItem) {
        var png = window.docsfwDiagramTools.renderSvg(block, "default").then(svgToPng);
        operation = navigator.clipboard.write([new ClipboardItem({ "image/png": png })]);
      } else {
        operation = Promise.reject(new Error("image clipboard is unavailable"));
      }
      operation.then(function () {
        showTemporaryFace(copy, labels.copied, ICON_COPIED, updateView);
      }).catch(function () {
        showTemporaryFace(copy, labels.copyError, ICON_ERROR, updateView);
      });
    });
    updateView();
  }

  function scan(root) {
    root.querySelectorAll("img").forEach(attachToImage);
    root.querySelectorAll(DIAGRAM_SELECTOR).forEach(attachToDiagram);
  }

  function initialize() {
    var root = contentRoot();
    if (!root || root.dataset.docsfwSvgObserved) { return; }
    root.dataset.docsfwSvgObserved = "true";
    scan(root);
    if (typeof MutationObserver !== "function") { return; }
    new MutationObserver(function () { scan(root); }).observe(root, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", initialize); }
  else { initialize(); }
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(initialize);
  }
})();
