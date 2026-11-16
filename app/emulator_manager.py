import os
import re
import json
import time
import subprocess
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

from .config import load_settings
from .database import get_vm_profiles, log_event

class EmulatorManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._adb_connected_ports = set()
        self._acc_cache: Dict[str, Any] = {}

    def get_settings(self) -> dict:
        return load_settings()

    def _get_mumu_manager_path(self) -> str:
        s = self.get_settings()
        path = s.get("mumu_manager_path", r"C:\Program Files\Netease\MuMuPlayer\nx_main\MuMuManager.exe")
        if os.path.exists(path):
            return path
        # Fallback searches
        candidates = [
            r"C:\Program Files\Netease\MuMuPlayer\nx_main\MuMuManager.exe",
            r"D:\Program Files\Netease\MuMuPlayer\nx_main\MuMuManager.exe",
            r"C:\Program Files\Netease\MuMuPlayer-12.0\nx_main\MuMuManager.exe"
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return path

    def _get_adb_path(self) -> str:
        s = self.get_settings()
        path = s.get("adb_path", "adb")
        if os.path.exists(path):
            return path
        candidates = [
            r"C:\Users\Admin\AppData\Local\Android\Sdk\platform-tools\adb.exe",
            r"C:\Program Files\Netease\MuMuPlayer\nx_device\adb.exe",
            "adb.exe"
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return "adb"

    def _run_mumu_cmd(self, args: List[str], timeout: int = 15) -> Dict[str, Any]:
        exe = self._get_mumu_manager_path()
        if not os.path.exists(exe):
            return {"success": False, "error": f"MuMuManager.exe not found at {exe}", "output": ""}
        cmd = [exe] + args
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            out = res.stdout.strip()
            err = res.stderr.strip()
            return {
                "success": res.returncode == 0,
                "returncode": res.returncode,
                "output": out if out else err,
                "raw_stdout": out,
                "raw_stderr": err
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out", "output": ""}
        except Exception as e:
            return {"success": False, "error": str(e), "output": ""}

    def _get_vm_adb_port(self, index: str) -> Optional[int]:
        """Read exact ADB port from MuMuPlayer vms config"""
        mumu_path = Path(self._get_mumu_manager_path()).resolve()
        # Vms dir is typically sibling or parent of nx_main
        # e.g., C:\Program Files\Netease\MuMuPlayer\vms\MuMuPlayerGlobal-15.0-<index>\configs\vm_config.json
        base_dir = mumu_path.parent.parent
        vms_dir = base_dir / "vms"
        
        candidates = [
            vms_dir / f"MuMuPlayerGlobal-15.0-{index}" / "configs" / "vm_config.json",
            vms_dir / f"MuMuPlayerGlobal-12.0-{index}" / "configs" / "vm_config.json",
            vms_dir / f"MuMuPlayer-12.0-{index}" / "configs" / "vm_config.json",
            vms_dir / f"MuMuPlayerGlobal-{index}" / "configs" / "vm_config.json",
        ]
        for p in candidates:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        port_str = data.get("vm", {}).get("nat", {}).get("port_forward", {}).get("adb", {}).get("host_port")
                        if port_str:
                            return int(port_str)
                except Exception:
                    pass

        # Fallback calculation if not found: 16384 + (index * 32)
        try:
            idx = int(index)
            return 16384 + (idx * 32)
        except Exception:
            return 16384

    def connect_adb(self, index: str) -> bool:
        port = self._get_vm_adb_port(index)
        if not port:
            return False
        adb = self._get_adb_path()
        target = f"127.0.0.1:{port}"
        try:
            res = subprocess.run(
                [adb, "connect", target],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if "connected to" in res.stdout.lower() or "already connected" in res.stdout.lower():
                self._adb_connected_ports.add(target)
                return True
        except Exception:
            pass
        return False

    def list_all_vms(self) -> List[Dict[str, Any]]:
        res = self._run_mumu_cmd(["info", "-v", "all"], timeout=10)
        profiles = get_vm_profiles()
        vms = []

        if res["success"] and res["output"]:
            try:
                data = json.loads(res["output"])
                for idx_str, info in data.items():
                    is_running = bool(info.get("is_android_started") or info.get("is_process_started"))
                    disk_bytes = info.get("disk_size_bytes", 0)
                    disk_mb = round(disk_bytes / (1024 * 1024), 1) if disk_bytes else 0.0
                    adb_port = self._get_vm_adb_port(idx_str)

                    prof = profiles.get(str(idx_str), {})
                    vm_obj = {
                        "index": str(idx_str),
                        "name": prof.get("custom_name") or info.get("name", f"Android {idx_str}"),
                        "original_name": info.get("name", ""),
                        "android_version": info.get("android_version", "15.0"),
                        "is_running": is_running,
                        "is_android_started": bool(info.get("is_android_started")),
                        "is_process_started": bool(info.get("is_process_started")),
                        "disk_size_mb": disk_mb,
                        "adb_port": adb_port,
                        "adb_target": f"127.0.0.1:{adb_port}",
                        "tags": prof.get("tags", []),
                        "assigned_proxy_id": prof.get("assigned_proxy_id"),
                        "assigned_account_id": prof.get("assigned_account_id"),
                        "auto_restart": bool(prof.get("auto_restart", 0)),
                        "notes": prof.get("notes", "")
                    }
                    vms.append(vm_obj)
            except Exception as e:
                log_event("ERROR", "EMULATOR", f"Parse info error: {e}")

        # Sort vms by integer index
        try:
            vms.sort(key=lambda x: int(x["index"]))
        except Exception:
            pass

        return vms

    def get_vm_info(self, index: str) -> Optional[Dict[str, Any]]:
        res = self._run_mumu_cmd(["info", "-v", str(index)], timeout=5)
        if not res["success"] or not res["output"]:
            return None
        try:
            info = json.loads(res["output"])
            is_running = bool(info.get("is_android_started") or info.get("is_process_started"))
            adb_port = self._get_vm_adb_port(str(index))
            profiles = get_vm_profiles()
            prof = profiles.get(str(index), {})
            return {
                "index": str(index),
                "name": prof.get("custom_name") or info.get("name", f"Android {index}"),
                "is_running": is_running,
                "is_android_started": bool(info.get("is_android_started")),
                "is_process_started": bool(info.get("is_process_started")),
                "android_version": info.get("android_version", "15.0"),
                "adb_port": adb_port,
                "adb_target": f"127.0.0.1:{adb_port}",
                "disk_size_mb": round(info.get("disk_size_bytes", 0) / (1024 * 1024), 1)
            }
        except Exception:
            return None

    def is_vm_running(self, index: str) -> bool:
        info = self.get_vm_info(index)
        return bool(info and info.get("is_running"))

    def launch_vm(self, index: str, headless: bool = False) -> Dict[str, Any]:
        log_event("INFO", "EMULATOR", f"Launching VM #{index} (headless={headless})...")
        res = self._run_mumu_cmd(["control", "-v", str(index), "launch"], timeout=15)
        
        # In background, attempt to connect ADB and handle window visibility
        def _bg_post_launch():
            if headless:
                # Repeatedly ensure window is hidden once spawned
                for _ in range(4):
                    time.sleep(2.5)
                    self.hide_window(index)
            else:
                time.sleep(2.5)
                self.show_window(index)

            for _ in range(8):
                time.sleep(2)
                if self.connect_adb(str(index)):
                    break
        threading.Thread(target=_bg_post_launch, daemon=True).start()

        if res["success"]:
            log_event("SUCCESS", "EMULATOR", f"VM #{index} launched successfully")
        else:
            log_event("ERROR", "EMULATOR", f"Failed to launch VM #{index}: {res.get('error') or res.get('output')}")
        return res

    def shutdown_vm(self, index: str) -> Dict[str, Any]:
        log_event("INFO", "EMULATOR", f"Shutting down VM #{index}...")
        res = self._run_mumu_cmd(["control", "-v", str(index), "shutdown"], timeout=15)
        if res["success"]:
            log_event("SUCCESS", "EMULATOR", f"VM #{index} shut down")
        else:
            log_event("ERROR", "EMULATOR", f"Failed to shutdown VM #{index}: {res.get('error') or res.get('output')}")
        return res

    def restart_vm(self, index: str) -> Dict[str, Any]:
        log_event("INFO", "EMULATOR", f"Restarting VM #{index}...")
        res = self._run_mumu_cmd(["control", "-v", str(index), "restart"], timeout=20)
        return res

    def show_window(self, index: str) -> Dict[str, Any]:
        return self._run_mumu_cmd(["control", "-v", str(index), "show_window"], timeout=5)

    def hide_window(self, index: str) -> Dict[str, Any]:
        return self._run_mumu_cmd(["control", "-v", str(index), "hide_window"], timeout=5)

    def sort_windows(self) -> Dict[str, Any]:
        log_event("INFO", "EMULATOR", "Arranging all emulator windows...")
        return self._run_mumu_cmd(["sort"], timeout=10)

    def create_vm(self, version: str = "15", count: int = 1) -> Dict[str, Any]:
        count = max(1, int(count))
        log_event("INFO", "EMULATOR", f"Creating {count} new Android {version} VM(s)...")
        res = self._run_mumu_cmd(["create", "-n", str(count), "-ver", str(version)], timeout=60 + 45 * count)
        if res["success"]:
            log_event("SUCCESS", "EMULATOR", "New VM created successfully")
        return res

    def clone_vm(self, index: str) -> Dict[str, Any]:
        log_event("INFO", "EMULATOR", f"Cloning VM #{index}...")
        res = self._run_mumu_cmd(["clone", "-v", str(index)], timeout=120)
        if res["success"]:
            log_event("SUCCESS", "EMULATOR", f"VM #{index} cloned successfully")
        return res

    def delete_vm(self, index: str) -> Dict[str, Any]:
        log_event("WARNING", "EMULATOR", f"Deleting VM #{index}...")
        res = self._run_mumu_cmd(["delete", "-v", str(index)], timeout=60)
        if res["success"]:
            log_event("SUCCESS", "EMULATOR", f"VM #{index} deleted")
        return res

    def rename_vm(self, index: str, new_name: str) -> Dict[str, Any]:
        res = self._run_mumu_cmd(["rename", "-v", str(index), "-n", str(new_name)], timeout=10)
        return res

    def get_vm_settings(self, index: str) -> Dict[str, Any]:
        res = self._run_mumu_cmd(["setting", "-v", str(index), "-a"], timeout=10)
        if res["success"] and res["output"]:
            try:
                return json.loads(res["output"])
            except Exception:
                pass
        return {}

    def set_vm_simulation(self, index: str, simu_key: str, simu_value: str) -> Dict[str, Any]:
        """Change android_id, mac_address, or imei"""
        return self._run_mumu_cmd(["simulation", "-v", str(index), "-sk", simu_key, "-sv", simu_value], timeout=10)

    def run_adb(self, index: str, adb_args: List[str], timeout: int = 10) -> Dict[str, Any]:
        port = self._get_vm_adb_port(str(index))
        target = f"127.0.0.1:{port}"
        self.connect_adb(str(index))
        adb = self._get_adb_path()
        cmd = [adb, "-s", target] + adb_args
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return {
                "success": res.returncode == 0,
                "output": res.stdout.strip() if res.stdout.strip() else res.stderr.strip()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def capture_screenshot(self, index: str) -> Optional[bytes]:
        port = self._get_vm_adb_port(str(index))
        target = f"127.0.0.1:{port}"
        self.connect_adb(str(index))
        adb = self._get_adb_path()
        cmd = [adb, "-s", target, "exec-out", "screencap", "-p"]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                timeout=6,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            if res.returncode == 0 and len(res.stdout) > 1000:
                return res.stdout
        except Exception:
            pass
        return None

    def send_key(self, index: str, key_name: str) -> bool:
        """Supported keys: back, home, recents, power, volume_up, volume_down, enter, delete"""
        key_map = {
            "back": "4",
            "home": "3",
            "recents": "187",
            "app_switch": "187",
            "power": "26",
            "volume_up": "24",
            "volume_down": "25",
            "enter": "66",
            "delete": "67",
            "space": "62",
            "tab": "61"
        }
        keycode = key_map.get(key_name.lower(), key_name)
        res = self.run_adb(index, ["shell", "input", "keyevent", keycode])
        return res.get("success", False)

    def tap(self, index: str, x: int, y: int) -> bool:
        res = self.run_adb(index, ["shell", "input", "tap", str(x), str(y)])
        return res.get("success", False)

    def swipe(self, index: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        res = self.run_adb(index, ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)])
        return res.get("success", False)

    def type_text(self, index: str, text: str) -> bool:
        # `input text` uses %s for spaces; quote the whole argument for the device shell
        payload = str(text).replace(" ", "%s")
        res = self.run_adb(index, ["shell", "input text " + self._sh_quote(payload)])
        return res.get("success", False)

    def set_http_proxy(self, index: str, host: str, port: int) -> bool:
        if not host or not port:
            # Clear proxy
            res = self.run_adb(index, ["shell", "settings", "put", "global", "http_proxy", ":0"])
        else:
            res = self.run_adb(index, ["shell", "settings", "put", "global", "http_proxy", f"{host}:{port}"])
        return res.get("success", False)

    def launch_app(self, index: str, package: str) -> bool:
        res = self._run_mumu_cmd(["control", "-v", str(index), "app", "launch", "-pkg", package])
        if not res["success"]:
            # Fallback to adb monkey
            res = self.run_adb(index, ["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"])
            return res.get("success", False)
        return True

    def install_apk(self, index: str, apk_path: str) -> Dict[str, Any]:
        log_event("INFO", "EMULATOR", f"Installing APK on VM #{index}: {Path(apk_path).name}")
        res = self._run_mumu_cmd(["control", "-v", str(index), "app", "install", "-apk", apk_path], timeout=90)
        if not res["success"]:
            # Fallback to adb install
            res = self.run_adb(index, ["install", "-r", apk_path], timeout=90)
        return res

    def optimize_cluster_for_testing(self, cpu: int = 1, mem_gb: float = 2.0, fps: int = 20, resolution: str = "phone.3") -> Dict[str, Any]:
        """
        Applies optimal resource constraints across all instances for continuous 12-VM app testing:
        - 1 vCPU per VM (prevents CPU contention on 12-thread host)
        - 2.0 GB RAM per VM (24GB total for 12 VMs, perfectly within 32GB RAM)
        - phone.3 resolution (540x960, 240 DPI, saves 65% VRAM on RTX 4050)
        - 20 FPS cap + dynamic background reduction to 10 FPS
        - Audio processing disabled
        """
        args = [
            "setting", "-v", "all",
            "-k", "performance_mode", "-val", "custom",
            "-k", "performance_cpu.custom", "-val", str(cpu),
            "-k", "performance_mem.custom", "-val", f"{mem_gb:.6f}",
            "-k", "resolution_mode", "-val", resolution,
            "-k", "max_frame_rate", "-val", str(fps),
            "-k", "dynamic_adjust_frame_rate", "-val", "true",
            "-k", "dynamic_low_frame_rate_limit", "-val", "10",
            "-k", "system_volume_close", "-val", "true",
            "-k", "vertical_sync", "-val", "false"
        ]
        log_event("SUCCESS", "EMULATOR", f"Optimized all instances for App Testing: {cpu} vCPU, {mem_gb}GB RAM, {fps}FPS, {resolution}")
        return self._run_mumu_cmd(args, timeout=30)

    def force_stop_app(self, index: str, package: str) -> bool:
        res = self.run_adb(index, ["shell", "am", "force-stop", package])
        return res.get("success", False)

    def clear_app_data(self, index: str, package: str) -> bool:
        res = self.run_adb(index, ["shell", "pm", "clear", package])
        return res.get("success", False)

    def run_monkey_test(self, index: str, package: str, events: int = 300, throttle: int = 150) -> Dict[str, Any]:
        res = self.run_adb(index, ["shell", "monkey", "-p", package, "--throttle", str(throttle), "-v", str(events)], timeout=60)
        return res

    def get_android_logged_in_accounts(self, index: str, max_age: float = 15.0) -> List[str]:
        """Query actual accounts logged into Android OS via ADB dumpsys account (cached for max_age seconds)"""
        cached = self._acc_cache.get(str(index))
        if cached and max_age > 0 and time.time() - cached[0] < max_age:
            return list(cached[1])
        accounts = self._query_android_accounts(index)
        self._acc_cache[str(index)] = (time.time(), accounts)
        return accounts

    def _query_android_accounts(self, index: str) -> List[str]:
        try:
            res = self.run_adb(index, ["shell", "dumpsys", "account"], timeout=4)
            if res.get("success") and res.get("output"):
                out = res["output"]
                # Explicit check for Accounts: 0
                if re.search(r"Accounts:\s*0\b", out):
                    return []
                # Match actual logged-in Account entries: Account {name=..., type=com.google}
                matches = re.findall(r"Account\s*\{name=([^,\}\s]+),\s*type=com\.google\}", out)
                if matches:
                    return list(set(matches))
                matches2 = re.findall(r"Account\s*\{[^}]*type=com\.google[^}]*name=([^,\}\s]+)", out)
                if matches2:
                    return list(set(matches2))
        except Exception:
            pass
        return []

    def perform_google_login(self, index: str, email: str, password: str = "") -> Dict[str, Any]:
        """
        Automates Google Sign-In on the VM:
        1. Opens Google Account setup or Play Store
        2. Types email and password via ADB without requiring user manual input
        """
        self.connect_adb(index)
        log_event("INFO", "ACCOUNT", f"Automating Google Sign-In on VM #{index} for {email}")

        # Open Google Account Setup
        self.run_adb(index, ["shell", "am", "start", "-a", "android.settings.ADD_ACCOUNT_SETTINGS", "--esa", "extra_account_types", "com.google"])
        time.sleep(2.5)

        # Type email
        if email:
            self.type_text(index, email)
            time.sleep(0.5)
            self.send_key(index, "enter")
            time.sleep(2.5)

        # Type password if available
        if password:
            self.type_text(index, password)
            time.sleep(0.5)
            self.send_key(index, "enter")

        return {"success": True, "message": f"Đã tự động gửi thông tin đăng nhập Google ({email}) tới VM #{index}"}


    # ==================== Google Play Closed Testing helpers ====================
    @staticmethod
    def _sh_quote(s: str) -> str:
        return "'" + str(s).replace("'", "'\\''") + "'"

    @staticmethod
    def is_valid_package(pkg: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+", pkg or ""))

    def wait_for_boot(self, index: str, timeout: int = 240, stop_event: Optional[threading.Event] = None) -> bool:
        """Block until Android reports sys.boot_completed=1 (or timeout / stop requested)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if stop_event is not None and stop_event.is_set():
                return False
            res = self.run_adb(index, ["shell", "getprop", "sys.boot_completed"], timeout=6)
            if res.get("success") and (res.get("output") or "").strip() == "1":
                return True
            time.sleep(3)
        return False

    def open_url(self, index: str, url: str) -> Dict[str, Any]:
        cmd = f"am start -a android.intent.action.VIEW -d {self._sh_quote(url)}"
        return self.run_adb(index, ["shell", cmd], timeout=10)

    def open_play_store(self, index: str, package: str) -> Dict[str, Any]:
        url = f"market://details?id={package}"
        cmd = f"am start -a android.intent.action.VIEW -d {self._sh_quote(url)} -p com.android.vending"
        return self.run_adb(index, ["shell", cmd], timeout=10)

    def get_package_info(self, index: str, package: str) -> Dict[str, Any]:
        """Return {'installed': bool, 'version_name': str, 'version_code': str, 'installer': str}"""
        info = {"installed": False, "version_name": "", "version_code": "", "installer": ""}
        if not self.is_valid_package(package):
            return info
        res = self.run_adb(index, ["shell", "pm", "list", "packages", "-i", package], timeout=8)
        out = res.get("output") or ""
        for line in out.splitlines():
            m = re.match(r"package:(\S+)(?:\s+installer=(\S+))?", line.strip())
            if m and m.group(1) == package:
                info["installed"] = True
                info["installer"] = m.group(2) or ""
                break
        if info["installed"]:
            dump = self.run_adb(index, ["shell", "dumpsys", "package", package], timeout=10).get("output") or ""
            mv = re.search(r"versionName=(\S+)", dump)
            mc = re.search(r"versionCode=(\d+)", dump)
            info["version_name"] = mv.group(1) if mv else ""
            info["version_code"] = mc.group(1) if mc else ""
        return info

    def run_engagement(self, index: str, package: str, minutes: int = 3, events_per_min: int = 60,
                       stop_event: Optional[threading.Event] = None) -> Dict[str, Any]:
        """
        Simulate a real tester session: open the app, interact for `minutes` minutes
        (light monkey bursts restricted to the package, no system keys), then force-stop.
        events_per_min = 0 keeps the app in the foreground without random input.
        """
        import random
        started = time.time()
        crashes = anrs = 0
        self.launch_app(index, package)
        time.sleep(5)
        minutes = max(1, int(minutes))
        for _ in range(minutes):
            if stop_event is not None and stop_event.is_set():
                break
            if events_per_min <= 0:
                time.sleep(60)
                continue
            throttle = max(150, int(60000 / max(1, events_per_min)))
            args = [
                "shell", "monkey", "-p", package,
                "--pct-syskeys", "0", "--pct-anyevent", "0",
                "--ignore-crashes", "--ignore-timeouts", "--ignore-security-exceptions",
                "--throttle", str(throttle), "-s", str(random.randint(1, 10_000_000)),
                "-v", str(int(events_per_min)),
            ]
            res = self.run_adb(index, args, timeout=150)
            out = res.get("output") or ""
            crashes += out.count("// CRASH")
            anrs += out.count("// NOT RESPONDING")
        self.force_stop_app(index, package)
        return {"duration_sec": int(time.time() - started), "crashes": crashes, "anrs": anrs}

    # Economical profile for a 12-VM tester farm (VMs run in small batches, then shut down)
    ECO_PROFILE = {
        "performance_mode": "custom",
        "performance_cpu.custom": "2",
        "performance_mem.custom": "2.000000",
        "resolution_mode": "phone.3",          # 540x960 @ 240dpi
        "max_frame_rate": "15",
        "dynamic_adjust_frame_rate": "true",
        "dynamic_low_frame_rate_limit": "5",
        "gpu_mode": "low",
        "system_volume_close": "true",
        "vertical_sync": "false",
        "app_keptlive": "false",
    }

    def apply_eco_profile(self, target: str = "all") -> Dict[str, Any]:
        args = ["setting", "-v", str(target)]
        for k, v in self.ECO_PROFILE.items():
            args += ["-k", k, "-val", v]
        res = self._run_mumu_cmd(args, timeout=40)
        log_event("SUCCESS" if res.get("success") else "ERROR", "EMULATOR",
                  "Áp cấu hình tiết kiệm (2 vCPU, 2GB, 540x960, 15FPS, GPU thấp) cho " + str(target))
        return res

    def ui_dump(self, index: str) -> str:
        """Return the current UI hierarchy XML (uiautomator) or '' on failure."""
        res = self.run_adb(index, ["shell", "uiautomator dump /sdcard/dr_ui.xml >/dev/null 2>&1; cat /sdcard/dr_ui.xml"],
                           timeout=20)
        out = res.get("output") or ""
        i, j = out.find("<?xml"), out.rfind("</hierarchy>")
        return out[i:j + len("</hierarchy>")] if i >= 0 and j > i else ""

emu_manager = EmulatorManager()


