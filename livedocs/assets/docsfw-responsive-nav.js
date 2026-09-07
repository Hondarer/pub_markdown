/* Pandoc HTML と共通のレスポンシブ ナビゲーション配置を適用する。 */
(function () {
  'use strict';

  var wideLayout = window.matchMedia('(min-width: 1400px)');
  /* Material がナビゲーションを入れ子の板 (スライド パネル) にする境界。
     打ち消す相手と一致させるため、docsfw の 1399px ではなくこの値を使う。 */
  var panelLayout = window.matchMedia('(max-width: 76.234375em)');
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

  /* 目次を入れる一覧を決める。
     Material は約 1220px 未満でナビゲーションを入れ子の板にし、ドロワーを
     開くと現在ページが属する板を表示する。根の一覧へ入れた目次は表示中の板の
     背面に回り、見出しだけが板の行に重なって見える。この幅では、現在ページの
     リンクが属する一覧 (= 表示中の板の一覧) を入れ先にする。
     1220px から 1399px の帯は板にならず一覧が 1 本につながるため、従来どおり
     根の一覧の最後へ入れる。 */
  function getPanelList() {
    var activeLink = document.querySelector(
      '.md-sidebar--primary .md-nav__link--active'
    );
    if (!activeLink || !activeLink.closest) { return null; }

    /* 現在ページ自身が節 (navigation.indexes の索引ページ) の場合、開くのは
       その節の板になる。親の一覧ではなく、節が持つ一覧を入れ先にする。 */
    var activeItem = activeLink.closest('.md-nav__item');
    var nestedList = activeItem
      ? activeItem.querySelector(':scope > nav.md-nav > .md-nav__list')
      : null;

    return nestedList || activeLink.closest('.md-nav__list');
  }

  function getTargetList() {
    if (panelLayout.matches) {
      var panelList = getPanelList();
      if (panelList) { return panelList; }
    }

    return document.querySelector(
      '.md-sidebar--primary nav.md-nav--primary > .md-nav__list'
    );
  }

  /* 目次は文書ツリーの一覧の最後の項目として入れる。一覧の中へ入れれば、
     ファイル単位の目次に続いて 1 本のスクロールで並ぶ。
     テンプレートの変更で一覧が見つからない場合に備え、従来の
     .md-sidebar__inner の末尾へ div で追加する経路を残す。 */
  function getCombinedContainer() {
    var primaryList = getTargetList();

    if (combinedContainer && combinedContainer.isConnected) {
      /* 幅が変わると入れ先の一覧も変わる。同じ器のまま移す。 */
      if (primaryList && combinedContainer.parentNode !== primaryList) {
        primaryList.appendChild(combinedContainer);
      }
      return combinedContainer;
    }

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

  [wideLayout, panelLayout].forEach(function (query) {
    if (query.addEventListener) {
      query.addEventListener('change', placeToc);
    } else {
      query.addListener(placeToc);
    }
  });

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
