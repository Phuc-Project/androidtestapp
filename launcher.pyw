import os
import sys
import time
import socket
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
LOG_FILE = DATA_DIR / "launcher.log"
SERVER_LOG = DATA_DIR / "server.log"

URL = "http://127.0.0.1:9090"
HOST = "127.0.0.1"
PORT = 9090

def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def is_server_running(host, port) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.6)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def start_server():
    if is_server_running(HOST, PORT):
        log("Server already running on port 9090")
        return

    log("Starting FastAPI server...")
    python_dir = Path(sys.executable).parent
    pythonw = python_dir / "pythonw.exe"
    exe = str(pythonw) if pythonw.exists() else sys.executable
    main_script = str(BASE_DIR / "main.py")

    server_log_fp = open(SERVER_LOG, "a", encoding="utf-8")

    flags = 0
    if os.name == 'nt':
        flags = subprocess.CREATE_NO_WINDOW

    p = subprocess.Popen(
        [exe, main_script, "--no-browser"],
        cwd=str(BASE_DIR),
        stdout=server_log_fp,
        stderr=server_log_fp,
        creationflags=flags
    )
    log(f"Spawned server process PID: {p.pid}")

    # Wait up to 10 seconds for server to be responsive
    for i in range(50):
        if is_server_running(HOST, PORT):
            log(f"Server became ready in {(i+1)*0.2:.1f}s")
            return
        time.sleep(0.2)

    log("Warning: Server did not respond within 10s")

def get_browser_exe():
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def launch_app_window():
    browser = get_browser_exe()
    log(f"Detected browser: {browser}")

    if browser:
        try:
            # Launch in app mode
            cmd = [
                browser,
                f"--app={URL}",
                "--window-size=1440,900"
            ]
            log(f"Executing: {' '.join(cmd)}")
            subprocess.Popen(cmd)
            log("Browser launched successfully")
            return
        except Exception as e:
            log(f"Browser launch failed: {e}")

    # Fallback to default system browser
    log("Falling back to webbrowser.open()")
    import webbrowser
    webbrowser.open(URL)

def main():
    log("=== Launcher Invoked ===")
    start_server()
    launch_app_window()
    log("=== Launcher Finished ===")

if __name__ == "__main__":
    main()
