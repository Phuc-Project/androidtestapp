// DroidTest — app shell: bootstrapping, toasts, menus, top bar

const App = {
  currentRemoteVm: "0",
  telemetryTimer: null,

  // ---------- pages ----------
  routes: {
    "": { view: "overview", title: "Tổng quan" },
    "play-console": { view: "console", title: "Play Console" },
    "lich-su": { view: "history", title: "Lịch sử" },
    "may-ao": { view: "devices", title: "Máy ảo" },
    "cong-cu": { view: "tools", title: "Công cụ" },
    "cai-dat": { view: "settings", tab: "accounts", title: "Tài khoản Google" },
    "cai-dat/chien-dich": { view: "settings", tab: "campaign", title: "Cài đặt chiến dịch" },
    "cai-dat/he-thong": { view: "settings", tab: "system", title: "Cài đặt hệ thống" },
  },

  go(path) {
    location.hash = "#/" + path;
  },

  route() {
    const path = location.hash.replace(/^#\/?/, "").replace(/\/$/, "");
    const r = this.routes[path] || this.routes[""];
    document.querySelectorAll("[data-view]").forEach((v) => (v.hidden = v.dataset.view !== r.view));
    document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === r.view));
    if (r.view === "settings") {
      document.querySelectorAll("[data-tab-panel]").forEach((p) => (p.hidden = p.dataset.tabPanel !== r.tab));
      document.querySelectorAll("[data-tab]").forEach((a) => a.classList.toggle("active", a.dataset.tab === r.tab));
      if (r.tab === "campaign") {
        CampaignModule._configFilled = false;
        CampaignModule.fillConfig();
      }
      if (r.tab === "system") this.loadSystemSettings();
    }
    if (r.view === "console") ConsoleModule.load();
    if (r.view === "history") HistoryModule.load();
    document.title = `${r.title} · DroidTest`;
    document.querySelectorAll(".menu.open").forEach((m) => m.classList.remove("open"));
    window.scrollTo(0, 0);
  },

  async loadSystemSettings() {
    try {
      const data = await (await fetch("/api/system/settings")).json();
      if (!data.success) return;
      const s = data.data;
      document.getElementById("sysMumuPath").value = s.mumu_manager_path || "";
      document.getElementById("sysAdbPath").value = s.adb_path || "";
      document.getElementById("sysPinEnabled").checked = !!s.pin_enabled;
      document.getElementById("sysPinCode").value = "";
      document.getElementById("sysPinCode").dataset.hasPin = s.has_pin ? "1" : "";
    } catch (e) {
      this.showToast("Không đọc được cài đặt hệ thống", "error");
    }
  },

  async saveSystemSettings() {
    const pinEnabled = document.getElementById("sysPinEnabled").checked;
    const pinInput = document.getElementById("sysPinCode");
    const pin = pinInput.value.trim();
    if (pinEnabled && !pin && !pinInput.dataset.hasPin) {
      this.showToast("Nhập mã PIN trước khi bật khoá", "error");
      pinInput.focus();
      return;
    }
    const body = { pin_enabled: pinEnabled };
    const mumu = document.getElementById("sysMumuPath").value.trim();
    const adb = document.getElementById("sysAdbPath").value.trim();
    if (mumu) body.mumu_manager_path = mumu;
    if (adb) body.adb_path = adb;
    if (pin) body.pin_code = pin;
    try {
      const res = await fetch("/api/system/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Không lưu được cài đặt");
      if (pinEnabled) {
        try { sessionStorage.setItem("pin_verified", "true"); } catch (e) {}
      }
      this.showToast("Đã lưu cài đặt hệ thống");
      this.loadSystemSettings();
    } catch (e) {
      this.showToast(e.message, "error");
    }
  },

  async optimizeHardware() {
    this.showToast("Đang dọn RAM, SSD và tối ưu đồ hoạ GPU...");
    try {
      const res = await fetch("/api/system/optimize-hardware", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        this.showToast(data.message);
        this.fetchTelemetry();
      } else {
        throw new Error(data.message || "Lỗi tối ưu phần cứng");
      }
    } catch (e) {
      this.showToast(e.message, "error");
    }
  },

  async cleanRamOnly() {
    this.showToast("Đang dọn sạch Working Set RAM...");
    try {
      const res = await fetch("/api/system/clean-ram", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        this.showToast(`Đã giải phóng ${data.data.ram_freed_mb} MB RAM (Hiện còn ${data.data.memory_percent}%)`);
        this.fetchTelemetry();
      }
    } catch (e) {
      this.showToast(e.message, "error");
    }
  },

  async optimizeGpuOnly() {
    this.showToast("Đang tắt animation và tối ưu GPU...");
    try {
      const res = await fetch("/api/system/optimize-gpu", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        this.showToast(data.message);
      }
    } catch (e) {
      this.showToast(e.message, "error");
    }
  },

  init() {
    window.addEventListener("hashchange", () => this.route());
    this.route();
    this.bindEvents();
    this.checkPinStatus();
    this.startTelemetryLoop();
    InstancesModule.load();
    AccountsModule.loadQuickPool();
    CampaignModule.load();
    CampaignModule.startPolling();
  },

  showToast(message, type = "success") {
    const container = document.getElementById("toastContainer");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type === "error" ? "error" : ""}`;
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    toast.textContent = message;
    container.appendChild(toast);
    while (container.children.length > 4) container.firstChild.remove();
    setTimeout(() => {
      toast.classList.add("leaving");
      setTimeout(() => toast.remove(), 260);
    }, type === "error" ? 6000 : 3800);
  },

  bindEvents() {
    const on = (id, fn) => document.getElementById(id)?.addEventListener("click", fn);
    on("btnOptimizeCluster", () => TestingModule.autoOptimizeCluster());
    on("btnStartAll", () => this.startAllVms());
    on("btnStopAll", () => this.stopAllVms());
    on("btnArrange", () => this.arrangeWindows());
    on("btnRefreshAll", () => this.refresh());
    on("btnQuitApp", () => this.quitEngine());
    on("cmpQuickBtn", () => CampaignModule.quickStart());
    document.getElementById("cmpQuickLink")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") CampaignModule.quickStart();
    });
    document.getElementById("pinForm")?.addEventListener("submit", (e) => {
      e.preventDefault();
      this.verifyPin();
    });

    // Dropdown menus (works for menus rendered later too)
    document.addEventListener("click", (e) => {
      const toggle = e.target.closest("[data-menu-toggle]");
      const openMenus = document.querySelectorAll(".menu.open");
      if (toggle) {
        const menu = toggle.closest(".menu");
        const wasOpen = menu.classList.contains("open");
        openMenus.forEach((m) => m.classList.remove("open"));
        if (!wasOpen) menu.classList.add("open");
        e.stopPropagation();
        return;
      }
      openMenus.forEach((m) => m.classList.remove("open"));
    });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      document.querySelectorAll(".menu.open").forEach((m) => m.classList.remove("open"));
      document.querySelectorAll(".modal-overlay.active").forEach((m) => {
        if (m.id === "pinOverlay") return;
        if (m.id === "modalRemote") RemoteModule.closeModal();
        else m.classList.remove("active");
      });
    });
  },

  refresh() {
    InstancesModule.load();
    AccountsModule.loadQuickPool();
    CampaignModule.load();
    this.updateTelemetry();
    this.showToast("Đã làm mới dữ liệu");
  },

  async startTelemetryLoop() {
    await this.updateTelemetry();
    this.telemetryTimer = setInterval(async () => {
      await this.updateTelemetry();
      await InstancesModule.load();
    }, 3500);
  },

  async updateTelemetry() {
    try {
      const res = await fetch("/api/system/stats");
      const data = await res.json();
      if (data.success) {
        const s = data.data;
        const cpu = document.getElementById("statCpu");
        const ram = document.getElementById("statRam");
        if (cpu) cpu.textContent = `${Math.round(s.cpu_percent)}%`;
        if (ram) {
          ram.textContent = `${Math.round(s.memory_percent)}%`;
          ram.title = `${s.memory_used_gb}/${s.memory_total_gb} GB`;
        }
      }
    } catch (e) {}
  },

  async startAllVms() {
    if (!confirm("Bật tất cả máy đang tắt? Với cấu hình tiết kiệm, nên chạy tối đa 3–4 máy cùng lúc.")) return;
    try {
      const data = await (await fetch("/api/instances")).json();
      const stopped = data.data.filter((v) => !v.is_running).map((v) => v.index);
      if (!stopped.length) return this.showToast("Tất cả máy đều đang chạy");
      await fetch("/api/instances/batch-launch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ indices: stopped }),
      });
      this.showToast(`Đang bật ${stopped.length} máy`);
      setTimeout(() => InstancesModule.load(), 2500);
    } catch (e) {
      this.showToast(e.message, "error");
    }
  },

  async stopAllVms() {
    if (!confirm("Tắt tất cả máy đang chạy?")) return;
    try {
      const data = await (await fetch("/api/instances")).json();
      const running = data.data.filter((v) => v.is_running).map((v) => v.index);
      if (!running.length) return this.showToast("Không có máy nào đang chạy");
      await fetch("/api/instances/batch-shutdown", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ indices: running }),
      });
      this.showToast(`Đang tắt ${running.length} máy`);
      setTimeout(() => InstancesModule.load(), 2000);
    } catch (e) {
      this.showToast(e.message, "error");
    }
  },

  async arrangeWindows() {
    try {
      const data = await (await fetch("/api/instances/arrange", { method: "POST" })).json();
      if (data.success) this.showToast("Đã xếp cửa sổ MuMu");
      else this.showToast(data.error || "Không xếp được cửa sổ", "error");
    } catch (e) {
      this.showToast(e.message, "error");
    }
  },

  async quitEngine() {
    if (!confirm("Dừng DroidTest và đóng ứng dụng? Các lượt test đang chạy sẽ bị huỷ.")) return;
    try {
      await fetch("/api/system/shutdown", { method: "POST" });
    } catch (e) {}
    document.body.innerHTML = `
      <div style="min-height:100vh;display:grid;place-items:center;font-family:var(--font);color:var(--ink);text-align:center;">
        <div><h2 style="font-size:18px;font-weight:600;">DroidTest đã dừng</h2>
        <p style="color:var(--muted);margin-top:4px;">Bạn có thể đóng cửa sổ này.</p></div>
      </div>`;
    setTimeout(() => window.close(), 1500);
  },

  async checkPinStatus() {
    try {
      const data = await (await fetch("/api/system/settings")).json();
      if (data.success && data.data?.pin_enabled && sessionStorage.getItem("pin_verified") !== "true") {
        document.getElementById("pinOverlay")?.classList.add("active");
      }
    } catch (e) {}
  },

  async verifyPin() {
    const input = document.getElementById("inputPin");
    try {
      const res = await fetch("/api/system/verify-pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin: input ? input.value : "" }),
      });
      const data = await res.json();
      if (data.success) {
        try { sessionStorage.setItem("pin_verified", "true"); } catch (e) {}
        document.getElementById("pinOverlay")?.classList.remove("active");
      } else {
        this.showToast("Mã PIN không đúng", "error");
        if (input) input.value = "";
      }
    } catch (e) {
      this.showToast("Không xác thực được mã PIN", "error");
    }
  },
};

document.addEventListener("DOMContentLoaded", () => App.init());
