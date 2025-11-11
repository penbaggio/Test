let token = null;
let me = null;
let ws = null;

function log(msg) {
  const el = document.getElementById('log');
  el.textContent += msg + "\n";
  el.scrollTop = el.scrollHeight;
}

async function login() {
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const form = new URLSearchParams();
  form.append('username', username);
  form.append('password', password);
  try {
    const r = await fetch('/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    });
    if (!r.ok) throw new Error('登录失败');
    const data = await r.json();
    token = data.access_token;
    const meResp = await fetch('/me', { headers: { 'Authorization': 'Bearer ' + token } });
    me = await meResp.json();
    document.getElementById('login').classList.add('hidden');
    document.getElementById('whoami').classList.remove('hidden');
    document.getElementById('meName').textContent = me.username;
    document.getElementById('meRole').textContent = me.role;
    if (me.role === 'INVESTMENT_MANAGER') {
      document.getElementById('imPanel').classList.remove('hidden');
      await refreshIMList();
    } else if (me.role === 'TRADER') {
      document.getElementById('traderPanel').classList.remove('hidden');
      await refreshTraderList();
    }
  } catch (e) {
    document.getElementById('loginMsg').textContent = e.message;
  }
}

function logout() {
  token = null; me = null;
  try { if (ws) ws.close(); } catch {}
  location.reload();
}

async function refreshIMList() {
  const r = await fetch('/instructions', { headers: { 'Authorization': 'Bearer ' + token }});
  const list = await r.json();
  const box = document.getElementById('imList');
  box.innerHTML = '';
  for (const it of list) {
    const div = document.createElement('div');
    div.className = 'card';
    div.innerHTML = `<b>#${it.id}</b> ${it.title} | ${it.asset_code} | ${it.side} x ${it.qty} | <span class="badge">${it.status}</span>`;
    box.appendChild(div);
  }
}

async function refreshTraderList() {
  const r = await fetch('/instructions', { headers: { 'Authorization': 'Bearer ' + token }});
  const list = await r.json();
  const box = document.getElementById('traderList');
  box.innerHTML = '';
  for (const it of list) {
    const div = document.createElement('div');
    div.className = 'card';
    div.innerHTML = `<b>#${it.id}</b> ${it.title} | ${it.asset_code} | ${it.side} x ${it.qty} | <span class="badge">${it.status}</span>
    <div style="margin-top:6px;">
      <button onclick="ack(${it.id})" ${it.status!=='SUBMITTED'&&it.status!=='SENT'?'disabled':''}>回执</button>
      <button onclick="executeInst(${it.id})" ${it.status!=='ACKED'?'disabled':''}>执行完成</button>
    </div>`;
    box.appendChild(div);
  }
}

async function createInstruction() {
  const payload = {
    title: document.getElementById('title').value || '新指令',
    asset_code: document.getElementById('asset_code').value,
    side: document.getElementById('side').value,
    qty: parseFloat(document.getElementById('qty').value || '0'),
    price_type: document.getElementById('price_type').value,
    limit_price: document.getElementById('limit_price').value ? parseFloat(document.getElementById('limit_price').value) : null,
  };
  const r = await fetch('/instructions', { method: 'POST', headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' }, body: JSON.stringify(payload)});
  if (!r.ok) { log('创建失败'); return; }
  log('创建成功');
  await refreshIMList();
}

function connectWS() {
  if (!token) { alert('请先登录'); return; }
  if (ws && ws.readyState === WebSocket.OPEN) return;
  const url = `ws://${location.host}/ws?token=${token}`;
  ws = new WebSocket(url);
  ws.onopen = () => { log('[WS] connected'); document.getElementById('wsState').textContent = '已连接'; };
  ws.onclose = () => { log('[WS] closed'); document.getElementById('wsState').textContent = '未连接'; };
  ws.onmessage = (ev) => {
    log('[WS] ' + ev.data);
    try {
      const msg = JSON.parse(ev.data);
      if (me && me.role === 'TRADER' && (msg.type === 'instruction.created' || msg.type === 'instruction.acked' || msg.type === 'instruction.executed')) {
        refreshTraderList();
      }
      if (me && me.role === 'INVESTMENT_MANAGER' && (msg.type === 'instruction.acked' || msg.type === 'instruction.executed')) {
        refreshIMList();
      }
    } catch {}
  };
}

async function ack(id) {
  const r = await fetch(`/instructions/${id}/ack`, { method: 'POST', headers: { 'Authorization': 'Bearer ' + token }});
  if (!r.ok) { log('回执失败'); return; }
  log('回执成功');
  await refreshTraderList();
}

async function executeInst(id) {
  const r = await fetch(`/instructions/${id}/execute`, { method: 'POST', headers: { 'Authorization': 'Bearer ' + token }});
  if (!r.ok) { log('执行失败'); return; }
  log('执行完成');
  await refreshTraderList();
}
