// DroidTest — quick tools for running devices

const TestingModule = {
  labels: {
    launch: "Mở app",
    stop: "Buộc dừng",
    clear: "Xoá dữ liệu",
    monkey: "Monkey 300 thao tác",
  },

  showResults(title, results, okText) {
    const box = document.getElementById("testConsoleBox");
    const wrap = document.getElementById("testConsoleContainer");
    if (!box || !wrap) return;
    wrap.hidden = false;
    const rows = Object.entries(results || {}).map(([idx, r]) => {
      const ok = !!r.success;
      const out = ok ? okText : (r.error || r.output || "Không thành công");
      return `<div class="r-row"><span class="dot ${ok ? "ok" : "bad"}"></span><span class="mono">#${this.esc(idx)}</span><span class="out" title="${this.esc(r.output || "")}">${this.esc(out)}</span></div>`;
    }).join("");
    box.innerHTML = `<div class="r-head">${this.esc(title)}</div>${rows}`;
  },

  showMessage(text) {
    const box = document.getElementById("testConsoleBox");
    const wrap = document.getElementById("testConsoleContainer");
    if (!box || !wrap) return;
    wrap.hidden = false;
    box.innerHTML = `<div class="r-head">${this.esc(text)}</div>`;
  },

  async runBatchAction(action) {
    const input = document.getElementById("testTargetPackage");
    const pkg = (input?.value || "").trim();
    if (!pkg) {
      App.showToast("Nhập package của app, ví dụ com.congty.app", "error");
      input?.focus();
      return;
    }
    const label = this.labels[action] || action;
    this.showMessage(`${label}: đang gửi lệnh tới các máy đang chạy…`);
    try {
      const res = await fetch("/api/services/batch-app-action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, package: pkg }),
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.message || "Không có máy nào đang chạy");
      this.showResults(`${label} · ${data.executed_count} máy`, data.results, "Xong");
      App.showToast(`${label}: xong trên ${data.executed_count} máy`);
    } catch (e) {
      this.showMessage(e.message);
      App.showToast(e.message, "error");
    }
  },

  async deployApk(file) {
    if (!file) return;
    this.showMessage(`Đang cài ${file.name} lên các máy đang chạy…`);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch("/api/services/batch-install-apk", { method: "POST", body: form });
      const data = await res.json();
      if (!data.success) throw new Error(data.message || "Không có máy nào đang chạy");
      this.showResults(`Cài ${data.filename} · ${data.installed_count} máy`, data.results, "Đã cài");
      App.showToast(`Đã cài ${data.filename} trên ${data.installed_count} máy`);
    } catch (e) {
      this.showMessage(e.message);
      App.showToast(e.message, "error");
    }
  },

  async autoOptimizeCluster() {
    if (!confirm("Áp cấu hình tiết kiệm cho tất cả máy?\n2 vCPU · 2 GB RAM · 540×960 · 15 FPS · GPU thấp · tắt âm thanh.\nMáy đang chạy sẽ áp dụng sau khi khởi động lại.")) return;
    try {
      const res = await fetch("/api/instances/optimize-cluster", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (!data.success) throw new Error("Không áp được cấu hình. Kiểm tra MuMuPlayer.");
      App.showToast("Đã áp cấu hình tiết kiệm cho tất cả máy");
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  esc(str) {
    return String(str ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[m]);
  },
};
