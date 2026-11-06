/* JS tối thiểu cho site public: menu mobile, lọc bonus và tab "Loại bonus" ở trang chủ.
   Mọi chức năng chính (link, form) vẫn chạy khi tắt JS. */
(function () {
  'use strict';

  // Menu mobile
  document.querySelectorAll('[data-nav-toggle]').forEach(function (btn) {
    var header = btn.closest('[data-header]');
    function setOpen(open) {
      header.classList.toggle('is-nav-open', open);
      btn.setAttribute('aria-expanded', String(open));
      btn.setAttribute('aria-label', open ? 'Đóng menu' : 'Mở menu');
    }
    btn.addEventListener('click', function () {
      setOpen(!header.classList.contains('is-nav-open'));
    });
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape' || !header.classList.contains('is-nav-open')) return;
      setOpen(false);
      btn.focus();
    });
  });

  // Đếm view quảng cáo dọc: chỉ khi rail thật sự hiển thị (cùng ngưỡng 1572px với .rail trong site.css)
  if (navigator.sendBeacon && window.matchMedia('(min-width: 1572px)').matches) {
    document.querySelectorAll('[data-view-url]').forEach(function (el) {
      navigator.sendBeacon(el.dataset.viewUrl);
    });
  }

  // Như thiết kế: sắp xếp, chọn sàn, tab chi tiết sàn giữ vị trí cuộn; tab danh sách về đầu trang; dải tab luôn giữ vị trí.
  // Tắt JS thì link vẫn chạy.
  var POS_KEY = 'tbh-keep-pos';
  var tabStrip = document.querySelector('.tabs');
  try {
    var pos = JSON.parse(sessionStorage.getItem(POS_KEY));
    sessionStorage.removeItem(POS_KEY);
    if (pos && pos.url === location.href) {
      if (tabStrip) tabStrip.scrollLeft = pos.left;
      window.scrollTo(0, pos.top);
    }
  } catch (e) { /* trình duyệt chặn lưu trữ: bỏ qua */ }
  function keepsTop(a) { return !a.closest('.tabs') || !!document.querySelector('.detail'); }
  document.querySelectorAll('.tabs a, .toolbar a, .compare-pick a').forEach(function (a) {
    a.addEventListener('click', function (e) {
      if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      try {
        sessionStorage.setItem(POS_KEY, JSON.stringify({ url: a.href, top: keepsTop(a) ? window.scrollY : 0, left: tabStrip ? tabStrip.scrollLeft : 0 }));
      } catch (err) { /* bỏ qua */ }
    });
  });

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
