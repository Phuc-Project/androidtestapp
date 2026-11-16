import csv
import io
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..campaign_runner import campaign_runner, now_str, tester_accounts
from ..database import (
    get_checklist, set_checklist_item,
    create_campaign, get_campaign_testers, get_current_campaign, get_test_sessions,
    log_event, update_campaign, upsert_campaign_tester,
)
from ..emulator_manager import emu_manager

router = APIRouter(prefix="/api/campaign", tags=["campaign"])


class CampaignModel(BaseModel):
    app_name: str = ""
    package_name: str
    optin_url: Optional[str] = ""
    start_date: Optional[str] = None
    target_days: int = Field(14, ge=1, le=90)
    target_testers: int = Field(12, ge=1, le=100)
    session_minutes: int = Field(3, ge=1, le=60)
    events_per_min: int = Field(30, ge=0, le=600)
    max_parallel: int = Field(4, ge=1, le=12)
    app_profile: Optional[str] = "light"
    auto_run_time: Optional[str] = "09:00"
    shutdown_after: bool = True
    status: Optional[str] = "active"
    notes: Optional[str] = ""
    console_url: Optional[str] = None


class RunRequest(BaseModel):
    indices: Optional[List[str]] = None
    force: bool = False


class TargetRequest(BaseModel):
    indices: Optional[List[str]] = None


class OptinRequest(BaseModel):
    opted_in: bool = True


def _require_campaign() -> Dict[str, Any]:
    c = get_current_campaign()
    if not c:
        raise HTTPException(status_code=400, detail="Chưa có chiến dịch test. Hãy tạo chiến dịch trước.")
    return c


def _optin_url(c: Dict[str, Any]) -> str:
    return (c.get("optin_url") or "").strip() or f"https://play.google.com/apps/testing/{c['package_name']}"


