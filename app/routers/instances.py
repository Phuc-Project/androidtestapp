import asyncio
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..emulator_manager import emu_manager
from ..database import save_vm_profile, get_vm_profiles, log_event

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
async def get_instances():
    vms = emu_manager.list_all_vms()
    return {"success": True, "data": vms, "total": len(vms)}

@router.get("/{index}")
async def get_instance(index: str):
    info = emu_manager.get_vm_info(index)
    if not info:
        raise HTTPException(status_code=404, detail=f"Instance #{index} not found")
    return {"success": True, "data": info}

@router.post("/{index}/launch")
async def launch_instance(index: str):
    res = emu_manager.launch_vm(index)
    return res

@router.post("/{index}/shutdown")
async def shutdown_instance(index: str):
    res = emu_manager.shutdown_vm(index)
    return res

@router.post("/{index}/restart")
async def restart_instance(index: str):
    res = emu_manager.restart_vm(index)
    return res

@router.post("/{index}/show")
async def show_window(index: str):
    res = emu_manager.show_window(index)
    return res

@router.post("/{index}/hide")
async def hide_window(index: str):
    res = emu_manager.hide_window(index)
    return res

@router.post("/arrange")
async def arrange_windows():
    res = emu_manager.sort_windows()
    return res

@router.post("/batch-launch")
async def batch_launch(req: BatchActionRequest, bg: BackgroundTasks):
    def _do_batch():
        for idx in req.indices:
            emu_manager.launch_vm(idx)
            asyncio.run(asyncio.sleep(2))
    bg.add_task(_do_batch)
    return {"success": True, "message": f"Queued launch for {len(req.indices)} instances"}

@router.post("/batch-shutdown")
async def batch_shutdown(req: BatchActionRequest, bg: BackgroundTasks):
    def _do_batch():
        for idx in req.indices:
            emu_manager.shutdown_vm(idx)
            asyncio.run(asyncio.sleep(1))
    bg.add_task(_do_batch)
    return {"success": True, "message": f"Queued shutdown for {len(req.indices)} instances"}

@router.post("/create")
async def create_instance(req: CreateVmRequest):
    res = emu_manager.create_vm(version=req.version or "15")
    return res

@router.post("/{index}/clone")
async def clone_instance(index: str):
    res = emu_manager.clone_vm(index)
    return res

@router.post("/{index}/delete")
async def delete_instance(index: str):
    res = emu_manager.delete_vm(index)
    return res

@router.post("/{index}/rename")
async def rename_instance(index: str, req: RenameRequest):
    res = emu_manager.rename_vm(index, req.name)
    return res

@router.get("/{index}/settings")
async def get_settings(index: str):
    settings = emu_manager.get_vm_settings(index)
    return {"success": True, "data": settings}

@router.post("/{index}/profile")
async def update_profile(index: str, req: ProfileUpdate):
    data = req.model_dump()
    save_vm_profile(index, data)
    return {"success": True, "message": "Profile updated"}

@router.post("/{index}/simulation")
async def set_simulation(index: str, req: SimulationRequest):
    res = emu_manager.set_instance_simulation(index, req.simu_key, req.simu_value)
    return res

@router.post("/{index}/adb")
async def run_adb(index: str, req: AdbCommandRequest):
    args = req.command.strip().split()
    res = emu_manager.run_adb(index, args)
    return res

class ClusterOptimizeRequest(BaseModel):
    cpu: Optional[int] = 1
    mem_gb: Optional[float] = 2.0
    fps: Optional[int] = 20
    resolution: Optional[str] = "phone.3"

@router.post("/optimize-cluster")
async def optimize_cluster(req: ClusterOptimizeRequest):
    res = emu_manager.optimize_cluster_for_testing(
        cpu=req.cpu or 1,
        mem_gb=req.mem_gb or 2.0,
        fps=req.fps or 20,
        resolution=req.resolution or "phone.3"
    )
    return {
        "success": res.get("success", False),
        "message": f"Cluster optimized for app testing: {req.cpu} vCPU, {req.mem_gb}GB RAM, {req.fps} FPS (540x960)",
        "details": res
    }

