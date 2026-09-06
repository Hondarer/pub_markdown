/* Pandoc HTML と共通のレスポンシブ ナビゲーション配置を適用する。 */
(function () {
  'use strict';

  var wideLayout = window.matchMedia('(min-width: 1625px)');
  var toc = null;
  var originalParent = null;
  var originalNextSibling = null;
  var combinedContainer = null;

  function resolveElements() {
    var nextToc = document.querySelector('.md-sidebar--secondary nav.md-nav--secondary');
    if (nextToc && nextToc !== toc) {
      toc = nextToc;
      originalParent = toc.parentNode;
      originalNextSibling = toc.nextSibling;
      combinedContainer = null;
    }
  }

  /* 目次は文書ツリーの一覧 (.md-nav--primary > .md-nav__list) の最後の項目として
     入れる。Material は約 1220px 未満で .md-nav--primary を絶対配置の板にして
     通常フローから外すため、一覧の外へ置いた要素は板の背面に隠れる。
     一覧の中へ入れれば、ファイル単位の目次に続いて 1 本のスクロールで並ぶ。
     テンプレートの変更で一覧が見つからない場合に備え、従来の
     .md-sidebar__inner の末尾へ div で追加する経路を残す。 */
  function getCombinedContainer() {
    if (combinedContainer && combinedContainer.isConnected) {
      return combinedContainer;
    }

    var primaryList = document.querySelector(
      '.md-sidebar--primary nav.md-nav--primary > .md-nav__list'
    );
    if (primaryList) {
      combinedContainer = document.createElement('li');
      combinedContainer.className = 'md-nav__item docsfw-combined-toc';
      primaryList.appendChild(combinedContainer);
      return combinedContainer;
    }

    var primaryInner = document.querySelector('.md-sidebar--primary .md-sidebar__inner');
    if (!primaryInner) { return null; }
    combinedContainer = document.createElement('div');
    combinedContainer.className = 'docsfw-combined-toc';
    primaryInner.appendChild(combinedContainer);
    return combinedContainer;
  }

  function placeToc() {
    resolveElements();
    if (!toc) { return; }

    if (wideLayout.matches) {
      if (originalParent && toc.parentNode !== originalParent) {
        originalParent.insertBefore(toc, originalNextSibling);
      }
      if (combinedContainer) {
        combinedContainer.remove();
        combinedContainer = null;
      }
      return;
    }

    var target = getCombinedContainer();
    if (target && toc.parentNode !== target) {
      target.appendChild(toc);
    }
  }

  /* ドロワーの中のページ内目次は同じページのアンカーへ移動するだけで、
     ページ遷移が起きない。Material がドロワーを閉じるのは遷移のときだけの
     ため、押した見出しがドロワーの背後に隠れたままになる。
     目次のリンクを押したら、覆いを押したときと同じようにドロワーを閉じる。 */
  function closeDrawerFromToc(event) {
    if (wideLayout.matches) { return; }

    var target = event.target;
    if (!target || !target.closest) { return; }
    if (!target.closest('.docsfw-combined-toc a')) { return; }

    var drawer = document.getElementById('__drawer');
    if (drawer) { drawer.checked = false; }
  }

  function init() {
    if (!toc || !toc.isConnected) {
      toc = null;
      originalParent = null;
      originalNextSibling = null;
      combinedContainer = null;
    }
    placeToc();
  }

  if (wideLayout.addEventListener) {
    wideLayout.addEventListener('change', placeToc);
  } else {
    wideLayout.addListener(placeToc);
  }

  document.addEventListener('click', closeDrawerFromToc);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  if (window.document$ && typeof window.document$.subscribe === 'function') {
    window.document$.subscribe(init);
  }
}());
