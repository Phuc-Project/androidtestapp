// DroidRouter 9 - Live Remote Screen & Interactive Controller

const RemoteModule = {
  streamInterval: null,
  isStreaming: false,
  dragStart: null,
  naturalWidth: 900,
  naturalHeight: 1600,

  async load() {
    this.populateVmSelector();
    this.startStreaming();
  },

  async populateVmSelector() {
    const sel = document.getElementById('remoteVmSelect');
    if (!sel) return;
    try {
      const res = await fetch('/api/instances');
      const data = await res.json();
      if (data.success) {
        sel.innerHTML = data.data.map(v => `
          <option value="${v.index}" ${v.index === App.currentRemoteVm ? 'selected' : ''}>
            VM #${v.index} - ${v.name} ${v.is_running ? '🟢' : '⚪'}
          </option>
        `).join('');
      }
    } catch (e) {}
  },

  onVmChange(newIndex) {
    App.currentRemoteVm = newIndex;
    this.fetchFrame();
  },

  startStreaming() {
    if (this.isStreaming) return;
    this.isStreaming = true;
    this.fetchFrame();
    this.streamInterval = setInterval(() => {
      if (App.activeTab === 'remote') {
        this.fetchFrame();
      }
    }, 1500); // 1.5s refresh for screencap
  },

  stopStreaming() {
    this.isStreaming = false;
    if (this.streamInterval) {
      clearInterval(this.streamInterval);
      this.streamInterval = null;
    }
  },

  async fetchFrame() {
    const img = document.getElementById('remoteScreenImg');
    const statusText = document.getElementById('screenStatusText');
    if (!img) return;

    const vmIdx = App.currentRemoteVm || '0';
    const timestamp = Date.now();
    const frameUrl = `/api/screen/${vmIdx}/frame?t=${timestamp}`;

    const tempImg = new Image();
    tempImg.onload = () => {
      img.src = tempImg.src;
      this.naturalWidth = tempImg.naturalWidth || 900;
      this.naturalHeight = tempImg.naturalHeight || 1600;
      if (statusText) statusText.textContent = `Connected (Resolution: ${this.naturalWidth}x${this.naturalHeight})`;
    };
    tempImg.onerror = () => {
      if (statusText) statusText.textContent = `Offline or Stopped (VM #${vmIdx})`;
    };
    tempImg.src = frameUrl;
  },

  handlePointerDown(e) {
    const img = document.getElementById('remoteScreenImg');
    if (!img) return;
    const rect = img.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    const x = Math.round((clientX / rect.width) * this.naturalWidth);
    const y = Math.round((clientY / rect.height) * this.naturalHeight);

    this.dragStart = { x, y, time: Date.now() };
  },

  handlePointerUp(e) {
    if (!this.dragStart) return;
    const img = document.getElementById('remoteScreenImg');
    if (!img) return;
    const rect = img.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    const x2 = Math.round((clientX / rect.width) * this.naturalWidth);
    const y2 = Math.round((clientY / rect.height) * this.naturalHeight);
    const x1 = this.dragStart.x;
    const y1 = this.dragStart.y;
    const duration = Date.now() - this.dragStart.time;
    this.dragStart = null;

    const distance = Math.hypot(x2 - x1, y2 - y1);
    const vmIdx = App.currentRemoteVm || '0';

    if (distance < 15) {
      // Tap
      this.sendTap(vmIdx, x1, y1);
    } else {
      // Swipe
      this.sendSwipe(vmIdx, x1, y1, x2, y2, Math.max(duration, 200));
    }
  },

  async sendTap(vmIdx, x, y) {
    try {
      await fetch(`/api/screen/${vmIdx}/tap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y })
      });
      setTimeout(() => this.fetchFrame(), 300);
    } catch (e) {}
  },

  async sendSwipe(vmIdx, x1, y1, x2, y2, duration_ms) {
    try {
      await fetch(`/api/screen/${vmIdx}/swipe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x1, y1, x2, y2, duration_ms })
      });
      setTimeout(() => this.fetchFrame(), 400);
    } catch (e) {}
  },

  async sendKey(keyName) {
    const vmIdx = App.currentRemoteVm || '0';
    try {
      await fetch(`/api/screen/${vmIdx}/key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: keyName })
      });
      App.showToast(`Sent key '${keyName}'`);
      setTimeout(() => this.fetchFrame(), 300);
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async sendText() {
    const input = document.getElementById('remoteTextInput');
    const text = input ? input.value : '';
    if (!text) return;
    const vmIdx = App.currentRemoteVm || '0';

    try {
      const res = await fetch(`/api/screen/${vmIdx}/text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      const data = await res.json();
      if (data.success) {
        App.showToast('Text sent to VM');
        if (input) input.value = '';
        setTimeout(() => this.fetchFrame(), 300);
      } else {
        App.showToast('Failed to send text', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async launchApp(packageId) {
    const vmIdx = App.currentRemoteVm || '0';
    App.showToast(`Launching ${packageId}...`);
    try {
      const res = await fetch(`/api/screen/${vmIdx}/launch-app`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ package: packageId })
      });
      const data = await res.json();
      if (data.success) {
        App.showToast('App launched');
        setTimeout(() => this.fetchFrame(), 1500);
      } else {
        App.showToast('Failed to launch app', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async installApkFile(file) {
    if (!file) return;
    const vmIdx = App.currentRemoteVm || '0';
    App.showToast(`Uploading and installing ${file.name} on VM #${vmIdx}...`);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`/api/screen/${vmIdx}/install-apk`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.success) {
        App.showToast(`Installed ${file.name} successfully`);
      } else {
        App.showToast(data.error || 'APK installation failed', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  }
};
