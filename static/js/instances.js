// DroidTest — virtual devices table

const InstancesModule = {
  vms: [],
  _lastRenderHash: "",

  async load() {
    const grid = document.getElementById("vmGrid");
    if (!grid) return;
    try {
      const res = await fetch("/api/instances");
      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Không đọc được danh sách máy");
      this.vms = data.data;
      this.updateHeaderTelemetry();
      const hash = JSON.stringify(this.vms.map((v) => [
        v.index, v.name, v.is_running, v.is_android_started, v.has_account, v.account_email,
        v.adb_target, v.automation ? v.automation.state + v.automation.msg : "",
      ])) + (typeof CampaignModule !== "undefined" ? CampaignModule.cardHash() : "");
      if (hash !== this._lastRenderHash) {
        this._lastRenderHash = hash;
        this.render();
        // Trang Tổng quan (chưa có chiến dịch) hiển thị số máy: vẽ lại khi danh sách máy thay đổi
        if (typeof CampaignModule !== "undefined" && CampaignModule._loaded && !CampaignModule.campaign) {
          CampaignModule.renderBody();
        }
      }
    } catch (e) {
      grid.innerHTML = `<div class="empty"><h3>Không kết nối được MuMu</h3><p>${this.escape(e.message)}</p></div>`;
    }
  },

  updateHeaderTelemetry() {
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    set("hdrRunningCount", this.vms.filter((v) => v.is_running).length);
    set("hdrTotalCount", this.vms.length);
    set("navVmCount", this.vms.length || "");
  },

  stateOf(vm) {
    if (vm.is_running && vm.is_android_started) return { cls: "ok", text: "Đang chạy" };
    if (vm.is_running) return { cls: "run", text: "Đang khởi động" };
    return { cls: "", text: "Đã tắt" };
  },

  render() {
    const grid = document.getElementById("vmGrid");
    if (!grid) return;
    if (typeof AccountsModule !== "undefined") AccountsModule.render(); // machine picker depends on the VM list
    if (this.vms.length === 0) {
      grid.innerHTML = `
        <div class="empty">
          <h3>Chưa có máy ảo</h3>
          <p>Cần 12 máy, mỗi máy là một tester. DroidTest tạo máy bằng MuMuPlayer.</p>
          <button class="btn btn-primary" onclick="InstancesModule.ensureCount(12)">Tạo 12 máy</button>
        </div>`;
      return;
    }
    const hasCampaign = typeof CampaignModule !== "undefined" && CampaignModule.campaign;
    const rows = this.vms.map((vm) => this.rowHtml(vm, hasCampaign)).join("");
    grid.innerHTML = `
      <table class="dtable">
        <thead>
          <tr>
            <th>Máy</th>
            <th>Trạng thái</th>
            <th>Tài khoản Google</th>
            ${hasCampaign ? "<th>App</th><th>Hôm nay</th>" : ""}
            <th>Tác vụ tự động</th>
            <th></th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  },

  rowHtml(vm, hasCampaign) {
    const idx = this.escape(vm.index);
    const st = this.stateOf(vm);
    const t = hasCampaign ? CampaignModule.testerFor(vm.index) : null;
    const account = vm.has_account
      ? `<span class="d-email" title="${this.escape(vm.account_email)}">${this.escape(vm.account_email)}</span>`
      : `<span class="d-missing">Chưa đăng nhập</span>`;

    let campaignCells = "";
    if (hasCampaign) {
      const app = t ? (t.installed ? `<span class="mono">v${this.escape(t.version_name || "?")}</span>` : `<span class="d-missing">Chưa cài</span>`) : `<span class="d-muted">—</span>`;
      const todayMap = { ok: ["ok", "Đã test"], pending: ["", "Chưa test"], failed: ["warn", "Lỗi"], missed: ["bad", "Bỏ lỡ"] };
      const td = t && todayMap[t.today];
      const today = td ? `<span class="badge ${td[0] || "idle"}">${td[1]}</span>` : `<span class="d-muted">—</span>`;
      campaignCells = `<td data-label="App">${app}</td><td data-label="Hôm nay">${today}</td>`;
    }

    const a = vm.automation;
    const autoText = { running: "", ok: "", manual: "Cần bạn xử lý: ", failed: "Lỗi: ", joined: "", stopped: "" };
    const auto = a
      ? `<span class="d-state"><span class="dot ${this.escape(a.state)}"></span><span>${autoText[a.state] || ""}${this.escape(a.msg)}<span class="when">${this.escape(a.ts)}</span></span></span>
         ${a.state === "manual" && vm.is_running ? `<br><button class="link-btn" style="font-size:12.5px" onclick="RemoteModule.openModal('${idx}')">Mở màn hình máy</button>` : ""}`
      : `<span class="d-muted">—</span>`;

    const primary = vm.is_running
      ? `<button class="btn btn-secondary btn-sm" onclick="RemoteModule.openModal('${idx}')" ${vm.is_android_started ? "" : "disabled"}>Màn hình</button>`
      : `<button class="btn btn-secondary btn-sm" onclick="InstancesModule.launch('${idx}')">Bật</button>`;
    const login = !vm.has_account
      ? `<button class="btn btn-secondary btn-sm" onclick="InstancesModule.oneClickGoogleLogin('${idx}')">Đăng nhập</button>` : "";
    const menu = `
      <div class="menu">
        <button class="btn btn-ghost btn-sm btn-icon" data-menu-toggle aria-haspopup="true" aria-label="Thao tác khác cho máy #${idx}">
          <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><circle cx="3.5" cy="8" r="1.3" fill="currentColor"/><circle cx="8" cy="8" r="1.3" fill="currentColor"/><circle cx="12.5" cy="8" r="1.3" fill="currentColor"/></svg>
        </button>
        <div class="menu-list menu-right" role="menu">
          ${vm.is_running ? `
            <button role="menuitem" onclick="InstancesModule.shutdown('${idx}')">Tắt máy</button>
            <button role="menuitem" onclick="InstancesModule.restart('${idx}')">Khởi động lại</button>
            <button role="menuitem" onclick="InstancesModule.toggleWindow('${idx}')">Hiện cửa sổ MuMu</button>
            <button role="menuitem" onclick="InstancesModule.hideWindow('${idx}')">Ẩn cửa sổ MuMu</button>`
          : `<button role="menuitem" onclick="InstancesModule.clone('${idx}')">Nhân bản máy</button>`}
          <button role="menuitem" onclick="InstancesModule.openRename('${idx}')">Đổi tên</button>
          <button role="menuitem" onclick="InstancesModule.openSimulation('${idx}')">Đổi định danh thiết bị</button>
          ${vm.has_account || vm.account_id ? `<button role="menuitem" onclick="InstancesModule.unlinkAccount('${idx}')">Bỏ gán tài khoản</button>` : ""}
          <div class="menu-sep"></div>
          <button role="menuitem" class="danger" onclick="InstancesModule.delete('${idx}')" ${vm.is_running ? "disabled" : ""}>Xoá máy</button>
        </div>
      </div>`;

    return `
      <tr>
        <td class="d-name"><b>${this.escape(vm.name)}</b><span>#${idx} · ${this.escape(vm.adb_target)}</span></td>
        <td data-label="Trạng thái"><span class="d-state"><span class="dot ${st.cls}"></span>${st.text}</span></td>
        <td data-label="Tài khoản">${account}</td>
        ${campaignCells}
        <td data-label="Tự động" class="d-auto">${auto}</td>
        <td><div class="d-actions">${login}${primary}${menu}</div></td>
      </tr>`;
  },

  async post(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch (e) {}
    if (!res.ok || data.success === false) throw new Error(data.detail || data.error || data.message || `Máy chủ trả lỗi ${res.status}`);
    return data;
  },

  async run(fn, after = 1500) {
    try {
      await fn();
      if (after) setTimeout(() => this.load(), after);
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  oneClickGoogleLogin(index) {
    return this.run(async () => {
      const d = await this.post(`/api/instances/${index}/google-login`, {});
      App.showToast(`Đang đăng nhập ${d.email} trên máy #${index}. Theo dõi ở cột Tác vụ tự động.`);
    }, 2500);
  },

  autoAssignAndLoginAll() {
    return this.run(async () => {
      const d = await this.post("/api/instances/auto-assign-google");
      App.showToast(d.message);
      if (typeof AccountsModule !== "undefined") await AccountsModule.loadQuickPool();
      await this.load();
      const assigned = new Set((AccountsModule.accounts || [])
        .filter((a) => a.assigned_vm_index !== "" && a.assigned_vm_index !== null)
        .map((a) => String(a.assigned_vm_index)));
      const toLogin = this.vms.filter((v) => v.is_android_started && !v.has_account && assigned.has(String(v.index)));
      for (const vm of toLogin) this.post(`/api/instances/${vm.index}/google-login`, {}).catch(() => {});
      if (toLogin.length) App.showToast(`Đang đăng nhập trên ${toLogin.length} máy đang bật`);
    }, 0);
  },

  unlinkAccount(index) {
    if (!confirm(`Bỏ gán tài khoản khỏi máy #${index}? Tài khoản vẫn còn trong danh sách.`)) return;
    return this.run(async () => {
      await this.post(`/api/instances/${index}/unlink-account`);
      App.showToast(`Đã bỏ gán tài khoản khỏi máy #${index}`);
      AccountsModule.loadQuickPool();
    });
  },

  launch(index) {
    return this.run(async () => {
      const d = await this.post(`/api/instances/${index}/launch`);
      App.showToast(d.message || `Đang bật máy #${index}`);
    }, 2500);
  },

  hideWindow(index) {
    return this.run(async () => {
      await this.post(`/api/instances/${index}/hide`);
      App.showToast(`Đã ẩn cửa sổ máy #${index}`);
    }, 0);
  },

  toggleWindow(index) {
    return this.run(async () => {
      await this.post(`/api/instances/${index}/show`);
      App.showToast(`Đã hiện cửa sổ máy #${index}`);
    }, 0);
  },

  shutdown(index) {
    return this.run(async () => {
      await this.post(`/api/instances/${index}/shutdown`);
      App.showToast(`Đã tắt máy #${index}`);
    });
  },

  restart(index) {
    return this.run(async () => {
      await this.post(`/api/instances/${index}/restart`);
      App.showToast(`Đang khởi động lại máy #${index}`);
    }, 2500);
  },

  async ensureCount(count = 12) {
    if (!confirm(`Tạo thêm máy cho đủ ${count} máy? Việc tạo máy mất vài phút và chạy ngầm.`)) return;
    return this.run(async () => {
      const d = await this.post("/api/instances/ensure-count", { count });
      App.showToast(d.message);
      if (d.created) setTimeout(() => this.load(), 15000);
    }, 0);
  },

  openCreateModal() {
    document.getElementById("modalCreateVm").classList.add("active");
  },

  submitCreateVm() {
    const ver = document.getElementById("newVmVersion").value || "15";
    document.getElementById("modalCreateVm").classList.remove("active");
    return this.run(async () => {
      await this.post("/api/instances/create", { version: ver });
      App.showToast("Đã tạo máy mới");
    }, 3000);
  },

  clone(index) {
    if (!confirm(`Nhân bản máy #${index}? Việc sao chép mất khoảng 30 giây.\nLưu ý: bản sao sẽ mang theo tài khoản Google đang đăng nhập.`)) return;
    App.showToast(`Đang nhân bản máy #${index}…`);
    return this.run(async () => {
      await this.post(`/api/instances/${index}/clone`);
      App.showToast(`Đã nhân bản máy #${index}`);
    }, 3000);
  },

  openRename(index) {
    const vm = this.vms.find((v) => String(v.index) === String(index));
    const current = vm ? vm.name : "";
    const name = prompt(`Tên mới cho máy #${index}:`, current);
    if (!name || name === current) return;
    return this.run(async () => {
      await this.post(`/api/instances/${index}/rename`, { name });
      App.showToast(`Đã đổi tên máy #${index}`);
    }, 300);
  },

  openSimulation(index) {
    document.getElementById("simVmIndex").value = index;
    document.getElementById("simVal").value = "";
    document.getElementById("modalSimulation").classList.add("active");
  },

  submitSimulation() {
    const index = document.getElementById("simVmIndex").value;
    const simu_key = document.getElementById("simKey").value;
    const simu_value = document.getElementById("simVal").value.trim();
    if (!simu_value) {
      App.showToast("Nhập giá trị mới trước khi áp dụng", "error");
      return;
    }
    return this.run(async () => {
      await this.post(`/api/instances/${index}/simulation`, { simu_key, simu_value });
      App.showToast(`Đã đổi ${simu_key} cho máy #${index}`);
      document.getElementById("modalSimulation").classList.remove("active");
    }, 0);
  },

  delete(index) {
    if (!confirm(`Xoá vĩnh viễn máy #${index}? Không thể hoàn tác.`)) return;
    return this.run(async () => {
      await this.post(`/api/instances/${index}/delete`);
      App.showToast(`Đã xoá máy #${index}`);
    }, 300);
  },

  escape(str) {
    return String(str ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[m]);
  },
};
