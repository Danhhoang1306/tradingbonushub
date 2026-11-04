/* JS tối thiểu cho site public: menu mobile, lọc bonus và tab "Loại bonus" ở trang chủ.
   Mọi chức năng chính (link, form) vẫn chạy khi tắt JS. */
(function () {
  'use strict';

  // Menu mobile
  document.querySelectorAll('[data-nav-toggle]').forEach(function (btn) {
    var header = btn.closest('[data-header]');
    btn.addEventListener('click', function () {
      var open = header.classList.toggle('is-nav-open');
      btn.setAttribute('aria-expanded', String(open));
      btn.setAttribute('aria-label', open ? 'Đóng menu' : 'Mở menu');
    });
  });

  // Đếm view quảng cáo dọc: chỉ khi rail thật sự hiển thị (cùng ngưỡng 1572px với .rail trong site.css)
  if (navigator.sendBeacon && window.matchMedia('(min-width: 1572px)').matches) {
    document.querySelectorAll('[data-view-url]').forEach(function (el) {
      navigator.sendBeacon(el.dataset.viewUrl);
    });
  }

  // Lọc "Bonus mới nhất" theo loại (trang chủ)
  var filterGroup = document.querySelector('[data-filter-group]');
  function applyFilter(type) {
    filterGroup.querySelectorAll('[data-filter]').forEach(function (b) {
      var on = b.dataset.filter === type;
      b.classList.toggle('is-active', on);
      b.setAttribute('aria-pressed', String(on));
    });
    document.querySelectorAll('#bonus [data-type]').forEach(function (card) {
      card.hidden = type !== 'all' && card.dataset.type !== type;
    });
  }
  if (filterGroup) {
    filterGroup.addEventListener('click', function (e) {
      var b = e.target.closest('[data-filter]');
      if (b) applyFilter(b.dataset.filter);
    });
  }
  document.querySelectorAll('[data-filter-go]').forEach(function (a) {
    // Có nút lọc cho loại này thì lọc ngay tại chỗ, không thì đi theo link tới /bonus?type=.
    a.addEventListener('click', function (e) {
      if (!filterGroup || !filterGroup.querySelector('[data-filter="' + a.dataset.filterGo + '"]')) return;
      e.preventDefault();
      applyFilter(a.dataset.filterGo);
      document.getElementById('bonus').scrollIntoView();
    });
  });

  // Tab "Loại bonus"
  var tabs = Array.prototype.slice.call(document.querySelectorAll('[data-type-tab]'));
  function selectType(tab, focus) {
    tabs.forEach(function (t) {
      var on = t === tab;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-selected', String(on));
      t.tabIndex = on ? 0 : -1;
    });
    document.querySelectorAll('[data-type-panel]').forEach(function (p) {
      p.hidden = p.dataset.typePanel !== tab.dataset.typeTab;
    });
    if (focus) tab.focus();
  }
  tabs.forEach(function (t, i) {
    t.tabIndex = i === 0 ? 0 : -1;
    t.addEventListener('click', function () { selectType(t, false); });
    t.addEventListener('keydown', function (e) {
      var d = e.key === 'ArrowDown' || e.key === 'ArrowRight' ? 1 : e.key === 'ArrowUp' || e.key === 'ArrowLeft' ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      selectType(tabs[(i + d + tabs.length) % tabs.length], true);
    });
  });
})();