def build_report(c: Dict[str, Any], vms: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    today = date.today()
    start = date.fromisoformat(c["start_date"])
    day_index = (today - start).days + 1  # 1-based; <=0 means not started yet
    target_days = int(c["target_days"])
    n_cols = min(max(target_days, day_index), 60)
    first = start if n_cols == max(target_days, day_index) else today - timedelta(days=n_cols - 1)
    days = [(first + timedelta(days=i)).isoformat() for i in range(n_cols)]

    sessions = get_test_sessions(c["id"])
    by_vm_date: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for s in sessions:
        by_vm_date.setdefault(s["vm_index"], {}).setdefault(s["run_date"], []).append(s)

    testers_state = get_campaign_testers(c["id"])
    accounts = tester_accounts()
    vms = vms if vms is not None else emu_manager.list_all_vms()
    vm_names = {str(v["index"]): v.get("name", "") for v in vms}
    all_idx = sorted(set(vm_names) | set(accounts) | set(testers_state),
                     key=lambda x: int(x) if x.isdigit() else 10**6)

    today_s = today.isoformat()
    rows = []
    for idx in all_idx:
        st = testers_state.get(idx, {})
        acc = accounts.get(idx)
        dates = by_vm_date.get(idx, {})
        matrix = {}
        for d in days:
            runs = dates.get(d, [])
            if any(r["status"] == "success" for r in runs):
                matrix[d] = "ok"
            elif d > today_s:
                matrix[d] = "future"
            elif d == today_s:
                matrix[d] = "failed" if runs else "pending"
            elif d < start.isoformat():
                matrix[d] = "none"
            else:
                matrix[d] = "failed" if runs else "missed"
        ok_dates = sorted(d for d, runs in dates.items() if any(r["status"] == "success" for r in runs))
        streak, cursor = 0, today if today_s in ok_dates else today - timedelta(days=1)
        ok_set = set(ok_dates)
        while cursor.isoformat() in ok_set:
            streak += 1
            cursor -= timedelta(days=1)
        last = max((r for runs in dates.values() for r in runs), key=lambda r: r["id"], default=None)
        rows.append({
            "vm_index": idx,
            "vm_name": vm_names.get(idx, f"VM #{idx}"),
            "vm_exists": idx in vm_names,
            "email": acc["username"] if acc else "",
            "is_tester": bool(acc),
            "opted_in": bool(st.get("opted_in")),
            "opted_in_at": st.get("opted_in_at", ""),
            "installed": bool(st.get("installed")),
            "version_name": st.get("version_name", ""),
            "last_check": st.get("last_check", ""),
            "days_active": len(ok_dates),
            "streak": streak,
            "today": matrix.get(today_s, "none"),
            "last_session": last,
            "matrix": matrix,
        })

    testers = [r for r in rows if r["is_tester"]]
    opted = [r for r in testers if r["opted_in"]]
    elapsed_full_days = max(0, day_index - 1)
    eligible = len(opted) >= int(c["target_testers"]) and elapsed_full_days >= target_days
    summary = {
        "day_index": day_index,
        "target_days": target_days,
        "target_testers": int(c["target_testers"]),
        "testers": len(testers),
        "opted_in": len(opted),
        "installed": sum(1 for r in testers if r["installed"]),
        "today_ok": sum(1 for r in testers if r["today"] == "ok"),
        "missed_total": sum(1 for r in testers for v in r["matrix"].values() if v == "missed"),
        "eligible": eligible,
        "days_left": max(0, target_days - elapsed_full_days),
    }
    return {"days": days, "today": today_s, "rows": rows, "summary": summary}


def _clean_console_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    m = re.match(r"https://play\.google\.com/console/u/(\d+)/developers/(\d+)/app/(\d+)", url)
    if not m:
        raise HTTPException(status_code=400, detail=(
            "Link Play Console chưa đúng. Mở app trong Play Console rồi copy link trên thanh địa chỉ, "
            "dạng https://play.google.com/console/u/0/developers/…/app/…/app-dashboard"))
    return f"https://play.google.com/console/u/{m.group(1)}/developers/{m.group(2)}/app/{m.group(3)}/app-dashboard"


def _campaign_view(c: Dict[str, Any]) -> Dict[str, Any]:
    c = dict(c)
    c["shutdown_after"] = bool(c.get("shutdown_after"))
    c["optin_url_effective"] = _optin_url(c)
    c["store_url"] = f"https://play.google.com/store/apps/details?id={c['package_name']}"
    return c


@router.get("")
def get_campaign_overview():
    c = get_current_campaign()
    if not c:
        return {"success": True, "campaign": None, "report": None, "job": campaign_runner.status()}
    return {"success": True, "campaign": _campaign_view(c), "report": build_report(c),
            "job": campaign_runner.status()}


@router.post("")
def save_campaign(req: CampaignModel):
    data = req.model_dump()
    data["package_name"] = data["package_name"].strip()
    if not emu_manager.is_valid_package(data["package_name"]):
        raise HTTPException(status_code=400, detail="Package name không hợp lệ (ví dụ đúng: com.congty.ungdung)")
    data["start_date"] = (data.get("start_date") or date.today().isoformat()).strip()
    try:
        date.fromisoformat(data["start_date"])
    except ValueError:
        raise HTTPException(status_code=400, detail="Ngày bắt đầu phải có dạng YYYY-MM-DD")
    t = (data.get("auto_run_time") or "").strip()
    if t and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t):
        raise HTTPException(status_code=400, detail="Giờ chạy tự động phải có dạng HH:MM (ví dụ 09:00)")
    data["auto_run_time"] = t
    url = (data.get("optin_url") or "").strip()
    if url and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Link opt-in phải bắt đầu bằng https://")
    data["optin_url"] = url
    data["shutdown_after"] = int(bool(data["shutdown_after"]))
    if data.get("console_url") is None:
        data.pop("console_url", None)
    else:
        data["console_url"] = _clean_console_url(data["console_url"])
    if data.get("status") not in ("active", "paused", "archived"):
        data["status"] = "active"

    current = get_current_campaign()
    if current:
        update_campaign(current["id"], data)
        log_event("INFO", "CAMPAIGN", f"Cập nhật chiến dịch #{current['id']} ({data['package_name']})")
        cid = current["id"]
    else:
        cid = create_campaign(data)
    return {"success": True, "id": cid, "message": "Đã lưu chiến dịch test"}


