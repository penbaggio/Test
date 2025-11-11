let token = null;
let me = null;
let ws = null;
let notificationPermission = false;

// 音频提醒（使用Web Audio API生成提示音）
function playNotificationSound() {
  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.frequency.value = 800; // 频率
    oscillator.type = 'sine';
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.5);
  } catch (e) {
    console.log('音频播放失败:', e);
  }
}

// 浏览器通知
function showBrowserNotification(title, body, data) {
  if (!notificationPermission) return;
  
  try {
    const notification = new Notification(title, {
      body: body,
      icon: '/favicon.ico',
      badge: '/favicon.ico',
      tag: 'instruction-' + (data?.id || Date.now()),
      requireInteraction: true, // 需要用户手动关闭
      data: data,
    });
    
    notification.onclick = function(event) {
      event.preventDefault();
      window.focus();
      notification.close();
      // 可以跳转到具体指令详情
      if (data?.id) {
        log(`点击查看指令 #${data.id}`);
      }
    };
    
    // 5秒后自动关闭
    setTimeout(() => notification.close(), 5000);
  } catch (e) {
    console.log('通知显示失败:', e);
  }
}

// 请求通知权限
async function requestNotificationPermission() {
  if (!("Notification" in window)) {
    log("此浏览器不支持桌面通知");
    return;
  }
  
  if (Notification.permission === "granted") {
    notificationPermission = true;
    log("✅ 通知权限已授予");
  } else if (Notification.permission !== "denied") {
    const permission = await Notification.requestPermission();
    if (permission === "granted") {
      notificationPermission = true;
      log("✅ 通知权限已授予");
      // 测试通知
      showBrowserNotification("通知已启用", "您将收到新指令的实时提醒", {});
    }
  }
}

