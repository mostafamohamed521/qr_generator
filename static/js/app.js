/* ============================================================
   QR Forge — app.js
   Shared frontend logic: bg canvas, tabs, form, history, toasts
   ============================================================ */

'use strict';

// ── Theme (dark/light) ───────────────────────────────────────────────────────
(function initTheme() {
  const saved = localStorage.getItem('qr-theme');
  const preferred = saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', preferred);

  const btn = document.getElementById('theme-toggle');
  btn?.addEventListener('click', () => {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('qr-theme', next);
  });
})();

// ── State ──────────────────────────────────────────────────────────────────
let currentImage = '';
let currentContent = '';
let lastGeneratedId = null;

// ── DOM references (index page only — guard with optional chaining) ─────────
const tabsEl        = document.getElementById('tabs');
const form          = document.getElementById('qr-form');
const genBtn        = document.getElementById('gen-btn');
const qrBox         = document.getElementById('qr-box');
const qrPlaceholder = document.getElementById('qr-placeholder');
const qrImage       = document.getElementById('qr-image');
const qrActions     = document.getElementById('qr-actions');
const historyList   = document.getElementById('history-list');
const sizeRange     = document.getElementById('size-range');
const sizeVal       = document.getElementById('size-val');
const toastCont     = document.getElementById('toasts');
const styleHidden   = document.getElementById('qr-style');
const typeHidden    = document.getElementById('qr-type');
const logob64       = document.getElementById('logo-b64');

// ── Background ───────────────────────────────────────────────────────────
// Previously an infinitely-animating canvas of blurred floating gradient
// orbs (continuous requestAnimationFrame loop, purely decorative — wasted
// battery/CPU on every page). Replaced with a static, subtle vignette
// drawn once in pure CSS (see #bg-canvas / body::before in style.css) for
// a calmer, more classic look with zero ongoing cost.

// ── Utilities ───────────────────────────────────────────────────────────────
function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function csrfToken() {
  return document.querySelector('[name=csrfmiddlewaretoken]')?.value
    || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
}

function toast(msg, type = 'info') {
  if (!toastCont) return;
  const icons = {
    ok:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>',
    err:  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
  };
  const el = document.createElement('div');
  el.className = `toast t-${type}`;
  el.innerHTML = `<div class="t-icon">${icons[type] ?? icons.info}</div><span>${esc(msg)}</span>`;
  toastCont.appendChild(el);
  setTimeout(() => {
    el.classList.add('out');
    el.addEventListener('animationend', () => el.remove(), { once: true });
  }, 3200);
}
window.showToast = toast;

// ── Tabs ────────────────────────────────────────────────────────────────────
tabsEl?.addEventListener('click', e => {
  const btn = e.target.closest('.tab');
  if (!btn) return;
  const tab = btn.dataset.tab;
  tabsEl.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.getElementById(`s-${tab}`)?.classList.add('active');
  if (typeHidden) typeHidden.value = tab;
});

// ── Size slider ──────────────────────────────────────────────────────────────
sizeRange?.addEventListener('input', () => {
  if (sizeVal) sizeVal.textContent = sizeRange.value + 'px';
});

// ── Style buttons ─────────────────────────────────────────────────────────
document.querySelectorAll('.style-btn').forEach(btn => {
  if (!btn.dataset.style) return;
  btn.addEventListener('click', () => {
    document.querySelectorAll('.style-btn[data-style]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    if (styleHidden) styleHidden.value = btn.dataset.style;
  });
});

// ── Logo upload ──────────────────────────────────────────────────────────────
const logoFile = document.getElementById('logo-file');
const logoPreviewWrap = document.getElementById('logo-preview-wrap');
const logoPreviewImg  = document.getElementById('logo-preview-img');
const logoPreviewName = document.getElementById('logo-preview-name');
const logoRemove      = document.getElementById('logo-remove');
const logoDrop        = document.getElementById('logo-drop');

logoFile?.addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  readLogoFile(file);
});