class QuickStartRequest(BaseModel):
    link: str
    package_name: Optional[str] = ""
    app_profile: Optional[str] = "light"
    auto_run_time: Optional[str] = "09:00"


ECO_DEFAULTS = {
    "target_days": 14, "target_testers": 12, "session_minutes": 3, "events_per_min": 30,
    "max_parallel": 4, "app_profile": "light", "auto_run_time": "09:00", "shutdown_after": 1, "status": "active",
}


def parse_app_link(link: str):
    """Return (package, optin_url) from a Play Store / opt-in link or a bare package name."""
    link = (link or "").strip()
    if not link:
        return "", ""
    if emu_manager.is_valid_package(link):
        return link, f"https://play.google.com/apps/testing/{link}"
    m = re.search(r"/apps/(?:testing|test)/([A-Za-z][A-Za-z0-9_.]+)", link)
    if m and emu_manager.is_valid_package(m.group(1)):
        pkg = m.group(1)
        base = link.split("?")[0] if "?" in link else link
        return pkg, base
    m = re.search(r"[?&]id=([A-Za-z][A-Za-z0-9_.]+)", link)
    if m and emu_manager.is_valid_package(m.group(1)):
        pkg = m.group(1)
        return pkg, f"https://play.google.com/apps/testing/{pkg}"
    if "play.google.com/apps/internaltest/" in link:
        m = re.search(r"[?&]id=([A-Za-z][A-Za-z0-9_.]+)", link)
        if m and emu_manager.is_valid_package(m.group(1)):
            return m.group(1), link
        return "", link
    # Fallback regex for URLs containing standard package format
    m = re.search(r"([A-Za-z][A-Za-z0-9_]+\.[A-Za-z0-9_.]+[A-Za-z0-9_])", link)
    if m and emu_manager.is_valid_package(m.group(1)):
        pkg = m.group(1)
        return pkg, f"https://play.google.com/apps/testing/{pkg}"
    return "", link


@router.post("/quick-start")
def quick_start(req: QuickStartRequest):
    """Paste a link -> campaign is created and the full pipeline starts (12 VMs, eco, login, join, install, use)."""
    if campaign_runner.is_running():
        raise HTTPException(status_code=409, detail="Đang có lượt test chạy – hãy dừng trước khi bắt đầu app mới.")
    pkg, optin = parse_app_link(req.link)
    pkg = pkg or (req.package_name or "").strip()
    if not emu_manager.is_valid_package(pkg):
        raise HTTPException(status_code=400, detail=(
            "Không đọc được package từ link. Dùng link 'Join on the web' dạng "
            "https://play.google.com/apps/testing/com.congty.app hoặc link Play Store ...details?id=com.congty.app"))
    
    app_prof = (req.app_profile or "light").lower()
    max_parallel = 2 if app_prof == "heavy" else 4
    auto_time = req.auto_run_time or "09:00"

    current = get_current_campaign()
    if current and current["package_name"] == pkg:
        data = {
            "optin_url": optin or current.get("optin_url") or "",
            "app_profile": app_prof,
            "max_parallel": max_parallel,
            "auto_run_time": auto_time,
            "status": "active"
        }
        update_campaign(current["id"], data)
        cid = current["id"]
    else:
        if current:
            update_campaign(current["id"], {"status": "archived"})
        data = dict(
            ECO_DEFAULTS,
            app_name=pkg.split(".")[-1].capitalize(),
            package_name=pkg,
            optin_url=optin,
            app_profile=app_prof,
            max_parallel=max_parallel,
            auto_run_time=auto_time,
            start_date=date.today().isoformat()
        )
        cid = create_campaign(data)
    c = get_current_campaign()
    res = campaign_runner.start(c, prepare=True)
    if not res["success"]:
        raise HTTPException(status_code=409, detail=res["message"])
    log_event("SUCCESS", "CAMPAIGN", f"Quick start chiến dịch #{cid} cho {pkg} ({app_prof.upper()} mode)")
    cluster_desc = "6 cụm × 2 máy" if app_prof == "heavy" else "3 cụm × 4 máy"
    return {
        "success": True,
        "package_name": pkg,
        "campaign_id": cid,
        "app_profile": app_prof,
        "max_parallel": max_parallel,
        "message": f"Đã nhận app {pkg} [{cluster_desc}] – đang chuẩn bị 12 máy và bắt đầu test tự động"
    }


