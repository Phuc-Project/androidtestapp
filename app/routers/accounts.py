import asyncio
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from ..database import (
    get_accounts, get_account_by_id, create_account,
    update_account, delete_account, log_event
)
from ..totp_helper import generate_totp
from ..emulator_manager import emu_manager

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

class AccountModel(BaseModel):
    service: str = "custom"  # google, tiktok, facebook, twitter, telegram, custom
    name: str
    username: str
    password: Optional[str] = ""
    two_factor_secret: Optional[str] = ""
    recovery_info: Optional[str] = ""
    assigned_vm_index: Optional[str] = ""
    status: Optional[str] = "active"  # active, logged_in, checkpoint, banned, idle
    notes: Optional[str] = ""

class AutoFillRequest(BaseModel):
    target_vm_index: str
    field: str = "all"  # "username", "password", "totp", "all"

@router.get("")
async def list_accounts():
    accounts = get_accounts()
    # Augment with live TOTP code if secret exists
    for acc in accounts:
        secret = acc.get("two_factor_secret") or ""
        if secret:
            totp_info = generate_totp(secret)
            acc["totp"] = totp_info
        else:
            acc["totp"] = None
    return {"success": True, "data": accounts, "total": len(accounts)}

@router.post("")
async def add_account(acc: AccountModel):
    new_id = create_account(acc.model_dump())
    return {"success": True, "id": new_id, "message": "Account created successfully"}

@router.get("/{account_id}")
async def get_account(account_id: int):
    acc = get_account_by_id(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    secret = acc.get("two_factor_secret") or ""
    if secret:
        acc["totp"] = generate_totp(secret)
    return {"success": True, "data": acc}

@router.put("/{account_id}")
async def edit_account(account_id: int, acc: AccountModel):
    success = update_account(account_id, acc.model_dump())
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"success": True, "message": "Account updated successfully"}

@router.delete("/{account_id}")
async def remove_account(account_id: int):
    success = delete_account(account_id)
    return {"success": success, "message": "Account deleted"}

@router.get("/{account_id}/totp")
async def get_account_totp(account_id: int):
    acc = get_account_by_id(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    secret = acc.get("two_factor_secret") or ""
    if not secret:
        return {"success": False, "error": "No 2FA secret set for this account"}
    totp = generate_totp(secret)
    return {"success": True, "data": totp}

@router.post("/{account_id}/autofill")
async def autofill_account(account_id: int, req: AutoFillRequest):
    acc = get_account_by_id(account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")

    target_vm = req.target_vm_index or acc.get("assigned_vm_index")
    if not target_vm and target_vm != "0":
        raise HTTPException(status_code=400, detail="No target VM specified or assigned")

    field = req.field.lower()
    log_event("INFO", "ACCOUNT", f"Auto-filling '{field}' for account {acc['name']} to VM #{target_vm}")

    if field == "username":
        ok = emu_manager.type_text(target_vm, acc["username"])
        return {"success": ok, "message": f"Typed username into VM #{target_vm}"}

    elif field == "password":
        if not acc.get("password"):
            return {"success": False, "error": "Account has no password saved"}
        ok = emu_manager.type_text(target_vm, acc["password"])
        return {"success": ok, "message": f"Typed password into VM #{target_vm}"}

    elif field == "totp":
        secret = acc.get("two_factor_secret")
        if not secret:
            return {"success": False, "error": "Account has no 2FA secret"}
        totp = generate_totp(secret)
        if not totp["valid"]:
            return {"success": False, "error": totp["error"]}
        ok = emu_manager.type_text(target_vm, totp["code"])
        return {"success": ok, "code": totp["code"], "message": f"Injected 2FA code {totp['code']} into VM #{target_vm}"}

    elif field == "all":
        # Type username, tab, type password
        emu_manager.type_text(target_vm, acc["username"])
        await asyncio.sleep(0.5)
        emu_manager.send_key(target_vm, "tab")
        await asyncio.sleep(0.5)
        if acc.get("password"):
            emu_manager.type_text(target_vm, acc["password"])
        return {"success": True, "message": f"Auto-filled username and password into VM #{target_vm}"}

    return {"success": False, "error": f"Unknown field '{field}'"}
