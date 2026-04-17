/* ═══════════════════════════════════════════════
   Toast notification system — replaces alert()
   Usage: showToast('message')
          showToast('message', 'error')
          showToast('message', 'success')
          showToast('message', 'warning')
          showToast('message', 'info')
   ═══════════════════════════════════════════════ */
(function () {
  // Create container once
  var container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  // Detect dark theme (customer portal / public pages)
  function isDark() {
    var bg = getComputedStyle(document.body).backgroundColor;
    if (!bg || bg === 'transparent') return document.body.style.background && document.body.style.background.indexOf('navy') !== -1;
    var m = bg.match(/\d+/g);
    if (!m) return false;
    return (parseInt(m[0]) + parseInt(m[1]) + parseInt(m[2])) / 3 < 80;
  }

  var icons = {
    error:   '&#10006;',
    success: '&#10003;',
    warning: '&#9888;',
    info:    '&#8505;'
  };

  /**
   * Show a toast notification
   * @param {string} message  - The message text
   * @param {string} type     - 'error' | 'success' | 'warning' | 'info' (default: 'info')
   * @param {number} duration - Auto-dismiss in ms (default: 4000, 0 = manual)
   */
  window.showToast = function (message, type, duration) {
    type = type || 'info';
    if (typeof duration === 'undefined') duration = 4000;

    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    if (isDark()) toast.classList.add('toast-dark');

    toast.innerHTML =
      '<span class="toast-icon">' + (icons[type] || icons.info) + '</span>' +
      '<span class="toast-body">' + escapeHtml(message) + '</span>' +
      '<button class="toast-close" aria-label="Close">&times;</button>';

    container.appendChild(toast);

    // Close on click
    var closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', function () { dismiss(toast); });
    toast.addEventListener('click', function (e) {
      if (e.target !== closeBtn) dismiss(toast);
    });

    // Auto dismiss
    if (duration > 0) {
      setTimeout(function () { dismiss(toast); }, duration);
    }

    return toast;
  };

  function dismiss(toast) {
    if (toast.classList.contains('removing')) return;
    toast.classList.add('removing');
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 200);
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // Override native alert() — keep original as fallback
  var _origAlert = window.alert;
  window.alert = function (msg) {
    if (typeof showToast === 'function') {
      // Detect type from message content
      var type = 'info';
      if (/error|fail|cannot|unable/i.test(msg)) type = 'error';
      else if (/success|saved|copied|revoked/i.test(msg)) type = 'success';
      else if (/please|enter|select|minimum|exceed|required|upload/i.test(msg)) type = 'warning';
      showToast(msg, type);
    } else {
      _origAlert(msg);
    }
  };

  /* ── Auto-convert "Loading..." text into skeleton loaders ── */
  document.addEventListener('DOMContentLoaded', function () {
    // Convert table loading cells
    document.querySelectorAll('td.empty, td.history-empty, td.empty-state').forEach(function (td) {
      if (!/Loading/i.test(td.textContent)) return;
      var cols = parseInt(td.getAttribute('colspan')) || 1;
      var rows = '';
      for (var i = 0; i < 3; i++) {
        rows += '<div class="skeleton-row">';
        for (var j = 0; j < Math.min(cols, 5); j++) {
          var w = 40 + Math.random() * 50;
          rows += '<div class="skeleton-cell" style="width:' + w + '%;height:12px;"></div>';
        }
        rows += '</div>';
      }
      td.innerHTML = '<div style="padding:8px 0;">' + rows + '</div>';
    });

    // Convert div loading areas
    document.querySelectorAll('.empty').forEach(function (el) {
      if (!/Loading/i.test(el.textContent)) return;
      if (el.tagName === 'TD') return; // already handled
      el.innerHTML =
        '<div style="padding:12px 0;">' +
          '<div class="skeleton" style="width:70%;height:14px;margin-bottom:10px;"></div>' +
          '<div class="skeleton" style="width:50%;height:14px;margin-bottom:10px;"></div>' +
          '<div class="skeleton" style="width:60%;height:14px;"></div>' +
        '</div>';
    });
  });
})();
