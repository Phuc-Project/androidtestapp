import asyncio
import time
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..emulator_manager import emu_manager
from .. import play_automation
from ..campaign_runner import auto_assign_accounts
from ..database import (
    save_vm_profile, get_vm_profiles, delete_vm_profile,
    log_event, get_accounts, update_account, get_account_by_id
)

router = APIRouter(prefix="/api/instances", tags=["instances"])

class ProfileUpdate(BaseModel):
    custom_name: Optional[str] = ""
    tags: Optional[List[str]] = []
    assigned_proxy_id: Optional[int] = None
    assigned_account_id: Optional[int] = None
    auto_restart: Optional[bool] = False
    notes: Optional[str] = ""

class RenameRequest(BaseModel):
    name: str

class SimulationRequest(BaseModel):
    simu_key: str  # android_id, mac_address, imei
    simu_value: str

class BatchActionRequest(BaseModel):
    indices: List[str]

class AdbCommandRequest(BaseModel):
    command: str

class CreateVmRequest(BaseModel):
    version: Optional[str] = "15"

@router.get("")
def get_instances():
    vms = emu_manager.list_all_vms()
    accounts = get_accounts()
    
    # Map accounts by assigned_vm_index
    acc_map = {}
    for acc in accounts:
        v_idx = str(acc.get("assigned_vm_index", ""))
        if v_idx:
            acc_map[v_idx] = acc

    for v in vms:
        idx = str(v["index"])
        is_running = bool(v.get("is_running"))
        is_android_started = bool(v.get("is_android_started"))

        if is_running and is_android_started:
            # Android OS is fully booted: query live accounts via ADB dumpsys
            live_accs = emu_manager.get_android_logged_in_accounts(idx)
            if live_accs:
                v["has_account"] = True
                v["account_email"] = live_accs[0]
                v["account_name"] = "Google Account"
                v["account_id"] = acc_map.get(idx, {}).get("id")
                # Synchronize DB status if bound
                if idx in acc_map:
                    need_update = False
                    if acc_map[idx].get("status") != "logged_in":
                        acc_map[idx]["status"] = "logged_in"
                        need_update = True
                    if acc_map[idx].get("username") != live_accs[0]:
                        acc_map[idx]["username"] = live_accs[0]
                        need_update = True
                    if need_update:
                        update_account(acc_map[idx]["id"], acc_map[idx])
            else:
                # Android OS is running and fully booted, but does NOT have a Google account!
                v["has_account"] = False
                v["account_email"] = None
                v["account_id"] = None
                if idx in acc_map and acc_map[idx].get("status") == "logged_in":
                    acc_map[idx]["status"] = "active"
                    update_account(acc_map[idx]["id"], acc_map[idx])
        elif is_running:
            # Machine is starting/booting up (is_android_started is False):
            # Preserve current known state from DB to avoid flicker during boot
            if idx in acc_map and acc_map[idx].get("status") == "logged_in":
                v["has_account"] = True
                v["account_email"] = acc_map[idx]["username"]
                v["account_name"] = acc_map[idx]["name"]
                v["account_id"] = acc_map[idx]["id"]
            else:
                v["has_account"] = False
                v["account_email"] = None
                v["account_id"] = None
        else:
            # Stopped machine: check if previously verified logged in
            if idx in acc_map and acc_map[idx].get("status") == "logged_in":
                v["has_account"] = True
                v["account_email"] = acc_map[idx]["username"]
                v["account_name"] = acc_map[idx]["name"]
                v["account_id"] = acc_map[idx]["id"]
            else:
                v["has_account"] = False
                v["account_email"] = None
                v["account_id"] = None

    auto = play_automation.get_status()
    for v in vms:
        v["automation"] = auto.get(str(v["index"]))
    return {"success": True, "data": vms, "total": len(vms)}

@router.get("/{index}")
def get_instance(index: str):
    info = emu_manager.get_vm_info(index)
    if not info:
        raise HTTPException(status_code=404, detail=f"Instance #{index} not found")
    return {"success": True, "data": info}

