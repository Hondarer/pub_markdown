// HTML を表示する前に配色を決め、図の共通レンダラーへ同じ属性で通知する。
(function () {
  "use strict";
  const key = "docsfw-color-scheme";
  const preference = window.matchMedia("(prefers-color-scheme: dark)");
  let selected = null;
  let button;
  const isJa = (document.documentElement.lang || "ja").toLowerCase().startsWith("ja");
  try { selected = localStorage.getItem(key); } catch (_) { /* 保存できない環境でも切り替えを使える。 */ }
  function normalize(value) { return value === "slate" || value === "default" ? value : null; }
  selected = normalize(selected);
  function apply() {
    const scheme = selected || (preference.matches ? "slate" : "default");
    document.documentElement.setAttribute("data-md-color-scheme", scheme);
    if (document.body) { document.body.setAttribute("data-md-color-scheme", scheme); }
    if (button) {
      const dark = scheme === "slate";
      const label = isJa ? (dark ? "ライト モードへ切り替え" : "ダーク モードへ切り替え") :
        (dark ? "Switch to light mode" : "Switch to dark mode");
      button.title = label;
      button.setAttribute("aria-label", label);
      button.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2">' +
        (dark ? '<circle cx="12" cy="12" r="4"/><path d="M12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12l2 2M4 20l2-2M18 6l2-2"/>' :
          '<path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z"/>') + '</svg>';
    }
  }
  apply();
  preference.addEventListener("change", apply);
  window.addEventListener("storage", event => {
    if (event.key === key || event.key === null) { selected = normalize(event.newValue); apply(); }
  });
  function initialize() {
    button = document.createElement("button");
    button.type = "button";
    button.id = "docsfw-theme-toggle";
    button.addEventListener("click", () => {
      selected = document.documentElement.getAttribute("data-md-color-scheme") === "slate" ? "default" : "slate";
      try { localStorage.setItem(key, selected); } catch (_) { /* このページでは選択を保持する。 */ }
      apply();
    });
    const actions = document.querySelector(".docsfw-header-actions");
    const nav = document.querySelector(".doc-info");
    if (actions) {
      actions.prepend(button);
    } else if (nav) {
      const item = document.createElement("li");
      item.appendChild(button);
      nav.prepend(item);
    } else {
      button.className = "docsfw-theme-floating";
      document.body.prepend(button);
    }
    apply();
  }
  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", initialize); }
  else { initialize(); }
})();
