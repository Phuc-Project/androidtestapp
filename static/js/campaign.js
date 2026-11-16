// DroidTest — closed-test campaign: overview, 12 x 14 schedule, daily runs

const CampaignModule = {
  campaign: null,
  report: null,
  job: null,
  testerMap: {},
  _timer: null,
  _tick: 0,
  _busy: false,
  _showQuick: false,

  // ---------- data ----------
  async api(url, options = {}) {
    const opts = { ...options };
    if (opts.body && typeof opts.body !== "string") {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(url, opts);
    let data = {};
    try {
      data = await res.json();
    } catch (e) {}
    if (!res.ok || data.success === false) {
      throw new Error(
        data.detail ||
          data.message ||
          data.error ||
          `Máy chủ trả lỗi ${res.status}`,
      );
    }
    return data;
  },

  async load() {
    try {
      const data = await this.api("/api/campaign");
      this.campaign = data.campaign;
      this.report = data.report;
      this.job = data.job;
      this.testerMap = {};
      (this.report?.rows || []).forEach(
        (r) => (this.testerMap[r.vm_index] = r),
      );
      this._loaded = true;
      // Settings form opened before data arrived: fill it once (never overwrite while the user edits)
      if (location.hash.includes("chien-dich") && !this._configFilled)
        this.fillConfig();
      // Pages opened directly by URL before campaign data was available
      if (
        location.hash.startsWith("#/play-console") &&
        !ConsoleModule.groups.length &&
        this.campaign
      )
        ConsoleModule.load();
      if (
        location.hash.startsWith("#/lich-su") &&
        HistoryModule.tab === "sessions" &&
        !HistoryModule.sessions.length &&
        this.campaign
      )
        HistoryModule.load();
      this.render();
      const pkgInput = document.getElementById("testTargetPackage");
      if (pkgInput && !pkgInput.value && this.campaign)
        pkgInput.value = this.campaign.package_name;
      if (
        typeof InstancesModule !== "undefined" &&
        InstancesModule.vms.length
      ) {
        InstancesModule._lastRenderHash = "";
        InstancesModule.render();
      }
    } catch (e) {
      const body = document.getElementById("overviewBody");
      if (body)
        body.innerHTML = `<div class="card"><p class="hint" style="margin:0">Không tải được dữ liệu chiến dịch: ${this.esc(e.message)}</p></div>`;
    }
  },

  startPolling() {
    if (this._timer) return;
    this._timer = setInterval(async () => {
      this._tick++;
      if (this.job?.running) {
        try {
          const d = await this.api("/api/campaign/job");
          this.job = d.job;
          this.renderJob();
          this.renderHeader();
          if (!this.job.running) this.load();
        } catch (e) {}
      } else if (this._tick % 5 === 0) {
        this.load();
      }
    }, 3000);
  },

  // ---------- actions ----------
  async withBusy(fn) {
    if (this._busy) return;
    this._busy = true;
    try {
      await fn();
    } catch (e) {
      App.showToast(e.message, "error");
    } finally {
      this._busy = false;
    }
  },

  run(force = false) {
    if (
      force &&
      !confirm("Chạy lại cho tất cả tester, kể cả máy đã test xong hôm nay?")
    )
      return;
    return this.withBusy(async () => {
      const d = await this.api("/api/campaign/run", {
        method: "POST",
        body: { force },
      });
      App.showToast(d.message);
      await this.load();
    });
  },

  runOne(index) {
    return this.withBusy(async () => {
      const d = await this.api("/api/campaign/run", {
        method: "POST",
        body: { force: true, indices: [String(index)] },
      });
      App.showToast(`Đang chạy test cho máy #${index}`);
      await this.load();
    });
  },

  stop() {
    return this.withBusy(async () => {
      const d = await this.api("/api/campaign/stop", { method: "POST" });
      App.showToast(d.message);
    });
  },

  openOptin() {
    return this.withBusy(async () => {
      const d = await this.api("/api/campaign/open-optin", {
        method: "POST",
        body: {},
      });
      App.showToast(
        `${d.message}. Bấm “Trở thành người thử nghiệm” trong màn hình của từng máy.`,
      );
    });
  },

  openStore() {
    return this.withBusy(async () => {
      const d = await this.api("/api/campaign/open-store", {
        method: "POST",
        body: {},
      });
      App.showToast(`${d.message}. Bấm “Cài đặt” trong màn hình của từng máy.`);
    });
  },

  checkInstall() {
    return this.withBusy(async () => {
      const d = await this.api("/api/campaign/check-install", {
        method: "POST",
        body: {},
      });
      App.showToast(d.message);
      await this.load();
    });
  },

  async toggleOptin(index, checked) {
    try {
      await this.api(`/api/campaign/testers/${index}/optin`, {
        method: "POST",
        body: { opted_in: checked },
      });
      await this.load();
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  copyOptin() {
    const url = this.campaign?.optin_url_effective;
    if (!url) return;
    navigator.clipboard?.writeText(url).then(
      () => App.showToast("Đã sao chép link tham gia test"),
      () => prompt("Link tham gia test:", url),
    );
  },

  toggleQuickStart(show) {
    this._showQuick = show ?? !this._showQuick;
    this.renderQuick();
    if (this._showQuick) document.getElementById("cmpQuickLink")?.focus();
  },

  async quickStart() {
    const input = document.getElementById("cmpQuickLink");
    const link = (input?.value || "").trim();
    const profile = document.getElementById("cmpQuickProfile")?.value || "light";
    const autoTime = document.getElementById("cmpQuickTime")?.value || "09:00";
    if (!link) {
      App.showToast("Dán link tham gia test hoặc package name vào ô trước", "error");
      input?.focus();
      return;
    }
    if (this.job?.running) {
      App.showToast(
        "Đang có lượt test chạy. Dừng lượt đó trước khi đổi app.",
        "error",
      );
      return;
    }
    if (
      this.campaign &&
      !link.includes(this.campaign.package_name) &&
      !confirm(
        `Chuyển sang test app mới? Chiến dịch ${this.campaign.package_name} sẽ kết thúc, dữ liệu cũ vẫn được giữ.`,
      )
    )
      return;
    const btn = document.getElementById("cmpQuickBtn");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Đang bắt đầu…";
    }
    try {
      const d = await this.api("/api/campaign/quick-start", {
        method: "POST",
        body: { link, app_profile: profile, auto_run_time: autoTime },
      });
      App.showToast(d.message);
      if (input) input.value = "";
      this._showQuick = false;
      await this.load();
    } catch (e) {
      App.showToast(e.message, "error");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Bắt đầu chiến dịch test";
      }
    }
  },

  onProfileChange(val) {
    const p = document.getElementById("cmpParallel");
    if (!p) return;
    if (val === "heavy") p.value = "2";
    else if (val === "light") p.value = "4";
  },

  // ---------- settings page ----------
  openConfig() {
    App.go("cai-dat/chien-dich");
  },

  fillConfig() {
    this._configFilled = !!this._loaded;
    const c = this.campaign || {};
    const sub = document.getElementById("cmpSettingsSub");
    if (sub)
      sub.textContent = this.campaign
        ? `Đang test ${c.package_name} từ ${this.fmtDate(c.start_date)}.`
        : "Chưa có chiến dịch. Cách nhanh nhất là dán link test ở trang Tổng quan.";
    const now = new Date();
    const iso = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 10);
    const set = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.value = v;
    };
    set("cmpAppName", c.app_name || "");
    set("cmpPackage", c.package_name || "");
    set("cmpOptinUrl", c.optin_url || "");
    set("cmpStartDate", c.start_date || iso);
    set("cmpTargetTesters", c.target_testers ?? 12);
    set("cmpTargetDays", c.target_days ?? 14);
    set("cmpMinutes", c.session_minutes ?? 3);
    set("cmpEvents", c.events_per_min ?? 30);
    const prof = c.app_profile || (c.max_parallel <= 2 ? "heavy" : (c.max_parallel === 4 ? "light" : "custom"));
    set("cmpAppProfile", prof);
    set("cmpParallel", c.max_parallel ?? (prof === "heavy" ? 2 : 4));
    set("cmpAutoTime", c.auto_run_time ?? "09:00");
    set("cmpStatus", c.status || "active");
    const sd = document.getElementById("cmpShutdownAfter");
    if (sd) sd.checked = c.shutdown_after ?? true;
    const archiveBtn = document.getElementById("cmpArchiveBtn");
    if (archiveBtn)
      archiveBtn.style.visibility = this.campaign ? "visible" : "hidden";
  },

  closeConfig() {
    App.go("");
  },

  async saveConfig() {
    const v = (id) => (document.getElementById(id)?.value || "").trim();
    const prof = v("cmpAppProfile") || "light";
    let par = parseInt(v("cmpParallel") || "4", 10);
    if (prof === "heavy" && par > 2) par = 2;
    if (prof === "light" && (par < 3 || par > 4)) par = 4;

    const body = {
      app_name: v("cmpAppName"),
      package_name: v("cmpPackage"),
      optin_url: v("cmpOptinUrl"),
      start_date: v("cmpStartDate"),
      target_testers: parseInt(v("cmpTargetTesters") || "12", 10),
      target_days: parseInt(v("cmpTargetDays") || "14", 10),
      session_minutes: parseInt(v("cmpMinutes") || "3", 10),
      events_per_min: parseInt(v("cmpEvents") || "0", 10),
      app_profile: prof,
      max_parallel: par,
      auto_run_time: v("cmpAutoTime"),
      shutdown_after: !!document.getElementById("cmpShutdownAfter")?.checked,
      status: v("cmpStatus") || "active",
    };
    if (!body.package_name) {
      App.showToast("Nhập package của app, ví dụ com.congty.app", "error");
      return;
    }
    try {
      await this.api("/api/campaign", { method: "POST", body });
      App.showToast("Đã lưu cài đặt chiến dịch");
      await this.load();
      this.fillConfig();
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  async archive() {
    if (
      !confirm(
        "Kết thúc chiến dịch hiện tại? Dữ liệu vẫn được giữ, lịch test sẽ bắt đầu lại với app mới.",
      )
    )
      return;
    try {
      await this.api("/api/campaign/archive", { method: "POST" });
      App.showToast("Đã kết thúc chiến dịch");
      this.closeConfig();
      await this.load();
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  // ---------- rendering ----------
  render() {
    this.renderHeader();
    this.renderQuick();
    this.renderBody();
    this.renderJob();
  },

  renderQuick() {
    const q = document.getElementById("quickStart");
    if (!q) return;
    q.hidden = !(this._showQuick || !this.campaign);
    // Chưa có chiến dịch: giới thiệu + checklist trước, form bắt đầu ở dưới.
    // Đã có chiến dịch ("Test app khác"): form nằm ngay dưới tiêu đề.
    const body = document.getElementById("overviewBody");
    if (body) {
      if (!this.campaign) body.after(q);
      else body.before(q);
    }
  },

  renderHeader() {
    const el = document.getElementById("overviewHeader");
    if (!el) return;
    const c = this.campaign;
    if (!c) {
      el.innerHTML = "";
      return;
    }
    const running = this.job?.running;
    const status = running
      ? `<span class="badge ok live">Đang chạy test</span>`
      : c.status === "active"
        ? `<span class="badge idle">Chờ lượt kế tiếp</span>`
        : `<span class="badge warn">Tạm dừng</span>`;
    const schedule = c.auto_run_time
      ? `Tự chạy ${this.esc(c.auto_run_time)} hằng ngày`
      : "Chưa hẹn giờ tự chạy";
    el.innerHTML = `
      <div class="ov-head">
        <div class="ov-title">
          <span class="eyebrow">Kiểm thử kín · Google Play</span>
          <h1>${this.esc(c.app_name || c.package_name)} ${status}</h1>
          <div class="ov-meta">
            <span class="mono">${this.esc(c.package_name)}</span>
            <span>Bắt đầu ${this.fmtDate(c.start_date)}</span>
            <span>${schedule}</span>
            <span class="badge idle">${c.app_profile === 'heavy' ? 'Cụm 2 máy (App nặng)' : 'Cụm 4 máy (App nhẹ)'}</span>
            <span>${c.session_minutes} phút/máy</span>
            <button class="link-btn" onclick="CampaignModule.copyOptin()">Sao chép link tham gia</button>
          </div>
        </div>
        <div class="ov-actions">
          <button class="btn btn-secondary" onclick="CampaignModule.toggleQuickStart()">Test app khác</button>
          <div class="menu">
            <button class="btn btn-secondary" data-menu-toggle aria-haspopup="true">
              Thao tác
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
            <div class="menu-list menu-right" role="menu">
              <button role="menuitem" onclick="CampaignModule.openConfig()">Cài đặt chiến dịch</button>
              <button role="menuitem" onclick="location.href='/api/campaign/report.csv'">Xuất báo cáo CSV</button>
              <div class="menu-sep"></div>
              <button role="menuitem" onclick="CampaignModule.run(true)" ${running || c.status !== "active" ? "disabled" : ""}>Chạy lại cả máy đã xong hôm nay</button>
            </div>
          </div>
          ${
            running
              ? `<button class="btn btn-danger" onclick="CampaignModule.stop()">Dừng lượt test</button>`
              : `<button class="btn btn-primary" onclick="CampaignModule.run(false)" ${c.status !== "active" ? "disabled" : ""}>Chạy test hôm nay</button>`
          }
        </div>
      </div>`;
  },

  renderBody() {
    const body = document.getElementById("overviewBody");
    if (!body) return;
    if (!this.campaign) {
      body.innerHTML = this.onboardingHtml();
      return;
    }
    const s = this.report.summary;
    body.innerHTML = `
      ${this.stripHtml()}
      <div class="card matrix-card">
        <div class="card-head">
          <h3>Lịch test ${s.target_days} ngày</h3>
          <div class="legend">
            <span><i class="cell ok"></i>Đã test</span>
            <span><i class="cell pending"></i>Chưa test hôm nay</span>
            <span><i class="cell failed"></i>Lỗi</span>
            <span><i class="cell missed"></i>Bỏ lỡ</span>
          </div>
        </div>
        <div class="matrix-wrap">${this.matrixHtml()}</div>
        <div class="manual-bar">
          <span>Làm tay trên máy đang bật:</span>
          <button class="btn btn-ghost btn-sm" onclick="CampaignModule.openOptin()">Mở link tham gia</button>
          <button class="btn btn-ghost btn-sm" onclick="CampaignModule.openStore()">Mở Play Store</button>
          <button class="btn btn-ghost btn-sm" onclick="CampaignModule.checkInstall()">Kiểm tra cài đặt</button>
        </div>
      </div>`;
  },

  stripHtml() {
    const c = this.campaign;
    const s = this.report.summary;
    const day = s.day_index;
    const shown = Math.max(0, Math.min(day, s.target_days));
    const track = Array.from(
      { length: s.target_days },
      (_, i) =>
        `<i class="${i + 1 < day ? "past" : i + 1 === day ? "now" : ""}"></i>`,
    ).join("");
    const end = new Date(c.start_date + "T00:00:00");
    end.setDate(end.getDate() + s.target_days);
    const endStr = `${String(end.getDate()).padStart(2, "0")}/${String(end.getMonth() + 1).padStart(2, "0")}`;
    const kpi = (label, n, total, note) => {
      const pct = total ? Math.min(100, Math.round((n / total) * 100)) : 0;
      return `
        <div class="kpi">
          <span class="kpi-label">${label}</span>
          <span class="kpi-value">${n}<small>/${total}</small></span>
          <div class="kpi-bar ${n < total ? "warn" : ""}"><i style="width:${pct}%"></i></div>
          <span class="kpi-note">${note}</span>
        </div>`;
    };
    const missingAcc = Math.max(0, s.target_testers - s.testers);
    return `
      <div class="strip">
        <div class="kpi">
          <span class="kpi-label">Tiến độ</span>
          <span class="day-big">${day <= 0 ? "--" : String(shown).padStart(2, "0")}<small>/${s.target_days} ngày</small></span>
          <div class="day-track" style="grid-template-columns:repeat(${s.target_days},1fr)">${track}</div>
          <span class="kpi-note">${day <= 0 ? `Bắt đầu ${this.fmtDate(c.start_date)}` : s.days_left > 0 ? `Còn ${s.days_left} ngày · sớm nhất ${endStr}` : "Đã đủ số ngày"}</span>
        </div>
        ${kpi("Máy có tài khoản", s.testers, s.target_testers, missingAcc ? `Thiếu ${missingAcc} tài khoản` : "Đủ tài khoản")}
        ${kpi("Đã tham gia test", s.opted_in, s.target_testers, "Tự xác nhận khi đã cài app")}
        ${kpi("Đã cài app", s.installed, Math.max(s.testers, 1), "Cài từ Play Store")}
        ${kpi("Đã test hôm nay", s.today_ok, Math.max(s.testers, 1), s.missed_total ? `${s.missed_total} lượt bỏ lỡ trước đây` : "Chưa bỏ lỡ ngày nào")}
        <div class="kpi ${s.eligible ? "good" : ""}">
          <span class="kpi-label">Phát hành chính thức</span>
          <span class="kpi-value" style="font-family:var(--font);font-size:17px;letter-spacing:-.3px">${s.eligible ? "Đủ điều kiện" : "Chưa đủ"}</span>
          <span class="kpi-note">${
            s.eligible
              ? `<a href="#/play-console">Gửi đơn trên Play Console</a>`
              : `Cần ${s.target_testers} tester × ${s.target_days} ngày · <a href="#/play-console">Xem các bước</a>`
          }</span>
        </div>
      </div>`;
  },

  matrixHtml() {
    const rep = this.report;
    const today = rep.today;
    const label = {
      ok: "đã test",
      missed: "bỏ lỡ",
      failed: "lỗi",
      pending: "chưa test",
      future: "",
      none: "",
    };
    const rows = rep.rows.filter((r) => r.vm_exists || r.is_tester);
    if (!rows.length) {
      return `<div class="empty"><h3>Chưa có máy nào</h3><p>Tạo máy ảo ở mục bên dưới, mỗi máy là một tester.</p></div>`;
    }
    const head = rep.days
      .map(
        (d, i) =>
          `<th class="mx-cell ${d === today ? "today" : ""}" title="${this.fmtDate(d)}">${String(i + 1).padStart(2, "0")}</th>`,
      )
      .join("");
    const body = rows
      .map((r) => {
        const cells = rep.days
          .map((d) => {
            const st = r.matrix[d] || "none";
            const tip = label[st]
              ? `${this.fmtDate(d)}: ${label[st]}`
              : this.fmtDate(d);
            return `<td class="mx-cell ${d === today ? "today" : ""}"><i class="cell ${st}" title="${tip}"></i></td>`;
          })
          .join("");
        const last = r.last_session;
        const tip = last
          ? `Lần gần nhất ${last.run_date}: ${last.message}`
          : "Chưa có phiên test";
        return `
        <tr class="${r.is_tester ? "" : "dim"}" title="${this.esc(tip)}">
          <td class="mx-who">
            <b>${r.is_tester ? this.esc(r.email) : "Chưa có tài khoản"}</b>
            <span>#${this.esc(r.vm_index)} · ${this.esc(r.vm_name)}${r.installed ? ` · v${this.esc(r.version_name || "?")}` : ""}</span>
          </td>
          <td class="mx-opt"><input class="tick" type="checkbox" ${r.opted_in ? "checked" : ""} ${r.is_tester ? "" : "disabled"}
              aria-label="Máy #${this.esc(r.vm_index)} đã tham gia test"
              onchange="CampaignModule.toggleOptin('${this.esc(r.vm_index)}', this.checked)"></td>
          ${cells}
          <td class="mx-days">${r.days_active}<small>/${rep.summary.target_days}</small></td>
          <td class="mx-run">${r.is_tester ? `<button class="btn btn-ghost btn-sm" onclick="CampaignModule.runOne('${this.esc(r.vm_index)}')" ${this.job?.running ? "disabled" : ""}>Chạy</button>` : ""}</td>
        </tr>`;
      })
      .join("");
    return `
      <table class="matrix">
        <thead><tr><th class="left">Tester</th><th class="left mx-opt" style="text-align:center">Tham gia</th>${head}<th class="mx-days">Ngày</th><th></th></tr></thead>
        <tbody>${body}</tbody>
      </table>`;
  },

  onboardingHtml() {
    const accs =
      (typeof AccountsModule !== "undefined" ? AccountsModule.accounts : []) ||
      [];
    const vms =
      (typeof InstancesModule !== "undefined" ? InstancesModule.vms : []) || [];
    const step = (done, title, text) => `
      <li>
        <span class="prep-dot ${done ? "done" : ""}"></span>
        <div><b>${title}</b><p>${text}</p></div>
      </li>`;
    return `
      <div class="card onboard">
        <div class="onboard-hero">
          <span class="eyebrow">Kiểm thử kín · Google Play</span>
          <h1 style="margin-top:6px">12 tester. 14 ngày liên tục.<br>Một đường link.</h1>
          <p>Tài khoản nhà phát triển cá nhân mới phải có ít nhất 12 người thử nghiệm dùng app suốt 14 ngày trước khi được phát hành chính thức. Dán link test ở ô bên dưới, phần còn lại DroidTest tự làm trên các máy ảo.</p>
          <p class="onboard-figure">${vms.length}/12 máy · ${accs.length}/12 tài khoản</p>
        </div>
        <ul class="prep">
          ${step(accs.length >= 12, "Thêm 12 tài khoản Google", `Trong <a href="#/cai-dat">Cài đặt → Tài khoản Google</a>. Hiện có ${accs.length}.`)}
          ${step(false, "Khai báo tester trong Play Console", "Kiểm thử kín → Người thử nghiệm: dán danh sách email (nút “Sao chép danh sách email”).")}
          ${step(false, "Lấy link “Tham gia trên web”", "Dán vào ô bên dưới rồi bấm Bắt đầu chiến dịch test.")}
          ${step(vms.length >= 12, "Máy ảo", vms.length >= 12 ? "Đã đủ 12 máy." : "Tool sẽ tự tạo thêm cho đủ 12 máy khi bắt đầu.")}
        </ul>
      </div>`;
  },

  renderJob() {
    const box = document.getElementById("cmpJob");
    if (!box) return;
    const j = this.job;
    if (
      !this.campaign ||
      !j ||
      (!j.total && !j.running && !(j.log || []).length)
    ) {
      box.innerHTML = "";
      return;
    }
    const pct = j.total ? Math.round((j.done / j.total) * 100) : 4;
    const items = Object.entries(j.vms)
      .sort((a, b) => Number(a[0]) - Number(b[0]))
      .map(
        ([idx, v]) => `
        <div class="run-item" title="${this.esc(v.email || "")}">
          <span class="dot ${this.esc(v.status)}"></span>
          <span class="mono">#${this.esc(idx)}</span>
          <span class="msg">${this.esc(v.step || "")}</span>
        </div>`,
      )
      .join("");
    const logs = (j.log || [])
      .slice(-40)
      .map(
        (l) =>
          `<div class="${this.esc(l.level)}"><span class="t">${this.esc(l.ts)}</span>${this.esc(l.msg)}</div>`,
      )
      .join("");
    box.innerHTML = `
      <div class="card run">
        <div class="run-head">
          <h3>${j.running ? "Lượt test đang chạy" : "Lượt test gần nhất"}</h3>
          <span class="muted">${j.trigger === "auto" ? "Theo lịch · " : ""}${this.esc(j.started_at)}${j.finished_at ? " – " + this.esc(j.finished_at.slice(11, 16)) : ""}</span>
          <span class="run-count">${j.done}/${j.total} máy · ${j.ok} xong · ${j.failed} cần xem</span>
        </div>
        ${j.phase ? `<p class="run-phase">${this.esc(j.phase)}</p>` : ""}
        <div class="progress"><i style="width:${pct}%"></i></div>
        ${items ? `<div class="run-list">${items}</div>` : ""}
        <details class="run-log">
          <summary>Nhật ký chi tiết</summary>
          <div class="log">${logs || "Chưa có nhật ký."}</div>
        </details>
      </div>`;
  },

  // Small summary used by the device table
  testerFor(index) {
    if (!this.campaign) return null;
    const r = this.testerMap[String(index)];
    return r && r.is_tester ? r : null;
  },

  cardHash() {
    if (!this.campaign) return "";
    return JSON.stringify(
      Object.values(this.testerMap).map((r) => [
        r.vm_index,
        r.opted_in,
        r.installed,
        r.version_name,
        r.days_active,
        r.today,
      ]),
    );
  },

  fmtDate(iso) {
    if (!iso) return "";
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
  },

  esc(str) {
    return String(str ?? "").replace(
      /[&<>"']/g,
      (m) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[m],
    );
  },
};