logoDrop?.addEventListener('dragover', e => { e.preventDefault(); logoDrop.style.borderColor='var(--accent)'; });
logoDrop?.addEventListener('dragleave', () => { logoDrop.style.borderColor=''; });
logoDrop?.addEventListener('drop', e => {
  e.preventDefault(); logoDrop.style.borderColor='';
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith('image/')) readLogoFile(file);
});

function readLogoFile(file) {
  const reader = new FileReader();
  reader.onload = ev => {
    const data = ev.target.result;
    if (logob64) logob64.value = data;
    if (logoPreviewImg) logoPreviewImg.src = data;
    if (logoPreviewName) logoPreviewName.textContent = file.name;
    if (logoPreviewWrap) logoPreviewWrap.style.display = 'flex';
  };
  reader.readAsDataURL(file);
}

logoRemove?.addEventListener('click', () => {
  if (logob64) logob64.value = '';
  if (logoFile) logoFile.value = '';
  if (logoPreviewWrap) logoPreviewWrap.style.display = 'none';
});

// ── Generate ────────────────────────────────────────────────────────────────
const transparentCheck = document.getElementById('transparent-bg-check');
const bgColorInput = document.getElementById('bg-color-input');

transparentCheck?.addEventListener('change', () => {
  if (bgColorInput) bgColorInput.disabled = transparentCheck.checked;
  triggerLivePreview();
});

async function runGenerate({ silent = false } = {}) {
  if (!genBtn) return;
  if (!silent) { genBtn.classList.add('loading'); genBtn.disabled = true; }

  try {
    const fd = new FormData(form);
    if (transparentCheck?.checked) fd.set('bg_color', 'transparent');

    const res = await fetch(`${window.APP_BASE}api/generate/`, { method: 'POST', body: fd });
    const data = await res.json();

    if (data.ok) {
      currentImage = data.image;
      currentContent = data.content || '';
      showQR(data.image);
      if (!silent) {
        loadHistory();
        toast('QR code generated!', 'ok');
        const hist = await (await fetch(`${window.APP_BASE}api/history/`)).json();
        if (hist.ok && hist.items.length) lastGeneratedId = hist.items[0].id;
      }
    } else if (!silent) {
      toast(data.error || 'Failed to generate QR code', 'err');
    }
  } catch {
    if (!silent) toast('Connection error — please try again', 'err');
  }

  if (!silent) { genBtn.classList.remove('loading'); genBtn.disabled = false; }
}

form?.addEventListener('submit', async e => {
  e.preventDefault();
  await runGenerate({ silent: false });
});

// Live preview: regenerate quietly as the user edits the active fields
let liveTimer = null;
function triggerLivePreview() {
  if (!form) return;
  clearTimeout(liveTimer);
  liveTimer = setTimeout(() => {
    // Only auto-preview if all currently-visible required fields have content
    const requiredFilled = [...form.querySelectorAll('input[required], textarea[required]')]
      .filter(el => el.offsetParent !== null) // visible only
      .every(el => el.value.trim().length > 0);
    if (requiredFilled) runGenerate({ silent: true });
  }, 600);
}
form?.addEventListener('input', triggerLivePreview);
form?.addEventListener('change', triggerLivePreview);

function showQR(src) {
  if (!qrPlaceholder || !qrImage || !qrActions) return;
  qrPlaceholder.style.display = 'none';
  qrImage.style.display = 'block';
  qrImage.classList.remove('pop-anim');
  void qrImage.offsetWidth;
  qrImage.classList.add('pop-anim');
  qrImage.src = src;
  qrActions.classList.add('visible');

  // show SVG button
  const svgBtn = document.getElementById('svg-btn');
  if (svgBtn) svgBtn.style.display = '';
}

// ── Download / Copy / Share ───────────────────────────────────────────────
function dlQR() {
  if (!currentImage) return;
  const a = document.createElement('a');
  a.href = currentImage;
  a.download = 'qrcode.png';
  a.click();
}

