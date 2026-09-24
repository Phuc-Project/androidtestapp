// DroidRouter 9 - Services & Multi-Device Command Broadcast

const ServicesModule = {
  async load() {
    this.refreshRunningCount();
  },

  async refreshRunningCount() {
    const el = document.getElementById('broadcastRunningTarget');
    if (!el) return;
    try {
      const res = await fetch('/api/instances');
      const data = await res.json();
      if (data.success) {
        const running = data.data.filter(v => v.is_running);
        el.textContent = `${running.length} Running VMs: [${running.map(v => '#' + v.index).join(', ') || 'None'}]`;
      }
    } catch (e) {}
  },

  async executeBroadcast() {
    const cmdInput = document.getElementById('broadcastCmdInput');
    const cmd = cmdInput ? cmdInput.value.trim() : '';
    const resBox = document.getElementById('broadcastResultBox');

    if (!cmd) {
      App.showToast('Please enter an ADB shell command', 'error');
      return;
    }

    App.showToast(`Broadcasting command '${cmd}'...`);
    if (resBox) resBox.innerHTML = '<div style="color:var(--text-muted);">Executing across all running VMs...</div>';

    try {
      const res = await fetch('/api/services/broadcast-adb', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd })
      });
      const data = await res.json();
      if (data.success && resBox) {
        let html = `<div style="color:var(--accent-green);margin-bottom:8px;">✅ Executed on ${data.executed_count} VMs:</div>`;
        for (const [idx, result] of Object.entries(data.results)) {
          html += `
            <div style="margin-bottom:4px;padding:4px 8px;background:var(--bg-input);border-radius:4px;">
              <span style="color:var(--accent-cyan);font-weight:700;">VM #${idx}:</span>
              <span>${result.output || (result.success ? 'Success (no output)' : 'Error')}</span>
            </div>
          `;
        }
        resBox.innerHTML = html;
        App.showToast('Broadcast completed');
      } else if (resBox) {
        resBox.innerHTML = `<div style="color:var(--accent-red);">${data.message || 'Execution failed'}</div>`;
      }
    } catch (e) {
      App.showToast(e.message, 'error');
    }
  },

  setPresetCommand(cmd) {
    const input = document.getElementById('broadcastCmdInput');
    if (input) input.value = cmd;
  }
};
