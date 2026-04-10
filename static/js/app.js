/* ============================================================
   QR Forge — app.js
   All frontend logic: tabs, form submit, history, toasts
   ============================================================ */

'use strict';

// ── State ──────────────────────────────────────────────────────────────────
let currentImage = '';

// ── DOM references ──────────────────────────────────────────────────────────
const tabsEl       = document.getElementById('tabs');
const form         = document.getElementById('qr-form');
const genBtn       = document.getElementById('gen-btn');
const qrBox        = document.getElementById('qr-box');
const qrPlaceholder= document.getElementById('qr-placeholder');
const qrImage      = document.getElementById('qr-image');
const qrActions    = document.getElementById('qr-actions');
const historyList  = document.getElementById('history-list');
const sizeRange    = document.getElementById('size-range');
const sizeVal      = document.getElementById('size-val');
const toastCont    = document.getElementById('toasts');
const styleHidden  = document.getElementById('qr-style');
const typeHidden   = document.getElementById('qr-type');

// ── Background canvas ───────────────────────────────────────────────────────
(function initBg() {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H;

  const orbs = [
    { x: 0.15, y: 0.1,  r: 420, c: '78,240,196',  s: 0.00012 },
    { x: 0.88, y: 0.85, r: 360, c: '124,110,247',  s: -0.00009 },
    { x: 0.55, y: 0.5,  r: 250, c: '247,194,110',  s: 0.00007 },
  ];
  let t = 0;

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }
  window.addEventListener('resize', resize);
  resize();

  function draw() {
    ctx.clearRect(0, 0, W, H);
    orbs.forEach(o => {
      const cx = W * o.x + Math.sin(t * o.s * W) * 80;
      const cy = H * o.y + Math.cos(t * o.s * H) * 60;
      const g  = ctx.createRadialGradient(cx, cy, 0, cx, cy, o.r);
      g.addColorStop(0,   `rgba(${o.c},0.13)`);
      g.addColorStop(1,   `rgba(${o.c},0)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(cx, cy, o.r, 0, Math.PI * 2);
      ctx.fill();
    });
    t++;
    requestAnimationFrame(draw);
  }
  draw();
})();

// ── Utilities ───────────────────────────────────────────────────────────────
function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function csrfToken() {
  return document.querySelector('[name=csrfmiddlewaretoken]')?.value ?? '';
}

function toast(msg, type = 'info') {
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

// ── Tabs ────────────────────────────────────────────────────────────────────
tabsEl.addEventListener('click', e => {
  const btn = e.target.closest('.tab');
  if (!btn) return;
  const tab = btn.dataset.tab;
  tabsEl.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.getElementById(`s-${tab}`)?.classList.add('active');
  typeHidden.value = tab;
});

// ── Size slider ──────────────────────────────────────────────────────────────
sizeRange.addEventListener('input', () => {
  sizeVal.textContent = sizeRange.value + 'px';
});

// ── Style buttons ─────────────────────────────────────────────────────────
document.querySelectorAll('.style-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    styleHidden.value = btn.dataset.style;
  });
});

// ── Generate ────────────────────────────────────────────────────────────────
form.addEventListener('submit', async e => {
  e.preventDefault();
  genBtn.classList.add('loading');
  genBtn.disabled = true;

  try {
    const fd  = new FormData(form);
    const res = await fetch('/api/generate/', { method: 'POST', body: fd });
    const data = await res.json();

    if (data.ok) {
      currentImage = data.image;
      showQR(data.image);
      loadHistory();
      toast('QR code generated!', 'ok');
    } else {
      toast(data.error || 'Failed to generate QR code', 'err');
    }
  } catch {
    toast('Connection error — please try again', 'err');
  }

  genBtn.classList.remove('loading');
  genBtn.disabled = false;
});

function showQR(src) {
  qrPlaceholder.style.display = 'none';
  qrImage.style.display = 'block';
  // re-trigger pop animation
  qrImage.classList.remove('pop-anim');
  void qrImage.offsetWidth;
  qrImage.src = src;
  qrActions.classList.add('show');
}

// ── Actions ──────────────────────────────────────────────────────────────────
async function dlQR() {
  if (!currentImage) return;
  const a = document.createElement('a');
  a.href = currentImage;
  a.download = `qr-forge-${Date.now()}.png`;
  a.click();
  toast('Saved!', 'ok');
}

async function cpQR() {
  if (!currentImage) return;
  try {
    const res  = await fetch(currentImage);
    const blob = await res.blob();
    await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
    toast('Copied to clipboard!', 'ok');
  } catch {
    toast('Copy not supported in this browser', 'err');
  }
}

async function shareQR() {
  if (!currentImage) return;
  if (navigator.share) {
    try {
      const res  = await fetch(currentImage);
      const blob = await res.blob();
      const file = new File([blob], 'qr-forge.png', { type: blob.type });
      await navigator.share({ title: 'QR Code', files: [file] });
    } catch { /* cancelled */ }
  } else {
    await cpQR();
  }
}

// expose to onclick handlers in template
window.dlQR    = dlQR;
window.cpQR    = cpQR;
window.shareQR = shareQR;

// ── History ───────────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res  = await fetch('/api/history/');
    const data = await res.json();

    if (!data.items?.length) {
      historyList.innerHTML = `
        <div class="empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="3" y="3" width="7" height="7" rx="1"/>
            <rect x="14" y="3" width="7" height="7" rx="1"/>
            <rect x="3" y="14" width="7" height="7" rx="1"/>
            <path d="M14 14h3v3m0 4h4m-4 0v-4m4 0h-3"/>
          </svg>
          No QR codes yet
        </div>`;
      return;
    }

    historyList.innerHTML = data.items.map(item => `
      <div class="h-item" onclick="previewItem('${encodeURIComponent(item.image)}')">
        ${item.image
          ? `<img class="h-thumb" src="${esc(item.image)}" alt="QR">`
          : `<div class="h-thumb"></div>`}
        <div class="h-info">
          <div class="h-label">${esc(item.label)}</div>
          <div class="h-meta">${esc(item.created_at)}</div>
        </div>
        <span class="badge b-${esc(item.qr_type)}">${esc(item.type_label)}</span>
        <button class="del-btn" title="Delete" onclick="event.stopPropagation();delItem(${item.id})">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6m4-6v6"/>
            <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
        </button>
      </div>
    `).join('');
  } catch { /* silent */ }
}

function previewItem(encoded) {
  const src = decodeURIComponent(encoded);
  if (!src) return;
  currentImage = src;
  showQR(src);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function delItem(id) {
  try {
    const res  = await fetch(`/api/delete/${id}/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken() },
    });
    if ((await res.json()).ok) {
      loadHistory();
      toast('Deleted', 'info');
    }
  } catch { toast('Delete failed', 'err'); }
}

async function clearAll() {
  try {
    await fetch('/api/clear/', {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken() },
    });
    loadHistory();
    toast('History cleared', 'info');
  } catch { toast('Failed', 'err'); }
}

window.previewItem = previewItem;
window.delItem     = delItem;
window.clearAll    = clearAll;

// ── Init ──────────────────────────────────────────────────────────────────────
loadHistory();
