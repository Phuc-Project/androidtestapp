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

    # Google Play Closed Testing campaigns
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS test_campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_name TEXT NOT NULL DEFAULT '',
        package_name TEXT NOT NULL DEFAULT '',
        optin_url TEXT DEFAULT '',
        start_date TEXT NOT NULL,
        target_days INTEGER NOT NULL DEFAULT 14,
        target_testers INTEGER NOT NULL DEFAULT 12,
        session_minutes INTEGER NOT NULL DEFAULT 3,
        events_per_min INTEGER NOT NULL DEFAULT 60,
        max_parallel INTEGER NOT NULL DEFAULT 4,
        auto_run_time TEXT DEFAULT '',
        shutdown_after INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'active',
        last_auto_run_date TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Per-VM tester state inside a campaign
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campaign_testers (
        campaign_id INTEGER NOT NULL,
        vm_index TEXT NOT NULL,
        opted_in INTEGER NOT NULL DEFAULT 0,
        opted_in_at TEXT DEFAULT '',
        installed INTEGER NOT NULL DEFAULT 0,
        version_name TEXT DEFAULT '',
        last_check TEXT DEFAULT '',
        PRIMARY KEY (campaign_id, vm_index)
    )
    """)

    # Daily test sessions (one row per VM run)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS test_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id INTEGER NOT NULL,
        vm_index TEXT NOT NULL,
        account_email TEXT DEFAULT '',
        run_date TEXT NOT NULL,
        started_at TEXT DEFAULT '',
        finished_at TEXT DEFAULT '',
        duration_sec INTEGER DEFAULT 0,
        status TEXT NOT NULL,
        version_name TEXT DEFAULT '',
        crashes INTEGER DEFAULT 0,
        anrs INTEGER DEFAULT 0,
        message TEXT DEFAULT ''
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_campaign ON test_sessions(campaign_id, vm_index, run_date)")

    # Play Console checklist (manual steps the developer ticks off)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS console_checklist (
        campaign_id INTEGER NOT NULL,
        item TEXT NOT NULL,
        done INTEGER NOT NULL DEFAULT 0,
        done_at TEXT DEFAULT '',
        PRIMARY KEY (campaign_id, item)
    )
    """)
    try:
        cursor.execute("ALTER TABLE test_campaigns ADD COLUMN console_url TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # column already exists
    try:
        cursor.execute("ALTER TABLE test_campaigns ADD COLUMN app_profile TEXT DEFAULT 'light'")
    except sqlite3.OperationalError:
        pass  # column already exists

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

def delete_vm_profile(vm_index: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vm_profiles WHERE vm_index = ?", (str(vm_index),))
    conn.commit()
    conn.close()
    return True


# ==================== Closed Testing Campaign helpers ====================
CAMPAIGN_FIELDS = [
    "app_name", "package_name", "optin_url", "start_date", "target_days", "target_testers",
    "session_minutes", "events_per_min", "max_parallel", "app_profile", "auto_run_time", "shutdown_after",
    "status", "last_auto_run_date", "notes", "console_url",
]

def get_current_campaign() -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM test_campaigns WHERE status != 'archived' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def get_campaign(campaign_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM test_campaigns WHERE id = ?", (campaign_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_campaign(data: Dict[str, Any]) -> int:
    data = dict(data)
    prof = data.get("app_profile") or "light"
    if "max_parallel" not in data or not data["max_parallel"]:
        data["max_parallel"] = 2 if prof == "heavy" else 4
    fields = [f for f in CAMPAIGN_FIELDS if f in data]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cols = fields + ["created_at", "updated_at"]
    vals = [data[f] for f in fields] + [now, now]
    conn = get_connection()
    cur = conn.execute(
        f"INSERT INTO test_campaigns ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", vals
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    log_event("SUCCESS", "CAMPAIGN", f"Tạo chiến dịch test '{data.get('app_name')}' ({data.get('package_name')})")
    return cid

def update_campaign(campaign_id: int, data: Dict[str, Any]) -> bool:
    fields = [f for f in CAMPAIGN_FIELDS if f in data]
    if not fields:
        return False
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sets = ", ".join(f"{f} = ?" for f in fields) + ", updated_at = ?"
    vals = [data[f] for f in fields] + [now, campaign_id]
    conn = get_connection()
    conn.execute(f"UPDATE test_campaigns SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return True

def get_campaign_testers(campaign_id: int) -> Dict[str, Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM campaign_testers WHERE campaign_id = ?", (campaign_id,)).fetchall()
    conn.close()
    return {str(r["vm_index"]): dict(r) for r in rows}

def upsert_campaign_tester(campaign_id: int, vm_index: str, **fields) -> None:
    allowed = {"opted_in", "opted_in_at", "installed", "version_name", "last_check"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO campaign_testers (campaign_id, vm_index) VALUES (?, ?)",
        (campaign_id, str(vm_index)),
    )
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(
            f"UPDATE campaign_testers SET {sets} WHERE campaign_id = ? AND vm_index = ?",
            list(fields.values()) + [campaign_id, str(vm_index)],
        )
    conn.commit()
    conn.close()

def add_test_session(data: Dict[str, Any]) -> int:
    conn = get_connection()
    cur = conn.execute("""
    INSERT INTO test_sessions (campaign_id, vm_index, account_email, run_date, started_at, finished_at,
        duration_sec, status, version_name, crashes, anrs, message)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["campaign_id"], str(data["vm_index"]), data.get("account_email", ""), data["run_date"],
        data.get("started_at", ""), data.get("finished_at", ""), int(data.get("duration_sec", 0)),
        data.get("status", "failed"), data.get("version_name", ""), int(data.get("crashes", 0)),
        int(data.get("anrs", 0)), data.get("message", ""),
    ))
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid

def get_test_sessions(campaign_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    sql = "SELECT * FROM test_sessions WHERE campaign_id = ? ORDER BY id DESC"
    params: list = [campaign_id]
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_checklist(campaign_id: int) -> Dict[str, Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM console_checklist WHERE campaign_id = ?", (campaign_id,)).fetchall()
    conn.close()
    return {r["item"]: dict(r) for r in rows}


def set_checklist_item(campaign_id: int, item: str, done: bool) -> None:
    conn = get_connection()
    conn.execute("""
    INSERT INTO console_checklist (campaign_id, item, done, done_at) VALUES (?, ?, ?, ?)
    ON CONFLICT(campaign_id, item) DO UPDATE SET done = excluded.done, done_at = excluded.done_at
    """, (campaign_id, item, int(done), datetime.now().strftime("%Y-%m-%d %H:%M:%S") if done else ""))
    conn.commit()
    conn.close()
