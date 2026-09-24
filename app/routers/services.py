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
