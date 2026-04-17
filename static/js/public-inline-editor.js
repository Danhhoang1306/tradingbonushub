/**
 * Public page inline editor — loaded only when edit_mode=True.
 * Makes all [data-edit-field] elements click-to-edit.
 * Saves via PUT /api/page-content/bulk.
 */
(function () {
  'use strict';

  var LANG = document.documentElement.lang || 'vi';
  var changes = {};   // key → new value

  // ── Inject styles ──────────────────────────────────────────────────────────
  var style = document.createElement('style');
  style.textContent = [
    '[data-edit-field]{cursor:pointer;outline:2px dashed transparent;outline-offset:3px;transition:outline-color .15s,background .15s}',
    '[data-edit-field]:hover{outline-color:#1a73e8;background:rgba(26,115,232,.05)}',
    '[data-edit-field].ef-active{outline-color:#1a73e8;background:rgba(26,115,232,.08)}',
    '[data-edit-field][contenteditable=true]:focus{outline-color:#0d47a1;background:rgba(26,115,232,.1)}',
    '#ef-bar{position:fixed;top:0;left:0;right:0;z-index:999999;background:#0a1628;color:#fff;padding:8px 16px;',
    '  display:flex;align-items:center;gap:12px;font-family:-apple-system,BlinkMacSystemFont,sans-serif;',
    '  font-size:13px;box-shadow:0 2px 10px rgba(0,0,0,.4);line-height:1}',
    '#ef-bar .ef-badge{background:#c9a84c;color:#000;padding:3px 8px;border-radius:4px;font-weight:800;font-size:11px;letter-spacing:.5px;white-space:nowrap}',
    '#ef-bar .ef-hint{color:rgba(255,255,255,.5);font-size:12px;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
    '#ef-bar .ef-dirty{color:#c9a84c;font-size:12px;font-weight:700;white-space:nowrap}',
    '#ef-bar .ef-status{font-size:12px;white-space:nowrap}',
    '#ef-bar .ef-status.ok{color:#81c784}',
    '#ef-bar .ef-status.err{color:#ef9a9a}',
    '#ef-bar button{padding:6px 14px;border:none;border-radius:4px;cursor:pointer;font-size:12px;font-weight:700;white-space:nowrap}',
    '#ef-bar .ef-btn-save{background:#4caf50;color:#fff}',
    '#ef-bar .ef-btn-save:hover:not(:disabled){background:#388e3c}',
    '#ef-bar .ef-btn-save:disabled{background:#555;color:#999;cursor:default}',
    '#ef-bar .ef-btn-exit{background:rgba(255,255,255,.12);color:#fff}',
    '#ef-bar .ef-btn-exit:hover{background:rgba(255,255,255,.2)}',
    'body{padding-top:46px!important}',
  ].join('');
  document.head.appendChild(style);

  // ── Build toolbar ──────────────────────────────────────────────────────────
  var bar = document.createElement('div');
  bar.id = 'ef-bar';
  bar.innerHTML =
    '<span class="ef-badge">EDIT MODE</span>' +
    '<span class="ef-hint">Click any text to edit</span>' +
    '<span class="ef-dirty" id="ef-dirty"></span>' +
    '<span class="ef-status" id="ef-status"></span>' +
    '<button class="ef-btn-save" id="ef-save" disabled>Save Changes</button>' +
    '<button class="ef-btn-exit" id="ef-exit">Exit</button>';
  document.body.insertBefore(bar, document.body.firstChild);

  var btnSave  = document.getElementById('ef-save');
  var btnExit  = document.getElementById('ef-exit');
  var elDirty  = document.getElementById('ef-dirty');
  var elStatus = document.getElementById('ef-status');

  // ── Track changes ──────────────────────────────────────────────────────────
  function markChanged(key, val) {
    changes[key] = val;
    var n = Object.keys(changes).length;
    elDirty.textContent  = n > 0 ? (n + ' unsaved changes') : '';
    btnSave.disabled     = n === 0;
    if (window.parent !== window) {
      window.parent.postMessage({ type: 'efDirty', count: n }, '*');
    }
  }

  // ── Activate element ───────────────────────────────────────────────────────
  function activate(el) {
    if (el.contentEditable === 'true') { el.focus(); return; }
    // Deactivate any currently active
    document.querySelectorAll('[data-edit-field][contenteditable=true]').forEach(function (other) {
      if (other !== el) deactivate(other, true);
    });
    el.contentEditable = 'true';
    el.classList.add('ef-active');
    el.focus();
    // Move cursor to end
    try {
      var r = document.createRange();
      r.selectNodeContents(el);
      r.collapse(false);
      var s = window.getSelection();
      s.removeAllRanges();
      s.addRange(r);
    } catch (e) {}

    el.addEventListener('keydown', onKeydown);
    el.addEventListener('blur',    onBlur);
  }

  function deactivate(el, silent) {
    el.removeEventListener('keydown', onKeydown);
    el.removeEventListener('blur',    onBlur);
    el.contentEditable = 'false';
    el.classList.remove('ef-active');
    if (!silent) {
      var key = el.dataset.editField;
      var val = el.innerText; // preserve newlines
      markChanged(key, val);
    }
  }

  function onKeydown(e) {
    if (e.key === 'Escape') { e.target.blur(); }
    if (e.key === 'Enter' && !e.shiftKey && !e.target.dataset.editMultiline) {
      e.preventDefault();
      e.target.blur();
    }
  }

  function onBlur(e) { deactivate(e.target, false); }

  // ── Block all link navigation in edit mode ────────────────────────────────
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    if (href.startsWith('#')) return; // allow anchor scrolling
    e.preventDefault();
    e.stopPropagation();
  }, true);

  // ── Wire up all editable fields ────────────────────────────────────────────
  document.querySelectorAll('[data-edit-field]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      activate(el);
    });
    // Prevent any child links from navigating
    el.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function (e) { e.preventDefault(); });
    });
  });

  // ── Save ───────────────────────────────────────────────────────────────────
  btnSave.addEventListener('click', async function () {
    var items = Object.keys(changes).map(function (key) {
      return { key: key, lang: LANG, value: changes[key] };
    });
    if (!items.length) return;

    btnSave.disabled    = true;
    elStatus.textContent = 'Saving…';
    elStatus.className  = 'ef-status';

    try {
      var res = await fetch('/api/page-content/bulk', {
        method:      'PUT',
        headers:     { 'Content-Type': 'application/json' },
        body:        JSON.stringify(items),
        credentials: 'same-origin',
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var d = await res.json();
      elStatus.textContent = '✓ Saved ' + (d.saved || items.length) + ' fields';
      elStatus.className   = 'ef-status ok';
      // Clear dirty state
      Object.keys(changes).forEach(function (k) { delete changes[k]; });
      elDirty.textContent = '';
      btnSave.disabled    = true;
      if (window.parent !== window) {
        window.parent.postMessage({ type: 'efDirty', count: 0 }, '*');
      }
      setTimeout(function () { elStatus.textContent = ''; elStatus.className = 'ef-status'; }, 3000);
      // Notify parent frame if inside iframe
      if (window.parent !== window) {
        window.parent.postMessage({ type: 'efSaved', count: d.saved || items.length }, '*');
      }
    } catch (err) {
      elStatus.textContent = '✗ ' + err.message;
      elStatus.className   = 'ef-status err';
      btnSave.disabled     = false;
    }
  });

  // ── Exit ───────────────────────────────────────────────────────────────────
  btnExit.addEventListener('click', function () {
    var n = Object.keys(changes).length;
    if (n > 0 && !confirm(n + ' unsaved changes. Exit anyway?')) return;
    if (window.parent !== window) {
      window.parent.postMessage({ type: 'efExit' }, '*');
    } else {
      window.location.href = '/admin/visual-editor';
    }
  });

  // ── Listen for messages from parent ───────────────────────────────────────
  window.addEventListener('message', function (e) {
    if (!e.data) return;
    if (e.data.type === 'efRequestSave') btnSave.click();
    if (e.data.type === 'efRequestExit') btnExit.click();
  });

})();
