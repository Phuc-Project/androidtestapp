import base64
import hmac
import hashlib
import struct
import time

def generate_totp(secret: str, digits: int = 6, period: int = 30) -> dict:
    """
    Generate RFC 6238 TOTP 6-digit code and seconds remaining.
    """
    if not secret:
        return {"code": "------", "remaining": 0, "valid": False, "error": "Empty secret"}

    clean_secret = secret.replace(" ", "").replace("-", "").upper()
    missing_padding = len(clean_secret) % 8
    if missing_padding:
        clean_secret += "=" * (8 - missing_padding)

    try:
        key = base64.b32decode(clean_secret)
    except Exception as e:
        return {"code": "ERR_SEC", "remaining": 0, "valid": False, "error": f"Invalid Base32 secret: {str(e)}"}

    now = time.time()
    counter = int(now // period)
    remaining = period - int(now % period)

    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[19] & 0x0F
    code_int = (struct.unpack(">I", digest[offset:offset+4])[0] & 0x7FFFFFFF) % (10 ** digits)
    code_str = f"{code_int:0{digits}d}"

    return {
        "code": code_str,
        "remaining": remaining,
        "valid": True,
        "period": period,
        "error": None
    }
