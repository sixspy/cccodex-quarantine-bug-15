
import { api } from '../api.js';

export async function renderPolicies(el) {
  const [rules, batches] = await Promise.all([
    api('/api/rules'),
    api('/api/batches'),
  ]);
  const openBatches = (batches.items || []).filter((b) => b.status !== '已关闭');
  el.innerHTML = `
    <div class="card">
      <h2>入舱规则</h2>
      <p class="muted">按质量标记自动入舱 / 关闭 / 观察。可对采集中批次一键套规则。</p>
      <div class="row">
        <input id="title" placeholder="规则标题" />
        <select id="qm">
          <option>缺字段</option><option>编码空</option><option>重复键</option><option>合格</option>
        </select>
        <select id="act">
          <option>入舱</option><option>直接关闭</option><option>观察</option>
        </select>
        <input id="bin" placeholder="目标舱号 BIN-A" value="BIN-A" />
        <button id="create">新增规则</button>
      </div>
    </div>
    <div class="card">
      <div class="row">
        <select id="batch">
          ${openBatches.map((b) => `<option value="${b.id}">${b.batch_code} · 坏件${b.bad_count}</option>`).join('')}
        </select>
        <button id="apply">对批次套规则</button>
        <span id="applyMsg" class="muted"></span>
      </div>
      <table>
        <thead><tr><th>编码</th><th>标题</th><th>匹配</th><th>动作</th><th>舱</th><th>启用</th><th></th></tr></thead>
        <tbody>
          ${(rules.items || []).map((r) => `
            <tr>
              <td>${r.rule_code}</td>
              <td>${r.title}</td>
              <td>${r.quality_match}</td>
              <td>${r.action}</td>
              <td>${r.target_bin_code || '-'}</td>
              <td><span class="chip ${r.enabled ? 'ok' : 'bad'}">${r.enabled ? '开' : '关'}</span></td>
              <td>
                <button data-en="${r.id}" data-v="${r.enabled ? 0 : 1}">
                  ${r.enabled ? '停用' : '启用'}
                </button>
              </td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
  el.querySelector('#create').onclick = async () => {
    await api('/api/rules', {
      method: 'POST',
      body: JSON.stringify({
        title: el.querySelector('#title').value,
        quality_match: el.querySelector('#qm').value,
        action: el.querySelector('#act').value,
        target_bin_code: el.querySelector('#bin').value,
      }),
    });
    await renderPolicies(el);
  };
  el.querySelector('#apply').onclick = async () => {
    const batch_id = Number(el.querySelector('#batch').value);
    const r = await api('/api/rules/apply', {
      method: 'POST',
      body: JSON.stringify({ batch_id }),
    });
    el.querySelector('#applyMsg').textContent =
      `入舱${r.entered} / 关闭${r.closed} / 观察${r.observed}`;
  };
  el.querySelectorAll('[data-en]').forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/rules/${btn.dataset.en}/enable`, {
        method: 'POST',
        body: JSON.stringify({ enabled: btn.dataset.v === '1' }),
      });
      await renderPolicies(el);
    };
  });
}