function dlSVG() {
  if (!lastGeneratedId) return;
  window.location.href = `${window.APP_BASE}api/export-svg/${lastGeneratedId}/`;
}

function cpQR() {
  if (!currentImage) return;
  fetch(currentImage)
    .then(r => r.blob())
    .then(blob => {
      navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
      toast('Copied to clipboard!', 'ok');
    })
    .catch(() => toast('Copy not supported in this browser', 'err'));
}

function cpContent() {
  if (!currentContent) return;
  navigator.clipboard.writeText(currentContent)
    .then(() => toast('Content copied!', 'ok'))
    .catch(() => toast('Copy not supported in this browser', 'err'));
}

function dlJPG() {
  if (!currentImage) return;
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = img.width;
    canvas.height = img.height;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0);
    const a = document.createElement('a');
    a.href = canvas.toDataURL('image/jpeg', 0.95);
    a.download = 'qrcode.jpg';
    a.click();
  };
  img.src = currentImage;
}

function shareQR() {
  if (!currentImage) return;
  if (navigator.share) {
    fetch(currentImage)
      .then(r => r.blob())
      .then(blob => {
        const file = new File([blob], 'qrcode.png', { type: 'image/png' });
        navigator.share({ files: [file], title: 'QR Code' }).catch(() => {});
      });
  } else {
    toast('Share not supported on this device', 'info');
  }
}

// ── History ─────────────────────────────────────────────────────────────────
let histCurrentPage = 1;

function histBuildParams() {
  const q    = document.getElementById('hist-search')?.value.trim() || '';
  const type = document.getElementById('hist-type-filter')?.value || 'all';
  const favOnly = document.getElementById('hist-fav-filter')?.classList.contains('active');
  const params = new URLSearchParams({ page: histCurrentPage });
  if (q)           params.set('q', q);
  if (type !== 'all') params.set('type', type);
  if (favOnly)      params.set('favorites', '1');
  return params;
}

async function loadHistory() {
  if (!historyList) return;
  try {
    const res  = await fetch(`${window.APP_BASE}api/history/?${histBuildParams()}`);
    const data = await res.json();
    if (!data.ok) return;

    if (data.items.length === 0) {
      historyList.innerHTML = `<div class="empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="40" height="40">
          <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3m0 4h4m-4 0v-4m4 0h-3"/>
        </svg>No QR codes yet</div>`;
      const pag = document.getElementById('hist-pagination');
      if (pag) pag.style.display = 'none';
      return;
    }

    historyList.innerHTML = data.items.map(q => `
      <div class="history-item" data-image="${esc(q.image)}" data-content="${esc(q.content)}">
        <img src="${esc(q.image)}" alt="QR">
        <div class="history-meta">
          <div class="history-label">${esc(q.label)}</div>
          <div class="history-sub">${esc(q.type_label)} · ${esc(q.created_at)}${q.scan_count ? ` · <b>${q.scan_count} scans</b>` : ''}</div>
        </div>
        <button class="history-fav ${q.is_favorite ? 'active' : ''}" data-id="${q.id}" title="Favorite">
          <svg viewBox="0 0 24 24" fill="${q.is_favorite ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" width="14" height="14">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
          </svg>
        </button>
        <button class="history-dup" data-id="${q.id}" title="Duplicate">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
          </svg>
        </button>
        <button class="history-del" data-id="${q.id}" title="Delete">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6"/><path d="M14 11v6"/>
          </svg>
        </button>
      </div>`).join('');

    const pag = document.getElementById('hist-pagination');
    const info = document.getElementById('hist-page-info');
    const prev = document.getElementById('hist-prev');
    const next = document.getElementById('hist-next');
    if (pag && data.pages > 1) {
      pag.style.display = 'flex';
      info.textContent = `${data.page} / ${data.pages}`;
      if (prev) prev.disabled = data.page <= 1;
      if (next) next.disabled = data.page >= data.pages;
    } else if (pag) {
      pag.style.display = 'none';
    }
  } catch { /* network err */ }
}

