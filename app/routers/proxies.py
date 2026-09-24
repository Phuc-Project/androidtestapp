from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from ..database import (
    get_proxies, create_proxy, update_proxy, delete_proxy,
    get_connection, log_event
)
from ..proxy_service import test_proxy
from ..emulator_manager import emu_manager

router = APIRouter(prefix="/api/proxies", tags=["proxies"])

class ProxyModel(BaseModel):
    name: str
    proto: str = "http"  # http, socks5
    host: str
    port: int
    username: Optional[str] = ""
    password: Optional[str] = ""
    assigned_vm_index: Optional[str] = ""
    status: Optional[str] = "unassigned"

@router.get("")
async def list_proxies():
    proxies = get_proxies()
    return {"success": True, "data": proxies, "total": len(proxies)}

@router.post("")
async def add_proxy(p: ProxyModel):
    new_id = create_proxy(p.model_dump())
    return {"success": True, "id": new_id, "message": "Proxy added successfully"}

@router.put("/{proxy_id}")
async def edit_proxy(proxy_id: int, p: ProxyModel):
    data = p.model_dump()
    data["id"] = proxy_id
    success = update_proxy(proxy_id, data)
    return {"success": success, "message": "Proxy updated"}

@router.delete("/{proxy_id}")
async def remove_proxy(proxy_id: int):
    success = delete_proxy(proxy_id)
    return {"success": success, "message": "Proxy deleted"}

@router.post("/{proxy_id}/test")
async def test_single_proxy(proxy_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM proxies WHERE id = ?", (proxy_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Proxy not found")

    p = dict(row)
    res = test_proxy(
        proto=p["proto"],
        host=p["host"],
        port=p["port"],
        username=p.get("username", ""),
        password=p.get("password", "")
    )

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "active" if res["success"] else "offline"

    p["status"] = status
    p["latency_ms"] = res.get("latency_ms", 0)
    p["outgoing_ip"] = res.get("outgoing_ip", "")
    p["country"] = res.get("country", "")
    p["city"] = res.get("city", "")
    p["last_checked"] = now_str

    update_proxy(proxy_id, p)
    log_event("INFO", "PROXY", f"Tested proxy '{p['name']}': status={status}, ping={p['latency_ms']}ms, ip={p['outgoing_ip']}")

    return {"success": True, "data": p, "test_result": res}

@router.post("/{proxy_id}/apply")
async def apply_proxy_to_vm(proxy_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM proxies WHERE id = ?", (proxy_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Proxy not found")

    p = dict(row)
    vm_idx = p.get("assigned_vm_index")
    if not vm_idx and vm_idx != "0":
        raise HTTPException(status_code=400, detail="No VM index assigned to this proxy")

    ok = emu_manager.set_http_proxy(vm_idx, p["host"], p["port"])
    if ok:
        log_event("SUCCESS", "PROXY", f"Applied proxy {p['name']} ({p['host']}:{p['port']}) to VM #{vm_idx}")
        return {"success": True, "message": f"Proxy applied to VM #{vm_idx}"}
    else:
        log_event("ERROR", "PROXY", f"Failed applying proxy {p['name']} to VM #{vm_idx}")
        return {"success": False, "error": f"Failed to apply proxy via ADB to VM #{vm_idx}"}

@router.post("/clear-vm/{vm_index}")
async def clear_vm_proxy(vm_index: str):
    ok = emu_manager.set_http_proxy(vm_index, "", 0)
    log_event("INFO", "PROXY", f"Cleared HTTP proxy on VM #{vm_index}")
    return {"success": ok, "message": f"Cleared proxy on VM #{vm_index}"}
