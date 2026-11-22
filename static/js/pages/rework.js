import { api } from '../api.js';

export async function renderRework(el) {
  const data = await api('/api/rework/jobs');
  el.innerHTML = `
    <div class="card">
      <h2><span class="chip" data-thick="page_merge">合并已亮</span> 回炉队列</h2>
      <table>
        <thead><tr><th>任务</th><th>条目</th><th>舱</th><th>状态</th><th>次数</th><th>操作</th></tr></thead>
        <tbody>
          ${(data.items || []).map((j) => `
            <tr>
              <td>${j.job_code}</td>
              <td>${j.item_key}</td>
              <td>${j.bin_code}</td>
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
    </div>`;
  el.querySelectorAll('[data-ok]').forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/rework/jobs/${btn.dataset.ok}/run`, {
        method: 'POST', body: JSON.stringify({ succeed: true }),
      });
      await renderRework(el);
    };
  });
  el.querySelectorAll('[data-bad]').forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/rework/jobs/${btn.dataset.bad}/run`, {
        method: 'POST', body: JSON.stringify({ succeed: false }),
      });
      await renderRework(el);
    };
  });
}
