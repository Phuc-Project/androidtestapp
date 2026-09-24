import os
import sys
import time
import socket
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
URL = "http://127.0.0.1:9090"
HOST = "127.0.0.1"
PORT = 9090

def is_server_running(host, port) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def start_server():
    if is_server_running(HOST, PORT):
        return

    # Look for pythonw or python
    python_dir = Path(sys.executable).parent
    pythonw = python_dir / "pythonw.exe"
    exe = str(pythonw) if pythonw.exists() else sys.executable

    main_script = str(BASE_DIR / "main.py")
    
    # Start silently in background without console window
    flags = 0
    if os.name == 'nt':
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

    subprocess.Popen(
        [exe, main_script],
        cwd=str(BASE_DIR),
        creationflags=flags,
        close_fds=True
    )

    # Wait up to 6 seconds for server to be responsive
    for _ in range(30):
        if is_server_running(HOST, PORT):
            break
        time.sleep(0.2)

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
    if browser:
        # Launch standalone frameless app window like native desktop app
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        cmd = [
            browser,
            f"--app={URL}",
            "--window-size=1440,900"
        ]
        subprocess.Popen(cmd, creationflags=flags)
    else:
        import webbrowser
        webbrowser.open(URL)

def main():
    start_server()
    launch_app_window()

if __name__ == "__main__":
    main()