@router.post("/archive")
def archive_campaign():
    c = _require_campaign()
    if campaign_runner.is_running():
        raise HTTPException(status_code=409, detail="Hãy dừng lượt test đang chạy trước.")
    update_campaign(c["id"], {"status": "archived"})
    log_event("WARNING", "CAMPAIGN", f"Kết thúc & lưu trữ chiến dịch #{c['id']}")
    return {"success": True, "message": "Đã kết thúc chiến dịch. Bạn có thể tạo chiến dịch mới."}


@router.post("/run")
def run_campaign(req: RunRequest):
    c = _require_campaign()
    if c["status"] != "active":
        raise HTTPException(status_code=400, detail="Chiến dịch đang tạm dừng.")
    res = campaign_runner.start(c, indices=req.indices, force=req.force)
    if not res["success"]:
        raise HTTPException(status_code=409, detail=res["message"])
    return res


@router.post("/stop")
def stop_campaign():
    return campaign_runner.stop()


@router.get("/job")
def job_status():
    return {"success": True, "job": campaign_runner.status()}


def _running_testers(indices: Optional[List[str]]) -> Dict[str, Any]:
    testers = tester_accounts()
    vms = {str(v["index"]): v for v in emu_manager.list_all_vms()}
    targets = [str(i) for i in indices] if indices else list(testers.keys())
    running, skipped = [], []
    for idx in targets:
        v = vms.get(idx)
        if v and v.get("is_android_started"):
            running.append(idx)
        else:
            skipped.append(idx)
    return {"running": running, "skipped": skipped}


@router.post("/open-optin")
def open_optin(req: TargetRequest):
    """Open the opt-in page on each running tester VM and bring its window up so the tester can tap 'Become a tester'."""
    c = _require_campaign()
    url = _optin_url(c)
    t = _running_testers(req.indices)
    results = {}
    for idx in t["running"]:
        r = emu_manager.open_url(idx, url)
        emu_manager.show_window(idx)
        results[idx] = {"success": bool(r.get("success"))}
    log_event("INFO", "CAMPAIGN", f"Mở link opt-in trên {len(t['running'])} máy")
    return {"success": True, "url": url, "results": results, "skipped": t["skipped"],
            "message": f"Đã mở link opt-in trên {len(t['running'])} máy"
                       + (f" (bỏ qua {len(t['skipped'])} máy chưa bật)" if t["skipped"] else "")}


@router.post("/open-store")
def open_store(req: TargetRequest):
    c = _require_campaign()
    t = _running_testers(req.indices)
    results = {}
    for idx in t["running"]:
        r = emu_manager.open_play_store(idx, c["package_name"])
        emu_manager.show_window(idx)
        results[idx] = {"success": bool(r.get("success"))}
    log_event("INFO", "CAMPAIGN", f"Mở Play Store ({c['package_name']}) trên {len(t['running'])} máy")
    return {"success": True, "results": results, "skipped": t["skipped"],
            "message": f"Đã mở trang Play Store trên {len(t['running'])} máy"
                       + (f" (bỏ qua {len(t['skipped'])} máy chưa bật)" if t["skipped"] else "")}


