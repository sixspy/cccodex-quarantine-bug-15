import { api } from '../api.js';

export async function renderReconcile(el) {
  const data = await api('/api/reports');
  el.innerHTML = `
    <div class="card">
      <h2>隔离对账</h2>
      <div class="row"><button id="run">生成对账报告</button></div>
      <table>
        <thead><tr><th>时间</th><th>摘要</th><th>待复核</th><th>放行</th><th>回炉</th><th>废弃</th><th>错位</th></tr></thead>
        <tbody>
          ${(data.items || []).map((r) => `
            <tr>
              <td>${r.created_at}</td>
              <td>${r.summary}</td>
              <td>${r.open_rows}</td>
              <td>${r.released}</td>
              <td>${r.reworking}</td>
              <td>${r.abandoned}</td>
              <td><span class="chip ${r.mismatch ? 'bad' : 'ok'}">${r.mismatch}</span></td>
            </tr>`).join('') || '<tr><td colspan="7" class="muted">暂无报告</td></tr>'}
        </tbody>
      </table>
    </div>`;
  el.querySelector('#run').onclick = async () => {
    await api('/api/reports/run', { method: 'POST', body: '{}' });
    await renderReconcile(el);
  };
}
