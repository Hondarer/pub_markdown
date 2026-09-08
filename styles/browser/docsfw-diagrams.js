// Pandoc HTML と MkDocs の図を、元ソースと現在の配色から描画する。
(function () {
  "use strict";

  const selector = "div.docsfw-mermaid, div.docsfw-plantuml";
  const states = new Map();
  const queue = [];
  let running = false;
  let serial = 0;

  function theme() {
    return document.body.getAttribute("data-md-color-scheme") === "slate" ? "dark" : "default";
  }

  function preparePlantuml(source) {
    let caption = "";
    const lines = source.replace(/\r\n?/g, "\n").split("\n").filter(function (line) {
      const match = line.match(/^\s*caption\s*(.*?)\s*$/i);
      if (!match) { return true; }
      caption = match[1];
      return false;
    });
    if (!caption) {
      for (const line of lines) {
        const match = line.match(/^\s*@start\w+\s+(.+?)\s*$/);
        if (match) { caption = match[1]; break; }
      }
    }
    let hasBackground = false;
    for (let i = 0; i < lines.length; i += 1) {
      if (/^skinparam\s+backgroundColor\s/i.test(lines[i])) {
        lines[i] = "skinparam backgroundColor transparent";
        hasBackground = true;
      }
    }
    if (!hasBackground) {
      const start = lines.findIndex(line => /^\s*@start\w+/.test(line));
      lines.splice(start + 1, 0, "skinparam backgroundColor transparent");
    }
    return { text: lines.join("\n"), caption: caption.replace(/~(.)/g, "$1") };
  }

  function addCaption(block, caption) {
    if (!caption || block.closest("figure")) { return; }
    const figure = document.createElement("figure");
    figure.className = "docsfw-figure docsfw-diagram-source-host";
    block.before(figure);
    figure.appendChild(block);
    const element = document.createElement("figcaption");
    element.className = "docsfw-caption";
    element.textContent = caption;
    figure.appendChild(element);
  }

  function showError(state, error) {
    const message = document.createElement("p");
    message.setAttribute("role", "status");
    message.textContent = String(error.message || error);
    const source = document.createElement("pre");
    source.textContent = state.source;
    state.block.replaceChildren(message, source);
    state.block.classList.add("docsfw-diagram--error");
  }

  function sourceElement(state) {
    const source = document.createElement("pre");
    source.className = "docsfw-diagram-source";
    const code = document.createElement("code");
    code.textContent = state.source;
    source.appendChild(code);
    return source;
  }

  function normalizeMermaid(block) {
    const svg = block.querySelector(":scope > svg");
    if (!svg) { return; }
    const box = svg.viewBox && svg.viewBox.baseVal;
    if (box && box.width > 0 && box.height > 0) {
      svg.setAttribute("width", (box.width * 0.875) + "px");
      svg.setAttribute("height", (box.height * 0.875) + "px");
      svg.style.width = (box.width * 0.875) + "px";
    }
    svg.style.height = "auto";
    svg.style.maxWidth = "100%";
  }

  // @plantuml/core は図形座標から viewBox を決め、線幅を含めない。
  // マインドマップのように左端が x=0 の図は、stroke の半分が切れる。
  function normalizePlantuml(block) {
    const svg = block.querySelector(":scope > svg");
    if (!svg) { return; }
    const box = svg.viewBox && svg.viewBox.baseVal;
    if (!box || box.width <= 0 || box.height <= 0) { return; }
    const pad = 2;
    const x = box.x;
    const y = box.y;
    const width = box.width;
    const height = box.height;
    svg.setAttribute("viewBox", (x - pad) + " " + (y - pad) + " " + (width + pad * 2) + " " + (height + pad * 2));
    const attrWidth = parseFloat(svg.getAttribute("width"));
    const attrHeight = parseFloat(svg.getAttribute("height"));
    if (attrWidth > 0) { svg.setAttribute("width", String(attrWidth + pad * 2)); }
    if (attrHeight > 0) { svg.setAttribute("height", String(attrHeight + pad * 2)); }
  }

  async function draw(state, selectedTheme, portable) {
    if (state.kind === "plantuml") {
      if (/^\s*@startsalt\b/im.test(state.source)) {
        throw new Error("この HTML では Salt 図を描画できません。元のソースを表示します。");
      }
      if (!window.docsfwLoadPlantuml) { throw new Error("PlantUML の描画エンジンを読み込めません。"); }
      const engine = await window.docsfwLoadPlantuml();
      // PlantUML は共有状態を持つため、成功または失敗の通知まで直列化する。
      // see: https://github.com/plantuml/plantuml/blob/master/src/main/resources/teavm/GITHUB_INTEGRATION.md
      return new Promise((resolve, reject) => {
        engine.renderToString(state.prepared.text.split("\n"), svg => resolve({ svg }),
          error => reject(new Error("PlantUML のレンダリングに失敗しました: " + error)),
          { dark: selectedTheme === "dark" });
      });
    }
    if (!window.mermaid) { throw new Error("Mermaid の描画エンジンを読み込めません。"); }
    window.mermaid.initialize({
      startOnLoad: false,
      theme: selectedTheme,
      securityLevel: "loose",
      // foreignObject を含む SVG は Canvas を汚染するため、保存・コピー用には SVG の text を使う。
      htmlLabels: !portable,
    });
    const host = document.createElement("div");
    host.className = "docsfw-diagram-measure";
    document.body.appendChild(host);
    try {
      return await window.mermaid.render("docsfw-mermaid-" + (++serial), state.source, host);
    } finally {
      host.remove();
    }
  }

  function applyDiagram(state, result, selectedTheme) {
    if (!state.block.isConnected || state.view !== "diagram" || selectedTheme !== theme()) { return; }
    state.block.innerHTML = result.svg;
    const host = state.block.closest("figure");
    if (host) { host.classList.remove("docsfw-diagram-source-host"); }
    state.block.classList.remove("docsfw-diagram--error");
    if (result.bindFunctions) { result.bindFunctions(state.block); }
    if (state.kind === "mermaid") { normalizeMermaid(state.block); }
    if (state.kind === "plantuml") { normalizePlantuml(state.block); }
    state.block.dataset.docsfwTheme = selectedTheme;
    state.block.dispatchEvent(new CustomEvent("docsfw-diagram-viewchange", { bubbles: true }));
  }

  function requestRender(state, selectedTheme, portable) {
    const cacheKey = selectedTheme + (portable ? ":portable" : "");
    if (state.cache.has(cacheKey)) {
      const result = state.cache.get(cacheKey);
      if (!portable) { applyDiagram(state, result, selectedTheme); }
      return Promise.resolve(result.svg);
    }
    if (state.pending.has(cacheKey)) { return state.pending.get(cacheKey); }

    let resolveRender;
    let rejectRender;
    const promise = new Promise((resolve, reject) => {
      resolveRender = resolve;
      rejectRender = reject;
    });
    state.pending.set(cacheKey, promise);
    if (!portable) {
      state.block.dataset.docsfwState = "rendering";
      state.block.setAttribute("aria-busy", "true");
    }
    queue.push({ state, selectedTheme, portable: !!portable, cacheKey, resolve: resolveRender, reject: rejectRender });
    drain();
    return promise;
  }

  async function drain() {
    if (running) { return; }
    running = true;
    try {
      while (queue.length) {
        const job = queue.shift();
        const state = job.state;
        const selectedTheme = job.selectedTheme;
        if (!state.block.isConnected) {
          state.pending.delete(job.cacheKey);
          job.reject(new Error("図が文書から取り除かれました。"));
          continue;
        }
        if (!job.portable) {
          state.block.dataset.docsfwState = "rendering";
          state.block.setAttribute("aria-busy", "true");
        }
        try {
          const result = await draw(state, selectedTheme, job.portable);
          state.cache.set(job.cacheKey, result);
          if (!job.portable) { applyDiagram(state, result, selectedTheme); }
          job.resolve(result.svg);
        } catch (error) {
          if (!job.portable && state.block.isConnected && state.view === "diagram" && selectedTheme === theme()) {
            showError(state, error);
          }
          job.reject(error);
        } finally {
          state.pending.delete(job.cacheKey);
          if (!job.portable) {
            state.block.removeAttribute("aria-busy");
            state.block.dataset.docsfwState = "done";
            if (selectedTheme === theme()) { state.block.dataset.docsfwTheme = selectedTheme; }
          }
          // 描画中の切り替えを取りこぼさず、現在の配色を用意する。
          if (state.block.isConnected && state.view === "diagram" && selectedTheme !== theme()) {
            requestRender(state, theme()).catch(() => {});
          }
        }
      }
    } finally {
      running = false;
    }
  }

  function enqueue(state) {
    if (!state || !state.block.isConnected) { return; }
    state.active = true;
    requestRender(state, theme()).catch(() => {});
  }

  function setView(state, view) {
    if (!state || !state.block.isConnected || (view !== "source" && view !== "diagram")) {
      return Promise.reject(new Error("図の表示状態を変更できません。"));
    }
    state.view = view;
    state.block.dataset.docsfwView = view;
    if (view === "source") {
      state.block.replaceChildren(sourceElement(state));
      const host = state.block.closest("figure");
      if (host) { host.classList.add("docsfw-diagram-source-host"); }
      state.block.classList.remove("docsfw-diagram--error");
      state.block.dispatchEvent(new CustomEvent("docsfw-diagram-viewchange", { bubbles: true }));
      return Promise.resolve();
    }
    state.block.dispatchEvent(new CustomEvent("docsfw-diagram-viewchange", { bubbles: true }));
    return requestRender(state, theme());
  }

  function scan() {
    for (const [block] of states) {
      if (!block.isConnected) { states.delete(block); }
    }
    document.querySelectorAll(selector).forEach(block => {
      if (states.has(block)) { return; }
      const kind = block.classList.contains("docsfw-plantuml") ? "plantuml" : "mermaid";
      const source = block.textContent;
      const renderSource = block.dataset.docsfwRenderSource || source;
      const state = {
        block,
        source,
        kind,
        active: false,
        view: "diagram",
        cache: new Map(),
        pending: new Map(),
      };
      block.dataset.docsfwSource = source;
      block.dataset.docsfwView = "diagram";
      if (kind === "plantuml") {
        state.prepared = preparePlantuml(renderSource);
        addCaption(block, state.prepared.caption);
      }
      const host = block.closest("figure");
      if (host) { host.classList.add("docsfw-diagram-source-host"); }
      states.set(block, state);
      // 初回描画前から、表示切り替え後と同じ要素とスタイルで元ソースを示す。
      block.replaceChildren(sourceElement(state));
      enqueue(state);
    });
  }

  window.docsfwDiagramTools = {
    getSource(block) {
      const state = states.get(block);
      return state ? state.source : "";
    },
    getView(block) {
      const state = states.get(block);
      return state ? state.view : "";
    },
    showSource(block) {
      return setView(states.get(block), "source");
    },
    showDiagram(block) {
      return setView(states.get(block), "diagram");
    },
    renderSvg(block, selectedTheme) {
      const state = states.get(block);
      if (!state) { return Promise.reject(new Error("図が見つかりません。")); }
      return requestRender(state, selectedTheme === "dark" ? "dark" : "default", true);
    },
  };

  function initialize() {
    let previous = theme();
    new MutationObserver(() => {
      const current = theme();
      if (previous === current) { return; }
      previous = current;
      for (const state of states.values()) {
        if (state.active && state.block.isConnected) { enqueue(state); }
      }
    }).observe(document.body, { attributes: true, attributeFilter: ["data-md-color-scheme"] });
    scan();
    if (window.document$ && typeof window.document$.subscribe === "function") {
      window.document$.subscribe(scan);
    }
  }

  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", initialize); }
  else { initialize(); }
})();
