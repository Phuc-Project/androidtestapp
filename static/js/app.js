// DroidRouter 9 - Core Application Logic

const App = {
  activeTab: 'instances',
  currentRemoteVm: '0',
  telemetryTimer: null,
  isAuthenticated: true,

  init() {
    this.bindEvents();
    this.checkPinStatus();
    this.startTelemetryLoop();
    this.switchTab('instances');
  },

  showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type === 'error' ? 'error' : ''}`;
    toast.innerHTML = `
      <span>${type === 'error' ? '⚠️' : '✅'}</span>
      <span>${message}</span>
    `;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(50px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  },

  bindEvents() {
    // Tab switching (both sidebar and header tabs)
    document.querySelectorAll('.sidebar-btn, .tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const tab = btn.dataset.tab;
        if (tab) this.switchTab(tab);
      });
    });

    // Global quick actions
    document.getElementById('btnOptimizeCluster')?.addEventListener('click', () => TestingModule.autoOptimizeCluster());
    document.getElementById('btnStartAll')?.addEventListener('click', () => this.startAllVms());
    document.getElementById('btnStopAll')?.addEventListener('click', () => this.stopAllVms());
    document.getElementById('btnArrange')?.addEventListener('click', () => this.arrangeWindows());
    document.getElementById('btnRefreshAll')?.addEventListener('click', () => this.refreshCurrentTab());
    document.getElementById('btnQuitApp')?.addEventListener('click', () => this.quitEngine());

    // Settings save
    document.getElementById('settingsForm')?.addEventListener('submit', (e) => {
      e.preventDefault();
      this.saveSettings();
    });

    // PIN lock form
    document.getElementById('pinForm')?.addEventListener('submit', (e) => {
      e.preventDefault();
      this.verifyPin();
    });
  },

  switchTab(tabName) {
    this.activeTab = tabName;
    document.querySelectorAll('.sidebar-btn, .tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    document.querySelectorAll('.tab-content').forEach(content => {
      content.classList.toggle('active', content.id === `tab-${tabName}`);
    });

    // Dynamic header title update
    const titleEl = document.getElementById('currentViewTitle');
    const titles = {
      instances: 'Thiết bị & Máy ảo (Device Nodes)',
      testing: 'Trung tâm Kiểm thử App (Test Suite)',
      remote: 'Điều khiển màn hình trực tiếp (Live Remote)',
      accounts: 'Kho tài khoản & Mã 2FA (Vault)',
      proxies: 'Cổng định tuyến Proxy (Gateway)',
      services: 'Điều khiển hàng loạt (Broadcast Shell)',
      logs: 'Nhật ký hệ thống (Logs & Events)',
      settings: 'Cài đặt Cụm (Cluster Settings)'
    };
    if (titleEl && titles[tabName]) {
      titleEl.textContent = titles[tabName];
    }

    // Trigger tab-specific loader
    if (tabName === 'instances') InstancesModule.load();
    if (tabName === 'testing') TestingModule.load();
    if (tabName === 'remote') RemoteModule.load();
    if (tabName === 'accounts') AccountsModule.load();
    if (tabName === 'proxies') ProxiesModule.load();
    if (tabName === 'services') ServicesModule.load();
    if (tabName === 'logs') this.loadLogs();
    if (tabName === 'settings') this.loadSettings();
  },

  refreshCurrentTab() {
    this.switchTab(this.activeTab);
    this.updateTelemetry();
    this.showToast('Data refreshed');
  },

  async startTelemetryLoop() {
    await this.updateTelemetry();
    this.telemetryTimer = setInterval(() => {
      this.updateTelemetry();
    }, 4000);
  },

  async updateTelemetry() {
    try {
      const res = await fetch('/api/system/stats');
      const data = await res.json();
      if (data.success) {
        const s = data.data;
        // CPU
        const cpuElem = document.getElementById('statCpu');
        const cpuBar = document.getElementById('statCpuBar');
        if (cpuElem) cpuElem.textContent = `${s.cpu_percent}%`;
        if (cpuBar) cpuBar.style.width = `${Math.min(s.cpu_percent, 100)}%`;

        // RAM
        const ramElem = document.getElementById('statRam');
        const ramBar = document.getElementById('statRamBar');
        const ramSub = document.getElementById('statRamSub');
        if (ramElem) ramElem.textContent = `${s.memory_percent}%`;
        if (ramBar) ramBar.style.width = `${Math.min(s.memory_percent, 100)}%`;
        if (ramSub) ramSub.textContent = `${s.memory_used_gb} / ${s.memory_total_gb} GB`;

        // VMs
        const vmsElem = document.getElementById('statVms');
        const vmsSub = document.getElementById('statVmsSub');
        const vmsBar = document.getElementById('statVmsBar');
        if (vmsElem) vmsElem.textContent = `${s.vms_running} / ${s.vms_total}`;
        if (vmsSub) vmsSub.textContent = `${s.vms_running} Running • ${s.vms_total - s.vms_running} Stopped`;
        if (vmsBar) {
          const pct = s.vms_total > 0 ? (s.vms_running / s.vms_total) * 100 : 0;
          vmsBar.style.width = `${pct}%`;
        }
      }
    } catch (e) {
      console.warn('Telemetry update failed', e);
    }
  },

  async startAllVms() {
    if (!confirm('Start all stopped Android VM instances?')) return;
    try {
      const res = await fetch('/api/instances');
      const data = await res.json();
      if (data.success) {
        const stopped = data.data.filter(v => !v.is_running).map(v => v.index);
        if (stopped.length === 0) {
          this.showToast('All VMs are already running');
          return;
        }
        await fetch('/api/instances/batch-launch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ indices: stopped })
        });
        this.showToast(`Starting ${stopped.length} VMs in background...`);
        setTimeout(() => InstancesModule.load(), 2000);
      }
    } catch (e) {
      this.showToast(e.message, 'error');
    }
  },

  async stopAllVms() {
    if (!confirm('Shutdown all running Android VM instances?')) return;
    try {
      const res = await fetch('/api/instances');
      const data = await res.json();
      if (data.success) {
        const running = data.data.filter(v => v.is_running).map(v => v.index);
        if (running.length === 0) {
          this.showToast('No VMs are currently running');
          return;
        }
        await fetch('/api/instances/batch-shutdown', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ indices: running })
        });
        this.showToast(`Stopping ${running.length} VMs...`);
        setTimeout(() => InstancesModule.load(), 2000);
      }
    } catch (e) {
      this.showToast(e.message, 'error');
    }
  },

  async arrangeWindows() {
    try {
      const res = await fetch('/api/instances/arrange', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        this.showToast('Windows arranged in grid layout');
      } else {
        this.showToast(data.error || 'Failed to arrange windows', 'error');
      }
    } catch (e) {
      this.showToast(e.message, 'error');
    }
  },

  async loadLogs() {
    const box = document.getElementById('systemLogBox');
    if (!box) return;
    try {
      const res = await fetch('/api/system/logs?limit=100');
      const data = await res.json();
      if (data.success) {
        box.innerHTML = data.data.map(l => `
          <div class="log-entry">
            <span class="log-ts">[${l.timestamp.split(' ')[1] || l.timestamp}]</span>
            <span class="log-src">[${l.source}]</span>
            <span class="log-lvl-${l.level}">${l.message}</span>
          </div>
        `).join('') || '<div style="color:var(--text-dim);padding:8px;">No logs recorded yet.</div>';
      }
    } catch (e) {
      box.innerHTML = `<div class="log-lvl-ERROR">Failed to load logs: ${e.message}</div>`;
    }
  },

  async loadSettings() {
    try {
      const res = await fetch('/api/system/settings');
      const data = await res.json();
      if (data.success) {
        const s = data.data;
        document.getElementById('settAppTitle').value = s.app_title || '';
        document.getElementById('settMumuPath').value = s.mumu_manager_path || '';
        document.getElementById('settAdbPath').value = s.adb_path || '';
        document.getElementById('settRefreshSec').value = s.auto_refresh_sec || 5;
        document.getElementById('settPinEnabled').checked = !!s.pin_enabled;
      }
    } catch (e) {
      this.showToast('Failed to load settings', 'error');
    }
  },

  async saveSettings() {
    const payload = {
      app_title: document.getElementById('settAppTitle').value,
      mumu_manager_path: document.getElementById('settMumuPath').value,
      adb_path: document.getElementById('settAdbPath').value,
      auto_refresh_sec: parseInt(document.getElementById('settRefreshSec').value) || 5,
      pin_enabled: document.getElementById('settPinEnabled').checked,
    };
    const newPin = document.getElementById('settPinCode').value;
    if (newPin) payload.pin_code = newPin;

    try {
      const res = await fetch('/api/system/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        this.showToast('Settings saved successfully');
      } else {
        this.showToast(data.message || 'Error saving settings', 'error');
      }
    } catch (e) {
      this.showToast(e.message, 'error');
    }
  },

  async checkPinStatus() {
    try {
      const res = await fetch('/api/system/settings');
      const data = await res.json();
      if (data.success && data.data.pin_enabled) {
        document.getElementById('pinOverlay').classList.add('active');
      }
    } catch (e) {}
  },

  async verifyPin() {
    const pin = document.getElementById('inputPin').value;
    try {
      const res = await fetch('/api/system/verify-pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin })
      });
      const data = await res.json();
      if (data.authenticated) {
        document.getElementById('pinOverlay').classList.remove('active');
        this.showToast('Dashboard unlocked');
      } else {
        alert('Invalid Security PIN Code');
      }
    } catch (e) {
      alert('Error verifying PIN');
    }
  },

  async quitEngine() {
    if (!confirm('Dừng toàn bộ hệ thống DroidRouter 9 và đóng ứng dụng?')) return;
    try {
      await fetch('/api/system/shutdown', { method: 'POST' });
      this.showToast('Hệ thống đang tắt...');
      setTimeout(() => {
        window.close();
      }, 800);
    } catch (e) {
      window.close();
    }
  }
};

window.addEventListener('DOMContentLoaded', () => App.init());