@router.post("/check-install")
def check_install(req: TargetRequest):
    c = _require_campaign()
    t = _running_testers(req.indices)
    results = {}
    for idx in t["running"]:
        info = emu_manager.get_package_info(idx, c["package_name"])
        fields = {"installed": int(info["installed"]), "version_name": info["version_name"], "last_check": now_str()}
        if info["installed"]:
            fields["opted_in"] = 1
        upsert_campaign_tester(c["id"], idx, **fields)
        if info["installed"] and not get_campaign_testers(c["id"]).get(idx, {}).get("opted_in_at"):
            upsert_campaign_tester(c["id"], idx, opted_in_at=now_str())
        results[idx] = info
    n = sum(1 for r in results.values() if r["installed"])
    return {"success": True, "results": results, "skipped": t["skipped"],
            "message": f"{n}/{len(results)} máy đang chạy đã cài app"
                       + (f" • {len(t['skipped'])} máy chưa bật nên chưa kiểm tra" if t["skipped"] else "")}


@router.post("/testers/{index}/optin")
def set_optin(index: str, req: OptinRequest):
    c = _require_campaign()
    upsert_campaign_tester(c["id"], index, opted_in=int(req.opted_in),
                           opted_in_at=now_str() if req.opted_in else "")
    return {"success": True, "message": f"VM #{index}: {'đã' if req.opted_in else 'chưa'} opt-in"}


@router.get("/sessions")
def list_sessions(limit: int = 100):
    c = _require_campaign()
    return {"success": True, "data": get_test_sessions(c["id"], limit=limit)}


@router.get("/report.csv")
def export_report_csv():
    c = _require_campaign()
    rep = build_report(c)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["VM", "Tên máy", "Tài khoản tester", "Opt-in", "Đã cài", "Phiên bản", "Số ngày test", "Chuỗi ngày"]
               + [f"Ngày {i + 1} ({d})" for i, d in enumerate(rep["days"])])
    label = {"ok": "OK", "missed": "BỎ LỠ", "failed": "LỖI", "pending": "CHỜ", "future": "", "none": ""}
    for r in rep["rows"]:
        if not r["is_tester"]:
            continue
        w.writerow([r["vm_index"], r["vm_name"], r["email"], "Có" if r["opted_in"] else "Chưa",
                    "Có" if r["installed"] else "Chưa", r["version_name"], r["days_active"], r["streak"]]
                   + [label.get(r["matrix"][d], "") for d in rep["days"]])
    w.writerow([])
    w.writerow(["Phiên test chi tiết"])
    w.writerow(["Ngày", "VM", "Tài khoản", "Bắt đầu", "Kết thúc", "Thời lượng (s)", "Trạng thái",
                "Phiên bản", "Crash", "ANR", "Ghi chú"])
    for s in reversed(get_test_sessions(c["id"])):
        w.writerow([s["run_date"], s["vm_index"], s["account_email"], s["started_at"], s["finished_at"],
                    s["duration_sec"], s["status"], s["version_name"], s["crashes"], s["anrs"], s["message"]])
    fname = f"closed-test-{c['package_name']}-{date.today().isoformat()}.csv"
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ==================== Play Console checklist ====================
CHECKLIST = [
    {"group": "setup", "items": [
        ("app_access", "Quyền truy cập ứng dụng", "Cho Google biết app có cần đăng nhập không; nếu có, cung cấp tài khoản demo."),
        ("ads", "Quảng cáo", "Khai báo app có chứa quảng cáo hay không."),
        ("content_rating", "Mức phân loại nội dung", "Trả lời bảng câu hỏi IARC."),
        ("target_audience", "Đối tượng mục tiêu và nội dung", "Chọn độ tuổi người dùng."),
        ("data_safety", "An toàn dữ liệu", "Khai báo dữ liệu app thu thập và chia sẻ."),
        ("gov_apps", "Ứng dụng của chính phủ", ""),
        ("financial", "Tính năng tài chính", ""),
        ("health", "Ứng dụng sức khoẻ", ""),
        ("privacy_policy", "Chính sách quyền riêng tư", "Đường link công khai tới chính sách."),
        ("category_contact", "Danh mục và thông tin liên hệ", ""),
        ("store_listing", "Trang thông tin trên Cửa hàng", "Tên, mô tả, biểu tượng 512×512, ảnh nổi bật 1024×500, ít nhất 2 ảnh chụp màn hình."),
    ]},
    {"group": "closed", "items": [
        ("countries", "Chọn quốc gia / khu vực", "Kiểm thử kín → Quốc gia/khu vực."),
        ("testers_list", "Thêm danh sách người thử nghiệm", "Tạo danh sách email gồm đủ 12 tài khoản tester."),
        ("release", "Tạo bản phát hành và tải tệp AAB lên", "Kiểm thử kín → Tạo bản phát hành mới."),
        ("rollout", "Xem xét và phát hành lên kênh kiểm thử kín", ""),
        ("send_review", "Gửi thay đổi để Google xét duyệt", "Tổng quan về xuất bản → Gửi thay đổi để xem xét."),
        ("closed_approved", "Google đã duyệt bản kiểm thử kín", "Thường mất vài giờ đến vài ngày. Sau đó link tham gia mới hoạt động."),
    ]},
    {"group": "production", "items": [
        ("apply_production", "Gửi đơn xin quyền phát hành chính thức", "Bảng điều khiển → Đăng ký quyền truy cập phát hành chính thức. Chỉ mở sau khi đủ 12 tester × 14 ngày."),
        ("production_approved", "Google đã chấp thuận đơn", "Google thường phản hồi trong khoảng 7 ngày."),
        ("production_release", "Tạo bản phát hành chính thức", "Phát hành → Chính thức → Tạo bản phát hành mới."),
    ]},
]
CHECKLIST_KEYS = {key for g in CHECKLIST for key, _, _ in g["items"]}