function histGoPage(delta) {
  histCurrentPage = Math.max(1, histCurrentPage + delta);
  loadHistory();
}

function loadFromHistory(src, content) {
  currentImage = src;
  currentContent = content || '';
  showQR(src);
}

// Delegated handlers (replaces inline onclick="..." that used to
// string-interpolate QR content into a JS literal — a QR containing a
// single quote could break out of that string and inject script).
historyList?.addEventListener('click', (e) => {
  const delBtn = e.target.closest('.history-del');
  if (delBtn) {
    e.stopPropagation();
    delQR(Number(delBtn.dataset.id), delBtn);
    return;
  }
  const favBtn = e.target.closest('.history-fav');
  if (favBtn) {
    e.stopPropagation();
    toggleFavorite(Number(favBtn.dataset.id), favBtn);
    return;
  }
  const dupBtn = e.target.closest('.history-dup');
  if (dupBtn) {
    e.stopPropagation();
    duplicateQR(Number(dupBtn.dataset.id), dupBtn);
    return;
  }
  const item = e.target.closest('.history-item');
  if (item) loadFromHistory(item.dataset.image, item.dataset.content);
});

document.getElementById('hist-fav-filter')?.addEventListener('click', function () {
  this.classList.toggle('active');
  histCurrentPage = 1;
  loadHistory();
});

function exportCSV() {
  const params = histBuildParams();
  window.location.href = `${window.APP_BASE}api/export-csv/?${params}`;
}

let histSearchTimer = null;
document.getElementById('hist-search')?.addEventListener('input', () => {
  clearTimeout(histSearchTimer);
  histCurrentPage = 1;
  histSearchTimer = setTimeout(loadHistory, 350);
});
document.getElementById('hist-type-filter')?.addEventListener('change', () => {
  histCurrentPage = 1;
  loadHistory();
});

async function delQR(id, btn) {
  const row = btn.closest('.history-item');
  row.style.opacity = '0.4';
  const res  = await fetch(`${window.APP_BASE}api/delete/${id}/`, {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken() },
  });
  const data = await res.json();
  if (data.ok) { row.remove(); toast('Deleted', 'ok'); }
  else { row.style.opacity = ''; toast('Failed to delete', 'err'); }
}

async function toggleFavorite(id, btn) {
  btn.disabled = true;
  try {
    const res  = await fetch(`${window.APP_BASE}api/favorite/${id}/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken() },
    });
    const data = await res.json();
    if (data.ok) {
      btn.classList.toggle('active', data.is_favorite);
      btn.querySelector('svg').setAttribute('fill', data.is_favorite ? 'currentColor' : 'none');
      // If a favorites-only filter is active and this item was just
      // unfavorited, it no longer belongs in the current list.
      if (!data.is_favorite && document.getElementById('hist-fav-filter')?.classList.contains('active')) {
        loadHistory();
      }
    } else {
      toast('Failed to update favorite', 'err');
    }
  } catch { toast('Connection error', 'err'); }
  btn.disabled = false;
}

async function duplicateQR(id, btn) {
  btn.disabled = true;
  try {
    const res  = await fetch(`${window.APP_BASE}api/duplicate/${id}/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken() },
    });
    const data = await res.json();
    if (data.ok) {
      toast('Duplicated', 'ok');
      histCurrentPage = 1;
      loadHistory();
    } else if (data.code === 'quota_exceeded') {
      toast(data.error, 'err');
    } else {
      toast(data.error || 'Failed to duplicate', 'err');
    }
  } catch { toast('Connection error', 'err'); }
  btn.disabled = false;
}

async function clearAll() {
  if (!confirm('Clear all QR code history?')) return;
  const res  = await fetch(`${window.APP_BASE}api/clear/`, {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken() },
  });
  const data = await res.json();
  if (data.ok) {
    loadHistory();
    toast('History cleared', 'ok');
  }
}

// ── Init ─────────────────────────────────────────────────────────────────────
loadHistory();
