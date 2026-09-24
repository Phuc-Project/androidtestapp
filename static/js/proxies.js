// DroidRouter 9 - Proxy Router & Network Management

const ProxiesModule = {
  proxies: [],

  async load() {
    this.fetchProxies();
  },

  async fetchProxies() {
    const list = document.getElementById('proxyList');
    if (!list) return;
    list.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:40px;">Loading proxy router...</div>';

    try {
      const res = await fetch('/api/proxies');
      const data = await res.json();
      if (data.success) {
        this.proxies = data.data;
        this.render();
      }
    } catch (e) {
      list.innerHTML = `<div style="color:var(--accent-red);">Error: ${e.message}</div>`;
    }
  },

  render() {
    const list = document.getElementById('proxyList');
    if (!list) return;

    if (this.proxies.length === 0) {
      list.innerHTML = `
        <div style="text-align:center;padding:50px;background:var(--bg-card);border-radius:var(--radius-md);border:1px dashed var(--border-color);">
          <div style="font-size:32px;margin-bottom:10px;">🌐</div>
          <h3 style="font-size:16px;margin-bottom:6px;">No Proxies Configured</h3>
          <p style="color:var(--text-dim);font-size:13px;margin-bottom:16px;">Add HTTP or SOCKS5 proxies to route network traffic per Android instance.</p>
          <button class="btn btn-primary" onclick="ProxiesModule.openAddModal()">+ Add New Proxy</button>
        </div>
      `;
      return;
    }

    list.innerHTML = this.proxies.map(p => {
      const isOnline = p.status === 'active';
      return `
        <div class="account-card" id="proxyCard-${p.id}">
          <div class="account-icon" style="background:#132034;color:var(--accent-cyan);">🌐</div>

          <div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px;">
              <span style="font-weight:700;font-size:14px;">${this.escape(p.name)}</span>
              <span class="vm-badge" style="text-transform:uppercase;">${p.proto}</span>
              ${p.assigned_vm_index !== '' ? `<span class="vm-badge" style="background:#0f2e24;color:var(--accent-green);">VM #${p.assigned_vm_index}</span>` : ''}
              <span class="vm-status-badge ${isOnline ? 'running' : 'stopped'}">
                ${isOnline ? 'ONLINE' : (p.status || 'UNTESTED')}
              </span>
            </div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-muted);display:flex;gap:14px;">
              <span>🔌 ${p.host}:${p.port}</span>
              ${p.outgoing_ip ? `<span>📍 IP: ${p.outgoing_ip} (${p.country || 'N/A'})</span>` : ''}
              ${p.latency_ms ? `<span>⚡ ${p.latency_ms}ms</span>` : ''}
            </div>
          </div>

          <div>
            ${p.last_checked ? `
              <div style="font-size:11px;color:var(--text-dim);text-align:right;">
                Tested: ${p.last_checked.split(' ')[1] || p.last_checked}
              </div>
            ` : '<div style="font-size:11px;color:var(--text-dim);text-align:right;">Not tested yet</div>'}
          </div>

          <div style="display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end;">
            <button class="btn btn-secondary btn-sm" onclick="ProxiesModule.testProxy('${p.id}')">🔄 Test</button>
            ${p.assigned_vm_index !== '' ? `
              <button class="btn btn-primary btn-sm" onclick="ProxiesModule.applyProxy('${p.id}')">⚡ Apply to VM</button>
              <button class="btn btn-secondary btn-sm" onclick="ProxiesModule.clearProxy('${p.assigned_vm_index}')">❌ Clear</button>
            ` : ''}
            <button class="btn btn-danger btn-sm" onclick="ProxiesModule.deleteProxy('${p.id}')">🗑️</button>
          </div>
        </div>
      `;
    }).join('');
  },

  async testProxy(id) {
    App.showToast(`Testing proxy connectivity...`);
    try {
      const res = await fetch(`/api/proxies/${id}/test`, { method: 'POST' });
      const data = await res.json();
      if (data.success && data.test_result.success) {
        App.showToast(`Proxy online: ${data.data.outgoing_ip} (${data.data.latency_ms}ms)`);
        this.fetchProxies();
      } else {
        App.showToast(`Proxy offline or failed: ${data.test_result?.error || 'Failed'}`, 'error');
        this.fetchProxies();
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async applyProxy(id) {
    App.showToast('Applying proxy to VM via ADB...');
    try {
      const res = await fetch(`/api/proxies/${id}/apply`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        App.showToast(data.message);
      } else {
        App.showToast(data.error || 'Failed to apply proxy', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async clearProxy(vmIndex) {
    App.showToast(`Clearing proxy on VM #${vmIndex}...`);
    try {
      const res = await fetch(`/api/proxies/clear-vm/${vmIndex}`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        App.showToast(`Proxy cleared on VM #${vmIndex}`);
      } else {
        App.showToast('Failed to clear proxy', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  openAddModal() {
    document.getElementById('proxyForm').reset();
    this.populateVmDropdown();
    document.getElementById('modalProxy').classList.add('active');
  },

  async populateVmDropdown() {
    const sel = document.getElementById('proxyVmIndex');
    if (!sel) return;
    try {
      const res = await fetch('/api/instances');
      const data = await res.json();
      if (data.success) {
        sel.innerHTML = `<option value="">-- None (Unbound) --</option>` +
          data.data.map(v => `<option value="${v.index}">VM #${v.index} (${v.name})</option>`).join('');
      }
    } catch (e) {}
  },

  async submitProxy() {
    const payload = {
      name: document.getElementById('proxyName').value.trim() || 'Proxy',
      proto: document.getElementById('proxyProto').value,
      host: document.getElementById('proxyHost').value.trim(),
      port: parseInt(document.getElementById('proxyPort').value) || 8080,
      username: document.getElementById('proxyUsername').value.trim(),
      password: document.getElementById('proxyPassword').value,
      assigned_vm_index: document.getElementById('proxyVmIndex').value
    };

    if (!payload.host || !payload.port) {
      App.showToast('Host and Port are required', 'error');
      return;
    }

    try {
      const res = await fetch('/api/proxies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        App.showToast('Proxy saved');
        document.getElementById('modalProxy').classList.remove('active');
        this.fetchProxies();
      } else {
        App.showToast(data.message || 'Error saving proxy', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async deleteProxy(id) {
    if (!confirm('Delete this proxy?')) return;
    try {
      const res = await fetch(`/api/proxies/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        App.showToast('Proxy deleted');
        this.fetchProxies();
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  escape(str) {
    return (str || '').replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[m]);
  }
};
