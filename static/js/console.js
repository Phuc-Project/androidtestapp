// DroidTest — Play Console page: link to the developer's console, publishing checklist, testing figures

const ConsoleModule = {
  groups: [],
  consoleUrl: "",
  summary: null,

  titles: {
    setup: ["Thiết lập ứng dụng", "Bảng điều khiển → Thiết lập ứng dụng"],
    closed: ["Kiểm thử kín", "Kiểm thử → Kiểm thử kín"],
    production: ["Phát hành chính thức", "Bảng điều khiển → Phát hành chính thức"],
  },

  async load() {
    const body = document.getElementById("consoleBody");
    if (!body) return;
    if (!CampaignModule.campaign) {
      body.innerHTML = `
        <div class="card empty">
          <h3>Chưa có chiến dịch</h3>
          <p>Dán link test của app ở trang Tổng quan, sau đó quay lại đây để theo dõi các bước trên Play Console.</p>
          <a class="btn btn-primary" href="#/">Về Tổng quan</a>
        </div>`;
      this.setOpenButton("");
      return;
    }
    try {
      const [cl, sm] = await Promise.all([
        CampaignModule.api("/api/campaign/checklist"),
        CampaignModule.api("/api/campaign/summary"),
      ]);
      this.groups = cl.groups;
      this.consoleUrl = cl.console_url || "";
      this.summary = sm.data;
      this.render();
    } catch (e) {
      body.innerHTML = `<div class="card"><p class="hint" style="margin:0">${this.esc(e.message)}</p></div>`;
    }
  },

  setOpenButton(url) {
    const btn = document.getElementById("consoleOpenBtn");
    if (!btn) return;
    btn.hidden = !url;
    if (url) btn.href = url;
  },

  counts() {
    const all = this.groups.flatMap((g) => g.items);
    return { done: all.filter((i) => i.done).length, total: all.length };
  },

  render() {
    const body = document.getElementById("consoleBody");
    if (!body) return;
    this.setOpenButton(this.consoleUrl);
    const { done, total } = this.counts();
    const nav = document.getElementById("navConsoleCount");
    if (nav) nav.textContent = `${done}/${total}`;
    const sm = this.summary || {};
    const rs = CampaignModule.report?.summary || {};

    const fact = (label, value, note) => `
      <div class="kpi">
        <span class="kpi-label">${label}</span>
        <span class="kpi-value">${value}</span>
        <span class="kpi-note">${note}</span>
      </div>`;

    const group = (g, extra = "") => {
      const [title, path] = this.titles[g.group] || [g.group, ""];
      const n = g.items.filter((i) => i.done).length;
      const pct = Math.round((n / g.items.length) * 100);
      return `
        <div class="cl-group">
          <div class="cl-head">
            <div class="cl-head-row"><h3>${title}</h3><span class="num">${n}/${g.items.length}</span></div>
            <small class="hint" style="margin:2px 0 0;display:block">${path}</small>
            <div class="kpi-bar ${n < g.items.length ? "warn" : ""}"><i style="width:${pct}%"></i></div>
          </div>
          ${g.items.map((i) => `
            <label class="cl-item ${i.done ? "done" : ""}">
              <input type="checkbox" ${i.done ? "checked" : ""} onchange="ConsoleModule.toggle('${i.key}', this.checked)">
              <span>
                <b>${this.esc(i.label)}</b>
                ${i.hint && !i.done ? `<small>${this.esc(i.hint)}</small>` : ""}
                ${i.done && i.done_at ? `<small class="when">Xong ${this.esc(i.done_at.slice(0, 16))}</small>` : ""}
              </span>
            </label>`).join("")}
          ${extra}
        </div>`;
    };

    const auto = (ok, title, note) => `
      <div class="cl-auto">
        <span class="sq ${ok ? "ok" : ""}"></span>
        <span><b>${title}</b><small>${note}</small></span>
      </div>`;
    const testers = rs.target_testers || 12;
    const days = rs.target_days || 14;
    const autoRows = `
      <div class="cl-sub">DroidTest tự theo dõi</div>
      ${auto((rs.opted_in || 0) >= testers, `${testers} tester đã tham gia`, `Hiện có ${rs.opted_in || 0}/${testers}. <a href="#/cai-dat">Quản lý tài khoản</a>`)}
      ${auto(rs.eligible, `${days} ngày test liên tục`, `Đang ở ngày ${Math.max(0, rs.day_index || 0)}/${days}. <a href="#/">Xem lịch test</a>`)}`;

    const byKey = Object.fromEntries(this.groups.map((g) => [g.group, g]));
    body.innerHTML = `
      <div class="card">
        <div class="card-head" style="margin-bottom:8px">
          <div>
            <h3>Liên kết Play Console</h3>
            <p class="card-sub">Mở app trong Play Console, copy địa chỉ trên thanh trình duyệt và dán vào đây để mở nhanh.</p>
          </div>
        </div>
        <form class="url-bar" onsubmit="event.preventDefault(); ConsoleModule.saveUrl();">
          <input type="url" id="consoleUrlInput" class="input mono" value="${this.esc(this.consoleUrl)}"
            placeholder="https://play.google.com/console/u/0/developers/…/app/…/app-dashboard">
          <button class="btn btn-secondary" type="submit">Lưu liên kết</button>
        </form>
      </div>

      <div class="card-head" style="margin:16px 0 8px">
        <div>
          <h3>Số liệu kiểm thử</h3>
          <p class="card-sub">Ghi nhận từ các phiên test thật trên máy ảo. Dùng khi trả lời phần câu hỏi về quá trình kiểm thử trong đơn xin phát hành.</p>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="ConsoleModule.copySummary()">Sao chép số liệu</button>
      </div>
      <div class="strip six">
        ${fact("Tester tham gia", `${sm.opted_in ?? 0}<small>/${sm.testers ?? 0}</small>`, "Tài khoản đã cài app từ Play")}
        ${fact("Ngày có hoạt động", `${sm.days_with_activity ?? 0}`, `Ít nhất ${sm.min_days_per_tester ?? 0} ngày mỗi tester`)}
        ${fact("Phiên thành công", `${sm.sessions_ok ?? 0}`, `${sm.sessions_failed ?? 0} phiên lỗi`)}
        ${fact("Thời gian dùng app", `${sm.total_minutes ?? 0}<small> phút</small>`, "Cộng dồn mọi phiên")}
        ${fact("Crash / ANR", `${sm.crashes ?? 0}<small> / ${sm.anrs ?? 0}</small>`, "Ghi nhận trong lúc dùng app")}
        ${fact("Phiên bản đã test", `${(sm.versions || []).length}`, (sm.versions || []).slice(-3).map((v) => "v" + this.esc(v)).join(", ") || "Chưa có")}
      </div>

      <div class="card-head" style="margin:16px 0 0">
        <div>
          <h3>Các bước trên Play Console</h3>
          <p class="card-sub">Đánh dấu khi đã làm xong trên Play Console. Đã xong ${done}/${total} việc.</p>
        </div>
      </div>
      <div class="cl-groups">
        ${byKey.setup ? group(byKey.setup) : ""}
        ${byKey.closed ? group(byKey.closed, autoRows) : ""}
        ${byKey.production ? group(byKey.production) : ""}
      </div>`;
  },

  async toggle(key, done) {
    try {
      await CampaignModule.api("/api/campaign/checklist", { method: "POST", body: { item: key, done } });
      const item = this.groups.flatMap((g) => g.items).find((i) => i.key === key);
      if (item) {
        item.done = done;
        item.done_at = done ? new Date().toISOString().replace("T", " ") : "";
      }
      this.render();
    } catch (e) {
      App.showToast(e.message, "error");
      this.load();
    }
  },

  async saveUrl() {
    const url = (document.getElementById("consoleUrlInput")?.value || "").trim();
    const c = CampaignModule.campaign;
    if (!c) return;
    const keep = ["app_name", "package_name", "optin_url", "start_date", "target_days", "target_testers",
      "session_minutes", "events_per_min", "max_parallel", "auto_run_time", "shutdown_after", "status", "notes"];
    const body = Object.fromEntries(keep.map((k) => [k, c[k]]));
    body.console_url = url;
    try {
      await CampaignModule.api("/api/campaign", { method: "POST", body });
      App.showToast(url ? "Đã lưu liên kết Play Console" : "Đã xoá liên kết Play Console");
      await CampaignModule.load();
      await this.load();
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  copySummary() {
    const s = this.summary;
    if (!s) return;
    const lines = [
      `Ứng dụng: ${s.package_name}`,
      `Bắt đầu kiểm thử kín: ${CampaignModule.fmtDate(s.start_date)} (ngày thứ ${Math.max(0, s.day_index)})`,
      `Số tester đã tham gia: ${s.opted_in}/${s.testers}`,
      `Số ngày có hoạt động: ${s.days_with_activity}; mỗi tester ít nhất ${s.min_days_per_tester} ngày`,
      `Phiên sử dụng thành công: ${s.sessions_ok}, tổng ${s.total_minutes} phút`,
      `Crash: ${s.crashes}, ANR: ${s.anrs}`,
      `Phiên bản đã kiểm thử: ${(s.versions || []).map((v) => "v" + v).join(", ") || "chưa có"}`,
    ].join("\n");
    navigator.clipboard?.writeText(lines).then(
      () => App.showToast("Đã sao chép số liệu kiểm thử"),
      () => prompt("Số liệu kiểm thử:", lines),
    );
  },

  esc(str) {
    return String(str ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[m]);
  },
};
