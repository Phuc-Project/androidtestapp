import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "droidrouter.db"
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "app_title": "DroidRouter 9",
    "host": "127.0.0.1",
    "port": 9090,
    "pin_enabled": False,
    "pin_code": "",
    "emulator_type": "mumu",  # "mumu", "ldplayer", "adb_only"
    "mumu_manager_path": r"C:\Program Files\Netease\MuMuPlayer\nx_main\MuMuManager.exe",
    "ldplayer_console_path": r"C:\LDPlayer\LDPlayer9\ldconsole.exe",
    "adb_path": r"C:\Users\Admin\AppData\Local\Android\Sdk\platform-tools\adb.exe",
    "auto_refresh_sec": 5,
    "auto_layout_cols": 3,
    "auto_layout_width": 450,
    "auto_layout_height": 800,
    "theme": "dark"
}

def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=2, ensure_ascii=False)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            merged = DEFAULT_SETTINGS.copy()
            merged.update(data)
            return merged
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(new_settings: dict) -> dict:
    current = DEFAULT_SETTINGS.copy()
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                current.update(json.load(f))
        except Exception:
            pass
    current.update(new_settings)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    return current
