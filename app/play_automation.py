"""
On-device UI automation (via `uiautomator dump` + `input tap/text`) so the whole
tester workflow runs from the dashboard with VMs hidden in the background:

  * google_login      – add a Google account in Android Settings
  * join_and_install  – join the closed test on Play Store (web opt-in fallback) and install the app

Screens are matched by visible button labels (English + Vietnamese). Anything the
script cannot handle (captcha, phone verification, unknown screen) is reported as
"manual" so the user can finish it in the dashboard's live screen viewer.
"""
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .database import get_accounts, log_event, update_account
from .emulator_manager import emu_manager
from .totp_helper import generate_totp

# ---------------------------------------------------------------- status board
_status_lock = threading.Lock()
STATUS: Dict[str, Dict[str, Any]] = {}       # vm_index -> {task, state, msg, ts}
_busy: Dict[str, threading.Lock] = {}


def set_status(idx: str, task: str, state: str, msg: str):
    with _status_lock:
        STATUS[str(idx)] = {"task": task, "state": state, "msg": msg, "ts": datetime.now().strftime("%H:%M:%S")}


def get_status() -> Dict[str, Dict[str, Any]]:
    with _status_lock:
        return {k: dict(v) for k, v in STATUS.items()}


def vm_lock(idx: str) -> threading.Lock:
    with _status_lock:
        return _busy.setdefault(str(idx), threading.Lock())


# ---------------------------------------------------------------- UI primitives
class Node:
    __slots__ = ("text", "desc", "rid", "cls", "pkg", "clickable", "enabled", "password", "bounds")

    def __init__(self, a: Dict[str, str]):
        self.text = (a.get("text") or "").strip()
        self.desc = (a.get("content-desc") or "").strip()
        self.rid = a.get("resource-id") or ""
        self.cls = a.get("class") or ""
        self.pkg = a.get("package") or ""
        self.clickable = a.get("clickable") == "true"
        self.enabled = a.get("enabled") != "false"
        self.password = a.get("password") == "true"
        m = re.findall(r"\d+", a.get("bounds") or "")
        self.bounds = tuple(int(x) for x in m[:4]) if len(m) >= 4 else (0, 0, 0, 0)

    @property
    def label(self) -> str:
        return (self.text or self.desc).lower()

    @property
    def center(self):
        x1, y1, x2, y2 = self.bounds
        return (x1 + x2) // 2, (y1 + y2) // 2

    @property
    def visible(self) -> bool:
        x1, y1, x2, y2 = self.bounds
        return x2 > x1 and y2 > y1


class Screen:
    def __init__(self, nodes: List[Node]):
        self.nodes = [n for n in nodes if n.visible]
        self.blob = " | ".join(n.label for n in self.nodes if n.label)
        self.packages = {n.pkg for n in self.nodes}

    def has(self, *phrases: str) -> bool:
        return any(p.lower() in self.blob for p in phrases)

    def button(self, *labels: str, prefix: bool = False) -> Optional[Node]:
        wanted = [l.lower() for l in labels]
        for w in wanted:  # respect priority order of labels
            for n in self.nodes:
                lab = n.label
                if not lab or not n.enabled:
                    continue
                if lab == w or (prefix and lab.startswith(w)):
                    return n
        return None

    def find(self, *phrases: str) -> Optional[Node]:
        """Find first enabled/clickable node whose label contains any of the phrases."""
        wanted = [p.lower() for p in phrases]
        for w in wanted:
            for n in self.nodes:
                lab = n.label
                if not lab or not n.enabled:
                    continue
                if w in lab:
                    return n
        return None

    def edit_texts(self) -> List[Node]:
        return [n for n in self.nodes if "EditText" in n.cls and n.enabled]


