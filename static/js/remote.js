// DroidTest SaaS - Live Remote Screen & Interactive Controller

const RemoteModule = {
  streamInterval: null,
  isStreaming: false,
  dragStart: null,
  naturalWidth: 540,
  naturalHeight: 960,

  openModal(index) {
    App.currentRemoteVm = String(index);
    const title = document.getElementById('remoteModalTitle');
    if (title) title.textContent = `Màn hình máy #${index}`;
    const modal = document.getElementById('modalRemote');
    if (modal) modal.classList.add('active');
    this.startStreaming();
  },

  closeModal() {
    const modal = document.getElementById('modalRemote');
    if (modal) modal.classList.remove('active');
    this.stopStreaming();
  },

  startStreaming() {
    if (this.isStreaming) return;
    this.isStreaming = true;
    this.fetchFrame();
    this.streamInterval = setInterval(() => {
      const modal = document.getElementById('modalRemote');
      if (modal && modal.classList.contains('active')) {
        this.fetchFrame();
      } else {
        this.stopStreaming();
      }
    }, 1200);
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
      this.naturalWidth = tempImg.naturalWidth || 540;
      this.naturalHeight = tempImg.naturalHeight || 960;
      if (statusText) statusText.textContent = `${this.naturalWidth}×${this.naturalHeight} · trực tiếp`;
    };
    tempImg.onerror = () => {
      if (statusText) statusText.textContent = `Không lấy được hình – máy #${vmIdx} đang tắt hoặc đang khởi động`;
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
      this.sendTap(vmIdx, x1, y1);
    } else {
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
        App.showToast('Đã gửi chữ vào máy');
        if (input) input.value = '';
        setTimeout(() => this.fetchFrame(), 300);
      } else {
        App.showToast('Không gửi được chữ – máy có đang bật không?', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  }
};
