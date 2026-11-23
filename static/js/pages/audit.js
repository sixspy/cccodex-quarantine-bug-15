
import { api } from '../api.js';

export async function renderAudit(el) {
  const data = await api('/api/audits?limit=120');
  const sum = data.summary || { total: 0, by_action: [] };
  el.innerHTML = `
    <div class="card">
      <h2>审计轨迹</h2>
      <p class="muted">共 ${sum.total} 条。动作分布：
        ${(sum.by_action || []).map((a) => `${a.action} ${a.c}`).join(' · ') || '暂无'}
      </p>
    </div>
    <div class="card">
      <table>
        <thead><tr><th>时间</th><th>操作者</th><th>动作</th><th>对象</th><th>详情</th></tr></thead>
        <tbody>
          ${(data.items || []).map((e) => `
            <tr>
              <td>${e.created_at}</td>
              <td>${e.actor}</td>
              <td><span class="chip">${e.action}</span></td>
              <td>${e.entity_type}#${e.entity_id}</td>
              <td>${e.detail || ''}</td>
            </tr>`).join('') || '<tr><td colspan="5" class="muted">暂无审计</td></tr>'}
        </tbody>
      </table>
    </div>`;
}