class Driver:
    def __init__(self, idx: str, stop: Optional[threading.Event] = None):
        self.idx = str(idx)
        self.stop = stop or threading.Event()

    def screen(self) -> Screen:
        for _ in range(3):
            xml = emu_manager.ui_dump(self.idx)
            if xml:
                try:
                    root = ET.fromstring(xml)
                    return Screen([Node(e.attrib) for e in root.iter("node")])
                except ET.ParseError:
                    pass
            time.sleep(1.5)
        return Screen([])

    def tap(self, node: Node, pause: float = 2.0):
        x, y = node.center
        emu_manager.tap(self.idx, x, y)
        time.sleep(pause)

    def type_into(self, node: Node, text: str):
        self.tap(node, 0.6)
        if node.text and not node.password:
            # clear existing content
            emu_manager.run_adb(self.idx, ["shell", "input", "keyevent", "KEYCODE_MOVE_END"])
            emu_manager.run_adb(self.idx, ["shell", "input", "keyevent"] + ["KEYCODE_DEL"] * min(60, len(node.text) + 2))
        emu_manager.type_text(self.idx, text)
        time.sleep(0.8)

    def scroll_down(self):
        emu_manager.swipe(self.idx, 270, 760, 270, 300, 350)
        time.sleep(1.2)

    def sleep(self, sec: float) -> bool:
        return not self.stop.wait(sec)


# ---------------------------------------------------------------- label sets
NEXT = ["Next", "Tiếp theo", "Tiếp"]
AGREE = ["I agree", "Tôi đồng ý", "Agree", "Đồng ý", "Accept", "Chấp nhận", "Accept all", "Chấp nhận tất cả"]
DISMISS = ["Skip", "Bỏ qua", "Not now", "Để sau", "Không phải bây giờ", "No thanks", "Không, cảm ơn",
           "Remind me later", "Nhắc tôi sau", "Got it", "Đã hiểu", "Done", "Xong", "OK", "Continue", "Tiếp tục"]
MORE = ["More", "Thêm"]

LOGIN_FAIL = {
    "wrong password": "Sai mật khẩu", "mật khẩu không chính xác": "Sai mật khẩu", "sai mật khẩu": "Sai mật khẩu",
    "couldn't find your google account": "Email không tồn tại",
    "không tìm thấy tài khoản google": "Email không tồn tại",
    "account disabled": "Tài khoản bị vô hiệu hoá", "tài khoản bị vô hiệu hóa": "Tài khoản bị vô hiệu hoá",
}
LOGIN_MANUAL = {
    "verify it's you": "Google yêu cầu xác minh danh tính",
    "xác minh danh tính": "Google yêu cầu xác minh danh tính",
    "xác minh đó là bạn": "Google yêu cầu xác minh danh tính",
    "type the text you hear or see": "Google yêu cầu nhập captcha",
    "nhập văn bản bạn nghe hoặc nhìn thấy": "Google yêu cầu nhập captcha",
    "enter a phone number": "Google yêu cầu số điện thoại",
    "nhập số điện thoại": "Google yêu cầu số điện thoại",
    "check your phone": "Google yêu cầu xác nhận trên điện thoại",
    "kiểm tra điện thoại": "Google yêu cầu xác nhận trên điện thoại",
    "couldn't sign you in": "Google chặn đăng nhập", "không thể đăng nhập": "Google chặn đăng nhập",
}


def _assigned_account(idx: str) -> Optional[Dict[str, Any]]:
    for a in get_accounts():
        if str(a.get("assigned_vm_index") or "") == str(idx):
            return a
    return None


