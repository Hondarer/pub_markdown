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
  var drawerToggle = null;

  /* ページ内目次も現在見出しへ .md-nav__link--active を付けるため、
     文書ツリーの現在ページだけを選ぶ。 */
  function getActivePageLink() {
    var links = document.querySelectorAll(
      '.md-sidebar--primary .md-nav__link--active[href]'
    );
    for (var i = 0; i < links.length; i++) {
      if (!links[i].closest('.docsfw-combined-toc')) { return links[i]; }
    }
    return null;
  }

  function resolveElements() {
    var nextToc = document.querySelector('.md-sidebar--secondary nav.md-nav--secondary');
    if (nextToc && nextToc !== toc) {
      toc = nextToc;
      originalParent = toc.parentNode;
      originalNextSibling = toc.nextSibling;
      combinedContainer = null;
    }
  }

  /* 表示中の板 (スライド パネル) の nav を返す。
     Material は約 1220px 未満でナビゲーションを入れ子の板にし、どの板を見せるかは
     各階層のチェックボックス (.md-nav__toggle) が checked かどうかで決まる。
     根の板から checked の子板をたどり、行き着いた板が表示中の板になる。
     現在ページのリンクが属する一覧は、表示中の板の一覧とは限らない。
     navigation.indexes の索引ページでは、その節自身の板が開いた状態で始まり、
     リンクは 1 つ上の一覧にある。戻る操作でも表示中の板だけが変わる。 */
  function getVisiblePanelNav() {
    var nav = document.querySelector('.md-sidebar--primary nav.md-nav--primary');
    while (nav) {
      var list = nav.querySelector(':scope > .md-nav__list');
      if (!list) { return nav; }
      var child = null;
      for (var i = 0; i < list.children.length; i++) {
        var toggle = list.children[i].querySelector(':scope > input.md-nav__toggle');
        var panel = list.children[i].querySelector(':scope > nav.md-nav');
        /* __toc は現在ページの行に付くページ内目次の開閉で、板ではない。
           重なった場合は後ろの要素が上に描かれるため、最後の checked を採る。 */
        if (toggle && panel && toggle.checked && toggle.id !== '__toc') { child = panel; }
      }
      if (!child) { return nav; }
      nav = child;
    }
    return nav;
  }

  /* 目次を入れる一覧を決める。
     根の一覧へ入れた目次は表示中の板の背面に回り、見出しだけが板の行に重なって
     見える。板になる幅では、表示中の板の一覧を入れ先にする。
     1220px から 1399px の帯は板にならず一覧が 1 本につながるため、従来どおり
     根の一覧の最後へ入れる。 */
  function getPanelList() {
    var nav = getVisiblePanelNav();
    return nav ? nav.querySelector(':scope > .md-nav__list') : null;
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

  /* ドロワーは横方向へスクロールしない。表示していない板は translateX で
     右へ退避しているだけのため、.md-sidebar__scrollwrap の scrollWidth は
     板の枚数だけ横に広い。何かの拍子に横位置が動くと、overflow-x: hidden で
     スクロール バーが出ず、利用者には戻す手段が無い。常に左端へ戻す。 */
  function resetHorizontalScroll() {
    var wrap = document.querySelector('.md-sidebar--primary .md-sidebar__scrollwrap');
    if (wrap && wrap.scrollLeft !== 0) { wrap.scrollLeft = 0; }
  }

  /* 中幅では実際のスクロール コンテナーを .md-nav__list へ移しているため、
     Material が .md-sidebar__scrollwrap に書く初期位置は効かない。
     Pandoc HTML と同じく、ドロワーを開くたびに現在ページを中央へ出す。
     板になる狭幅では、ページ内目次の現在見出しを優先して中央へ出す。
     現在見出しがない文書上端では、表示中の板に現在ページの行がある場合だけ
     その行を中央へ出す。表示していない板の行へ scrollIntoView すると横方向へ
     スクロールするため、表示中の一覧に含まれる項目だけを対象にする。 */
  function revealDrawerSelection() {
    if (wideLayout.matches || !drawerToggle || !drawerToggle.checked) { return; }
    var activeLink = panelLayout.matches
      ? document.querySelector(
        '.docsfw-combined-toc a.md-nav__link--active[href^="#"]')
      : null;
    if (!activeLink) { activeLink = getActivePageLink(); }
    if (!activeLink) { return; }
    var panelList = panelLayout.matches ? getPanelList() : null;
    if (panelList && !panelList.contains(activeLink)) {
      resetHorizontalScroll();
      return;
    }
    window.requestAnimationFrame(function () {
      if (!drawerToggle || !drawerToggle.checked || !activeLink.isConnected) { return; }
      activeLink.scrollIntoView({ block: 'center', behavior: 'auto' });
      resetHorizontalScroll();
    });
  }

  function bindDrawerToggle() {
    var nextToggle = document.getElementById('__drawer');
    if (nextToggle === drawerToggle) { return; }
    if (drawerToggle) { drawerToggle.removeEventListener('change', revealDrawerSelection); }
    drawerToggle = nextToggle;
    if (drawerToggle) { drawerToggle.addEventListener('change', revealDrawerSelection); }
  }

  function init() {
    if (!toc || !toc.isConnected) {
      toc = null;
      originalParent = null;
      originalNextSibling = null;
      combinedContainer = null;
    }
    placeToc();
    bindDrawerToggle();
  }

  [wideLayout, panelLayout].forEach(function (query) {
    if (query.addEventListener) {
      query.addEventListener('change', placeToc);
    } else {
      query.addListener(placeToc);
    }
  });

  document.addEventListener('click', closeDrawerFromToc);

  /* 板の出し入れはチェックボックスの状態変化で起きる。change は文書まで
     上がるため、ここで受けて目次を新しい表示中の板へ移す。
     Pandoc HTML (docsfw-nav.js の setActivePanel) と同じく、どの階層の板を
     見ていてもファイル単位の目次に続けてページ内目次を出す。 */
  document.addEventListener('change', function (event) {
    var target = event.target;
    if (!target || !target.classList) { return; }
    if (!target.classList.contains('md-nav__toggle') || target.id === '__toc') { return; }
    placeToc();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  if (window.document$ && typeof window.document$.subscribe === 'function') {
    window.document$.subscribe(init);
  }
}());