@router.post("/{index}/launch")
def launch_instance(index: str, headless: Optional[bool] = None, auto_login: bool = True):
    """VMs always run hidden; Google login and testing are driven from the dashboard."""
    if headless is None:
        headless = True
    res = emu_manager.launch_vm(index, headless=headless)
    msg = f"VM #{index} đang khởi động (chạy ngầm)"
    if auto_login and res.get("success"):
        acc = next((a for a in get_accounts() if str(a.get("assigned_vm_index")) == str(index)), None)
        if acc and acc.get("status") != "logged_in" and acc.get("password"):
            r = play_automation.start_login_async(index)
            if r.get("success"):
                msg += " – sẽ tự đăng nhập Google " + acc["username"]
    return {"success": res.get("success", False), "headless": headless, "message": msg,
            "error": None if res.get("success") else (res.get("error") or res.get("output"))}

@router.post("/{index}/shutdown")
def shutdown_instance(index: str):
    res = emu_manager.shutdown_vm(index)
    return res

@router.post("/{index}/restart")
def restart_instance(index: str):
    res = emu_manager.restart_vm(index)
    return res

@router.post("/{index}/show")
def show_window(index: str):
    res = emu_manager.show_window(index)
    return res

@router.post("/{index}/hide")
def hide_window(index: str):
    res = emu_manager.hide_window(index)
    return res

@router.post("/arrange")
def arrange_windows():
    res = emu_manager.sort_windows()
    return res

@router.post("/batch-launch")
def batch_launch(req: BatchActionRequest, bg: BackgroundTasks):
    def _do_batch():
        accounts = get_accounts()
        logged_in_indices = {str(a.get("assigned_vm_index")) for a in accounts if a.get("status") == "logged_in"}
        for idx in req.indices:
            is_headless = True
            emu_manager.launch_vm(idx, headless=is_headless)
            time.sleep(2)
    bg.add_task(_do_batch)
    return {"success": True, "message": f"Queued launch for {len(req.indices)} instances"}

@router.post("/batch-shutdown")
def batch_shutdown(req: BatchActionRequest, bg: BackgroundTasks):
    def _do_batch():
        for idx in req.indices:
            emu_manager.shutdown_vm(idx)
            time.sleep(1)
    bg.add_task(_do_batch)
    return {"success": True, "message": f"Queued shutdown for {len(req.indices)} instances"}

@router.post("/create")
def create_instance(req: CreateVmRequest):
    res = emu_manager.create_vm(version=req.version or "15")
    return res

@router.post("/{index}/clone")
def clone_instance(index: str):
    res = emu_manager.clone_vm(index)
    return res

@router.post("/{index}/delete")
def delete_instance(index: str):
    res = emu_manager.delete_vm(index)
    if res.get("success"):
        # Unbind accounts mapped to this VM
        accounts = get_accounts()
        for a in accounts:
            if str(a.get("assigned_vm_index")) == str(index):
                a["assigned_vm_index"] = ""
                update_account(a["id"], a)
        # Remove profile from SQLite
        delete_vm_profile(str(index))
    return res

@router.post("/{index}/rename")
def rename_instance(index: str, req: RenameRequest):
    # Persist custom name to SQLite database
    profiles = get_vm_profiles()
    prof = profiles.get(str(index), {})
    prof["custom_name"] = req.name
    save_vm_profile(str(index), prof)
    # Also instruct MuMuManager
    res = emu_manager.rename_vm(index, req.name)
    return {"success": True, "name": req.name, "mumu_result": res}

@router.get("/{index}/settings")
def get_settings(index: str):
    settings = emu_manager.get_vm_settings(index)
    return {"success": True, "data": settings}

@router.post("/{index}/profile")
def update_profile(index: str, req: ProfileUpdate):
    data = req.model_dump()
    save_vm_profile(index, data)
    return {"success": True, "message": "Profile updated"}

