import { api } from '../api.js';

export async function renderRework(el) {
  const data = await api('/api/rework/jobs');
  const bins = await api('/api/bins');
  el.innerHTML = `
    <div class="card">
      <h2>回炉队列</h2>
      <p class="err" id="err"></p>
      <table>
        <thead><tr><th>任务</th><th>条目</th><th>舱</th><th>合并引用</th><th>状态</th><th>次数</th><th>操作</th></tr></thead>
        <tbody>
          ${(data.items || []).map((j) => `
            <tr>
              <td>${j.job_code}</td>
              <td>${j.item_key}</td>
              <td>${j.bin_code}</td>
              <td>${j.merge_key
                ? `<span class="chip ok" title="合并键号">${j.merge_key}</span>`
                : '<span class="muted">未合并</span>'}</td>
              <td><span class="chip">${j.status}</span></td>
              <td>${j.attempt}</td>
              <td class="row">
                ${['排队','失败'].includes(j.status) ? `
                  <button data-ok="${j.id}">执行成功</button>
                  <button data-bad="${j.id}">执行失败</button>
                ` : (j.message || '')}
              </td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>
    <div class="card">
      <h2>舱位卡片</h2>
      <div class="stat-strip">
        ${(bins.items || []).map((b) => `
          <div class="stat">
            <b>${b.bin_code}</b>
            <span class="chip">${b.status}</span>
            <div class="muted">占用 ${b.row_count}/${b.capacity} · 待复核 ${b.pending_count}</div>
            <div class="muted">合并落点 ${b.landing_count}</div>
          </div>`).join('')}
      </div>
    </div>`;
  const onErr = (e) => { el.querySelector('#err').textContent = e.message; };
  el.querySelectorAll('[data-ok]').forEach((btn) => {
    btn.onclick = async () => {
      el.querySelector('#err').textContent = '';
      try {
        await api(`/api/rework/jobs/${btn.dataset.ok}/run`, {
          method: 'POST', body: JSON.stringify({ succeed: true }),
        });
        await renderRework(el);
      } catch (e) { onErr(e); }
    };
  });
  el.querySelectorAll('[data-bad]').forEach((btn) => {
    btn.onclick = async () => {
      el.querySelector('#err').textContent = '';
      try {
        await api(`/api/rework/jobs/${btn.dataset.bad}/run`, {
          method: 'POST', body: JSON.stringify({ succeed: false }),
        });
        await renderRework(el);
      } catch (e) { onErr(e); }
    };
  });
}
