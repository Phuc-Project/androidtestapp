"""
DroidTest 9 - Compact Desktop Floating HUD Widget.
Always-on-top, draggable mini status monitor and quick controller for Windows.
"""
import os
import sys
import json
import time
import urllib.request
import webbrowser
import threading
import tkinter as tk
from tkinter import font as tkfont

SERVER_URL = "http://127.0.0.1:9090"

class DesktopWidget:
    def __init__(self, root):
        self.root = root
        self.root.title("DroidTest Widget")
        
        # Dimensions & Default Top-Right Screen Position
        self.width = 320
        self.height = 175
        screen_w = self.root.winfo_screenwidth()
        x_pos = max(10, screen_w - self.width - 25)
        y_pos = 45
        self.root.geometry(f"{self.width}x{self.height}+{x_pos}+{y_pos}")

        # Window Styles: Frameless & Always-on-top
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg="#111318")

        # Dragging state
        self._offset_x = 0
        self._offset_y = 0
        self._is_collapsed = False
        self._running = True

        # Build UI
        self._build_ui()

        # Telemetry Polling Loop
        self.poll_telemetry()

    def _build_ui(self):
        # Outer Border Frame
        self.outer_frame = tk.Frame(self.root, bg="#262A36", bd=1)
        self.outer_frame.pack(fill=tk.BOTH, expand=True)

        self.main_frame = tk.Frame(self.outer_frame, bg="#111318", padx=10, pady=8)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Header Bar (Draggable)
        self.header = tk.Frame(self.main_frame, bg="#111318", cursor="fleur")
        self.header.pack(fill=tk.X, side=tk.TOP)
        self.header.bind("<Button-1>", self._start_drag)
        self.header.bind("<B1-Motion>", self._on_drag)
        self.header.bind("<Double-Button-1>", self._toggle_collapse)

        # Brand Title
        self.lbl_title = tk.Label(
            self.header, text="DROIDTEST 9", fg="#00E5FF", bg="#111318",
            font=("Segoe UI", 9, "bold")
        )
        self.lbl_title.pack(side=tk.LEFT)
        self.lbl_title.bind("<Button-1>", self._start_drag)
        self.lbl_title.bind("<B1-Motion>", self._on_drag)
        self.lbl_title.bind("<Double-Button-1>", self._toggle_collapse)

        # Status Pill
        self.lbl_status = tk.Label(
            self.header, text="ONLINE", fg="#10B981", bg="#182A24",
            font=("Segoe UI", 7, "bold"), padx=5, pady=1
        )
        self.lbl_status.pack(side=tk.LEFT, padx=6)

        # Window Controls: Minimize/Collapse & Close
        btn_close = tk.Label(
            self.header, text="✕", fg="#8A92A6", bg="#111318",
            font=("Segoe UI", 9), cursor="hand2", padx=4
        )
        btn_close.pack(side=tk.RIGHT)
        btn_close.bind("<Button-1>", lambda e: self.close())

        btn_dash = tk.Label(
            self.header, text="🌐", fg="#8A92A6", bg="#111318",
            font=("Segoe UI", 8), cursor="hand2", padx=3
        )
        btn_dash.pack(side=tk.RIGHT)
        btn_dash.bind("<Button-1>", lambda e: self.open_dashboard())

        # Body Frame (Hidden when collapsed)
        self.body_frame = tk.Frame(self.main_frame, bg="#111318")
        self.body_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        # App / Campaign Line
        self.lbl_campaign = tk.Label(
            self.body_frame, text="Đang kết nối backend...", fg="#FFFFFF", bg="#111318",
            font=("Segoe UI", 9, "bold"), anchor="w"
        )
        self.lbl_campaign.pack(fill=tk.X)

        # Sub / Phase Line (Cluster progress)
        self.lbl_phase = tk.Label(
            self.body_frame, text="Sẵn sàng chạy test", fg="#8A92A6", bg="#111318",
            font=("Segoe UI", 8), anchor="w"
        )
        self.lbl_phase.pack(fill=tk.X, pady=(2, 6))

        # Hardware Telemetry Grid (CPU | RAM | VMs)
        self.hw_frame = tk.Frame(self.body_frame, bg="#171A21", padx=6, pady=4)
        self.hw_frame.pack(fill=tk.X, pady=(0, 8))

        self.lbl_cpu = tk.Label(
            self.hw_frame, text="CPU: --%", fg="#CBD5E1", bg="#171A21",
            font=("Consolas", 8)
        )
        self.lbl_cpu.pack(side=tk.LEFT, expand=True)

        self.lbl_ram = tk.Label(
            self.hw_frame, text="RAM: --%", fg="#CBD5E1", bg="#171A21",
            font=("Consolas", 8)
        )
        self.lbl_ram.pack(side=tk.LEFT, expand=True)

        self.lbl_vms = tk.Label(
            self.hw_frame, text="VMs: 0/12", fg="#00E5FF", bg="#171A21",
            font=("Consolas", 8, "bold")
        )
        self.lbl_vms.pack(side=tk.LEFT, expand=True)

        # Quick Control Buttons
        self.btn_bar = tk.Frame(self.body_frame, bg="#111318")
        self.btn_bar.pack(fill=tk.X)

        self.btn_run = tk.Button(
            self.btn_bar, text="▶ Chạy test", bg="#1E293B", fg="#38BDF8",
            activebackground="#0284C7", activeforeground="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT, bd=0, padx=6, pady=3,
            cursor="hand2", command=self.trigger_run
        )
        self.btn_run.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_opt = tk.Button(
            self.btn_bar, text="⚡ Dọn RAM", bg="#1E293B", fg="#10B981",
            activebackground="#059669", activeforeground="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT, bd=0, padx=6, pady=3,
            cursor="hand2", command=self.trigger_optimize
        )
        self.btn_opt.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_stop = tk.Button(
            self.btn_bar, text="⏹ Dừng", bg="#1E293B", fg="#EF4444",
            activebackground="#DC2626", activeforeground="#FFFFFF",
            font=("Segoe UI", 8), relief=tk.FLAT, bd=0, padx=6, pady=3,
            cursor="hand2", command=self.trigger_stop
        )
        self.btn_stop.pack(side=tk.LEFT)

    # ---------- Window Dragging ----------
    def _start_drag(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + (event.x - self._offset_x)
        y = self.root.winfo_y() + (event.y - self._offset_y)
        self.root.geometry(f"+{x}+{y}")

    def _toggle_collapse(self, event=None):
        if self._is_collapsed:
            self.body_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
            self.root.geometry(f"{self.width}x{self.height}")
            self._is_collapsed = False
        else:
            self.body_frame.pack_forget()
            self.root.geometry(f"{self.width}x36")
            self._is_collapsed = True

    # ---------- Actions ----------
    def open_dashboard(self):
        webbrowser.open(SERVER_URL)

    def trigger_run(self):
        def _req():
            try:
                req = urllib.request.Request(
                    f"{SERVER_URL}/api/campaign/run",
                    data=json.dumps({"force": False}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=3)
            except Exception as e:
                pass
        threading.Thread(target=_req, daemon=True).start()
        self.lbl_phase.config(text="Đang bắt đầu lượt test...", fg="#38BDF8")

    def trigger_stop(self):
        def _req():
            try:
                req = urllib.request.Request(
                    f"{SERVER_URL}/api/campaign/stop",
                    data=b"{}",
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass
        threading.Thread(target=_req, daemon=True).start()
        self.lbl_phase.config(text="Đang dừng lượt test...", fg="#EF4444")

    def trigger_optimize(self):
        def _req():
            try:
                req = urllib.request.Request(
                    f"{SERVER_URL}/api/system/clean-ram",
                    data=b"{}",
                    headers={"Content-Type": "application/json"}
                )
                res = urllib.request.urlopen(req, timeout=4)
                data = json.loads(res.read().decode("utf-8"))
                freed = data.get("data", {}).get("ram_freed_mb", 0)
                self.root.after(0, lambda: self.lbl_phase.config(
                    text=f"Đã giải phóng {freed} MB RAM!", fg="#10B981"
                ))
            except Exception:
                pass
        threading.Thread(target=_req, daemon=True).start()
        self.lbl_phase.config(text="Đang dọn Working Set RAM...", fg="#10B981")

    def close(self):
        self._running = False
        self.root.destroy()
        sys.exit(0)

    # ---------- Background Telemetry Polling ----------
    def poll_telemetry(self):
        def _worker():
            stats = None
            job = None
            camp = None
            try:
                # System stats
                with urllib.request.urlopen(f"{SERVER_URL}/api/system/stats", timeout=1.8) as r:
                    stats = json.loads(r.read().decode("utf-8")).get("data", {})
                # Campaign & Job status
                with urllib.request.urlopen(f"{SERVER_URL}/api/campaign", timeout=1.8) as r:
                    cdata = json.loads(r.read().decode("utf-8"))
                    camp = cdata.get("campaign")
                    job = cdata.get("job")
            except Exception:
                pass

            self.root.after(0, self._update_ui, stats, camp, job)

        threading.Thread(target=_worker, daemon=True).start()
        if self._running:
            self.root.after(2000, self.poll_telemetry)

    def _update_ui(self, stats, camp, job):
        if not stats:
            self.lbl_status.config(text="OFFLINE", fg="#EF4444", bg="#2D1518")
            self.lbl_campaign.config(text="Backend chưa bật", fg="#94A3B8")
            self.lbl_phase.config(text="Nhấn phím tắt mở DroidTest", fg="#64748B")
            return

        self.lbl_status.config(text="ONLINE", fg="#10B981", bg="#182A24")
        cpu = stats.get("cpu_percent", 0)
        ram = stats.get("memory_percent", 0)
        ram_gb = stats.get("memory_used_gb", 0)
        running_vms = stats.get("vms_running", 0)
        total_vms = stats.get("vms_total", 12)

        self.lbl_cpu.config(text=f"CPU: {cpu}%")
        self.lbl_ram.config(text=f"RAM: {ram}%")
        self.lbl_vms.config(text=f"VMs: {running_vms}/{total_vms}")

        # Update Campaign & Job info
        if camp:
            app_name = camp.get("app_name") or camp.get("package_name") or "Chưa chọn app"
            prof = camp.get("app_profile") or "light"
            prof_tag = "[4-VM]" if prof == "light" else "[2-VM]"
            self.lbl_campaign.config(text=f"{app_name[:22]} {prof_tag}", fg="#FFFFFF")
        else:
            self.lbl_campaign.config(text="Chưa có chiến dịch test", fg="#94A3B8")

        if job and job.get("running"):
            self.lbl_status.config(text="TESTING", fg="#38BDF8", bg="#0F2D3D")
            phase = job.get("phase") or "Đang chạy test..."
            done = job.get("done", 0)
            total = job.get("total", 0)
            self.lbl_phase.config(text=f"({done}/{total}) {phase[:30]}", fg="#38BDF8")
        elif camp:
            sched = camp.get("auto_run_time")
            sched_text = f"Tự chạy lúc {sched} hàng ngày" if sched else "Chờ lệnh chạy thủ công"
            self.lbl_phase.config(text=sched_text, fg="#94A3B8")

def main():
    root = tk.Tk()
    app = DesktopWidget(root)
    root.mainloop()

if __name__ == "__main__":
    main()