# ---------------------------------------------------------------- Google login
def google_login(idx: str, email: str, password: str, totp_secret: str = "",
                 stop: Optional[threading.Event] = None, timeout: int = 300) -> Dict[str, str]:
    d = Driver(idx, stop)
    email_l = email.lower()

    def logged_in() -> bool:
        return email_l in [a.lower() for a in emu_manager.get_android_logged_in_accounts(idx, max_age=0)]

    if logged_in():
        return {"state": "ok", "msg": f"Đã đăng nhập {email}"}

    set_status(idx, "login", "running", f"Mở màn hình đăng nhập Google ({email})")
    emu_manager.run_adb(idx, ["shell", "am", "start", "-a", "android.settings.ADD_ACCOUNT_SETTINGS",
                              "--esa", "extra_account_types", "com.google"])
    d.sleep(5)

    deadline = time.time() + timeout
    email_done_at = pw_done_at = 0.0
    totp_done_at = 0.0
    idle = 0
    it = 0
    while time.time() < deadline:
        if d.stop.is_set():
            return {"state": "stopped", "msg": "Đã dừng"}
        it += 1
        if it % 2 == 0 and logged_in():
            return {"state": "ok", "msg": f"Đăng nhập thành công {email}"}
        s = d.screen()

        for phrase, msg in LOGIN_FAIL.items():
            if s.has(phrase):
                return {"state": "failed", "msg": msg}
        for phrase, msg in LOGIN_MANUAL.items():
            if s.has(phrase):
                # TOTP challenge is solvable automatically
                if totp_secret and s.has("authenticator", "google authenticator", "ứng dụng xác thực"):
                    break
                return {"state": "manual", "msg": msg + ". Hoàn tất trong màn hình máy"}

        edits = s.edit_texts()
        pw_field = next((e for e in edits if e.password or "password" in e.rid.lower()), None)
        email_field = next((e for e in edits if "identifier" in e.rid.lower()), None)
        if not email_field and not pw_field and edits and s.has("email or phone", "email hoặc số điện thoại"):
            email_field = edits[0]

        # Account type picker (some images show a list first)
        g = s.button("Google")
        if g and not edits and s.has("add an account", "thêm tài khoản"):
            d.tap(g, 4)
            continue

        if email_field and time.time() - email_done_at > 20:
            set_status(idx, "login", "running", "Nhập email")
            if email_field.text.lower() != email_l:
                d.type_into(email_field, email)
            nb = d.screen().button(*NEXT)
            if nb:
                d.tap(nb, 5)
            else:
                emu_manager.send_key(idx, "enter"); d.sleep(5)
            email_done_at = time.time()
            idle = 0
            continue

        if pw_field and time.time() - pw_done_at > 20:
            if not password:
                return {"state": "manual", "msg": "Tài khoản chưa lưu mật khẩu – nhập tay trong màn hình máy"}
            set_status(idx, "login", "running", "Nhập mật khẩu")
            d.type_into(pw_field, password)
            nb = d.screen().button(*NEXT)
            if nb:
                d.tap(nb, 6)
            else:
                emu_manager.send_key(idx, "enter"); d.sleep(6)
            pw_done_at = time.time()
            idle = 0
            continue

        if edits and totp_secret and s.has("authenticator", "ứng dụng xác thực", "enter code", "nhập mã") \
                and time.time() - totp_done_at > 35:
            code = generate_totp(totp_secret)
            if code.get("valid"):
                set_status(idx, "login", "running", "Nhập mã 2FA")
                d.type_into(edits[0], code["code"])
                nb = d.screen().button(*NEXT)
                if nb:
                    d.tap(nb, 6)
                totp_done_at = time.time()
                continue

        btn = s.button(*AGREE) or s.button(*MORE) or s.button(*DISMISS)
        if btn:
            set_status(idx, "login", "running", f"Bấm '{btn.text or btn.desc}'")
            d.tap(btn, 3)
            idle = 0
            continue

        idle += 1
        if idle in (6, 12):  # a long-loading screen: try scrolling to reveal hidden buttons
            d.scroll_down()
        d.sleep(3)

    if logged_in():
        return {"state": "ok", "msg": f"Đăng nhập thành công {email}"}
    return {"state": "manual", "msg": "Quá thời gian đăng nhập – hãy kiểm tra trong màn hình máy"}


def ensure_logged_in(idx: str, stop: Optional[threading.Event] = None) -> Dict[str, str]:
    """Log the VM's assigned account in (VM must be booted). Updates the account row."""
    acc = _assigned_account(idx)
    live = emu_manager.get_android_logged_in_accounts(idx, max_age=0)
    if live:
        return {"state": "ok", "msg": f"Đã đăng nhập {live[0]}"}
    if not acc:
        return {"state": "manual", "msg": "Máy chưa được gán tài khoản Google"}
    res = google_login(idx, acc["username"], acc.get("password") or "", acc.get("two_factor_secret") or "", stop)
    acc = dict(acc)
    if res["state"] == "ok":
        acc["status"] = "logged_in"
    elif res["state"] == "failed":
        acc["status"] = "checkpoint"
    update_account(acc["id"], acc)
    log_event("SUCCESS" if res["state"] == "ok" else "WARNING", "ACCOUNT", f"VM #{idx} login {acc['username']}: {res['msg']}")
    return res