function log(msg) {
  const el = document.getElementById('log');
  const timestamp = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  el.textContent += `[${timestamp}] ${msg}\n`;
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
    
    log(`✅ 登录成功: ${me.username} (${me.role})`);
    
    // 请求通知权限
    await requestNotificationPermission();
    
    if (me.role === 'INVESTMENT_MANAGER') {
      document.getElementById('imPanel').classList.remove('hidden');
      await refreshIMList();
    } else if (me.role === 'TRADER') {
      document.getElementById('traderPanel').classList.remove('hidden');
      await refreshTraderList();
      // 交易员自动连接WebSocket
      connectWS();
    } else if (me.role === 'ADMIN') {
      document.getElementById('adminPanel').classList.remove('hidden');
      await refreshAdminList();
      connectWS();
    }
  } catch (e) {
    document.getElementById('loginMsg').textContent = e.message;
    log('❌ ' + e.message);
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
    const statusColor = getStatusColor(it.status);
    const urgencyBadge = it.urgency === 'HIGH' ? '<span class="badge" style="background:#f44336;color:white;">紧急</span>' : '';
    div.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <b>#${it.id}</b> ${it.title} ${urgencyBadge}<br>
          <small>${it.asset_code} | ${it.side} × ${it.qty} | ${it.price_type}${it.limit_price ? ' @' + it.limit_price : ''}</small>
        </div>
        <div>
          <span class="badge" style="background:${statusColor}">${it.status}</span>
          ${it.status === 'SUBMITTED' || it.status === 'SENT' ? 
            `<button onclick="cancelInstruction(${it.id})" style="margin-left:8px;">撤销</button>` : ''}
        </div>
      </div>
      <small style="color:#888;">创建时间: ${new Date(it.created_at).toLocaleString('zh-CN')}</small>
    `;
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
    const statusColor = getStatusColor(it.status);
    const urgencyBadge = it.urgency === 'HIGH' ? '<span class="badge" style="background:#f44336;color:white;">紧急</span>' : '';
    div.innerHTML = `
      <div><b>#${it.id}</b> ${it.title} ${urgencyBadge}</div>
      <div>${it.asset_code} | ${it.side} × ${it.qty} | ${it.price_type}${it.limit_price ? ' @' + it.limit_price : ''}</div>
      <div style="margin-top:4px;"><span class="badge" style="background:${statusColor}">${it.status}</span></div>
      ${it.remarks ? `<div style="margin-top:4px;"><small>备注: ${it.remarks}</small></div>` : ''}
      <div style="margin-top:8px;">
        <button onclick="acknowledgeInstruction(${it.id}, 'RECEIVED')" 
                ${it.status!=='SUBMITTED'&&it.status!=='SENT'?'disabled':''}>
          已接收
        </button>
        <button onclick="acknowledgeInstruction(${it.id}, 'IN_PROGRESS')" 
                ${it.status==='CANCELLED'||it.status==='EXECUTED'||it.status==='FAILED'?'disabled':''}>
          执行中
        </button>
        <button onclick="showExecuteDialog(${it.id})" 
                ${it.status==='CANCELLED'||it.status==='EXECUTED'||it.status==='FAILED'?'disabled':''} 
                style="background:#4caf50;color:white;">
          执行完成
        </button>
        <button onclick="acknowledgeInstruction(${it.id}, 'FAILED')" 
                ${it.status==='CANCELLED'||it.status==='EXECUTED'||it.status==='FAILED'?'disabled':''} 
                style="background:#f44336;color:white;">
          执行失败
        </button>
      </div>
    `;
    box.appendChild(div);
  }
}

async function refreshAdminList() {
  const r = await fetch('/instructions', { headers: { 'Authorization': 'Bearer ' + token }});
  const list = await r.json();
  const box = document.getElementById('adminList');
  box.innerHTML = '<h4>所有指令历史</h4>';
  for (const it of list) {
    const div = document.createElement('div');
    div.className = 'card';
    const statusColor = getStatusColor(it.status);
    div.innerHTML = `
      <b>#${it.id}</b> ${it.title} | ${it.asset_code} | ${it.side} × ${it.qty} 
      | <span class="badge" style="background:${statusColor}">${it.status}</span><br>
      <small>创建: ${new Date(it.created_at).toLocaleString('zh-CN')} | 更新: ${new Date(it.updated_at).toLocaleString('zh-CN')}</small>
    `;
    box.appendChild(div);
  }
}

function getStatusColor(status) {
  const colors = {
    'SUBMITTED': '#ff9800',
    'SENT': '#2196f3',
    'EXECUTING': '#9c27b0',
    'EXECUTED': '#4caf50',
    'CANCELLED': '#757575',
    'FAILED': '#f44336',
  };
  return colors[status] || '#999';
}

async function createInstruction() {
  const payload = {
    title: document.getElementById('title').value || '新指令',
    asset_code: document.getElementById('asset_code').value,
    side: document.getElementById('side').value,
    qty: parseFloat(document.getElementById('qty').value || '0'),
    price_type: document.getElementById('price_type').value,
    limit_price: document.getElementById('limit_price').value ? parseFloat(document.getElementById('limit_price').value) : null,
    urgency: document.getElementById('urgency').value,
    remarks: document.getElementById('remarks').value || null,
  };
  
  if (payload.qty <= 0) {
    alert('数量必须大于0');
    return;
  }
  
  const r = await fetch('/instructions', { 
    method: 'POST', 
    headers: { 
      'Authorization': 'Bearer ' + token, 
      'Content-Type': 'application/json' 
    }, 
    body: JSON.stringify(payload)
  });
  
  if (!r.ok) { 
    log('❌ 创建失败'); 
    return; 
  }
  
  log('✅ 指令已下达');
  // 清空表单
  document.getElementById('title').value = '';
  document.getElementById('remarks').value = '';
  await refreshIMList();
}

async function cancelInstruction(id) {
  if (!confirm('确定要撤销此指令吗?')) return;
  
  const r = await fetch(`/instructions/${id}/cancel`, { 
    method: 'POST', 
    headers: { 'Authorization': 'Bearer ' + token }
  });
  
  if (!r.ok) { 
    const err = await r.json();
    alert(err.detail || '撤销失败'); 
    return; 
  }
  
  log(`✅ 指令 #${id} 已撤销`);
  await refreshIMList();
}

