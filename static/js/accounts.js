// DroidRouter 9 - Accounts Vault & ADB Auto-Login Injector

const AccountsModule = {
  accounts: [],
  totpTimer: null,

  async load() {
    this.fetchAccounts();
    this.startTotpTicker();
  },

  async fetchAccounts() {
    const list = document.getElementById('accountsList');
    if (!list) return;
    list.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:40px;">Loading accounts vault...</div>';

    try {
      const res = await fetch('/api/accounts');
      const data = await res.json();
      if (data.success) {
        this.accounts = data.data;
        this.render();
      }
    } catch (e) {
      list.innerHTML = `<div style="color:var(--accent-red);">Error: ${e.message}</div>`;
    }
  },

  startTotpTicker() {
    if (this.totpTimer) clearInterval(this.totpTimer);
    this.totpTimer = setInterval(() => {
      // Local decrement of remaining seconds
      let needsRefresh = false;
      this.accounts.forEach(acc => {
        if (acc.totp && acc.totp.valid) {
          acc.totp.remaining = (acc.totp.remaining || 30) - 1;
          if (acc.totp.remaining <= 0) {
            needsRefresh = true;
          }
          const el = document.getElementById(`totpSec-${acc.id}`);
          if (el) el.textContent = `${acc.totp.remaining}s`;
        }
      });
      if (needsRefresh) {
        this.fetchAccounts();
      }
    }, 1000);
  },

  render() {
    const list = document.getElementById('accountsList');
    if (!list) return;

    if (this.accounts.length === 0) {
      list.innerHTML = `
        <div style="text-align:center;padding:50px;background:var(--bg-card);border-radius:var(--radius-md);border:1px dashed var(--border-color);">
          <div style="font-size:32px;margin-bottom:10px;">🔑</div>
          <h3 style="font-size:16px;margin-bottom:6px;">No Accounts Stored</h3>
          <p style="color:var(--text-dim);font-size:13px;margin-bottom:16px;">Save your Google, TikTok, Facebook, or custom accounts for 1-click auto-fill onto Android VMs.</p>
          <button class="btn btn-primary" onclick="AccountsModule.openAddModal()">+ Add New Account</button>
        </div>
      `;
      return;
    }

    const serviceIcons = {
      google: '🔴',
      tiktok: '🎵',
      facebook: '🔷',
      twitter: '🐦',
      telegram: '✈️',
      discord: '👾',
      custom: '🔑'
    };

    list.innerHTML = this.accounts.map(acc => {
      const icon = serviceIcons[acc.service] || '🔑';
      const hasTotp = acc.totp && acc.totp.valid;
      return `
        <div class="account-card" id="accCard-${acc.id}">
          <div class="account-icon">${icon}</div>
          
          <div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px;">
              <span style="font-weight:700;font-size:14px;">${this.escape(acc.name)}</span>
              <span class="vm-badge" style="text-transform:uppercase;">${acc.service}</span>
              ${acc.assigned_vm_index !== '' ? `<span class="vm-badge" style="background:#0f2e24;color:var(--accent-green);">Bound to VM #${acc.assigned_vm_index}</span>` : ''}
            </div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-muted);display:flex;gap:12px;">
              <span>👤 ${this.escape(acc.username)}</span>
              ${acc.password ? `<span>🔒 ••••••••</span>` : ''}
            </div>
          </div>

          <div>
            ${hasTotp ? `
              <div class="totp-box" title="Click to copy 2FA code" onclick="AccountsModule.copyTotp('${acc.totp.code}')" style="cursor:pointer;">
                <span class="totp-code">${acc.totp.code}</span>
                <span class="totp-countdown" id="totpSec-${acc.id}">${acc.totp.remaining}s</span>
              </div>
            ` : `
              <div style="font-size:11px;color:var(--text-dim);text-align:center;">No 2FA Configured</div>
            `}
          </div>

          <div style="display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end;">
            <button class="btn btn-secondary btn-sm" onclick="AccountsModule.autofill('${acc.id}', 'username')">👤 Type User</button>
            <button class="btn btn-secondary btn-sm" onclick="AccountsModule.autofill('${acc.id}', 'password')">🔑 Type Pass</button>
            ${hasTotp ? `<button class="btn btn-secondary btn-sm" onclick="AccountsModule.autofill('${acc.id}', 'totp')">⚡ Type 2FA</button>` : ''}
            <button class="btn btn-primary btn-sm" onclick="AccountsModule.autofill('${acc.id}', 'all')">🚀 Auto-Fill</button>
            <button class="btn btn-danger btn-sm" onclick="AccountsModule.deleteAccount('${acc.id}')">🗑️</button>
          </div>
        </div>
      `;
    }).join('');
  },

  async autofill(accountId, field) {
    const acc = this.accounts.find(a => String(a.id) === String(accountId));
    if (!acc) return;

    let targetVm = acc.assigned_vm_index;
    if (!targetVm && targetVm !== '0') {
      targetVm = prompt(`Select target VM index for account '${acc.name}':`, App.currentRemoteVm || '0');
      if (targetVm === null) return;
    }

    App.showToast(`Injecting '${field}' to VM #${targetVm}...`);
    try {
      const res = await fetch(`/api/accounts/${accountId}/autofill`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_vm_index: String(targetVm), field })
      });
      const data = await res.json();
      if (data.success) {
        App.showToast(data.message || 'Auto-filled successfully');
      } else {
        App.showToast(data.error || 'Auto-fill failed', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  copyTotp(code) {
    navigator.clipboard.writeText(code);
    App.showToast(`Copied 2FA code ${code}`);
  },

  openAddModal() {
    document.getElementById('accForm').reset();
    document.getElementById('accEditId').value = '';
    this.populateVmDropdown();
    document.getElementById('modalAccount').classList.add('active');
  },

  async populateVmDropdown() {
    const sel = document.getElementById('accVmIndex');
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

  async submitAccount() {
    const editId = document.getElementById('accEditId').value;
    const payload = {
      service: document.getElementById('accService').value,
      name: document.getElementById('accName').value.trim() || 'Account',
      username: document.getElementById('accUsername').value.trim(),
      password: document.getElementById('accPassword').value,
      two_factor_secret: document.getElementById('acc2FaSecret').value.trim(),
      assigned_vm_index: document.getElementById('accVmIndex').value,
      notes: document.getElementById('accNotes').value
    };

    if (!payload.username) {
      App.showToast('Username/Email is required', 'error');
      return;
    }

    try {
      const url = editId ? `/api/accounts/${editId}` : '/api/accounts';
      const method = editId ? 'PUT' : 'POST';
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        App.showToast(data.message || 'Account saved');
        document.getElementById('modalAccount').classList.remove('active');
        this.fetchAccounts();
      } else {
        App.showToast(data.message || 'Error saving account', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async deleteAccount(id) {
    if (!confirm('Delete this saved account?')) return;
    try {
      const res = await fetch(`/api/accounts/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        App.showToast('Account deleted');
        this.fetchAccounts();
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
