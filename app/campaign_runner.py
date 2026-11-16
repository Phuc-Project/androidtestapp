"""
Google Play Closed Testing - tester runner.

Google Play requires new personal developer accounts to run a closed test with
at least 12 opted-in testers for 14 consecutive days before applying for
production access. Each VM in the farm acts as one tester (one Google account).

For every tester VM the runner: boots it headless -> logs the Google account in
(if needed) -> joins the test & installs the app from Play Store (if needed) ->
uses the app for a few minutes -> records a session -> shuts the VM down.
`prepare=True` additionally creates missing VMs, applies the eco profile and
assigns free accounts first (the "paste link and go" flow).
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from . import play_automation
from .database import (
    add_test_session, get_accounts, get_campaign_testers, get_current_campaign, get_test_sessions,
    log_event, update_account, update_campaign, upsert_campaign_tester,
)
from .emulator_manager import emu_manager


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _idx_key(x: str) -> int:
    return int(x) if str(x).isdigit() else 10 ** 6


def tester_accounts() -> Dict[str, Dict[str, Any]]:
    """Map vm_index -> assigned Google account."""
    result = {}
    for acc in get_accounts():
        idx = str(acc.get("assigned_vm_index") or "")
        if idx != "":
            result[idx] = acc
    return result


def auto_assign_accounts(vm_indices: Optional[List[str]] = None) -> int:
    """Give every VM without an account one free Google account from the pool."""
    if vm_indices is None:
        vm_indices = [str(v["index"]) for v in emu_manager.list_all_vms()]
    accounts = get_accounts()
    existing = set(vm_indices)
    # release accounts bound to VMs that no longer exist
    for a in accounts:
        idx = str(a.get("assigned_vm_index") or "")
        if idx and idx not in existing and a.get("status") != "logged_in":
            a["assigned_vm_index"] = ""
            update_account(a["id"], a)
    taken = {str(a.get("assigned_vm_index")) for a in accounts if a.get("assigned_vm_index")}
    free = sorted(
        [a for a in accounts if not a.get("assigned_vm_index")
         and (a.get("service") or "google") == "google" and a.get("status") not in ("checkpoint", "banned")],
        key=lambda a: a["id"],
    )
    count = 0
    for idx in sorted(vm_indices, key=_idx_key):
        if idx in taken or not free:
            continue
        acc = free.pop(0)
        acc["assigned_vm_index"] = idx
        update_account(acc["id"], acc)
        count += 1
    if count:
        log_event("SUCCESS", "ACCOUNT", f"Tự gán {count} tài khoản Google cho máy trống")
    return count


class CampaignRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._scheduler: Optional[threading.Thread] = None
        self.state: Dict[str, Any] = self._empty_state()

    @staticmethod
    def _empty_state() -> Dict[str, Any]:
        return {
            "running": False, "trigger": "", "campaign_id": None, "phase": "",
            "started_at": "", "finished_at": "", "total": 0, "done": 0,
            "ok": 0, "failed": 0, "vms": {}, "log": [],
        }

    # ---------- state helpers ----------
    def status(self) -> Dict[str, Any]:
        with self._lock:
            s = dict(self.state)
            s["vms"] = {k: dict(v) for k, v in self.state["vms"].items()}
            s["log"] = list(self.state["log"][-150:])
            return s

    def _log(self, msg: str, level: str = "INFO"):
        line = {"ts": datetime.now().strftime("%H:%M:%S"), "level": level, "msg": msg}
        with self._lock:
            self.state["log"].append(line)
            if len(self.state["log"]) > 400:
                self.state["log"] = self.state["log"][-400:]
        if level in ("SUCCESS", "ERROR", "WARNING"):
            log_event(level, "CAMPAIGN", msg)

    def _set_vm(self, idx: str, **fields):
        with self._lock:
            self.state["vms"].setdefault(idx, {}).update(fields)

    def _phase(self, text: str):
        with self._lock:
            self.state["phase"] = text
        self._log(text)

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ---------- target selection ----------
    def _resolve_targets(self, campaign, indices, force):
        testers = tester_accounts()
        targets = [str(i) for i in (indices or sorted(testers.keys(), key=_idx_key))]
        targets = [i for i in targets if i in testers]
        if not targets:
            return [], testers, "Chưa có máy nào được gán tài khoản Google (tester)."
        existing = {str(v["index"]) for v in emu_manager.list_all_vms()}
        missing = [i for i in targets if i not in existing]
        targets = [i for i in targets if i in existing]
        if missing:
            self._log(f"Bỏ qua máy không tồn tại: {', '.join('#' + m for m in missing)}", "WARNING")
        if not targets:
            return [], testers, "Các máy được gán tài khoản không tồn tại trong MuMu."
        if not force:
            today = date.today().isoformat()
            done_today = {s["vm_index"] for s in get_test_sessions(campaign["id"])
                          if s["run_date"] == today and s["status"] == "success"}
            skipped = [i for i in targets if i in done_today]
            targets = [i for i in targets if i not in done_today]
            if not targets:
                return [], testers, f"Tất cả {len(skipped)} tester đã test xong hôm nay."
        return targets, testers, ""

    # ---------- control ----------
    def start(self, campaign: Dict[str, Any], indices: Optional[List[str]] = None,
              force: bool = False, trigger: str = "manual", prepare: bool = False) -> Dict[str, Any]:
        if self.is_running():
            return {"success": False, "message": "Đang có một lượt test chạy, hãy chờ hoặc dừng trước."}
        if not emu_manager.is_valid_package(campaign.get("package_name", "")):
            return {"success": False, "message": "Package name của chiến dịch không hợp lệ."}

        targets = None
        if not prepare:
            targets, testers, err = self._resolve_targets(campaign, indices, force)
            if not targets:
                return {"success": False, "message": err}  # keep the previous run's state visible
        with self._lock:
            self.state = self._empty_state()
            self.state.update({"running": True, "trigger": trigger, "campaign_id": campaign["id"],
                               "started_at": now_str()})

        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(campaign, targets, indices, force, prepare),
                                        daemon=True, name="campaign-runner")
        self._thread.start()
        if prepare:
            return {"success": True, "message": "Đang chuẩn bị 12 máy và bắt đầu test tự động"}
        return {"success": True, "message": f"Bắt đầu lượt test cho {len(targets)} máy", "targets": targets}

    def stop(self) -> Dict[str, Any]:
        if not self.is_running():
            return {"success": False, "message": "Không có lượt test nào đang chạy."}
        self._stop.set()
        self._log("Đã yêu cầu dừng – các máy đang chạy sẽ dừng sau bước hiện tại.", "WARNING")
        return {"success": True, "message": "Đang dừng lượt test..."}

    # ---------- preparation (paste-link flow) ----------
    def _prepare(self, campaign: Dict[str, Any]):
        target = int(campaign.get("target_testers") or 12)
        vms = emu_manager.list_all_vms()
        if len(vms) < target:
            n = target - len(vms)
            self._phase(f"Tạo thêm {n} máy ảo Android 15 cho đủ {target} tester (mất vài phút)...")
            res = emu_manager.create_vm("15", n)
            if not res.get("success"):
                self._log(f"Tạo máy ảo lỗi: {res.get('error') or res.get('output')}", "ERROR")
            for _ in range(20):  # wait until MuMu lists them
                if len(emu_manager.list_all_vms()) >= target or self._stop.is_set():
                    break
                time.sleep(3)
        self._phase("Áp cấu hình tiết kiệm cho toàn bộ máy (2 vCPU • 2GB • 540x960 • 15FPS • GPU thấp)")
        emu_manager.apply_eco_profile()
        self._phase("Gán tài khoản Google còn trống cho các máy")
        assigned = auto_assign_accounts()
        testers = tester_accounts()
        existing = {str(v["index"]) for v in emu_manager.list_all_vms()}
        n_testers = len([i for i in testers if i in existing])
        self._log(f"Đã gán thêm {assigned} tài khoản – hiện có {n_testers}/{target} máy có tài khoản",
                  "SUCCESS" if n_testers >= target else "WARNING")
        if n_testers < target:
            self._log(f"Cần thêm {target - n_testers} tài khoản Google vào kho để đủ {target} tester", "WARNING")

    # ---------- worker ----------
    def _run(self, campaign, targets, indices, force, prepare):
        try:
            if prepare:
                self._prepare(campaign)
                if self._stop.is_set():
                    return
                targets, testers, err = self._resolve_targets(campaign, indices, force)
                if not targets:
                    self._log(err, "WARNING")
                    return
            else:
                testers = tester_accounts()
            with self._lock:
                self.state["total"] = len(targets)
                self.state["vms"] = {i: {"step": "Đang chờ", "status": "queued", "email": testers[i]["username"]}
                                     for i in targets}

            # Determine cluster size based on app_profile or max_parallel:
            # Light app: max 4 VMs concurrently (3 clusters for 12 VMs)
            # Heavy app: max 2 VMs concurrently (6 clusters for 12 VMs)
            app_prof = (campaign.get("app_profile") or "light").lower()
            if app_prof == "heavy":
                cluster_size = 2
            elif app_prof == "light":
                cluster_size = 4
            else:
                cluster_size = max(1, min(12, int(campaign.get("max_parallel") or 4)))

            clusters = [targets[i:i + cluster_size] for i in range(0, len(targets), cluster_size)]
            total_clusters = len(clusters)

            self._phase(
                f"Test '{campaign['app_name'] or campaign['package_name']}' trên {len(targets)} máy "
                f"({total_clusters} cụm, tối đa {cluster_size} máy/lần [{app_prof.upper()}], {campaign['session_minutes']} phút/máy)"
            )
            self._log(
                f"Khởi động kiểm thử theo cụm: {total_clusters} cụm ({cluster_size} máy/cụm) – "
                f"Chế độ: {'App Nặng (2 máy/lần)' if cluster_size == 2 else 'App Nhẹ (4 máy/lần)'}"
            )

            for c_idx, cluster in enumerate(clusters, 1):
                if self._stop.is_set():
                    for idx in cluster:
                        self._set_vm(idx, step="Đã hủy", status="stopped")
                    continue

                cluster_label = f"Cụm {c_idx}/{total_clusters} (Máy {', '.join('#' + x for x in cluster)})"
                self._phase(f"Đang chạy {cluster_label}...")
                self._log(f"=== Bắt đầu {cluster_label} ===")

                with ThreadPoolExecutor(max_workers=len(cluster)) as pool:
                    futures = []
                    for i, idx in enumerate(cluster):
                        if self._stop.is_set():
                            self._set_vm(idx, step="Đã hủy", status="stopped")
                            continue
                        futures.append(pool.submit(self._process_vm_safe, campaign, idx, testers[idx]))
                        if i < len(cluster) - 1:
                            time.sleep(5)  # Stagger boot between VMs in cluster

                    for f in futures:
                        try:
                            f.result()
                        except Exception as e:
                            self._log(f"Lỗi thực thi trong cụm: {e}", "ERROR")

                # Clean shutdown of all VMs in completed cluster to free RAM/CPU
                if campaign.get("shutdown_after"):
                    for idx in cluster:
                        try:
                            if emu_manager.is_vm_running(idx):
                                emu_manager.shutdown_vm(idx)
                        except Exception:
                            pass

                # Automatically flush physical RAM working set after cluster finishes
                try:
                    from .hardware_optimizer import clean_ram
                    clean_ram()
                except Exception:
                    pass

                if c_idx < total_clusters and not self._stop.is_set():
                    self._phase(f"Hoàn thành {cluster_label}. Nghỉ 8s giải phóng RAM & CPU trước cụm tiếp theo...")
                    time.sleep(8)
        except Exception as e:
            self._log(f"Lượt test dừng do lỗi: {e}", "ERROR")
        finally:
            with self._lock:
                self.state["running"] = False
                self.state["phase"] = ""
                self.state["finished_at"] = now_str()
                ok, failed = self.state["ok"], self.state["failed"]
            self._log(f"Hoàn tất lượt test: {ok} thành công, {failed} lỗi/bỏ qua.",
                      "SUCCESS" if failed == 0 else "WARNING")

    def _process_vm_safe(self, campaign, idx, account):
        try:
            self._process_vm(campaign, idx, account)
        except Exception as e:  # never let one VM kill the batch
            self._finish(campaign, idx, account, time.time(), "failed", f"Lỗi không mong đợi: {e}")

    def _finish(self, campaign, idx, account, started_ts, status, message, version="", crashes=0, anrs=0):
        add_test_session({
            "campaign_id": campaign["id"], "vm_index": idx, "account_email": account.get("username", ""),
            "run_date": date.today().isoformat(),
            "started_at": datetime.fromtimestamp(started_ts).strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": now_str(), "duration_sec": int(time.time() - started_ts),
            "status": status, "version_name": version, "crashes": crashes, "anrs": anrs, "message": message,
        })
        with self._lock:
            self.state["done"] += 1
            if status == "success":
                self.state["ok"] += 1
            else:
                self.state["failed"] += 1
        self._set_vm(idx, step=message, status=status)
        self._log(f"VM #{idx}: {message}", "SUCCESS" if status == "success" else "WARNING")

    def _process_vm(self, campaign: Dict[str, Any], idx: str, account: Dict[str, Any]):
        lock = play_automation.vm_lock(idx)
        if not lock.acquire(blocking=False):
            return self._finish(campaign, idx, account, time.time(), "failed", "Máy đang bận tác vụ tự động khác")
        launched = {"by_us": False}
        status = "failed"
        try:
            status = self._process_vm_inner(campaign, idx, account, launched)
        finally:
            lock.release()
            is_batch = int(self.state.get("total", 0)) > 1
            keep_for_user = (not is_batch) and status in ("no_account", "not_installed") and self.state.get("trigger") != "auto"
            if launched["by_us"] and campaign.get("shutdown_after") and not keep_for_user:
                emu_manager.shutdown_vm(idx)

    def _process_vm_inner(self, campaign: Dict[str, Any], idx: str, account: Dict[str, Any],
                          launched: Dict[str, bool]) -> str:
        pkg = campaign["package_name"]
        optin_url = (campaign.get("optin_url") or "").strip() or f"https://play.google.com/apps/testing/{pkg}"
        started = time.time()
        stop = self._stop

        self._set_vm(idx, step="Khởi động máy (chạy ngầm)", status="running")
        if not emu_manager.is_vm_running(idx):
            emu_manager.launch_vm(idx, headless=True)
            launched["by_us"] = True

        self._set_vm(idx, step="Chờ Android khởi động")
        if not emu_manager.wait_for_boot(idx, timeout=300, stop_event=stop):
            if stop.is_set():
                self._finish(campaign, idx, account, started, "stopped", "Đã dừng theo yêu cầu")
                return "stopped"
            self._finish(campaign, idx, account, started, "failed", "Android không khởi động xong sau 5 phút")
            return "failed"
        time.sleep(5)  # let Google services settle after boot

        # 1) Google account
        self._set_vm(idx, step="Kiểm tra tài khoản Google")
        if not emu_manager.get_android_logged_in_accounts(idx, max_age=0):
            self._set_vm(idx, step=f"Tự đăng nhập Google ({account['username']})")
            res = play_automation.ensure_logged_in(idx, stop)
            play_automation.set_status(idx, "login", res["state"], res["msg"])
            if res["state"] != "ok":
                self._finish(campaign, idx, account, started, "no_account", f"Chưa đăng nhập được: {res['msg']}")
                return "no_account"

        # 2) Join test + install from Play Store
        self._set_vm(idx, step="Kiểm tra app đã cài")
        info = emu_manager.get_package_info(idx, pkg)
        if not info["installed"]:
            self._set_vm(idx, step="Tham gia test & cài app từ Play Store")
            res = play_automation.join_and_install(idx, pkg, optin_url, stop)
            play_automation.set_status(idx, "install", res["state"], res["msg"])
            if res.get("joined"):
                self._mark_opted_in(campaign["id"], idx)
            if res["state"] != "ok":
                upsert_campaign_tester(campaign["id"], idx, installed=0, last_check=now_str())
                self._finish(campaign, idx, account, started, "not_installed", res["msg"])
                return "not_installed"
            info = emu_manager.get_package_info(idx, pkg)
        else:
            self._set_vm(idx, step="Kiểm tra bản cập nhật trên Play Store")
            upd = play_automation.update_if_available(idx, pkg, stop)
            if upd["updated"]:
                self._log(f"VM #{idx}: {upd['msg']}", "SUCCESS")
                info = emu_manager.get_package_info(idx, pkg)
        upsert_campaign_tester(campaign["id"], idx, installed=int(info["installed"]),
                               version_name=info["version_name"], last_check=now_str())
        self._mark_opted_in(campaign["id"], idx)  # a closed-track app is only installable after opt-in

        # 3) Use the app
        minutes = int(campaign.get("session_minutes") or 3)
        self._set_vm(idx, step=f"Đang dùng app {minutes} phút (v{info['version_name'] or '?'})")
        eng = emu_manager.run_engagement(idx, pkg, minutes=minutes,
                                         events_per_min=int(campaign.get("events_per_min") or 0),
                                         stop_event=stop)
        if launched["by_us"] and campaign.get("shutdown_after"):
            self._set_vm(idx, step="Tắt máy")

        if stop.is_set() and eng["duration_sec"] < minutes * 60:
            self._finish(campaign, idx, account, started, "stopped", f"Dừng sớm sau {eng['duration_sec']}s",
                         info["version_name"], eng["crashes"], eng["anrs"])
            return "stopped"
        note = f"Đã dùng app {eng['duration_sec'] // 60}p{eng['duration_sec'] % 60:02d}s"
        if eng["crashes"] or eng["anrs"]:
            note += f" • {eng['crashes']} crash, {eng['anrs']} ANR"
        self._finish(campaign, idx, account, started, "success", note, info["version_name"], eng["crashes"], eng["anrs"])
        return "success"

    @staticmethod
    def _mark_opted_in(campaign_id: int, idx: str):
        t = get_campaign_testers(campaign_id).get(str(idx), {})
        fields = {"opted_in": 1}
        if not t.get("opted_in_at"):
            fields["opted_in_at"] = now_str()
        upsert_campaign_tester(campaign_id, idx, **fields)

    # ---------- daily scheduler ----------
    def start_scheduler(self):
        if self._scheduler and self._scheduler.is_alive():
            return
        self._scheduler = threading.Thread(target=self._scheduler_loop, daemon=True, name="campaign-scheduler")
        self._scheduler.start()

    def _scheduler_loop(self):
        while True:
            try:
                self._scheduler_tick()
            except Exception as e:
                print(f"[campaign-scheduler] {e}")
            time.sleep(30)

    def _scheduler_tick(self):
        c = get_current_campaign()
        if not c or c.get("status") != "active" or not c.get("auto_run_time"):
            return
        today = date.today().isoformat()
        if c.get("start_date", today) > today or c.get("last_auto_run_date") == today:
            return
        if datetime.now().strftime("%H:%M") < c["auto_run_time"] or self.is_running():
            return
        update_campaign(c["id"], {"last_auto_run_date": today})
        res = self.start(c, trigger="auto")
        log_event("INFO", "CAMPAIGN", f"Hẹn giờ {c['auto_run_time']}: {res['message']}")


campaign_runner = CampaignRunner()
