# DROIDROUTER 9 - ANDROID VM & PROXY GATEWAY ENGINE

**DroidRouter 9** là giải pháp bảng điều khiển (Dashboard) cục bộ được thiết kế theo phong cách hiện đại của **9Router**, dành riêng cho việc quản lý, tự động hóa máy ảo Android (MuMuPlayer, LDPlayer, ADB) và định tuyến dịch vụ Proxy/Tài khoản ngay trên máy tính của bạn.

---

## 🌟 ĐẶC ĐIỂM NỔI BẬT

1. **Thay thế hoàn toàn Multi-Player thủ công**:
   - Bạn **không cần mở trình quản lý Multi** cồng kềnh của giả lập nữa.
   - Giao diện trực tiếp điều khiển qua CLI Engine (`MuMuManager.exe` / `ldconsole.exe` / `adb.exe`).
   - Thao tác 1-chạm: **Bật (Launch)**, **Tắt (Shutdown)**, **Khởi động lại (Reboot)**, **Ẩn/Hiện cửa sổ (Show/Hide)**, **Tự động xếp lưới (Arrange/Sort)**, **Clone**, **Xóa**, **Đổi tên**, và **Fake phần cứng (Android ID, IMEI, MAC Address)**.

2. **Bảng điều khiển Telemetry Realtime (Cyberpunk 9Router Style)**:
   - Theo dõi trạng thái toàn bộ máy ảo: Số lượng đang chạy / đã dừng.
   - Giám sát CPU, RAM, ổ đĩa phần cứng của máy chủ thời gian thực.
   - Trạng thái kết nối ADB Port tự động nhận diện cho từng máy ảo (Ví dụ: `127.0.0.1:16384`, `16416`,...).

3. **Màn hình điều khiển tương tác trực tiếp (Live Remote Screen)**:
   - Truyền hình ảnh màn hình trực tiếp từ máy ảo lên trình duyệt.
   - Hỗ trợ click chuột và vuốt (Swipe) điều khiển cảm ứng trực tiếp trên màn hình web.
   - Phím cứng ảo Android: **Back**, **Home**, **Recents**, **Power**, **Tăng/Giảm âm lượng**.
   - Gõ phím hoặc dán văn bản từ máy tính vào máy ảo chỉ với 1 click.
   - Cài đặt file APK kéo thả hoặc chọn file trực tiếp từ web.

4. **Két lưu trữ tài khoản & Tự động đăng nhập (Account Vault & 2FA)**:
   - Quản lý tài khoản: Google, TikTok, Facebook, Twitter/X, Telegram, Discord, hoặc Custom App.
   - **Tích hợp bộ tạo mã 2FA TOTP (RFC 6238)**: Tự động nhảy mã 6 số theo thời gian thực (30s) kèm thanh đếm ngược, click để sao chép.
   - **Tự động điền (Auto-Fill) vào máy ảo**:
     - *Inject Username*: Tự động gõ tên đăng nhập vào máy ảo qua ADB.
     - *Inject Password*: Tự động gõ mật khẩu vào máy ảo qua ADB.
     - *Inject 2FA Code*: Tự động tính toán mã OTP hiện tại và gõ ngay vào máy ảo.
     - *Auto-Fill Full*: Tự động điền tài khoản + Tab + mật khẩu.

5. **Proxy Router (Theo chuẩn 9Router Gateway)**:
   - Thêm danh sách Proxy HTTP / SOCKS5.
   - Kiểm tra trực tiếp độ trễ (Ping ms), IP thực tế, Quốc gia, Thành phố, Nhà mạng.
   - Gán Proxy cho từng máy ảo cụ thể và áp dụng tự động qua ADB (`settings put global http_proxy`).

6. **Điều khiển hàng loạt (Broadcast ADB Runner)**:
   - Gửi lệnh Shell/ADB đồng thời tới tất cả các máy ảo đang chạy (Ví dụ: Xóa cache ứng dụng, mở app, reboot đồng loạt, quay về Home).

7. **Bảo mật & Cài đặt Local**:
   - Chạy 100% trên máy tính của bạn tại `http://127.0.0.1:9090`.
   - Hỗ trợ mã PIN bảo vệ Dashboard (tùy chọn trong Settings).
   - Cơ sở dữ liệu SQLite cục bộ `data/droidrouter.db`.

---

## 🚀 CÁCH KHỞI CHẠY (1-CLICK RUN)

### Cách 1: Sử dụng File chạy nhanh (Khuyên dùng)
- Mở thư mục `d:\máy ảo`.
- Nhấp đúp vào file **`start.bat`**.
- Hệ thống sẽ tự động khởi động server và mở trình duyệt tại địa chỉ:
  👉 **`http://127.0.0.1:9090`**

### Cách 2: Chạy bằng lệnh Python
```powershell
cd "d:\máy ảo"
python main.py
```

---

## 📁 CẤU TRÚC DỰ ÁN

```
d:\máy ảo\
├── app\
│   ├── config.py             # Cấu hình đường dẫn MuMu/ADB, cổng port, PIN
│   ├── database.py           # Quản lý cơ sở dữ liệu SQLite cục bộ
│   ├── emulator_manager.py   # Lõi điều khiển MuMuManager & ADB CLI
│   ├── proxy_service.py      # Kiểm tra Proxy & Geolocation
│   ├── system_monitor.py     # Giám sát tài nguyên CPU, RAM, Disk
│   ├── totp_helper.py        # Bộ giải thuật sinh mã 2FA TOTP 6 số
│   └── routers\
│       ├── instances.py      # API quản lý máy ảo (bật/tắt/clone/xếp cửa sổ/...)
│       ├── screen.py         # API truyền hình ảnh & cảm ứng chuột/phím
│       ├── accounts.py       # API lưu trữ tài khoản & auto-fill ADB
│       ├── proxies.py        # API quản lý & test Proxy
│       ├── services.py       # API Broadcast lệnh hàng loạt
│       └── system.py         # API thống kê & cài đặt
├── data\                     # Thư mục lưu trữ Database và Settings
│   ├── droidrouter.db        # SQLite database
│   └── settings.json         # File cấu hình tùy chỉnh
├── static\                   # Giao diện Web SPA Cyberpunk
│   ├── css\style.css         # Bộ giao diện Dark Mode 9Router
│   ├── js\
│   │   ├── app.js            # Điều phối giao diện & Telemetry
│   │   ├── instances.js      # Module máy ảo
│   │   ├── remote.js         # Module màn hình điều khiển
│   │   ├── accounts.js       # Module tài khoản & 2FA
│   │   ├── proxies.js        # Module Proxy
│   │   └── services.js       # Module điều khiển hàng loạt
│   └── index.html            # Trang giao diện chính
├── main.py                   # Điểm khởi chạy FastAPI Backend
├── start.bat                 # File khởi chạy 1-click cho Windows
└── requirements.txt          # Danh sách thư viện Python
```