class ChecklistRequest(BaseModel):
    item: str
    done: bool


@router.get("/checklist")
def get_console_checklist():
    c = _require_campaign()
    state = get_checklist(c["id"])
    groups = []
    for g in CHECKLIST:
        groups.append({"group": g["group"], "items": [
            {"key": k, "label": label, "hint": hint,
             "done": bool(state.get(k, {}).get("done")), "done_at": state.get(k, {}).get("done_at", "")}
            for k, label, hint in g["items"]]})
    return {"success": True, "groups": groups, "console_url": c.get("console_url") or ""}


@router.post("/checklist")
def set_console_checklist(req: ChecklistRequest):
    c = _require_campaign()
    if req.item not in CHECKLIST_KEYS:
        raise HTTPException(status_code=400, detail="Mục không tồn tại")
    set_checklist_item(c["id"], req.item, req.done)
    return {"success": True}


@router.get("/summary")
def testing_summary():
    """Factual numbers about the closed test, taken from recorded sessions."""
    c = _require_campaign()
    rep = build_report(c)
    sessions = get_test_sessions(c["id"])
    ok = [s for s in sessions if s["status"] == "success"]
    versions = sorted({s["version_name"] for s in ok if s["version_name"]})
    testers = [r for r in rep["rows"] if r["is_tester"]]
    return {"success": True, "data": {
        "package_name": c["package_name"],
        "start_date": c["start_date"],
        "day_index": rep["summary"]["day_index"],
        "testers": len(testers),
        "opted_in": rep["summary"]["opted_in"],
        "days_with_activity": len({s["run_date"] for s in ok}),
        "sessions_ok": len(ok),
        "sessions_failed": len(sessions) - len(ok),
        "total_minutes": round(sum(s["duration_sec"] for s in ok) / 60),
        "crashes": sum(s["crashes"] for s in sessions),
        "anrs": sum(s["anrs"] for s in sessions),
        "versions": versions,
        "min_days_per_tester": min((r["days_active"] for r in testers), default=0),
    }}