# ---------------------------------------------------------------- join test + install
JOIN = ["Become a tester", "Trở thành người thử nghiệm", "Accept invite", "Chấp nhận lời mời",
        "Join the beta", "Tham gia chương trình thử nghiệm", "Join test", "Tham gia thử nghiệm",
        "Join", "Tham gia", "Accept invitation", "Join the test"]
DOWNLOAD_ON_PLAY = [
    "download it on google play", "download on google play",
    "tải ứng dụng trên google play", "tải trên google play", "tải xuống trên google play",
    "cài đặt trên google play", "get it on google play", "download the public version on google play",
    "download the app", "tải ứng dụng"
]
INSTALL = ["Install", "Cài đặt", "Update", "Cập nhật"]
INSTALLED_MARKERS = ["Open", "Mở", "Uninstall", "Gỡ cài đặt"]
JOINED_TEXT = ["you're a tester", "you are a tester", "bạn là người thử nghiệm", "you're a beta tester",
               "bạn đã tham gia", "you've joined", "đã trở thành người thử nghiệm", "welcome to the testing"]
NOT_FOUND = ["item not found", "không tìm thấy mục", "isn't available", "không có sẵn", "not available"]
CHROME_FIRST_RUN = ["Accept & continue", "Chấp nhận và tiếp tục", "Yes, I'm in", "Tôi đồng ý",
                    "No thanks", "Không, cảm ơn", "Got it", "Đã hiểu", "Continue as", "Tiếp tục với tư cách"]
APP_CHOOSER = ["google play store", "cửa hàng google play", "play store",
               "just once", "chỉ một lần", "always", "luôn chọn"]
SKIP_SETUP = ["skip", "bỏ qua", "not now", "để sau", "no thanks", "không, cảm ơn"]
NETWORK_CONFIRM = ["download now", "tải xuống ngay", "over any network", "qua bất kỳ mạng nào",
                   "now (over any network)", "now", "ok", "tiếp tục", "continue"]
NOT_INVITED = ["isn't available for this account", "chưa dùng được cho tài khoản này",
               "hasn't been published yet", "chưa được xuất bản", "chưa được phát hành",
               "you must be invited", "bạn phải được mời", "không thể tham gia chương trình"]


