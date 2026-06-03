"""
Auth 中间件 — JWT 签发 + 验证 + 权限检查
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .models import User, Role

# JWT Secret (生产环境用环境变量)
JWT_SECRET = os.environ.get("JWT_SECRET", "dsagent-jwt-secret-change-me")
JWT_EXPIRY_HOURS = 8

bearer_scheme = HTTPBearer(auto_error=False)

# ──── JWT ────

def _b64url_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64url_decode(s: str) -> bytes:
    import base64
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)

def create_access_token(user: User) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url_encode(json.dumps({
        "sub": user.username,
        "role": user.role.value,
        "display_name": user.display_name,
        "exp": int(time.time()) + JWT_EXPIRY_HOURS * 3600,
        "iat": int(time.time()),
    }).encode())
    signature = _b64url_encode(
        hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"

def decode_token(token: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload, signature = parts
        expected_sig = _b64url_encode(
            hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected_sig):
            return None
        data = json.loads(_b64url_decode(payload))
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None

# ──── FastAPI Dependencies ────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    user_store = _load_users()
    username = payload.get("sub", "")
    user_dict = user_store.get(username)
    if not user_dict or not user_dict.get("enabled", True):
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return User(
        username=username,
        password_hash=user_dict.get("password_hash", ""),
        role=Role(user_dict.get("role", "viewer")),
        display_name=user_dict.get("display_name", username),
        enabled=user_dict.get("enabled", True),
        created_at=user_dict.get("created_at", ""),
    )

def require_role(min_role: Role):
    """FastAPI dependency factory — 要求最低角色"""
    async def _check(user: User = Depends(get_current_user)):
        role_order = {Role.VIEWER: 0, Role.OPERATOR: 1, Role.ADMIN: 2}
        if role_order.get(user.role, 0) < role_order.get(min_role, 0):
            raise HTTPException(status_code=403, detail=f"权限不足, 需要 {min_role.value} 角色")
        return user
    return _check

def optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> Optional[User]:
    """可选的用户认证 — 不强制登录"""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if not payload:
            return None
        user_store = _load_users()
        username = payload.get("sub", "")
        user_dict = user_store.get(username)
        if user_dict:
            return User(
                username=username,
                password_hash=user_dict.get("password_hash", ""),
                role=Role(user_dict.get("role", "viewer")),
                display_name=user_dict.get("display_name", username),
            )
    except Exception:
        pass
    return None

# ──── 用户存储 (JSON 文件) ────

USER_STORE_PATH = Path("data/users.json")

def _load_users() -> dict:
    if USER_STORE_PATH.exists():
        with open(USER_STORE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    _init_default_admin()
    return _load_users()

def _save_users(users: dict):
    USER_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(USER_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def _init_default_admin():
    """创建默认管理员"""
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    _save_users({
        "admin": {
            "password_hash": admin_hash,
            "role": "admin",
            "display_name": "管理员",
            "enabled": True,
            "created_at": datetime.now().isoformat(),
        }
    })

def get_user_store():
    return _load_users()

def save_user(username: str, user_data: dict):
    users = _load_users()
    users[username] = user_data
    _save_users(users)

def delete_user(username: str):
    users = _load_users()
    if username in users:
        users[username]["enabled"] = False
        _save_users(users)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()
