"""
Auth module — JWT authentication
Roles:
  auditor   → read all apps, run audit pipeline
  admin     → full access
  bankuser  → upload documents for their assigned app(s)
"""
import jwt, hashlib
from datetime import datetime, timedelta
from typing import Optional

SECRET_KEY         = "audit-vault-bank-2024"
ALGORITHM          = "HS256"
TOKEN_EXPIRY_HOURS = 8

def _h(pw): return hashlib.sha256(pw.encode()).hexdigest()

USERS = {
    # ── Auditors / admin ──────────────────────────────────────────────
    "auditor1": {"password": _h("audit@123"),  "role": "auditor",  "name": "Alice Auditor",   "app_ids": ["APP001","APP002","APP003"]},
    "auditor2": {"password": _h("audit@456"),  "role": "auditor",  "name": "David Auditor",   "app_ids": ["APP001","APP002","APP003"]},
    "admin":    {"password": _h("admin@123"),  "role": "admin",    "name": "Admin User",       "app_ids": ["APP001","APP002","APP003"]},

    # ── BankUsers per application ──────────────────────────────────────
    "bankuser1": {"password": _h("bank@001"), "role": "bankuser", "name": "BankUser APP001",  "app_ids": ["APP001"]},
    "bankuser2": {"password": _h("bank@002"), "role": "bankuser", "name": "BankUser APP002",  "app_ids": ["APP002"]},
    "bankuser3": {"password": _h("bank@003"), "role": "bankuser", "name": "BankUser APP003",  "app_ids": ["APP003"]},
}

def authenticate_user(username: str, password: str) -> Optional[dict]:
    u = USERS.get(username)
    if not u or u["password"] != _h(password):
        return None
    return {"username": username, "role": u["role"], "name": u["name"], "app_ids": u["app_ids"]}

def create_token(data: dict) -> str:
    payload = {**data, "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None
