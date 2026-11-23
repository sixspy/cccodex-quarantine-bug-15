import { api } from '../api.js';

export async function renderCaptures(el) {
  const data = await api('/api/batches');
  const bins = await api('/api/bins');
  const dash = await api('/api/dashboard');
  const reports = await api('/api/reports');
  const latest = (reports.items || [])[0];
  const openBin = (bins.items || []).find((b) => b.status === '开放');
  el.innerHTML = `
    <div class="card">
      <h2>抓取批次</h2>
      <p class="err" id="err"></p>
      <div class="row">
        <input id="src" placeholder="来源名" />
        <input id="note" placeholder="备注" />
        <button id="create">新建批次</button>
      </div>
    </div>
    <div class="card">
      <h2>抓取摘要</h2>
      <div class="stat-strip">
        <div class="stat"><b>${dash.batches}</b><span class="muted">批次</span></div>
        <div class="stat"><b>${dash.items}</b><span class="muted">条目</span></div>
        <div class="stat"><b>${dash.page_merge ? dash.page_merge.merge_count : 0}</b><span class="muted">合并账册</span></div>
        <div class="stat"><b>${dash.page_merge ? dash.page_merge.landing_count : 0}</b><span class="muted">合并落点</span></div>
      </div>
      <div class="hint-box">
        对账条：待复核 ${dash.pending_rows} · 回炉 ${dash.rework_queue} · 复核待决 ${dash.tickets_open}
        ${latest ? ` · 最近对账：${latest.summary}（错位 ${latest.mismatch}）` : ' · 暂无对账报告'}
      </div>
      <table>
        <thead><tr><th>批号</th><th>来源</th><th>状态</th><th>条目/坏件</th><th>合并键号</th><th>操作</th></tr></thead>
        <tbody>
          ${(data.items || []).map((b) => `
            <tr>
              <td>${b.batch_code}</td>
              <td>${b.source_name}</td>
              <td><span class="chip">${b.status}</span></td>
              <td>${b.item_count} / <span class="chip bad">${b.bad_count}</span></td>
              <td>${b.merge_key
                ? `<span class="chip ok" title="合并键号">${b.merge_key}</span><span class="muted"> 落点${b.merge_landing_count}</span>`
                : '<span class="muted">未合并</span>'}</td>
              <td class="row">
                <button data-open="${b.id}">详情</button>
                <button data-close="${b.id}">关闭</button>
                ${openBin ? `<button data-auto="${b.id}">坏件入舱</button>` : ''}
              </td>
            </tr>`).join('')}
        </tbody>
      </table>
      <div id="detail" class="grid" style="margin-top:12px"></div>
    </div>`;
  const onErr = (e) => { el.querySelector('#err').textContent = e.message; };
  el.querySelector('#create').onclick = async () => {
    try {
      await api('/api/batches', {
        method: 'POST',
        body: JSON.stringify({
          source_name: el.querySelector('#src').value,
          note: el.querySelector('#note').value,
        }),
      });
      await renderCaptures(el);
    } catch (e) { onErr(e); }
  };
  el.querySelectorAll('[data-close]').forEach((btn) => {
    btn.onclick = async () => {
      try {
        await api(`/api/batches/${btn.dataset.close}/close`, { method: 'POST', body: '{}' });
        await renderCaptures(el);
      } catch (e) { onErr(e); }
    };
  });
  el.querySelectorAll('[data-auto]').forEach((btn) => {
    btn.onclick = async () => {
      if (!openBin) return;
      try {
        await api('/api/quarantine/auto-enter', {
          method: 'POST',
          body: JSON.stringify({ batch_id: Number(btn.dataset.auto), bin_id: openBin.id }),
        });
        await renderCaptures(el);
      } catch (e) { onErr(e); }
    };
  });
  el.querySelectorAll('[data-open]').forEach((btn) => {
    btn.onclick = async () => {
      const d = await api(`/api/batches/${btn.dataset.open}`);
      const box = el.querySelector('#detail');
      box.innerHTML = `
        <h3>${d.batch_code} 条目</h3>
        <div class="hint-box">
          ${d.merge
            ? `合并键号 <span class="chip ok">${d.merge.merge_key}</span> · 分页 ${d.merge.page_key} · 指纹 ${d.merge.fingerprint.slice(0, 8)} · 落点 ${d.merge.landing_count}`
            : '尚未合并落账'}
        </div>
        <div class="row">
          <input id="ikey" placeholder="条目键" />
          <select id="iq">
            <option>合格</option><option>缺字段</option><option>编码空</option><option>重复键</option>
          </select>
          <button id="addItem">追加条目</button>
        </div>
        <div class="row">
          <input id="pkey" placeholder="分页键（默认 P1）" />
          <button id="mergeBtn">合并落账</button>
        </div>
        <table>
          <thead><tr><th>键</th><th>质量</th><th>状态</th></tr></thead>
          <tbody>
            ${(d.items || []).map((i) => `
              <tr>
                <td>${i.item_key}</td>
                <td><span class="chip ${i.quality === '合格' ? 'ok' : 'bad'}">${i.quality}</span></td>
                <td>${i.status}</td>
              </tr>`).join('')}
          </tbody>
        </table>`;
      box.querySelector('#addItem').onclick = async () => {
        try {
          await api(`/api/batches/${d.id}/items`, {
            method: 'POST',
            body: JSON.stringify({
              item_key: box.querySelector('#ikey').value,
              quality: box.querySelector('#iq').value,
              payload: '{}',
            }),
          });
          btn.click();
        } catch (e) { onErr(e); }
      };
      box.querySelector('#mergeBtn').onclick = async () => {
        try {
          await api('/api/page_merge/commit', {
            method: 'POST',
            body: JSON.stringify({
              batch_id: d.id,
              page_key: box.querySelector('#pkey').value || 'P1',
            }),
          });
          await renderCaptures(el);
        } catch (e) { onErr(e); }
      };
    };
  });
}
