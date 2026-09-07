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
    figure.className = "docsfw-figure";
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

  async function draw(state, selectedTheme) {
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
    window.mermaid.initialize({ startOnLoad: false, theme: selectedTheme, securityLevel: "loose" });
    const host = document.createElement("div");
    host.className = "docsfw-diagram-measure";
    document.body.appendChild(host);
    try {
      return await window.mermaid.render("docsfw-mermaid-" + (++serial), state.source, host);
    } finally {
      host.remove();
    }
  }

  async function drain() {
    if (running) { return; }
    running = true;
    try {
      while (queue.length) {
        const state = queue.shift();
        if (!state.block.isConnected) { state.queued = false; continue; }
        const selectedTheme = theme();
        state.block.dataset.docsfwState = "rendering";
        state.block.setAttribute("aria-busy", "true");
        try {
          const result = await draw(state, selectedTheme);
          if (state.block.isConnected && selectedTheme === theme()) {
            state.block.innerHTML = result.svg;
            state.block.classList.remove("docsfw-diagram--error");
            if (result.bindFunctions) { result.bindFunctions(state.block); }
            if (state.kind === "mermaid") { normalizeMermaid(state.block); }
            if (state.kind === "plantuml") { normalizePlantuml(state.block); }
          }
        } catch (error) {
          if (state.block.isConnected && selectedTheme === theme()) { showError(state, error); }
        } finally {
          state.queued = false;
          state.block.removeAttribute("aria-busy");
          state.block.dataset.docsfwState = "done";
          state.block.dataset.docsfwTheme = selectedTheme;
          // 描画中の切り替えを取りこぼさず、古い結果は表示しない。
          if (state.block.isConnected && selectedTheme !== theme()) { enqueue(state); }
        }
      }
    } finally {
      running = false;
    }
  }

  function enqueue(state) {
    if (!state || !state.block.isConnected) { return; }
    state.active = true;
    if (state.queued) { return; }
    state.queued = true;
    queue.push(state);
    drain();
  }

  function scan() {
    for (const [block] of states) {
      if (!block.isConnected) { states.delete(block); }
    }
    document.querySelectorAll(selector).forEach(block => {
      if (states.has(block)) { return; }
      const kind = block.classList.contains("docsfw-plantuml") ? "plantuml" : "mermaid";
      const source = block.textContent;
      const state = { block, source, kind, active: false, queued: false };
      block.dataset.docsfwSource = source;
      if (kind === "plantuml") {
        state.prepared = preparePlantuml(source);
        addCaption(block, state.prepared.caption);
      }
      states.set(block, state);
      enqueue(state);
    });
  }

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
