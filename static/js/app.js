import { api } from './api.js';
import { renderCaptures } from './pages/captures.js';
import { renderBins } from './pages/bins.js';
import { renderReview } from './pages/review.js';
import { renderRework } from './pages/rework.js';
import { renderReconcile } from './pages/reconcile.js';
import { renderSources } from './pages/sources.js';
import { renderPolicies } from './pages/policies.js';
import { renderAudit } from './pages/audit.js';
import { renderSettings } from './pages/settings.js';

const view = document.getElementById('view');
const pages = {
  captures: renderCaptures,
  bins: renderBins,
  review: renderReview,
  rework: renderRework,
  reconcile: renderReconcile,
  sources: renderSources,
  policies: renderPolicies,
  audit: renderAudit,
  settings: renderSettings,
};

async function refreshDash() {
  try {
    const d = await api('/api/dashboard');
    document.getElementById('dashHint').textContent =
      ` · 批次${d.batches} · 源站${d.sites} · 待复核${d.pending_rows} · 回炉${d.rework_queue} · 审计${d.audits}`;
  } catch (e) {
    if (String(e.message).includes('未登录')) location.href = '/login';
  }
}

async function go(name) {
  document.querySelectorAll('button.nav').forEach((b) => {
    b.classList.toggle('active', b.dataset.page === name);
  });
  view.innerHTML = '<p class="muted">加载中…</p>';
  await pages[name](view);
  await refreshDash();
}

document.querySelectorAll('button.nav').forEach((b) => {
  b.onclick = () => go(b.dataset.page);
});
document.getElementById('logoutBtn').onclick = async () => {
  await api('/api/logout', { method: 'POST' });
  location.href = '/login';
};

go('captures');
