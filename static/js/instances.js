// DroidRouter 9 - Virtual Machine Instances Management

const InstancesModule = {
  vms: [],
  selectedIndices: new Set(),

  async load() {
    const grid = document.getElementById('vmGrid');
    if (!grid) return;
    grid.innerHTML = '<div style="color:var(--text-muted);grid-column:1/-1;text-align:center;padding:40px;">Scanning emulator instances...</div>';

    try {
      const res = await fetch('/api/instances');
      const data = await res.json();
      if (data.success) {
        this.vms = data.data;
        this.render();
      } else {
        grid.innerHTML = `<div style="color:var(--accent-red);grid-column:1/-1;">Error: ${data.error || 'Failed to list instances'}</div>`;
      }
    } catch (e) {
      grid.innerHTML = `<div style="color:var(--accent-red);grid-column:1/-1;">Connection error: ${e.message}</div>`;
    }
  },

  render() {
    const grid = document.getElementById('vmGrid');
    if (!grid) return;

    if (this.vms.length === 0) {
      grid.innerHTML = `
        <div style="grid-column:1/-1;text-align:center;padding:50px;background:var(--bg-card);border-radius:var(--radius-md);border:1px dashed var(--border-color);">
          <div style="font-size:32px;margin-bottom:10px;">📱</div>
          <h3 style="font-size:16px;margin-bottom:6px;">No Android Instances Detected</h3>
          <p style="color:var(--text-dim);font-size:13px;margin-bottom:16px;">Create a new instance or check your MuMuPlayer path in Settings.</p>
          <button class="btn btn-primary" onclick="InstancesModule.openCreateModal()">+ Create Android VM</button>
        </div>
      `;
      return;
    }

    grid.innerHTML = this.vms.map(vm => {
      const isRunning = vm.is_running;
      return `
        <div class="vm-card ${isRunning ? 'running' : 'stopped'}" id="vmCard-${vm.index}">
          <div>
            <div class="vm-card-header">
              <div class="vm-title">
                <span class="vm-badge">VM #${vm.index}</span>
                <span class="vm-name">${this.escape(vm.name)}</span>
              </div>
              <span class="vm-status-badge ${isRunning ? 'running' : 'stopped'}">
                <span class="pulse-dot" style="display:${isRunning ? 'inline-block' : 'none'};"></span>
                ${isRunning ? 'RUNNING' : 'STOPPED'}
              </span>
            </div>

            <div class="vm-details">
              <div>
                <div class="vm-prop-label">Android OS</div>
                <div class="vm-prop-val">v${vm.android_version}</div>
              </div>
              <div>
                <div class="vm-prop-label">Disk Storage</div>
                <div class="vm-prop-val">${vm.disk_size_mb} MB</div>
              </div>
              <div>
                <div class="vm-prop-label">ADB Target</div>
                <div class="vm-prop-val" style="color:var(--accent-cyan);">${vm.adb_target}</div>
              </div>
              <div>
                <div class="vm-prop-label">Proxy Status</div>
                <div class="vm-prop-val">${vm.assigned_proxy_id ? 'Assigned' : 'Direct'}</div>
              </div>
            </div>
          </div>

          <div class="vm-actions">
            ${isRunning ? `
              <button class="btn btn-danger btn-sm" onclick="InstancesModule.shutdown('${vm.index}')">🛑 Stop</button>
              <button class="btn btn-secondary btn-sm" onclick="InstancesModule.restart('${vm.index}')">🔄 Reboot</button>
              <button class="btn btn-secondary btn-sm" onclick="InstancesModule.toggleWindow('${vm.index}')">👁️ Window</button>
              <button class="btn btn-primary btn-sm" onclick="InstancesModule.openRemote('${vm.index}')">🎮 Remote</button>
            ` : `
              <button class="btn btn-primary btn-sm" onclick="InstancesModule.launch('${vm.index}')">🟢 Start</button>
              <button class="btn btn-secondary btn-sm" onclick="InstancesModule.openClone('${vm.index}')">🧬 Clone</button>
              <button class="btn btn-secondary btn-sm" onclick="InstancesModule.openSimulation('${vm.index}')">📱 Simu</button>
              <button class="btn btn-secondary btn-sm" onclick="InstancesModule.openRename('${vm.index}', '${this.escape(vm.name)}')">✏️ Rename</button>
              <button class="btn btn-danger btn-sm" onclick="InstancesModule.delete('${vm.index}')">🗑️</button>
            `}
          </div>
        </div>
      `;
    }).join('');
  },

  async launch(index) {
    App.showToast(`Starting VM #${index}...`);
    try {
      const res = await fetch(`/api/instances/${index}/launch`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        App.showToast(`VM #${index} launched`);
        setTimeout(() => this.load(), 2000);
      } else {
        App.showToast(data.error || 'Failed to start VM', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async shutdown(index) {
    App.showToast(`Stopping VM #${index}...`);
    try {
      const res = await fetch(`/api/instances/${index}/shutdown`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        App.showToast(`VM #${index} stopped`);
        setTimeout(() => this.load(), 1500);
      } else {
        App.showToast(data.error || 'Failed to stop VM', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async restart(index) {
    App.showToast(`Restarting VM #${index}...`);
    try {
      await fetch(`/api/instances/${index}/restart`, { method: 'POST' });
      App.showToast(`VM #${index} restart triggered`);
      setTimeout(() => this.load(), 2500);
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async toggleWindow(index) {
    try {
      await fetch(`/api/instances/${index}/show`, { method: 'POST' });
      App.showToast(`Window brought to front`);
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  openRemote(index) {
    App.currentRemoteVm = index;
    App.switchTab('remote');
  },

  openCreateModal() {
    document.getElementById('modalCreateVm').classList.add('active');
  },

  async submitCreateVm() {
    const ver = document.getElementById('newVmVersion').value || '15';
    document.getElementById('modalCreateVm').classList.remove('active');
    App.showToast(`Creating new Android ${ver} instance in background...`);
    try {
      const res = await fetch('/api/instances/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version: ver })
      });
      const data = await res.json();
      if (data.success) {
        App.showToast('VM instance created successfully');
        setTimeout(() => this.load(), 3000);
      } else {
        App.showToast(data.error || 'Creation failed', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async openClone(index) {
    if (!confirm(`Clone VM #${index}? This may take a minute.`)) return;
    App.showToast(`Cloning VM #${index}...`);
    try {
      const res = await fetch(`/api/instances/${index}/clone`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        App.showToast(`VM #${index} cloned successfully`);
        setTimeout(() => this.load(), 3000);
      } else {
        App.showToast(data.error || 'Clone failed', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  openRename(index, currentName) {
    const newName = prompt(`Enter new name for VM #${index}:`, currentName);
    if (!newName || newName === currentName) return;
    this.submitRename(index, newName);
  },

  async submitRename(index, newName) {
    try {
      const res = await fetch(`/api/instances/${index}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName })
      });
      const data = await res.json();
      if (data.success) {
        App.showToast(`Renamed VM #${index} to '${newName}'`);
        this.load();
      } else {
        App.showToast(data.error || 'Rename failed', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  openSimulation(index) {
    document.getElementById('simVmIndex').value = index;
    document.getElementById('modalSimulation').classList.add('active');
  },

  async submitSimulation() {
    const index = document.getElementById('simVmIndex').value;
    const simu_key = document.getElementById('simKey').value;
    const simu_value = document.getElementById('simVal').value.trim();
    if (!simu_value) {
      App.showToast('Please enter a value', 'error');
      return;
    }

    try {
      const res = await fetch(`/api/instances/${index}/simulation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ simu_key, simu_value })
      });
      const data = await res.json();
      if (data.success) {
        App.showToast(`Updated ${simu_key} for VM #${index}`);
        document.getElementById('modalSimulation').classList.remove('active');
      } else {
        App.showToast(data.error || 'Failed to update simulation', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async delete(index) {
    if (!confirm(`Are you sure you want to permanently delete VM #${index}? This cannot be undone!`)) return;
    App.showToast(`Deleting VM #${index}...`);
    try {
      const res = await fetch(`/api/instances/${index}/delete`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        App.showToast(`VM #${index} deleted`);
        this.load();
      } else {
        App.showToast(data.error || 'Delete failed', 'error');
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