@router.post("/{index}/simulation")
def set_simulation(index: str, req: SimulationRequest):
    res = emu_manager.set_instance_simulation(index, req.simu_key, req.simu_value)
    return res

@router.post("/{index}/adb")
def run_adb(index: str, req: AdbCommandRequest):
    args = req.command.strip().split()
    res = emu_manager.run_adb(index, args)
    return res

class ClusterOptimizeRequest(BaseModel):
    cpu: Optional[int] = 1
    mem_gb: Optional[float] = 2.0
    fps: Optional[int] = 20
    resolution: Optional[str] = "phone.3"

@router.post("/optimize-cluster")
def optimize_cluster(req: ClusterOptimizeRequest):
    res = emu_manager.apply_eco_profile("all")
    return {
        "success": res.get("success", False),
        "message": "Đã áp cấu hình tiết kiệm: 2 vCPU • 2GB RAM • 540x960 • 15 FPS • GPU thấp (máy đang chạy sẽ áp dụng sau khi khởi động lại)",
        "details": res,
    }

class GoogleLoginRequest(BaseModel):
    account_id: Optional[int] = None
    email: Optional[str] = None
    password: Optional[str] = None

@router.post("/{index}/google-login")
def vm_google_login(index: str, req: GoogleLoginRequest):
    """Assign an account if needed, then log it in automatically in the background (no MuMu window)."""
    accounts = get_accounts()
    if req.account_id:
        for a in accounts:
            if str(a.get("assigned_vm_index")) == str(index) and a["id"] != req.account_id:
                a["assigned_vm_index"] = ""
                update_account(a["id"], a)
        acc = get_account_by_id(req.account_id)
        if not acc:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
        acc["assigned_vm_index"] = str(index)
        update_account(acc["id"], acc)
    elif not any(str(a.get("assigned_vm_index")) == str(index) for a in accounts):
        auto_assign_accounts([str(index)])
    acc = next((a for a in get_accounts() if str(a.get("assigned_vm_index")) == str(index)), None)
    if not acc:
        raise HTTPException(status_code=400, detail="Kho chưa có tài khoản Google trống! Hãy thêm tài khoản vào kho trước.")
    res = play_automation.start_login_async(index)
    if not res.get("success"):
        raise HTTPException(status_code=409, detail=res["message"])
    return {"success": True, "email": acc["username"], "message": res["message"]}

@router.post("/auto-assign-google")
def auto_assign_google():
    n = auto_assign_accounts()
    return {"success": True, "assigned_count": n, "message": f"Đã tự động gán tài khoản cho {n} máy ảo"}

@router.post("/{index}/unlink-account")
def unlink_account(index: str):
    accounts = get_accounts()
    count = 0
    for a in accounts:
        if str(a.get("assigned_vm_index")) == str(index):
            a["assigned_vm_index"] = ""
            update_account(a["id"], a)
            count += 1
    return {"success": True, "message": f"Đã hủy liên kết tài khoản khỏi VM #{index}"}


class EnsureCountRequest(BaseModel):
    count: int = 12
    version: Optional[str] = "15"

@router.post("/ensure-count")
def ensure_vm_count(req: EnsureCountRequest, bg: BackgroundTasks):
    """Create enough VMs so the farm has `count` instances (one VM = one Play Console tester)."""
    target = max(1, min(int(req.count), 32))
    current = len(emu_manager.list_all_vms())
    missing = target - current
    if missing <= 0:
        return {"success": True, "created": 0, "message": f"Đã có đủ {current} máy ảo (mục tiêu {target})"}
    def _create_then_optimize():
        emu_manager.create_vm(req.version or "15", missing)
        emu_manager.apply_eco_profile("all")
    bg.add_task(_create_then_optimize)
    log_event("INFO", "EMULATOR", f"Queued creation of {missing} VM(s) to reach {target}")
    return {"success": True, "created": missing,
            "message": f"Đang tạo thêm {missing} máy ảo trong nền (mất vài phút), sau đó tự áp cấu hình tiết kiệm."}
