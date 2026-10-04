// Pandoc HTML と MkDocs の図を、元ソースと現在の配色から描画する。
// エンジンの評価は iframe 内で行い、親ページは mermaid.render と renderToString を呼ばない。
(function () {
  "use strict";

  const selector = "div.docsfw-mermaid, div.docsfw-plantuml";
  const frameSentinel = "DOCSFW_FRAME_SCRIPT_END_7f3a9c";
  // 初期化 30 秒、描画 15 秒。既存図の実測と根拠は docs/html-theme.md。
  // 局所テストは window.docsfwDiagramTimeouts で上書きできる。
  const configured = window.docsfwDiagramTimeouts || {};
  const initTimeoutMs = Number(configured.init) > 0 ? Number(configured.init) : 30000;
  const renderTimeoutMs = Number(configured.render) > 0 ? Number(configured.render) : 15000;
  const states = new Map();
  const queue = [];
  const slots = {
    mermaid: emptySlot(),
    plantuml: emptySlot(),
  };
  let running = false;
  let serial = 0;
  let gatePromise = null;
  let queueStarted = false;

  function emptySlot() {
    return { frame: null, generation: 0, ready: null, pending: null, pendingReady: null };
  }

  function trace(event) {
    const record = window.docsfwDiagramTrace || (window.docsfwDiagramTrace = []);
    record.push({ event: event, time: performance.now(), readyState: document.readyState });
  }

  function theme() {
    return document.body.getAttribute("data-md-color-scheme") === "slate" ? "dark" : "default";
  }

  function measureWidth() {
    const width = document.documentElement && document.documentElement.clientWidth;
    return Math.max(width || 0, 320);
  }

  function withTimeout(promise, ms, message) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(message)), ms);
      promise.then(value => {
        clearTimeout(timer);
        resolve(value);
      }, error => {
        clearTimeout(timer);
        reject(error);
      });
    });
  }

  function contentLoaded() {
    const navigation = performance.getEntriesByType && performance.getEntriesByType("navigation")[0];
    // エントリが無い場合は、complete なら DOMContentLoaded 済みとして扱う。
    // interactive でも後続の defer スクリプトが読込中の場合がある。
    // 配送開始を確認できた場合だけ、次タスクで配送完了を待つ。
    // navigation エントリが無い再入時は load を完了通知の予備にする。
    if (navigation && navigation.domContentLoadedEventEnd > 0) { return Promise.resolve(); }
    if (document.readyState === "complete") { return Promise.resolve(); }
    return new Promise(resolve => {
      let settled = false;
      const finish = () => {
        if (settled) { return; }
        settled = true;
        document.removeEventListener("DOMContentLoaded", finish);
        window.removeEventListener("load", finish);
        resolve();
      };
      document.addEventListener("DOMContentLoaded", finish, { once: true });
      window.addEventListener("load", finish, { once: true });
      if (navigation && navigation.domContentLoadedEventStart > 0) {
        setTimeout(finish, 0);
      }
    });
  }

  function paintOpportunity() {
    return new Promise(resolve => {
      const frames = () => requestAnimationFrame(() => requestAnimationFrame(resolve));
      // 非表示タブでは requestAnimationFrame が保留される。表示に戻ってから開始する。
      if (document.hidden) {
        document.addEventListener("visibilitychange", function onShow() {
          if (document.hidden) { return; }
          document.removeEventListener("visibilitychange", onShow);
          frames();
        });
        return;
      }
      frames();
    });
  }

  function openGate() {
    if (!gatePromise) {
      gatePromise = contentLoaded().then(() => {
        trace("content-loaded");
        return paintOpportunity();
      }).then(() => {
        trace("paint-opportunity");
      });
    }
    return gatePromise;
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

  function destroySlot(slot) {
    slot.generation += 1;
    slot.ready = null;
    slot.pending = null;
    slot.pendingReady = null;
    if (slot.frame) {
      slot.frame.remove();
      slot.frame = null;
    }
  }

  function onWindowMessage(event) {
    for (const kind of ["mermaid", "plantuml"]) {
      const slot = slots[kind];
      if (!slot.frame || event.source !== slot.frame.contentWindow) { continue; }
      const data = event.data;
      if (!data || typeof data.kind !== "string") { return; }
      if (data.kind === "ready" && slot.pendingReady) {
        const pending = slot.pendingReady;
        slot.pendingReady = null;
        pending.resolve();
        return;
      }
      if (data.kind === "init-error" && slot.pendingReady) {
        const pending = slot.pendingReady;
        slot.pendingReady = null;
        pending.reject(new Error(String(data.error || "図の描画エンジンを初期化できません。")));
        return;
      }
      if (data.kind === "result" && slot.pending && data.requestId === slot.pending.requestId) {
        const pending = slot.pending;
        slot.pending = null;
        if (typeof data.svg === "string" && data.svg && data.error === undefined) {
          pending.resolve({ svg: data.svg });
        } else {
          pending.reject(new Error(String(data.error || "図の描画に失敗しました。")));
        }
        return;
      }
    }
  }

  function embeddedFrame(kind) {
    const node = document.getElementById("docsfw-" + kind + "-frame");
    if (!node || node.getAttribute("type") !== "text/plain") { return ""; }
    return node.textContent.split(frameSentinel).join("</script>");
  }

  function frameLocation(kind) {
    const hooked = window.docsfwDiagramFrames && window.docsfwDiagramFrames[kind];
    if (hooked && (hooked.src || hooked.srcdoc)) { return hooked; }
    const srcdoc = embeddedFrame(kind);
    if (srcdoc) { return { srcdoc: srcdoc }; }
    if (typeof window.docsfwDiagramFrameUrl === "function") {
      return { src: window.docsfwDiagramFrameUrl(kind) };
    }
    const owner = document.querySelector("script[src*='docsfw-diagrams.js']");
    if (owner && owner.src) {
      return { src: new URL("docsfw-" + kind + "-frame.html", owner.src).href };
    }
    throw new Error(kind === "plantuml" ?
      "PlantUML の描画エンジンを読み込めません。" : "Mermaid の描画エンジンを読み込めません。");
  }

  function createFrameElement(kind) {
    const frame = document.createElement("iframe");
    frame.className = "docsfw-diagram-frame";
    frame.dataset.docsfwEngine = kind;
    frame.setAttribute("sandbox", "allow-scripts");
    frame.setAttribute("aria-hidden", "true");
    frame.tabIndex = -1;
    frame.title = "";
    // 不透明オリジンの iframe をビューポート外へ置くと、Chromium は requestAnimationFrame を止める。
    // Mermaid はフレーム内の rAF 後に寸法を測るため、fixed で重ねて透過し、操作には載せない。
    // see: https://chromestatus.com/feature/5175574929080320
    frame.style.position = "fixed";
    frame.style.left = "0";
    frame.style.top = "0";
    frame.style.width = measureWidth() + "px";
    frame.style.height = "4000px";
    frame.style.border = "0";
    frame.style.opacity = "0";
    frame.style.pointerEvents = "none";
    frame.style.zIndex = "-1";
    if ("inert" in frame) { frame.inert = true; }
    return frame;
  }

  function ensureFrame(kind) {
    const slot = slots[kind];
    if (slot.ready) { return slot.ready; }
    const location = frameLocation(kind);
    const frame = createFrameElement(kind);
    const generation = slot.generation + 1;
    slot.generation = generation;
    slot.frame = frame;
    slot.pending = null;
    let resolveReady;
    let rejectReady;
    const ready = new Promise((resolve, reject) => {
      resolveReady = resolve;
      rejectReady = reject;
    });
    slot.pendingReady = { resolve: resolveReady, reject: rejectReady };
    slot.ready = withTimeout(ready, initTimeoutMs, "図の描画エンジンの初期化がタイムアウトしました。").catch(error => {
      if (slot.generation === generation) { destroySlot(slot); }
      throw error;
    });
    frame.addEventListener("error", () => {
      if (slot.generation !== generation || !slot.pendingReady) { return; }
      const pending = slot.pendingReady;
      slot.pendingReady = null;
      pending.reject(new Error(kind === "plantuml" ?
        "PlantUML の描画エンジンを読み込めません。" : "Mermaid の描画エンジンを読み込めません。"));
    }, { once: true });
    document.body.appendChild(frame);
    trace("frame-load");
    if (location.srcdoc !== undefined) { frame.srcdoc = location.srcdoc; }
    else { frame.src = location.src; }
    return slot.ready;
  }

  async function waitForTestHold(kind) {
    const hold = window.docsfwDiagramTest && window.docsfwDiagramTest[kind];
    if (hold && typeof hold.then === "function") { await hold; }
  }

  async function renderInFrame(kind, source, selectedTheme, portable) {
    await waitForTestHold(kind);
    const slot = slots[kind];
    await ensureFrame(kind);
    if (!slot.frame || !slot.frame.contentWindow) {
      throw new Error(kind === "plantuml" ?
        "PlantUML の描画エンジンを読み込めません。" : "Mermaid の描画エンジンを読み込めません。");
    }
    slot.frame.style.width = measureWidth() + "px";
    const requestId = "d" + (++serial);
    let rejectPending;
    let pendingRequest;
    const result = withTimeout(new Promise((resolve, reject) => {
      pendingRequest = { requestId: requestId, resolve: resolve, reject: reject };
      slot.pending = pendingRequest;
      slot.frame.contentWindow.postMessage({
        kind: "render",
        requestId: requestId,
        source: source,
        dark: selectedTheme === "dark",
        portable: !!portable,
      }, "*");
    }), renderTimeoutMs, "図の描画がタイムアウトしました。");
    try {
      return await result;
    } catch (error) {
      // タイムアウト後の共有状態は不明なので、遅延応答を捨ててフレームを作り直す。
      if (slot.pending === pendingRequest) {
        destroySlot(slot);
        pendingRequest.reject(error);
      }
      throw error;
    }
  }

  async function draw(state, selectedTheme, portable) {
    if (state.kind === "plantuml") {
      if (/^\s*@startsalt\b/im.test(state.source)) {
        throw new Error("この HTML では Salt 図を描画できません。元のソースを表示します。");
      }
      // PlantUML は共有状態を持つため、成功または失敗の通知まで直列化する。
      // see: https://github.com/plantuml/plantuml/blob/master/src/main/resources/teavm/GITHUB_INTEGRATION.md
      return renderInFrame("plantuml", state.prepared.text, selectedTheme, portable);
    }
    return renderInFrame("mermaid", state.source, selectedTheme, portable);
  }

  function applyDiagram(state, result, selectedTheme) {
    if (!state.block.isConnected || state.view !== "diagram" || selectedTheme !== theme()) { return; }
    state.block.innerHTML = result.svg;
    const host = state.block.closest("figure");
    if (host) { host.classList.remove("docsfw-diagram-source-host"); }
    state.block.classList.remove("docsfw-diagram--error");
    // JavaScript 関数を呼ぶ click は iframe の外へ渡せない。SVG 内のリンクは文字列のまま残す。
    if (state.kind === "mermaid") { normalizeMermaid(state.block); }
    if (state.kind === "plantuml") { normalizePlantuml(state.block); }
    state.block.dataset.docsfwTheme = selectedTheme;
    state.block.dispatchEvent(new CustomEvent("docsfw-diagram-viewchange", { bubbles: true }));
  }

  function requestRender(state, selectedTheme, portable) {
    portable = !!portable;
    if (!portable && !queueStarted) {
      const existing = queue.find(job => job.state === state && job.liveTheme);
      if (existing) { return existing.promise; }
    }
    const cacheKey = selectedTheme + (portable ? ":portable" : "");
    if (queueStarted || portable) {
      if (state.cache.has(cacheKey)) {
        const result = state.cache.get(cacheKey);
        if (!portable) { applyDiagram(state, result, selectedTheme); }
        return Promise.resolve(result.svg);
      }
      if (state.pending.has(cacheKey)) { return state.pending.get(cacheKey); }
    }
    let resolveRender;
    let rejectRender;
    const promise = new Promise((resolve, reject) => {
      resolveRender = resolve;
      rejectRender = reject;
    });
    const liveTheme = !portable && !queueStarted;
    if (liveTheme) { state.pending.set("live", promise); }
    else { state.pending.set(cacheKey, promise); }
    if (!portable) {
      state.block.dataset.docsfwState = "rendering";
      state.block.setAttribute("aria-busy", "true");
    }
    queue.push({
      state: state,
      selectedTheme: selectedTheme,
      portable: portable,
      cacheKey: cacheKey,
      liveTheme: liveTheme,
      promise: promise,
      resolve: resolveRender,
      reject: rejectRender,
    });
    drain();
    return promise;
  }

  function releaseLiveTheme(openingTheme) {
    for (const job of queue) {
      if (!job.liveTheme) { continue; }
      job.state.pending.delete("live");
      job.selectedTheme = openingTheme;
      job.cacheKey = openingTheme;
      job.liveTheme = false;
      job.state.pending.set(job.cacheKey, job.promise);
    }
  }

  async function drain() {
    if (running) { return; }
    running = true;
    try {
      await openGate();
      if (!queueStarted) {
        const openingTheme = theme();
        queueStarted = true;
        releaseLiveTheme(openingTheme);
        trace("queue-start");
      }
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
      if (queue.length) { drain(); }
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
        block: block,
        source: source,
        kind: kind,
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
    trace("scan");
  }

  window.addEventListener("message", onWindowMessage);
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

  function boot() {
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

  if (document.body) { boot(); }
  else { document.addEventListener("DOMContentLoaded", boot); }
})();
