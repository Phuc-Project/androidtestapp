import time
import requests
from typing import Dict, Any, Optional

def test_proxy(proto: str, host: str, port: int, username: str = "", password: str = "", timeout: int = 6) -> Dict[str, Any]:
    """
    Tests proxy connectivity, latency, outgoing IP, and geolocation.
    """
    proto = proto.lower().strip()
    if proto not in ["http", "https", "socks5", "socks5h"]:
        proto = "http"

    auth_str = ""
    if username:
        auth_str = f"{username}:{password}@"

    proxy_url = f"{proto}://{auth_str}{host}:{port}"
    proxies = {
        "http": proxy_url,
        "https": proxy_url
    }

    start_time = time.time()
    try:
        # Check against IP API
        res = requests.get(
            "http://ip-api.com/json/?fields=status,message,country,city,query,isp",
            proxies=proxies,
            timeout=timeout
        )
        latency = int((time.time() - start_time) * 1000)

        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                return {
                    "success": True,
                    "latency_ms": latency,
                    "outgoing_ip": data.get("query", ""),
                    "country": data.get("country", "Unknown"),
                    "city": data.get("city", ""),
                    "isp": data.get("isp", ""),
                    "error": None
                }

        # Fallback to ipify if ip-api rate limited
        res2 = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=timeout)
        latency2 = int((time.time() - start_time) * 1000)
        if res2.status_code == 200:
            return {
                "success": True,
                "latency_ms": latency2,
                "outgoing_ip": res2.json().get("ip", ""),
                "country": "Online",
                "city": "",
                "isp": "",
                "error": None
            }

        return {
            "success": False,
            "latency_ms": latency,
            "outgoing_ip": "",
            "country": "",
            "city": "",
            "isp": "",
            "error": f"HTTP {res.status_code}"
        }
    except Exception as e:
        latency = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "latency_ms": latency,
            "outgoing_ip": "",
            "country": "",
            "city": "",
            "isp": "",
            "error": str(e)
        }
