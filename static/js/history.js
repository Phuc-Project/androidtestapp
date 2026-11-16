// DroidTest — history: test sessions and system log

const HistoryModule = {
  tab: "sessions",
  sessions: [],
  logs: [],

  statusLabel: {
    success: ["ok", "Thành công"],
    failed: ["bad", "Lỗi"],
    no_account: ["warn", "Chưa đăng nhập"],
    not_installed: ["warn", "Chưa cài app"],
    stopped: ["", "Đã dừng"],
  },

  async load() {
    try {
      if (this.tab === "sessions") {
        this.sessions = CampaignModule.campaign
          ? (await CampaignModule.api("/api/campaign/sessions?limit=2000")).data : [];
        this.fillVmFilter();
      } else {
        this.logs = (await (await fetch("/api/system/logs?limit=400")).json()).data || [];
      }
      this.render();
    } catch (e) {
      document.getElementById("historyBody").innerHTML = `<div class="empty"><h3>Không tải được dữ liệu</h3><p>${this.esc(e.message)}</p></div>`;
    }
  },

  setTab(tab) {
    this.tab = tab;
    document.querySelectorAll("[data-history-tab]").forEach((b) => b.classList.toggle("active", b.dataset.historyTab === tab));
    document.getElementById("historyFilters").hidden = tab !== "sessions";
    this.load();
  },

  fillVmFilter() {
    const sel = document.getElementById("hfVm");
    if (!sel) return;
    const current = sel.value;
    const vms = [...new Set(this.sessions.map((s) => s.vm_index))].sort((a, b) => Number(a) - Number(b));
    sel.innerHTML = `<option value="">Tất cả máy</option>` +
      vms.map((v) => `<option value="${this.esc(v)}" ${v === current ? "selected" : ""}>Máy #${this.esc(v)}</option>`).join("");
  },

  render() {
    const body = document.getElementById("historyBody");
    const count = document.getElementById("hfCount");
    if (!body) return;
    if (this.tab === "logs") return this.renderLogs(body);

    const vm = document.getElementById("hfVm")?.value || "";
    const st = document.getElementById("hfStatus")?.value || "";
    const day = document.getElementById("hfDate")?.value || "";
    const rows = this.sessions.filter((s) => (!vm || s.vm_index === vm) && (!st || s.status === st) && (!day || s.run_date === day));
    if (count) count.textContent = `${rows.length} phiên`;
    if (!rows.length) {
      body.innerHTML = `<div class="empty"><h3>Chưa có phiên nào</h3><p>${this.sessions.length ? "Không có phiên khớp bộ lọc." : "Phiên test sẽ xuất hiện ở đây sau lượt chạy đầu tiên."}</p></div>`;
      return;
    }
    const dur = (s) => `${Math.floor(s.duration_sec / 60)}p${String(s.duration_sec % 60).padStart(2, "0")}s`;
    body.innerHTML = `
      <table class="dtable">
        <thead><tr><th>Ngày</th><th>Máy</th><th>Tài khoản</th><th>Bắt đầu</th><th>Thời lượng</th><th>Phiên bản</th><th>Crash / ANR</th><th>Kết quả</th><th>Ghi chú</th></tr></thead>
        <tbody>${rows.map((s) => {
          const [cls, label] = this.statusLabel[s.status] || ["", s.status];
          return `
            <tr>
              <td class="num">${CampaignModule.fmtDate(s.run_date)}</td>
              <td class="num" data-label="Máy">#${this.esc(s.vm_index)}</td>
              <td data-label="Tài khoản"><span class="d-email">${this.esc(s.account_email)}</span></td>
              <td class="num" data-label="Bắt đầu">${this.esc((s.started_at || "").slice(11, 16))}</td>
              <td class="num" data-label="Thời lượng">${dur(s)}</td>
              <td class="num" data-label="Phiên bản">${s.version_name ? "v" + this.esc(s.version_name) : "—"}</td>
              <td class="num" data-label="Crash / ANR">${s.crashes} / ${s.anrs}</td>
              <td data-label="Kết quả"><span class="d-state"><span class="dot ${cls}"></span>${label}</span></td>
              <td class="wrap" data-label="Ghi chú">${this.esc(s.message)}</td>
            </tr>`;
        }).join("")}</tbody>
      </table>`;
  },

  renderLogs(body) {
    if (!this.logs.length) {
      body.innerHTML = `<div class="empty"><h3>Nhật ký trống</h3><p>Hoạt động của hệ thống sẽ được ghi lại ở đây.</p></div>`;
      return;
    }
    const level = { SUCCESS: "Thành công", INFO: "Thông tin", WARNING: "Cảnh báo", ERROR: "Lỗi" };
    body.innerHTML = `
      <table class="dtable">
        <thead><tr><th>Thời gian</th><th>Mức</th><th>Nguồn</th><th>Nội dung</th></tr></thead>
        <tbody>${this.logs.map((l) => `
          <tr>
            <td class="num">${this.esc(l.timestamp)}</td>
            <td data-label="Mức" class="lv-${this.esc(l.level)}">${level[l.level] || this.esc(l.level)}</td>
            <td class="num" data-label="Nguồn">${this.esc(l.source)}</td>
            <td class="wrap" data-label="Nội dung">${this.esc(l.message)}</td>
          </tr>`).join("")}</tbody>
      </table>`;
  },

  esc(str) {
    return String(str ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[m]);
  },
};
