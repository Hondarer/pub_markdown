// PlantUML をブラウザー上でレンダリングする。
//
// @plantuml/core (TeaVM でコンパイルされた MIT ライセンス版) を使用し、
// ビルド時の図生成を不要にする。前処理は docsfw の
// bin/pandoc-filters/plantuml.lua と同じ規則に合わせている。
//
// 1 ページに 30 個の図を含むドキュメントがあるため、
// IntersectionObserver でビューポートに入った図だけを描画する。

import { renderToString } from "./plantuml/plantuml.js";

const BLOCK_SELECTOR = "div.docsfw-plantuml";
const OBSERVER_MARGIN = "400px";

const CAPTION_LINE = /^\s*caption\s*(.*?)\s*$/i;
// caption 行がないとき、@start<種別> に続く名前をキャプションとして採用する。
// 種別は限定しない。docsfw の plantuml.lua と同じ規則。
const START_TITLE = /^\s*@start\w+\s+(.+?)\s*$/;
// @startebnf や @startregex を含め、あらゆる @start<種別> の直後へ挿入する。
// 種別を限定すると列挙外の図で @start より前へ入る。PlantUML の CLI は
// @start より前の行を無視するが、@plantuml/core はエラー図を返す。
// docsfw の bin/pandoc-filters/plantuml.lua も同じ規則にそろえている。
const START_ANY = /^\s*@start\w+/;

/** 1 個ずつ順に描画するための直列キュー。 */
const queue = [];
let queueRunning = false;

/**
 * PlantUML ソースからキャプションを取り出し、描画用のソースへ整形する。
 *
 * plantuml.lua と同じく、caption 行を取り除き、@start* の後に
 * 背景を透過させる skinparam を挿入する。
 *
 * @param {string} source フェンスに書かれた PlantUML ソース。
 * @returns {{text: string, caption: string}} 整形後のソースとキャプション。
 */
function preparePlantUmlSource(source) {
  const lines = source.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
  const kept = [];
  let caption = "";

  for (const line of lines) {
    const match = line.match(CAPTION_LINE);
    if (match) {
      caption = match[1];
      continue;
    }
    kept.push(line);
  }

  if (!caption) {
    for (const line of kept) {
      const match = line.match(START_TITLE);
      if (match) {
        caption = match[1].trim();
        break;
      }
    }
  }

  // PlantUML の ~ エスケープを取り除く (~__attribute__~ など)。
  caption = caption.replace(/~(.)/g, "$1");

  let hasBackgroundColor = false;
  for (let index = 0; index < kept.length; index += 1) {
    if (/^skinparam\s+backgroundColor\s/i.test(kept[index])) {
      kept[index] = "skinparam backgroundColor transparent";
      hasBackgroundColor = true;
    }
  }

  if (!hasBackgroundColor) {
    let insertAt = 0;
    for (let index = 0; index < kept.length; index += 1) {
      if (START_ANY.test(kept[index])) {
        insertAt = index + 1;
        break;
      }
    }
    kept.splice(insertAt, 0, "skinparam backgroundColor transparent");
  }

  return { text: kept.join("\n"), caption: caption };
}

/** Material のカラー スキームがダークかどうかを返す。 */
function isDarkScheme() {
  const scheme = document.body.getAttribute("data-md-color-scheme");
  return scheme === "slate";
}

/** キューを 1 件ずつ処理する。 */
function runQueue() {
  if (queueRunning) {
    return;
  }
  const task = queue.shift();
  if (!task) {
    return;
  }
  queueRunning = true;
  task(() => {
    queueRunning = false;
    runQueue();
  });
}

/**
 * 描画済みのブロックへキャプションを付け、pandoc 発行版と同じ figure を作る。
 *
 * pandoc 発行版はキャプションを持つ図だけを ``<figure>`` にするため、
 * キャプションが無いブロックは包まない。
 * ``CodeBlock:`` 行で既に figure へ包まれている場合は、その figcaption を
 * 優先する。``CodeBlock:`` 行が ``caption`` 行より優先される規則は
 * bin/pandoc-filters/codeblock-caption.lua と同じ。
 *
 * @param {HTMLElement} block 描画済みの div 要素。
 * @param {string} caption ソースから取り出したキャプション。
 */
function addCaption(block, caption) {
  if (!caption || block.closest("figure")) {
    return;
  }

  const figure = document.createElement("figure");
  figure.className = "docsfw-figure";
  block.parentNode.insertBefore(figure, block);
  figure.appendChild(block);

  const element = document.createElement("figcaption");
  element.className = "docsfw-caption";
  element.textContent = caption;
  figure.appendChild(element);
}

/**
 * 1 個のブロックを描画する。
 *
 * @param {HTMLElement} block 対象の div 要素。
 */
function renderBlock(block) {
  if (block.dataset.docsfwState === "rendering" || block.dataset.docsfwState === "done") {
    return;
  }
  block.dataset.docsfwState = "rendering";

  if (block.dataset.docsfwSource === undefined) {
    block.dataset.docsfwSource = block.textContent;
  }

  const prepared = preparePlantUmlSource(block.dataset.docsfwSource);
  block.textContent = "";
  block.classList.add("docsfw-plantuml--pending");

  queue.push((done) => {
    const finish = (html, failed) => {
      block.classList.remove("docsfw-plantuml--pending");
      block.dataset.docsfwState = "done";
      if (failed) {
        block.classList.add("docsfw-plantuml--error");
        block.textContent = html;
      } else {
        block.innerHTML = html;
        addCaption(block, prepared.caption);
      }
      done();
    };

    try {
      // renderToString の第 4 引数は README に明記が無いが、plantuml.js の
      // コンパイル済みコード上は render(lines, targetId, {dark}) と同じ
      // dark フラグを共有しており、ダーク モードの配色切り替えに使える。
      renderToString(
        prepared.text.split("\n"),
        (svg) => finish(svg, false),
        (error) => finish("PlantUML のレンダリングに失敗しました: " + error, true),
        { dark: isDarkScheme() }
      );
    } catch (error) {
      finish("PlantUML のレンダリングに失敗しました: " + error, true);
    }
  });

  runQueue();
}

/** ページ内のすべてのブロックを監視対象にする。 */
function observeBlocks() {
  const blocks = document.querySelectorAll(BLOCK_SELECTOR);
  if (blocks.length === 0) {
    return;
  }

  if (typeof IntersectionObserver !== "function") {
    blocks.forEach(renderBlock);
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          observer.unobserve(entry.target);
          renderBlock(entry.target);
        }
      }
    },
    { rootMargin: OBSERVER_MARGIN }
  );

  blocks.forEach((block) => observer.observe(block));
}

/** カラー スキームの切り替えで、描画済みの図を作り直す。 */
function watchColorScheme() {
  let previous = isDarkScheme();
  const observer = new MutationObserver(() => {
    const current = isDarkScheme();
    if (current === previous) {
      return;
    }
    previous = current;
    document.querySelectorAll(BLOCK_SELECTOR).forEach((block) => {
      if (block.dataset.docsfwState === "done") {
        block.dataset.docsfwState = "";
        renderBlock(block);
      }
    });
  });
  observer.observe(document.body, { attributes: true, attributeFilter: ["data-md-color-scheme"] });
}

function initialize() {
  observeBlocks();
  watchColorScheme();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialize);
} else {
  initialize();
}

// Material のインスタント ローディングでページが差し替わったときに再初期化する。
if (window.document$ && typeof window.document$.subscribe === "function") {
  window.document$.subscribe(observeBlocks);
}