async function acknowledgeInstruction(id, ackType) {
  const payload = {
    ack_type: ackType,
  };
  
  const r = await fetch(`/instructions/${id}/ack`, { 
    method: 'POST', 
    headers: { 
      'Authorization': 'Bearer ' + token,
      'Content-Type': 'application/json',
    }, 
    body: JSON.stringify(payload)
  });
  
  if (!r.ok) { 
    log(`❌ 回执失败`); 
    return; 
  }
  
  log(`✅ 指令 #${id} 回执: ${ackType}`);
  await refreshTraderList();
}

function showExecuteDialog(id) {
  const price = prompt('请输入实际成交价格:');
  if (!price) return;
  
  const qty = prompt('请输入实际成交数量:');
  if (!qty) return;
  
  executeInstructionWithDetails(id, parseFloat(price), parseFloat(qty));
}

async function executeInstructionWithDetails(id, price, qty) {
  const payload = {
    ack_type: 'COMPLETED',
    execution_price: price,
    execution_qty: qty,
    execution_time: new Date().toISOString(),
  };
  
  const r = await fetch(`/instructions/${id}/ack`, { 
    method: 'POST', 
    headers: { 
      'Authorization': 'Bearer ' + token,
      'Content-Type': 'application/json',
    }, 
    body: JSON.stringify(payload)
  });
  
  if (!r.ok) { 
    log('❌ 执行回报失败'); 
    return; 
  }
  
  log(`✅ 指令 #${id} 执行完成 (价格: ${price}, 数量: ${qty})`);
  await refreshTraderList();
}

function connectWS() {
  if (!token) { alert('请先登录'); return; }
  if (ws && ws.readyState === WebSocket.OPEN) {
    log('⚠️ WebSocket已连接');
    return;
  }
  
  const url = `ws://${location.host}/ws?token=${token}`;
  ws = new WebSocket(url);
  
  ws.onopen = () => { 
    log('🔗 WebSocket已连接'); 
    document.getElementById('wsState').textContent = '已连接';
    document.getElementById('wsState').style.background = '#4caf50';
    document.getElementById('wsState').style.color = 'white';
    
    // 发送心跳
    setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      }
    }, 30000); // 30秒心跳
  };
  
  ws.onclose = () => { 
    log('⚠️ WebSocket已断开'); 
    document.getElementById('wsState').textContent = '未连接';
    document.getElementById('wsState').style.background = '#f44336';
    document.getElementById('wsState').style.color = 'white';
    
    // 自动重连
    setTimeout(() => {
      if (token && me) {
        log('🔄 尝试重新连接...');
        connectWS();
      }
    }, 3000);
  };
  
  ws.onerror = (err) => {
    log('❌ WebSocket错误: ' + err);
  };
  
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      
      if (msg.type === 'pong') return; // 忽略心跳响应
      
      log(`📨 ${msg.type}`);
      
      // 新指令通知
      if (msg.type === 'instruction.created' && me && me.role === 'TRADER') {
        const data = msg.data;
        playNotificationSound();
        showBrowserNotification(
          `新投资指令 #${data.id}`,
          `${data.asset_code} ${data.side} ${data.qty}股\n紧急程度: ${data.urgency}`,
          data
        );
        refreshTraderList();
      }
      
      // 回执通知
      if (msg.type === 'instruction.acknowledged') {
        if (me && me.role === 'INVESTMENT_MANAGER') {
          refreshIMList();
        }
        if (me && me.role === 'TRADER') {
          refreshTraderList();
        }
      }
      
      // 撤销通知
      if (msg.type === 'instruction.cancelled' && me && me.role === 'TRADER') {
        playNotificationSound();
        showBrowserNotification(
          `指令已撤销 #${msg.data.id}`,
          `${msg.data.title} 已被 ${msg.data.cancelled_by} 撤销`,
          msg.data
        );
        refreshTraderList();
      }
      
      // 管理员刷新
      if (me && me.role === 'ADMIN') {
        refreshAdminList();
      }
      
    } catch (e) {
      console.log('消息解析失败:', e);
    }
  };
}
