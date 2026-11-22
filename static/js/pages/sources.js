
import { api } from '../api.js';

export async function renderSources(el) {
  const data = await api('/api/sites');
  el.innerHTML = `
    <div class="card">
      <h2>源站名册</h2>
      <p class="muted">登记可采集源站、日配额与启停状态，批次来源名与源站名对齐。</p>
      <div class="row">
        <input id="sname" placeholder="源站名" />
        <input id="surl" placeholder="基址 URL" />
        <input id="squota" type="number" value="100" style="width:100px" />
        <button id="create">登记源站</button>
      </div>
    </div>
    <div class="card">
      <table>
        <thead><tr><th>编码</th><th>名称</th><th>状态</th><th>日配额</th><th>批次数</th><th>操作</th></tr></thead>
        <tbody>
          ${(data.items || []).map((s) => `
            <tr>
              <td>${s.site_code}</td>
              <td>${s.site_name}<div class="muted">${s.base_url || ''}</div></td>
              <td><span class="chip">${s.status}</span></td>
              <td>${s.daily_quota}</td>
              <td>${s.batch_count}</td>
              <td class="row">
                <button data-st="启用" data-id="${s.id}">启用</button>
                <button data-st="停用" data-id="${s.id}">停用</button>
                <button data-st="观察" data-id="${s.id}">观察</button>
                <button data-q="${s.id}">配额+20</button>
              </td>
            </tr>`).join('')}
        </tbody>
      </table>
      <div id="siteDetail" class="grid" style="margin-top:12px"></div>
    </div>`;
  el.querySelector('#create').onclick = async () => {
    await api('/api/sites', {
      method: 'POST',
      body: JSON.stringify({
        site_name: el.querySelector('#sname').value,
        base_url: el.querySelector('#surl').value,
        daily_quota: Number(el.querySelector('#squota').value || 100),
      }),
    });
    await renderSources(el);
  };
  el.querySelectorAll('[data-st]').forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/sites/${btn.dataset.id}/status`, {
        method: 'POST',
        body: JSON.stringify({ status: btn.dataset.st }),
      });
      await renderSources(el);
    };
  });
  el.querySelectorAll('[data-q]').forEach((btn) => {
    btn.onclick = async () => {
      const site = (data.items || []).find((x) => String(x.id) === btn.dataset.q);
      await api(`/api/sites/${btn.dataset.q}/quota`, {
        method: 'POST',
        body: JSON.stringify({ daily_quota: (site?.daily_quota || 100) + 20 }),
      });
      await renderSources(el);
    };
  });
}