def join_and_install(idx: str, package: str, optin_url: str, stop: Optional[threading.Event] = None,
                     timeout: int = 900) -> Dict[str, Any]:
    """Return {'state': ok|joined|manual|failed|stopped, 'msg', 'joined': bool, 'version_name'}."""
    d = Driver(idx, stop)
    joined = False

    def installed():
        info = emu_manager.get_package_info(idx, package)
        return info if info["installed"] else None

    info = installed()
    if info:
        return {"state": "ok", "msg": "App đã được cài", "joined": True, "version_name": info["version_name"]}

    # If optin_url is provided, start directly in browser so tester can join test first
    if optin_url:
        set_status(idx, "install", "running", "Mở link tham gia test trên trình duyệt")
        emu_manager.open_url(idx, optin_url)
        web_tried = True
        web_opened_at = time.time()
        d.sleep(6)
    else:
        set_status(idx, "install", "running", "Mở Google Play Store")
        emu_manager.open_play_store(idx, package)
        web_tried = False
        web_opened_at = 0.0
        d.sleep(6)

    deadline = time.time() + timeout
    last_open = time.time()
    scrolls = 0
    install_tapped_at = 0.0
    it = 0
    while time.time() < deadline:
        if d.stop.is_set():
            return {"state": "stopped", "msg": "Đã dừng", "joined": joined}
        it += 1
        if it % 3 == 0 or install_tapped_at:
            info = installed()
            if info:
                return {"state": "ok", "msg": f"Đã cài app v{info['version_name']}", "joined": True,
                        "version_name": info["version_name"]}

        s = d.screen()
        in_store = "com.android.vending" in s.packages
        in_chrome = "com.android.chrome" in s.packages

        if install_tapped_at:
            # downloading – just wait; Play Store shows a progress / "Cancel" button meanwhile
            if time.time() - install_tapped_at > 420:
                return {"state": "manual", "msg": "Tải app quá lâu – kiểm tra mạng trong màn hình máy", "joined": True}
            set_status(idx, "install", "running", "Đang tải & cài app từ Play Store")
            if s.button(*INSTALL) and time.time() - install_tapped_at > 25:
                install_tapped_at = 0.0  # button came back -> tap again below
            else:
                d.sleep(6)
                continue

        # Check for uninvited / unapproved release warning
        if s.has(*NOT_INVITED):
            return {
                "state": "manual",
                "msg": "Tài khoản chưa có trong danh sách tester trên Play Console hoặc bản phát hành kín chưa được Google duyệt",
                "joined": False
            }

        if s.has(*JOINED_TEXT):
            joined = True

        # Play Store / Android dialog: Skip payment method setup
        btn_skip = s.button(*SKIP_SETUP) or s.find(*SKIP_SETUP)
        if btn_skip and in_store:
            set_status(idx, "install", "running", "Bỏ qua thiết lập thanh toán")
            d.tap(btn_skip, 3)
            continue

        # Play Store dialog: Download over any network confirmation
        btn_net = s.button(*NETWORK_CONFIRM) or s.find(*NETWORK_CONFIRM)
        if btn_net and in_store and not s.button(*INSTALL):
            set_status(idx, "install", "running", "Xác nhận tải qua mạng")
            d.tap(btn_net, 4)
            install_tapped_at = time.time()
            continue

        # Android App Chooser (e.g. Open with Play Store)
        btn_chooser = s.find(*APP_CHOOSER)
        if btn_chooser:
            set_status(idx, "install", "running", "Mở bằng Cửa hàng Play")
            d.tap(btn_chooser, 4)
            continue

        # Play Store: Install button
        btn = s.button(*INSTALL)
        if btn and in_store:
            set_status(idx, "install", "running", "Bấm Cài đặt")
            d.tap(btn, 4)
            install_tapped_at = time.time()
            joined = True
            continue

        # Play Store: Installed markers
        if s.button(*INSTALLED_MARKERS) and in_store:
            info = installed()
            if info:
                return {"state": "ok", "msg": f"Đã cài app v{info['version_name']}", "joined": True,
                        "version_name": info["version_name"]}

        # Web Opt-in: Become a tester button
        btn_join = s.button(*JOIN, prefix=False) or s.find(*JOIN)
        if btn_join:
            set_status(idx, "install", "running", f"Tham gia chương trình test ('{btn_join.text or btn_join.desc}')")
            d.tap(btn_join, 4)
            joined = True
            continue

        # Web Opt-in: Download link after joining
        btn_dl = s.find(*DOWNLOAD_ON_PLAY)
        if btn_dl:
            set_status(idx, "install", "running", "Chuyển sang Play Store để cài đặt")
            d.tap(btn_dl, 5)
            joined = True
            continue

        # Chrome first run dialogs
        btn = s.button("Continue as", "Tiếp tục với tư cách", prefix=True) or s.button(*CHROME_FIRST_RUN) or s.find(*CHROME_FIRST_RUN)
        if btn and in_chrome:
            d.tap(btn, 3)
            continue

        btn = s.button(*AGREE)
        if btn:  # Terms on first launch
            d.tap(btn, 3)
            continue

        # Play Store: Item not found -> try web opt-in URL
        if s.has(*NOT_FOUND) or (joined is False and scrolls >= 4):
            if not web_tried and optin_url:
                set_status(idx, "install", "running", "Mở link opt-in trên trình duyệt")
                emu_manager.open_url(idx, optin_url)
                web_tried = True
                web_opened_at = time.time()
                scrolls = 0
                d.sleep(8)
                continue
            if not joined:
                return {"state": "manual",
                        "msg": "Không thấy nút tham gia test – kiểm tra email đã có trong danh sách tester trên Play Console",
                        "joined": False}

        if joined and not in_store and time.time() - last_open > 15:
            emu_manager.open_play_store(idx, package)
            last_open = time.time()
            d.sleep(6)
            continue

        if joined and time.time() - last_open > 60:
            # Google needs a few moments after opt-in before the Install button activates
            set_status(idx, "install", "running", "Đã tham gia – chờ Google kích hoạt quyền tải app")
            emu_manager.open_play_store(idx, package)
            last_open = time.time()
            d.sleep(6)
            continue

        if in_store and scrolls < 4 and not joined:
            d.scroll_down()
            scrolls += 1
            continue
        if web_tried and not joined and not in_store and time.time() - web_opened_at > 120:
            return {"state": "manual", "joined": False,
                    "msg": "Trang opt-in không hiện nút 'Trở thành người thử nghiệm' – xem trong màn hình máy"}
        d.sleep(4)

    if joined:
        return {"state": "joined", "msg": "Đã tham gia test, Google chưa cho tải app – lượt sau sẽ thử lại", "joined": True}
    return {"state": "manual", "msg": "Quá thời gian tham gia/cài app", "joined": False}


