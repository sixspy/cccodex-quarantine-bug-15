import { api } from '../api.js';

export async function renderSettings(el) {
  const data = await api('/api/settings');
  el.innerHTML = `
    <div class="card">
      <h2>台参数</h2>
      <table>
        <thead><tr><th>项</th><th>说明</th><th>值</th><th></th></tr></thead>
        <tbody>
          ${(data.items || []).map((s) => `
            <tr>
              <td>${s.key}</td>
              <td>${s.label}</td>
              <td><input data-key="${s.key}" value="${s.value}" /></td>
              <td><button data-save="${s.key}">保存</button></td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
  el.querySelectorAll('[data-save]').forEach((btn) => {
    btn.onclick = async () => {
      const input = el.querySelector(`input[data-key="${btn.dataset.save}"]`);
      await api('/api/settings/update', {
        method: 'POST',
        body: JSON.stringify({ key: btn.dataset.save, value: input.value }),
      });
      await renderSettings(el);
    };
  });

  try {
    const dash = await api('/api/page_merge/dash');
    const spec = dash.spec || {};
    el.innerHTML += `<div class="card" style="margin-top:1rem">
      <h3>分页合并口径</h3>
      <table>
        <tbody>
          <tr><td>工程形态</td><td><span class="chip ok">${spec.mode || ''}</span></td></tr>
          <tr><td>回炉读轨</td><td>${spec.read_track || ''}</td></tr>
          <tr><td>拒回刷</td><td>${spec.reject_refresh ? '启用' : '停用'}</td></tr>
          <tr><td>账册笔数</td><td>${spec.merge_count ?? 0}</td></tr>
          <tr><td>落点行数</td><td>${spec.landing_count ?? 0}</td></tr>
          <tr><td>最近合并键号</td><td>${spec.latest_merge_key || '无'}</td></tr>
          <tr><td>最近合并指纹</td><td>${spec.latest_fingerprint || '无'}</td></tr>
        </tbody>
      </table>
      <p class="muted">口径只读：合并落账在抓取批次详情内发起，回炉侧只读账册引用。</p>
    </div>`;
  } catch (e) { /* optional surface */ }

}
