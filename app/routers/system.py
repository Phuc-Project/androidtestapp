from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from ..system_monitor import get_system_stats
from ..database import get_recent_logs, log_event
from ..config import load_settings, save_settings
from ..emulator_manager import emu_manager
from ..hardware_optimizer import clean_ram, clean_ssd, optimize_gpu, run_full_optimization

router = APIRouter(prefix="/api/system", tags=["system"])

class SettingsUpdate(BaseModel):
    app_title: Optional[str] = None
    pin_enabled: Optional[bool] = None
    pin_code: Optional[str] = None
    mumu_manager_path: Optional[str] = None
    adb_path: Optional[str] = None
    auto_refresh_sec: Optional[int] = None
    theme: Optional[str] = None

class PinVerifyRequest(BaseModel):
    pin: str

@router.get("/stats")
def system_stats():
    stats = get_system_stats()
    vms = emu_manager.list_all_vms()
    running_vms = sum(1 for v in vms if v.get("is_running"))
    stats["vms_total"] = len(vms)
    stats["vms_running"] = running_vms
    return {"success": True, "data": stats}

@router.get("/logs")
def system_logs(limit: int = 50):
    logs = get_recent_logs(limit=limit)
    return {"success": True, "data": logs}

@router.get("/settings")
def get_app_settings():
    s = load_settings()
    # Mask pin code
    masked = s.copy()
    if masked.get("pin_code"):
        masked["has_pin"] = True
        masked["pin_code"] = "******"
    else:
        masked["has_pin"] = False
    return {"success": True, "data": masked}

@router.post("/settings")
def update_app_settings(req: SettingsUpdate):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    saved = save_settings(updates)
    log_event("INFO", "SYSTEM", "System settings updated")
    return {"success": True, "data": saved, "message": "Settings saved"}

@router.post("/verify-pin")
def verify_pin(req: PinVerifyRequest):
    s = load_settings()
    if not s.get("pin_enabled"):
        return {"success": True, "authenticated": True}
    valid = (req.pin == s.get("pin_code"))
    return {"success": valid, "authenticated": valid}

@router.post("/optimize-hardware")
def optimize_system_hardware():
    res = run_full_optimization()
    return {"success": True, "data": res, "message": res["message"]}

@router.post("/clean-ram")
def trigger_clean_ram():
    res = clean_ram()
    return {"success": True, "data": res, "message": f"Đã giải phóng {res['ram_freed_mb']} MB RAM"}

@router.post("/optimize-gpu")
def trigger_optimize_gpu():
    res = optimize_gpu()
    return {"success": True, "data": res, "message": "Đã tối ưu hóa GPU và tắt animation"}

@router.post("/shutdown")
def shutdown_system():
    import threading, time, os
    def _exit():
        time.sleep(0.8)
        os._exit(0)
    threading.Thread(target=_exit, daemon=True).start()
    log_event("WARNING", "SYSTEM", "DroidRouter 9 Engine shutdown initiated")
    return {"success": True, "message": "Engine shutting down"}

