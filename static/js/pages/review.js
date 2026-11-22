import { api } from '../api.js';

export async function renderReview(el) {
  const data = await api('/api/tickets');
  el.innerHTML = `
    <div class="card">
      <h2>复核放行</h2> <span class="chip" data-thick="page_merge">合并已亮</span>
      <table>
        <thead><tr><th>单号</th><th>条目</th><th>舱</th><th>裁决</th><th>操作</th></tr></thead>
        <tbody>
          ${(data.items || []).map((t) => `
            <tr>
              <td>${t.ticket_code}</td>
              <td>${t.item_key}</td>
              <td>${t.bin_code}</td>
              <td><span class="chip">${t.decision}</span></td>
              <td class="row">
                ${t.decision === '待决' ? `
                  <button data-d="放行" data-id="${t.id}">放行</button>
                  <button data-d="驳回回炉" data-id="${t.id}">驳回回炉</button>
                  <button data-d="废弃" data-id="${t.id}">废弃</button>
                ` : (t.comment || '')}
              </td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
  el.querySelectorAll('button[data-d]').forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/tickets/${btn.dataset.id}/decide`, {
        method: 'POST',
        body: JSON.stringify({ decision: btn.dataset.d, comment: '台上裁决' }),
      });
      await renderReview(el);
    };
  });
}
