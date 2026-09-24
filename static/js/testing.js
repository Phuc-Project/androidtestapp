// DroidRouter SaaS - App Test Suite & Batch Automation

const TestingModule = {
  async load() {
    this.refreshRunningStatus();
  },

  async refreshRunningStatus() {
    const el = document.getElementById('testRunningCount');
    if (!el) return;
    try {
      const res = await fetch('/api/instances');
      const data = await res.json();
      if (data.success) {
        const running = data.data.filter(v => v.is_running);
        el.textContent = `${running.length} / ${data.data.length} Nodes Online`;
      }
    } catch (e) {}
  },

  async runBatchAction(action) {
    const pkgInput = document.getElementById('testTargetPackage');
    const pkg = pkgInput ? pkgInput.value.trim() : '';
    const consoleBox = document.getElementById('testConsoleBox');

    if (!pkg) {
      App.showToast('Vui lòng nhập tên Package ứng dụng (ví dụ: com.example.app)', 'error');
      return;
    }

    const actionLabels = {
      launch: 'Mở ứng dụng',
      stop: 'Buộc dừng ứng dụng',
      clear: 'Xóa sạch dữ liệu (Clear Data)',
      monkey: 'Chạy Monkey Stress Test (300 sự kiện)'
    };

    App.showToast(`Đang ${actionLabels[action] || action} trên các máy ảo...`);
    if (consoleBox) consoleBox.innerHTML = `<div style="color:#94a3b8;">Đang gửi lệnh ${action} cho package '${pkg}'...</div>`;

    try {
      const res = await fetch('/api/services/batch-app-action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, package: pkg })
      });
      const data = await res.json();
      if (data.success && consoleBox) {
        let html = `<div style="color:#34d399;margin-bottom:8px;font-weight:700;">✅ Hoàn tất '${actionLabels[action] || action}' trên ${data.executed_count} máy ảo:</div>`;
        for (const [idx, r] of Object.entries(data.results)) {
          const isOk = r.success;
          html += `
            <div style="margin-bottom:4px;padding:4px 8px;background:#1e293b;border-radius:4px;font-size:11.5px;">
              <span style="color:#38bdf8;font-weight:700;">Node #${idx}:</span>
              <span style="color:${isOk ? '#f8fafc' : '#f87171'}">${r.output || (isOk ? 'Thành công' : 'Lỗi')}</span>
            </div>
          `;
        }
        consoleBox.innerHTML = html;
        App.showToast('Lệnh test hoàn tất');
      } else if (consoleBox) {
        consoleBox.innerHTML = `<div style="color:#f87171;">${data.message || 'Thực thi thất bại'}</div>`;
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async deployApk(file) {
    if (!file) return;
    const consoleBox = document.getElementById('testConsoleBox');
    App.showToast(`Đang tải lên và phân phối APK '${file.name}' tới toàn bộ máy ảo...`);
    if (consoleBox) consoleBox.innerHTML = `<div style="color:#94a3b8;">Đang cài đặt ${file.name} đồng thời lên các máy đang chạy...</div>`;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/services/batch-install-apk', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.success && consoleBox) {
        let html = `<div style="color:#34d399;margin-bottom:8px;font-weight:700;">✅ Đã cài đặt APK '${data.filename}' thành công trên ${data.installed_count} máy ảo!</div>`;
        for (const [idx, r] of Object.entries(data.results)) {
          html += `
            <div style="margin-bottom:4px;padding:4px 8px;background:#1e293b;border-radius:4px;font-size:11.5px;">
              <span style="color:#38bdf8;font-weight:700;">Node #${idx}:</span>
              <span>${r.success ? 'Cài đặt hoàn tất' : (r.error || 'Thất bại')}</span>
            </div>
          `;
        }
        consoleBox.innerHTML = html;
        App.showToast(`Cài đặt APK hoàn tất trên ${data.installed_count} máy`);
      } else if (consoleBox) {
        consoleBox.innerHTML = `<div style="color:#f87171;">${data.message || 'Cài đặt thất bại'}</div>`;
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  async autoOptimizeCluster() {
    if (!confirm('Áp dụng cấu hình siêu tối ưu cho 12 máy ảo chạy test app liên tục?\n(1 vCPU, 2GB RAM, 540x960 @ 20FPS, Tắt âm thanh)')) return;
    App.showToast('Đang áp dụng thông số tối ưu cho toàn bộ máy ảo...');
    try {
      const res = await fetch('/api/instances/optimize-cluster', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cpu: 1, mem_gb: 2.0, fps: 20, resolution: 'phone.3' })
      });
      const data = await res.json();
      if (data.success) {
        App.showToast(data.message);
        setTimeout(() => InstancesModule.load(), 1500);
      } else {
        App.showToast('Áp dụng thất bại', 'error');
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  }
};
