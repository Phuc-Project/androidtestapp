from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..emulator_manager import emu_manager
from ..database import log_event

router = APIRouter(prefix="/api/services", tags=["services"])

class BroadcastCommandRequest(BaseModel):
    command: str
    target_indices: Optional[List[str]] = None  # None or empty = all running

@router.post("/broadcast-adb")
async def broadcast_adb_command(req: BroadcastCommandRequest):
    all_vms = emu_manager.list_all_vms()
    running_indices = [v["index"] for v in all_vms if v.get("is_running")]

    targets = req.target_indices if req.target_indices else running_indices
    if not targets:
        return {"success": False, "message": "No running VMs to execute command"}

    results = {}
    args = req.command.strip().split()
    log_event("INFO", "SERVICE", f"Broadcasting ADB command '{req.command}' to {len(targets)} VMs")

    for idx in targets:
        res = emu_manager.run_adb(idx, args)
        results[idx] = res

    return {"success": True, "executed_count": len(targets), "results": results}

@router.post("/reboot-all")
async def reboot_all_running(bg: BackgroundTasks):
    all_vms = emu_manager.list_all_vms()
    running_indices = [v["index"] for v in all_vms if v.get("is_running")]

    def _do_reboot():
        for idx in running_indices:
            emu_manager.restart_vm(idx)
    bg.add_task(_do_reboot)

    return {"success": True, "message": f"Queued reboot for {len(running_indices)} instances"}

class BatchAppActionRequest(BaseModel):
    action: str  # "launch", "stop", "clear", "monkey"
    package: str
    target_indices: Optional[List[str]] = None
    events: Optional[int] = 300

@router.post("/batch-app-action")
async def batch_app_action(req: BatchAppActionRequest):
    all_vms = emu_manager.list_all_vms()
    running_indices = [v["index"] for v in all_vms if v.get("is_running")]
    targets = req.target_indices if req.target_indices else running_indices

    if not targets:
        return {"success": False, "message": "No running VMs to execute action on"}

    pkg = req.package.strip()
    if not pkg:
        return {"success": False, "message": "Package name is required"}

    results = {}
    log_event("INFO", "TESTING", f"Batch '{req.action}' for package '{pkg}' on {len(targets)} VMs")

    for idx in targets:
        if req.action == "launch":
            ok = emu_manager.launch_app(idx, pkg)
            results[idx] = {"success": ok}
        elif req.action == "stop":
            ok = emu_manager.force_stop_app(idx, pkg)
            results[idx] = {"success": ok}
        elif req.action == "clear":
            ok = emu_manager.clear_app_data(idx, pkg)
            results[idx] = {"success": ok}
        elif req.action == "monkey":
            res = emu_manager.run_monkey_test(idx, pkg, events=req.events or 300)
            results[idx] = res
        else:
            results[idx] = {"success": False, "error": f"Unknown action: {req.action}"}

    return {"success": True, "action": req.action, "package": pkg, "executed_count": len(targets), "results": results}

from fastapi import UploadFile, File
import shutil, tempfile, os
from pathlib import Path

@router.post("/batch-install-apk")
async def batch_install_apk(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".apk") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        all_vms = emu_manager.list_all_vms()
        running_indices = [v["index"] for v in all_vms if v.get("is_running")]
        if not running_indices:
            return {"success": False, "message": "No running VMs to install APK on"}

        results = {}
        for idx in running_indices:
            res = emu_manager.install_apk(idx, tmp_path)
            results[idx] = res

        log_event("SUCCESS", "TESTING", f"Batch installed {file.filename} on {len(running_indices)} VMs")
        return {"success": True, "filename": file.filename, "installed_count": len(running_indices), "results": results}
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

