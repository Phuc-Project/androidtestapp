import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from .config import DB_PATH

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Accounts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service TEXT NOT NULL DEFAULT 'custom',
        name TEXT NOT NULL,
        username TEXT NOT NULL,
        password TEXT NOT NULL DEFAULT '',
        two_factor_secret TEXT DEFAULT '',
        recovery_info TEXT DEFAULT '',
        assigned_vm_index TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active',
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Proxies table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS proxies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        proto TEXT NOT NULL DEFAULT 'http',
        host TEXT NOT NULL,
        port INTEGER NOT NULL,
        username TEXT DEFAULT '',
        password TEXT DEFAULT '',
        assigned_vm_index TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'unassigned',
        latency_ms INTEGER DEFAULT 0,
        outgoing_ip TEXT DEFAULT '',
        country TEXT DEFAULT '',
        city TEXT DEFAULT '',
        last_checked TEXT DEFAULT ''
    )
    """)

    # VM Profiles / Metadata table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vm_profiles (
        vm_index TEXT PRIMARY KEY,
        custom_name TEXT DEFAULT '',
        tags TEXT DEFAULT '[]',
        assigned_proxy_id INTEGER DEFAULT NULL,
        assigned_account_id INTEGER DEFAULT NULL,
        auto_restart INTEGER DEFAULT 0,
        notes TEXT DEFAULT ''
    )
    """)

    # System Logs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        level TEXT NOT NULL DEFAULT 'INFO',
        source TEXT NOT NULL DEFAULT 'SYSTEM',
        message TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

def log_event(level: str, source: str, message: str):
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO system_logs (timestamp, level, source, message) VALUES (?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), level, source, message)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Log Error: {e}")

def get_recent_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM system_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Account helpers
def get_accounts() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_account_by_id(account_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_account(data: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO accounts (service, name, username, password, two_factor_secret, recovery_info, assigned_vm_index, status, notes, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("service", "custom"),
        data.get("name", "Account"),
        data.get("username", ""),
        data.get("password", ""),
        data.get("two_factor_secret", ""),
        data.get("recovery_info", ""),
        data.get("assigned_vm_index", ""),
        data.get("status", "active"),
        data.get("notes", ""),
        now, now
    ))
    account_id = cursor.lastrowid
    conn.commit()
    conn.close()
    log_event("SUCCESS", "ACCOUNT", f"Created account '{data.get('name')}' ({data.get('username')})")
    return account_id

def update_account(account_id: int, data: Dict[str, Any]) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    UPDATE accounts SET
        service = ?, name = ?, username = ?, password = ?, two_factor_secret = ?,
        recovery_info = ?, assigned_vm_index = ?, status = ?, notes = ?, updated_at = ?
    WHERE id = ?
    """, (
        data.get("service", "custom"),
        data.get("name", "Account"),
        data.get("username", ""),
        data.get("password", ""),
        data.get("two_factor_secret", ""),
        data.get("recovery_info", ""),
        data.get("assigned_vm_index", ""),
        data.get("status", "active"),
        data.get("notes", ""),
        now,
        account_id
    ))
    conn.commit()
    conn.close()
    log_event("INFO", "ACCOUNT", f"Updated account ID #{account_id}")
    return True

def delete_account(account_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()
    log_event("WARNING", "ACCOUNT", f"Deleted account ID #{account_id}")
    return True

# Proxy helpers
def get_proxies() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM proxies ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_proxy(data: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO proxies (name, proto, host, port, username, password, assigned_vm_index, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("name", "Proxy"),
        data.get("proto", "http"),
        data.get("host", ""),
        int(data.get("port", 8080)),
        data.get("username", ""),
        data.get("password", ""),
        data.get("assigned_vm_index", ""),
        data.get("status", "unassigned")
    ))
    proxy_id = cursor.lastrowid
    conn.commit()
    conn.close()
    log_event("SUCCESS", "PROXY", f"Added proxy '{data.get('name')}' ({data.get('host')}:{data.get('port')})")
    return proxy_id

def update_proxy(proxy_id: int, data: Dict[str, Any]) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE proxies SET
        name = ?, proto = ?, host = ?, port = ?, username = ?, password = ?,
        assigned_vm_index = ?, status = ?, latency_ms = ?, outgoing_ip = ?, country = ?, city = ?, last_checked = ?
    WHERE id = ?
    """, (
        data.get("name", "Proxy"),
        data.get("proto", "http"),
        data.get("host", ""),
        int(data.get("port", 8080)),
        data.get("username", ""),
        data.get("password", ""),
        data.get("assigned_vm_index", ""),
        data.get("status", "unassigned"),
        int(data.get("latency_ms", 0)),
        data.get("outgoing_ip", ""),
        data.get("country", ""),
        data.get("city", ""),
        data.get("last_checked", ""),
        proxy_id
    ))
    conn.commit()
    conn.close()
    return True

def delete_proxy(proxy_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM proxies WHERE id = ?", (proxy_id,))
    conn.commit()
    conn.close()
    log_event("WARNING", "PROXY", f"Deleted proxy ID #{proxy_id}")
    return True

# VM Profiles helpers
def get_vm_profiles() -> Dict[str, Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vm_profiles")
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for r in rows:
        d = dict(r)
        try:
            d["tags"] = json.loads(d["tags"])
        except Exception:
            d["tags"] = []
        result[str(d["vm_index"])] = d
    return result

def save_vm_profile(vm_index: str, data: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor()
    tags_str = json.dumps(data.get("tags", []))
    cursor.execute("""
    INSERT INTO vm_profiles (vm_index, custom_name, tags, assigned_proxy_id, assigned_account_id, auto_restart, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(vm_index) DO UPDATE SET
        custom_name = excluded.custom_name,
        tags = excluded.tags,
        assigned_proxy_id = excluded.assigned_proxy_id,
        assigned_account_id = excluded.assigned_account_id,
        auto_restart = excluded.auto_restart,
        notes = excluded.notes
    """, (
        str(vm_index),
        data.get("custom_name", ""),
        tags_str,
        data.get("assigned_proxy_id"),
        data.get("assigned_account_id"),
        int(data.get("auto_restart", 0)),
        data.get("notes", "")
    ))
    conn.commit()
    conn.close()
