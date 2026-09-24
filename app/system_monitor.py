import os
import time
import psutil
from typing import Dict, Any

_BOOT_TIME = time.time()

def get_system_stats() -> Dict[str, Any]:
    try:
        cpu_pct = psutil.cpu_percent(interval=None)
        cpu_count = psutil.cpu_count(logical=True)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(os.path.splitdrive(os.getcwd())[0] or "C:")
        uptime_sec = int(time.time() - _BOOT_TIME)
        
        # Count emulator related processes
        running_emu_procs = 0
        for p in psutil.process_iter(['name']):
            try:
                name = (p.info['name'] or '').lower()
                if any(x in name for x in ['mumu', 'dnplayer', 'nox', 'memu', 'hd-player', 'qemu-system']):
                    running_emu_procs += 1
            except Exception:
                pass

        return {
            "cpu_percent": round(cpu_pct, 1),
            "cpu_count": cpu_count,
            "memory_percent": round(mem.percent, 1),
            "memory_used_gb": round(mem.used / (1024**3), 2),
            "memory_total_gb": round(mem.total / (1024**3), 2),
            "disk_percent": round(disk.percent, 1),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "uptime_seconds": uptime_sec,
            "emulator_processes": running_emu_procs
        }
    except Exception as e:
        return {
            "cpu_percent": 0.0,
            "cpu_count": 4,
            "memory_percent": 0.0,
            "memory_used_gb": 0.0,
            "memory_total_gb": 0.0,
            "disk_percent": 0.0,
            "disk_used_gb": 0.0,
            "disk_total_gb": 0.0,
            "uptime_seconds": 0,
            "emulator_processes": 0,
            "error": str(e)
        }
