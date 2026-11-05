/* Quản trị TradingBonusHub – chỉ làm tăng trải nghiệm; mọi form vẫn chạy khi tắt JS. */
(function () {
  'use strict';
  var doc = document.documentElement;
  doc.classList.remove('no-js');
  doc.classList.add('js');

  var MAX_UPLOAD = 5 * 1024 * 1024;

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function on(root, type, sel, fn) {
    root.addEventListener(type, function (e) {
      var t = e.target.closest(sel);
      if (t && root.contains(t)) fn(e, t);
    });
  }
  function fire(el) { el.dispatchEvent(new Event('input', { bubbles: true })); }
  function attr(submitter, form, name) {
    return (submitter && submitter.getAttribute(name)) || form.getAttribute(name);
  }
  // Đặt (hoặc bỏ) một <img> duy nhất trong el.
  function putImg(el, src) {
    el.textContent = '';
    if (src) { var img = document.createElement('img'); img.src = src; img.alt = ''; el.appendChild(img); }
  }

  /* ---------- Nút ↑ ↓ ✕ dùng chung cho dòng lặp và danh sách chữ ---------- */
  // item: phần tử con trực tiếp của list; act: up | down | remove.
  function reorder(list, item, act) {
    if (act === 'remove') {
      if (list.children.length === 1) $$('input, textarea', item).forEach(function (i) { i.value = ''; fire(i); });
      else list.removeChild(item);
    } else if (act === 'up' && item.previousElementSibling) {
      list.insertBefore(item, item.previousElementSibling);
    } else if (act === 'down' && item.nextElementSibling) {
      list.insertBefore(item.nextElementSibling, item);
    }
    refreshArrows(list);
  }
  function refreshArrows(list) {
    var n = list.children.length;
    Array.prototype.forEach.call(list.children, function (item, i) {
      var up = $(':scope > [data-tools] > [data-act=up]', item), down = $(':scope > [data-tools] > [data-act=down]', item);
      if (up) up.disabled = i === 0;
      if (down) down.disabled = i === n - 1;
    });
  }
  // Một handler cho mọi danh sách: tìm list gần nhất chứa nút.
  function initReorder() {
    on(document, 'click', '[data-tools] > [data-act]', function (e, btn) {
      var tools = btn.parentNode, item = tools.parentNode, list = item.parentNode;
      reorder(list, item, btn.getAttribute('data-act'));
      var lines = list.closest('.lines-list');
      if (lines) lines.dispatchEvent(new Event('lines-change'));
      if (document.contains(btn)) btn.focus();
    });
  }
  function toolsEl() {
    var tools = document.createElement('div');
    tools.className = 'rows-tools';
    tools.setAttribute('data-tools', '');
    [['↑', 'up', 'Lên'], ['↓', 'down', 'Xuống'], ['✕', 'remove', 'Xóa']].forEach(function (b) {
      var btn = document.createElement('button');
      btn.type = 'button'; btn.className = 'icon-btn' + (b[1] === 'remove' ? ' icon-btn-danger' : '');
      btn.textContent = b[0]; btn.setAttribute('data-act', b[1]); btn.setAttribute('aria-label', b[2]);
      tools.appendChild(btn);
    });
    return tools;
  }

  /* ---------- "Đã lưu" tự ẩn sau 1,8s ---------- */
  function initFlash() {
    var f = $('[data-flash]');
    if (f) setTimeout(function () { f.classList.add('is-hidden'); }, 1800);
  }

  /* ---------- Nút "Xuất bản thay đổi": màn danh sách lưu ngay từng thao tác nên chỉ báo đã lưu ---------- */
  function initPublish() {
    var note = $('[data-publish-note]'), timer = null;
    function show() {
      var old = $('[data-flash]');
      if (old) old.hidden = true;
      note.hidden = false;
      clearTimeout(timer);
      timer = setTimeout(function () { note.hidden = true; }, 1800);
    }
    on(document, 'click', '[data-publish]', show);
    // Gửi email: nút này lưu nháp; chưa soạn gì thì không có gì để lưu.
    var mail = $('#mail-form');
    var draftBtn = mail && $('button[form="mail-form"]');
    if (draftBtn) draftBtn.addEventListener('click', function (e) {
      if (mail.elements.subject.value.trim() || mail.elements.body.value.trim()) return;
      e.preventDefault();
      show();
    });
  }

  /* ---------- Công tắc, mũi tên: tải lại trang vẫn giữ vị trí cuộn ---------- */
  function initScroll() {
    var KEY = 'admin-scroll';
    try {
      var saved = JSON.parse(sessionStorage.getItem(KEY));
      sessionStorage.removeItem(KEY);
      if (saved && saved.path === location.pathname) window.scrollTo(0, saved.y);
    } catch (e) { /* trình duyệt chặn storage: bỏ qua */ }
    document.addEventListener('submit', function (e) {
      if (!e.target.closest('.toggle-form')) return;
      try { sessionStorage.setItem(KEY, JSON.stringify({ path: location.pathname, y: window.scrollY })); } catch (err) { /* như trên */ }
    });
  }

  /* ---------- Ô tìm kiếm lọc ngay khi gõ: lấy lại trang, thay các vùng data-live ---------- */
  function initLiveSearch() {
    var form = $('[data-live-search]');
    if (!form) return;
    var timer = null, pending = null;
    function run() {
      var url = form.getAttribute('action') + '?' + new URLSearchParams(new FormData(form)).toString();
      if (pending) pending.abort();
      pending = new AbortController();
      fetch(url, { credentials: 'same-origin', signal: pending.signal })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
        .then(function (html) {
          var next = new DOMParser().parseFromString(html, 'text/html');
          $$('[data-live]').forEach(function (el) {
            var fresh = $('[data-live="' + el.getAttribute('data-live') + '"]', next);
            if (fresh) el.replaceWith(fresh);
          });
          history.replaceState(null, '', url);
        }).catch(function () { /* lỗi mạng hoặc bị hủy: Enter vẫn tìm được */ });
    }
    form.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 200); });
  }

  /* ---------- Xác nhận trước khi xóa / gửi ---------- */
  function initConfirm() {
    var dlg = $('#confirm-dialog');
    document.addEventListener('submit', function (e) {
      var form = e.target, submitter = e.submitter;
      var msg = attr(submitter, form, 'data-confirm');
      if (!msg) return;
      e.preventDefault();
      var proceed = function () {
        // form.submit() không kèm nút bấm: thêm tạm giá trị nút (vd. action=send) rồi gỡ ngay
        var h = null;
        if (submitter && submitter.name) {
          h = document.createElement('input');
          h.type = 'hidden'; h.name = submitter.name; h.value = submitter.value;
          form.appendChild(h);
        }
        form.submit();
        if (h) form.removeChild(h);
      };
      if (!dlg || typeof dlg.showModal !== 'function') { if (window.confirm(msg)) proceed(); return; }
      $('[data-confirm-text]', dlg).textContent = msg;
      var ok = $('button[value=ok]', dlg);
      ok.textContent = attr(submitter, form, 'data-confirm-ok') || 'Xóa';
      ok.className = (attr(submitter, form, 'data-confirm-variant') || 'danger') === 'danger' ? 'btn-danger-solid' : 'btn-primary';
      dlg.returnValue = '';
      dlg.showModal();
      dlg.addEventListener('close', function handler() {
        dlg.removeEventListener('close', handler);
        if (dlg.returnValue === 'ok') proceed();
      });
    }, true);
  }

  /* ---------- Drawer: Esc đóng, focus ô đầu ---------- */
  function initDrawer() {
    var wrap = $('[data-drawer]');
    if (!wrap) return;
    var close = $('a[data-drawer-close]', wrap);
    // Thiết kế không focus ô đầu: focus vào drawer để Tab đi từ đây, chỉ nhảy vào ô khi có lỗi.
    ($('.drawer-body .has-error :is(input, select, textarea)', wrap) || $('.drawer', wrap)).focus();
    var dirty = !!$('.drawer-body .alert-error', wrap);  // lỗi 400: form đang giữ chữ chưa lưu
    wrap.addEventListener('click', function (e) {
      if (e.target.closest('[data-act], [data-row-add], .btn-add')) dirty = true;
    });
    function canLeave() { return !dirty || window.confirm('Bỏ các thay đổi chưa lưu?'); }
    ['input', 'change'].forEach(function (t) { wrap.addEventListener(t, function () { dirty = true; }); });
    $$('[data-drawer-close]', wrap).forEach(function (a) {
      a.addEventListener('click', function (e) { if (!canLeave()) e.preventDefault(); });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape' || !close || $('dialog[open]')) return;
      if (canLeave()) window.location.href = close.href;
    });
  }

  /* ---------- Danh sách lặp: thêm dòng ---------- */
  function rowsInit() {
    $$('[data-rows]').forEach(function (box) {
      var list = $('[data-rows-list]', box);
      // dòng trống dự phòng cho chế độ tắt JS: bỏ đi nếu đã có dòng khác
      var blank = $(':scope > [data-blank]', list);
      if (blank && list.children.length > 1) list.removeChild(blank);
      else if (blank) blank.removeAttribute('data-blank');
      refreshArrows(list);
    });
    on(document, 'click', '[data-row-add]', function (e, btn) {
      var box = btn.closest('[data-rows]'), list = $('[data-rows-list]', box);
      var node = $('template[data-rows-template]', box).content.firstElementChild.cloneNode(true);
      list.appendChild(node);
      linesInit(node);
      refreshArrows(list);
      var f = $('input, textarea', node);
      if (f) f.focus();
    });
  }

  /* ---------- Textarea "mỗi dòng một ý" → danh sách ô ---------- */
  function splitPair(line) {
    var i = line.indexOf('|');
    return i < 0 ? [line.trim(), ''] : [line.slice(0, i).trim(), line.slice(i + 1).trim()];
  }
  function linesInit(root) {
    $$('textarea[data-lines]', root).forEach(function (ta) {
      if (ta.dataset.ready) return;
      ta.dataset.ready = '1';
      var pair = ta.getAttribute('data-lines') === 'pair';
      var box = document.createElement('div');
      box.className = 'lines-list';
      var add = document.createElement('button');
      add.type = 'button'; add.className = 'btn-add'; add.textContent = ta.getAttribute('data-add-label') || '+ Thêm dòng';
      ta.hidden = true;
      ta.after(box, add);

      function sync() {
        ta.value = $$('.lines-item', box).map(function (item) {
          var v = $$('input', item).map(function (i) { return i.value.trim(); });
          return pair ? (v[0] || v[1] ? v[0] + ' | ' + v[1] : '') : v[0];
        }).filter(Boolean).join('\n');
        if (ta.hasAttribute('data-bind')) fire(ta);
      }
      function addItem(text, focus) {
        var item = document.createElement('div');
        item.className = 'lines-item' + (pair ? ' lines-pair' : '');
        (pair ? splitPair(text) : [text]).forEach(function (p, i) {
          var inp = document.createElement('input');
          inp.type = 'text'; inp.value = p;
          inp.placeholder = pair ? (i === 0 ? 'Nhãn' : '/duong-dan hoặc https://') : 'Nội dung';
          inp.setAttribute('aria-label', inp.placeholder);
          item.appendChild(inp);
        });
        item.appendChild(toolsEl());
        box.appendChild(item);
        refreshArrows(box);
        if (focus) $('input', item).focus();
      }
      var lines = ta.value.split('\n').filter(function (l) { return l.trim(); });
      (lines.length ? lines : ['']).forEach(function (l) { addItem(l); });
      box.addEventListener('input', function (e) { e.stopPropagation(); sync(); });
      box.addEventListener('lines-change', sync);
      add.addEventListener('click', function () { addItem('', true); });
    });
  }

  /* ---------- Trường ảnh + hộp chọn từ thư viện ---------- */
  // Cập nhật ô ảnh: đường dẫn, ảnh nhỏ, ghi chú và khối xem trước (data-pv-img).
  function setImage(field, src, note, path) {
    var pathInput = $('[data-img-path]', field);
    if (path !== undefined) pathInput.value = path;
    putImg($('[data-img-thumb]', field), src);
    if (note) $('[data-img-name]', field).textContent = note;
    fire(pathInput);  // báo cho drawer biết form đã đổi (hộp chọn ảnh nằm ngoài drawer)
    var key = pathInput.getAttribute('data-bind-img');
    if (!key) return;
    $$('[data-pv-img="' + key + '"]').forEach(function (el) {
      if (el.hasAttribute('data-pv-bg')) el.style.backgroundImage = src ? 'url("' + src.replace(/"/g, '') + '")' : '';
      else putImg(el, src);
    });
  }
  function initImages() {
    $$('[data-img-name]').forEach(function (n) { n.dataset.hint = n.textContent; });
    on(document, 'change', '[data-img-file]', function (e, input) {
      var field = input.closest('[data-image-field]');
      var f = input.files && input.files[0];
      var saved = $('[data-img-path]', field).value.trim();
      if (!f) { setImage(field, saved, $('[data-img-name]', field).dataset.hint); return; }
      if (f.size > MAX_UPLOAD) {  // không gửi file chắc chắn bị từ chối
        input.value = '';
        setImage(field, saved, f.name + ' quá 5MB, chưa được chọn.');
        return;
      }
      var note = 'Sẽ tải lên khi lưu: ' + f.name + ' (' + Math.round(f.size / 1024) + ' KB)';
      // CSP chỉ cho ảnh 'self' và data: → đọc file thành data URL (không dùng blob:)
      var reader = new FileReader();
      reader.onload = function () { setImage(field, reader.result, note); };
      reader.readAsDataURL(f);
    });
    on(document, 'click', '[data-img-clear]', function (e, btn) {
      var field = btn.closest('[data-image-field]');
      $('[data-img-file]', field).value = '';
      setImage(field, '', 'Đã bỏ ảnh (lưu để áp dụng).', '');
    });
    on(document, 'change', '[data-img-path]', function (e, input) {
      setImage(input.closest('[data-image-field]'), input.value.trim());
    });

    var picker = $('#media-picker');
    if (!picker) {
      $$('[data-pick]').forEach(function (b) { b.hidden = true; });
      return;
    }
    var current = null, filterInput = $('[data-picker-filter]', picker);
    function filter(q) {
      q = q.trim().toLowerCase();
      $$('.picker-item', picker).forEach(function (it) {
        it.hidden = q && it.getAttribute('data-alt').indexOf(q) < 0 && it.getAttribute('data-path').indexOf(q) < 0;
      });
    }
    on(document, 'click', '[data-pick]', function (e, btn) {
      current = btn.closest('[data-image-field]');
      picker.showModal();
      filterInput.value = ''; filter('');
      filterInput.focus();
    });
    on(picker, 'click', '[data-picker-close]', function () { picker.close(); });
    picker.addEventListener('click', function (e) { if (e.target === picker) picker.close(); });
    on(picker, 'click', '.picker-item', function (e, item) {
      if (!current) return;
      var path = item.getAttribute('data-path');
      $('[data-img-file]', current).value = '';
      setImage(current, path, 'Đã chọn từ thư viện.', path);
      picker.close();
    });
    filterInput.addEventListener('input', function (e) { filter(e.target.value); });
  }

  /* ---------- Xem trước chữ trực tiếp ---------- */
  function initPreview() {
    var targets = {};
    $$('[data-pv]').forEach(function (el) {
      var k = el.getAttribute('data-pv');
      (targets[k] = targets[k] || []).push(el);
    });
    document.addEventListener('input', function (e) {
      var els = targets[e.target.getAttribute && e.target.getAttribute('data-bind')];
      if (!els) return;
      els.forEach(function (el) { el.textContent = e.target.value || el.getAttribute('data-pv-empty') || ''; });
    });
  }

  /* ---------- Copy link (Thư viện ảnh) ---------- */
  function initCopy() {
    on(document, 'click', '[data-copy]', function (e, btn) {
      var text = new URL(btn.getAttribute('data-copy'), window.location.origin).href;
      var done = function () { var old = btn.textContent; btn.textContent = 'Đã copy'; setTimeout(function () { btn.textContent = old; }, 1500); };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () { window.prompt('Copy link:', text); });
      else window.prompt('Copy link:', text);
    });
  }

  /* ---------- Kéo thả ảnh vào ô upload ---------- */
  function initDropzone() {
    $$('[data-dropzone]').forEach(function (zone) {
      var input = $('input[type=file]', zone), label = $('[data-drop-label]', zone);
      function show() {
        var n = input.files.length;
        label.textContent = n ? (n === 1 ? input.files[0].name : n + ' ảnh đã chọn') : label.getAttribute('data-default');
      }
      ['dragenter', 'dragover'].forEach(function (t) { zone.addEventListener(t, function (e) { e.preventDefault(); zone.classList.add('is-over'); }); });
      ['dragleave', 'drop'].forEach(function (t) { zone.addEventListener(t, function () { zone.classList.remove('is-over'); }); });
      zone.addEventListener('drop', function (e) { e.preventDefault(); input.files = e.dataTransfer.files; show(); });
      input.addEventListener('change', show);
    });
  }

  /* ---------- Gửi email: đếm lại người nhận khi đổi nhóm ---------- */
  function initAudience() {
    var form = $('[data-audience-form]');
    if (!form || form.hasAttribute('data-retry')) return;  // gửi lại: nhãn cố định, không đếm theo nhóm
    var out = $('[data-audience-count]', form), send = out.closest('button');
    var pending = null;
    function recount() {
      var params = new URLSearchParams();
      $$('input[name=audience]:checked', form).forEach(function (c) { params.append('aud', c.value); });
      if (pending) pending.abort();  // chỉ lấy kết quả của lần chọn cuối
      out.textContent = '…';  // số cũ không còn đúng, kể cả khi yêu cầu dưới đây lỗi
      send.setAttribute('data-confirm', 'Gửi email này tới các nhóm đã chọn?');
      send.disabled = true;
      pending = new AbortController();
      fetch(form.getAttribute('data-audience-url') + '?' + params.toString(), { credentials: 'same-origin', signal: pending.signal })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) {
          var n = d.count.toLocaleString('vi-VN');
          out.textContent = n;
          send.setAttribute('data-confirm', 'Gửi email này tới ' + n + ' người đăng ký?');
          send.disabled = d.count === 0;  // 0 người: server cũng từ chối
        }).catch(function (err) {  // lỗi: giữ "…" và câu xác nhận chung, không hiện số sai
          if (err.name !== 'AbortError') send.disabled = false;
        });
    }
    form.addEventListener('change', function (e) { if (e.target.name === 'audience') recount(); });
    // Trình duyệt có thể khôi phục ô đã tick khi tải lại/quay lại: số do server in khi đó không còn đúng.
    window.addEventListener('pageshow', function () {
      var restored = $$('input[name=audience]', form).some(function (c) { return c.checked !== c.defaultChecked; });
      if (restored) recount();
      else send.disabled = out.textContent === '0';
    });
  }

  /* ---------- Mobile: đóng menu khi chọn mục ---------- */
  function initNav() {
    var t = $('#nav-toggle');
    if (t) on(document, 'click', '.nav-link', function () { t.checked = false; });
  }

  // Sau lỗi 400, ô nhập mang giá trị vừa gửi: đồng bộ khối xem trước với ô nhập.
  function syncPreview() {
    if (!$('.page-form-layout') || !$('.alert-error')) return;
    $$('[data-bind]').forEach(fire);
    $$('[data-bind-img]').forEach(function (i) { setImage(i.closest('[data-image-field]'), i.value.trim()); });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initScroll(); initFlash(); initPublish(); initLiveSearch(); initConfirm(); initDrawer(); initReorder(); rowsInit(); linesInit(document);
    initImages(); initPreview(); initCopy(); initDropzone(); initAudience(); initNav(); syncPreview();
  });
})();
