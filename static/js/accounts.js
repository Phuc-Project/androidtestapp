// DroidTest — tester Google accounts

const AccountsModule = {
  accounts: [],

  async loadQuickPool() {
    try {
      const res = await fetch("/api/accounts");
      const data = await res.json();
      if (data.success) {
        this.accounts = data.data;
        const counter = document.getElementById("googlePoolCount");
        if (counter) counter.textContent = this.accounts.length;
        this.render();
      }
    } catch (e) {
      console.warn("Không tải được danh sách tài khoản", e);
    }
  },

  render() {
    const list = document.getElementById("googleAccountChips");
    if (!list) return;
    if (this.accounts.length === 0) {
      list.innerHTML = `<div class="empty"><h3>Chưa có tài khoản</h3><p>Thêm từng tài khoản ở trên, hoặc dán cả danh sách bằng “Nhập nhiều tài khoản”.</p></div>`;
      return;
    }
    const vms = (typeof InstancesModule !== "undefined" ? InstancesModule.vms : []) || [];
    const status = {
      logged_in: ["ok", "Đã đăng nhập"],
      checkpoint: ["bad", "Google cần xác minh"],
      banned: ["bad", "Bị khoá"],
    };
    const rows = this.accounts.map((acc) => {
      const vmIdx = acc.assigned_vm_index === null || acc.assigned_vm_index === undefined ? "" : String(acc.assigned_vm_index);
      const vm = vms.find((v) => String(v.index) === vmIdx);
      const known = new Set(vms.map((v) => String(v.index)));
      const options = [`<option value="">Chưa gán</option>`]
        .concat(vms.map((v) => {
          const owner = this.accounts.find((a) => String(a.assigned_vm_index) === String(v.index) && a.id !== acc.id);
          return `<option value="${this.escape(v.index)}" ${String(v.index) === vmIdx ? "selected" : ""}>Máy #${this.escape(v.index)}${owner ? " (đang có TK)" : ""}</option>`;
        }))
        .concat(vmIdx && !known.has(vmIdx) ? [`<option value="${this.escape(vmIdx)}" selected>Máy #${this.escape(vmIdx)} (đã xoá)</option>`] : [])
        .join("");
      const live = vm && vm.has_account && (vm.account_email || "").toLowerCase() === acc.username.toLowerCase();
      const [cls, text] = live ? status.logged_in
        : vmIdx && vms.length && !vm ? ["warn", "Máy đã bị xoá – chọn máy khác"]
        : status[acc.status] || (vmIdx ? ["", "Chưa đăng nhập"] : ["stopped", "Chưa dùng"]);
      const canLogin = vm && !live;
      return `
        <tr>
          <td><span class="d-email" title="${this.escape(acc.username)}">${this.escape(acc.username)}</span></td>
          <td data-label="Máy">
            <select class="input acc-select" aria-label="Máy dùng ${this.escape(acc.username)}" onchange="AccountsModule.assign(${acc.id}, this.value)">${options}</select>
          </td>
          <td data-label="Trạng thái"><span class="d-state"><span class="dot ${cls}"></span>${text}</span></td>
          <td data-label="Bảo mật" class="d-muted">${acc.password ? "Có mật khẩu" : "Thiếu mật khẩu"}${acc.two_factor_secret ? " · 2FA" : ""}</td>
          <td>
            <div class="d-actions">
              ${canLogin ? `<button class="btn btn-primary btn-sm" onclick="InstancesModule.oneClickGoogleLogin('${this.escape(vmIdx)}')">Đăng nhập lên máy</button>` : ""}
              <button class="btn btn-ghost btn-sm" onclick="AccountsModule.deleteAccount(${acc.id})">Xoá</button>
            </div>
          </td>
        </tr>`;
    }).join("");
    list.innerHTML = `
      <table class="dtable">
        <thead><tr><th>Email</th><th>Máy</th><th>Trạng thái</th><th>Bảo mật</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  },

  accountPayload(acc, patch = {}) {
    const pick = ["service", "name", "username", "password", "two_factor_secret", "recovery_info", "assigned_vm_index", "status", "notes"];
    const body = {};
    pick.forEach((k) => (body[k] = acc[k] ?? ""));
    return { ...body, ...patch };
  },

  async put(acc, patch) {
    const res = await fetch(`/api/accounts/${acc.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(this.accountPayload(acc, patch)),
    });
    if (!res.ok) throw new Error("Không cập nhật được tài khoản");
  },

  async assign(id, vmIdx) {
    const acc = this.accounts.find((a) => a.id === id);
    if (!acc) return;
    try {
      if (vmIdx) {
        const holder = this.accounts.find((a) => String(a.assigned_vm_index) === String(vmIdx) && a.id !== id);
        if (holder) {
          if (!confirm(`Máy #${vmIdx} đang dùng ${holder.username}. Chuyển máy này sang ${acc.username}?`)) return this.render();
          await this.put(holder, { assigned_vm_index: "", status: holder.status === "logged_in" ? "active" : holder.status });
        }
      }
      const moved = String(acc.assigned_vm_index ?? "") !== String(vmIdx);
      await this.put(acc, { assigned_vm_index: vmIdx, status: moved && acc.status === "logged_in" ? "active" : acc.status });
      App.showToast(vmIdx ? `Đã gán ${acc.username} cho máy #${vmIdx}` : `Đã bỏ gán ${acc.username}`);
      await this.loadQuickPool();
      InstancesModule.load();
    } catch (e) {
      App.showToast(e.message, "error");
      this.render();
    }
  },

  async submitQuickAdd() {
    const emailInput = document.getElementById("quickGoogleEmail");
    const passInput = document.getElementById("quickGooglePass");
    const tfaInput = document.getElementById("quickGoogle2fa");
    const email = (emailInput?.value || "").trim();
    const pass = (passInput?.value || "").trim();
    const tfa = (tfaInput?.value || "").replace(/\s+/g, "").toUpperCase();
    if (tfa && !/^[A-Z2-7]{16,64}=*$/.test(tfa)) {
      App.showToast("Khoá 2FA không hợp lệ. Đây là chuỗi chữ A–Z và số 2–7 Google cấp khi bật ứng dụng xác thực.", "error");
      tfaInput.focus();
      return;
    }
    if (!email || !email.includes("@")) {
      App.showToast("Nhập địa chỉ Gmail của tester", "error");
      emailInput?.focus();
      return;
    }
    try {
      const res = await fetch("/api/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service: "google", name: email.split("@")[0], username: email, password: pass, two_factor_secret: tfa, assigned_vm_index: "" }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.detail || data.error || "Không thêm được tài khoản");
      App.showToast(`Đã thêm ${email}`);
      emailInput.value = "";
      passInput.value = "";
      if (tfaInput) tfaInput.value = "";
      emailInput.focus();
      await this.loadQuickPool();
      InstancesModule.load();
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  copyEmails() {
    const emails = this.accounts.filter((a) => (a.service || "google") === "google").map((a) => a.username);
    if (!emails.length) {
      App.showToast("Danh sách tài khoản đang trống", "error");
      return;
    }
    const text = emails.join(", ");
    const done = () => App.showToast(`Đã sao chép ${emails.length} email. Dán vào danh sách người thử nghiệm trong Play Console.`);
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, () => prompt("Danh sách email:", text));
    else prompt("Danh sách email:", text);
  },

  openBulkModal() {
    const input = document.getElementById("bulkGoogleInput");
    if (input) input.value = "";
    document.getElementById("modalBulkGoogle")?.classList.add("active");
    input?.focus();
  },

  async submitBulkGoogle() {
    const text = (document.getElementById("bulkGoogleInput")?.value || "").trim();
    if (!text) {
      App.showToast("Dán danh sách tài khoản vào ô trước", "error");
      return;
    }
    try {
      const res = await fetch("/api/accounts/bulk-google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: text }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.detail || data.error || "Không nhập được danh sách");
      App.showToast(`Đã thêm ${data.added} tài khoản`);
      document.getElementById("modalBulkGoogle").classList.remove("active");
      await this.loadQuickPool();
      InstancesModule.load();
      CampaignModule.render();
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  async deleteAccount(id) {
    const acc = this.accounts.find((a) => a.id === id);
    if (!confirm(`Xoá ${acc ? acc.username : "tài khoản này"} khỏi danh sách?`)) return;
    try {
      const res = await fetch(`/api/accounts/${id}`, { method: "DELETE" });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Không xoá được");
      App.showToast("Đã xoá tài khoản");
      await this.loadQuickPool();
      InstancesModule.load();
    } catch (e) {
      App.showToast(e.message, "error");
    }
  },

  escape(str) {
    return String(str ?? "").replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[m]);
  },
};
