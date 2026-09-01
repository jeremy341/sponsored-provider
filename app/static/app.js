const money = n => `$${Number(n || 0).toFixed(2)}`;
const number = n => Number(n || 0).toLocaleString();
function render(data) {
  const b = data.budget || {}; const used = Number(b.used_usd || 0);
  document.querySelector('#used').textContent = money(used); document.querySelector('#limit').textContent = money(b.hard_stop_usd);
  document.querySelector('#remaining').textContent = `${money(b.remaining_usd)} remaining`; document.querySelector('#rail').style.width = `${b.percent || 0}%`;
  const stopped = data.stopped; document.querySelector('#status').innerHTML = `<span style="background:${stopped ? 'var(--rust)' : 'var(--green)'}"></span> ${stopped ? 'stopped' : 'operational'}`;
  document.querySelector('#signal-title').textContent = stopped ? 'Provider stopped' : (used >= Number(b.warning_usd || 25) ? 'Approaching limit' : 'Within guardrails');
  document.querySelector('#signal-copy').textContent = stopped ? 'New requests are blocked until an operator reviews usage.' : 'Requests are accepted only for allowlisted models and tracked against the local budget.';
  const t = data.totals || {}; document.querySelector('#requests').textContent = number(t.requests); document.querySelector('#tokens').textContent = number(t.total_tokens); document.querySelector('#input').textContent = number(t.input_tokens); document.querySelector('#output').textContent = number(t.output_tokens);
  document.querySelector('#models').innerHTML = data.by_model?.length ? data.by_model.map(x => `<div class="model-row"><div><span class="model-name">${x.model}</span><span class="row-meta">${number(x.requests)} requests · ${number(x.total_tokens)} tokens</span></div><div class="row-cost">${money(x.estimated_cost_usd)}</div></div>`).join('') : '<p class="empty">No usage recorded yet.</p>';
  document.querySelector('#keys').innerHTML = data.keys?.length ? data.keys.map(x => `<div class="key-row"><div><span class="key-name">${x.label}</span><span class="row-meta">${x.key_prefix} · ${number(x.request_count)} requests</span></div><div class="key-state">${x.revoked_at ? 'revoked' : x.enabled ? 'enabled' : 'disabled'}</div></div>`).join('') : '<p class="empty">No keys created yet.</p>';
  document.querySelector('#activity').innerHTML = data.recent?.length ? data.recent.map(x => `<tr><td>${new Date(x.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</td><td>${x.model}</td><td class="${x.status === 'success' ? 'ok' : 'bad'}">${x.status}</td><td>${number(x.total_tokens)}</td><td>${money(x.estimated_cost_usd)}</td></tr>`).join('') : '<tr><td colspan="5" class="empty">No requests recorded yet.</td></tr>';
  document.querySelector('#updated').textContent = `updated ${new Date().toLocaleTimeString()}`; document.querySelector('#refresh').textContent = 'auto-refresh 10s';
}
const token = () => sessionStorage.getItem('provider-admin-token') || '';
document.querySelector('#auth').addEventListener('submit', event => { event.preventDefault(); sessionStorage.setItem('provider-admin-token', document.querySelector('#admin-token').value); refresh(); });
async function refresh(){try{const response=await fetch('/api/dashboard',{cache:'no-store',headers:{'X-Admin-Token':token()}}); if(response.status===401){document.querySelector('#signal-title').textContent='Operator unlock required'; document.querySelector('#signal-copy').textContent='Enter the admin token to view usage telemetry.'; return} if(response.ok) render(await response.json())}catch(e){document.querySelector('#status').innerHTML='<span style="background:var(--rust)"></span> offline'}}
refresh(); setInterval(refresh,10000);
