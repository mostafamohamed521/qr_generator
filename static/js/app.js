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
async function loadHistory() {
  if (!historyList) return;
  try {
    const res  = await fetch(`${window.APP_BASE}api/history/`);
    const data = await res.json();
    if (!data.ok) return;

    if (data.items.length === 0) {
      historyList.innerHTML = `<div class="empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="40" height="40">
          <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3m0 4h4m-4 0v-4m4 0h-3"/>
        </svg>No QR codes yet</div>`;
      return;
    }

    historyList.innerHTML = data.items.map(q => `
      <div class="history-item" onclick="loadFromHistory('${esc(q.image)}')">
        <img src="${esc(q.image)}" alt="QR">
        <div class="history-meta">
          <div class="history-label">${esc(q.label)}</div>
          <div class="history-sub">${esc(q.type_label)} · ${esc(q.created_at)}</div>
        </div>
        <button class="history-del" onclick="event.stopPropagation();delQR(${q.id},this)" title="Delete">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6"/><path d="M14 11v6"/>
          </svg>
        </button>
      </div>`).join('');
  } catch { /* network err */ }
}

function loadFromHistory(src) {
  currentImage = src;
  showQR(src);
}

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
