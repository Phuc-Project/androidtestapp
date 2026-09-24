import io
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Response, UploadFile, File

from ..emulator_manager import emu_manager

router = APIRouter(prefix="/api/screen", tags=["screen"])

class TapRequest(BaseModel):
    x: int
    y: int

class SwipeRequest(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    duration_ms: Optional[int] = 300

class KeyRequest(BaseModel):
    key: str  # back, home, recents, power, volume_up, volume_down, enter, delete, space

class TextRequest(BaseModel):
    text: str

class AppLaunchRequest(BaseModel):
    package: str

@router.get("/{index}/frame")
async def get_screen_frame(index: str):
    """
    Returns live screenshot frame of the specified VM.
    """
    data = emu_manager.capture_screenshot(index)
    if not data:
        # Generate transparent / placeholder 1x1 or error
        raise HTTPException(status_code=503, detail="Unable to capture frame. VM might be stopped.")
    return Response(content=data, media_type="image/png", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    })

@router.post("/{index}/tap")
async def send_tap(index: str, req: TapRequest):
    ok = emu_manager.tap(index, req.x, req.y)
    return {"success": ok}

@router.post("/{index}/swipe")
async def send_swipe(index: str, req: SwipeRequest):
    ok = emu_manager.swipe(index, req.x1, req.y1, req.x2, req.y2, req.duration_ms or 300)
    return {"success": ok}

@router.post("/{index}/key")
async def send_key(index: str, req: KeyRequest):
    ok = emu_manager.send_key(index, req.key)
    return {"success": ok}

@router.post("/{index}/text")
async def send_text(index: str, req: TextRequest):
    ok = emu_manager.type_text(index, req.text)
    return {"success": ok}

@router.post("/{index}/launch-app")
async def launch_app(index: str, req: AppLaunchRequest):
    ok = emu_manager.launch_app(index, req.package)
    return {"success": ok}

@router.post("/{index}/install-apk")
async def upload_and_install_apk(index: str, file: UploadFile = File(...)):
    import tempfile
    import shutil
    with tempfile.NamedTemporaryFile(delete=False, suffix=".apk") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        res = emu_manager.install_apk(index, tmp_path)
        return res
    finally:
        try:
            import os
            os.remove(tmp_path)
        except Exception:
            pass