# ---------------------------------------------------------------- async helper (dashboard buttons)
def start_login_async(idx: str) -> Dict[str, Any]:
    lock = vm_lock(idx)
    if lock.locked():
        return {"success": False, "message": f"VM #{idx} đang bận một tác vụ tự động khác"}

    def _job():
        with lock:
            try:
                if not emu_manager.is_vm_running(idx):
                    set_status(idx, "login", "running", "Bật máy (chạy ngầm)")
                    emu_manager.launch_vm(idx, headless=True)
                set_status(idx, "login", "running", "Chờ Android khởi động")
                if not emu_manager.wait_for_boot(idx, timeout=240):
                    set_status(idx, "login", "failed", "Android không khởi động được")
                    return
                time.sleep(5)
                res = ensure_logged_in(idx)
                set_status(idx, "login", res["state"], res["msg"])
            except Exception as e:
                set_status(idx, "login", "failed", f"Lỗi: {e}")

    threading.Thread(target=_job, daemon=True, name=f"login-{idx}").start()
    return {"success": True, "message": f"Đang tự đăng nhập Google trên VM #{idx} (chạy ngầm)"}


UPDATE = ["Update", "Cập nhật"]


def update_if_available(idx: str, package: str, stop: Optional[threading.Event] = None,
                        timeout: int = 300) -> Dict[str, Any]:
    """Open the app's Play Store page; if an Update button is shown, tap it and wait for the new version."""
    d = Driver(idx, stop)
    before = emu_manager.get_package_info(idx, package).get("version_code", "")
    emu_manager.open_play_store(idx, package)
    found = None
    for _ in range(5):  # page needs a few seconds to load
        if not d.sleep(3):
            return {"updated": False, "msg": "Đã dừng"}
        s = d.screen()
        found = s.button(*UPDATE)
        if found or s.button(*INSTALLED_MARKERS):
            break
    if not found:
        emu_manager.send_key(idx, "home")
        return {"updated": False, "msg": "Đang ở bản mới nhất"}
    set_status(idx, "install", "running", "Đang cập nhật app lên bản mới")
    d.tap(found, 4)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not d.sleep(6):
            break
        info = emu_manager.get_package_info(idx, package)
        if info.get("version_code") and info["version_code"] != before:
            emu_manager.send_key(idx, "home")
            return {"updated": True, "msg": f"Đã cập nhật lên v{info['version_name']}"}
    emu_manager.send_key(idx, "home")
    return {"updated": False, "msg": "Cập nhật chưa xong, sẽ thử lại lượt sau"}
