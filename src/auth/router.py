"""
Auth API 路由
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from .models import Role, User
from .middleware import (
    create_access_token, decode_token, get_current_user, require_role,
    get_user_store, save_user, delete_user, hash_password,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "viewer"
    display_name: str = ""


class RoleChangeRequest(BaseModel):
    role: str


@router.post("/login")
async def login(request: LoginRequest):
    users = get_user_store()
    user_dict = users.get(request.username)
    if not user_dict or not user_dict.get("enabled", True):
        raise HTTPException(401, "用户名或密码错误")
    pwd_hash = hash_password(request.password)
    if not pwd_hash == user_dict.get("password_hash", ""):
        raise HTTPException(401, "用户名或密码错误")

    user = User(
        username=request.username,
        password_hash=user_dict["password_hash"],
        role=Role(user_dict.get("role", "viewer")),
        display_name=user_dict.get("display_name", request.username),
    )
    token = create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role.value,
        "display_name": user.display_name,
    }


@router.post("/register")
async def register(request: RegisterRequest,
                   _admin: User = Depends(require_role(Role.ADMIN))):
    users = get_user_store()
    if request.username in users:
        raise HTTPException(400, "用户名已存在")
    if len(request.password) < 6:
        raise HTTPException(400, "密码至少6位")
    if request.role not in ("admin", "operator", "viewer"):
        raise HTTPException(400, "角色无效")

    save_user(request.username, {
        "password_hash": hash_password(request.password),
        "role": request.role,
        "display_name": request.display_name or request.username,
        "enabled": True,
        "created_at": datetime.now().isoformat(),
    })
    return {"status": "created", "username": request.username}


@router.get("/users")
async def list_users(_admin: User = Depends(require_role(Role.ADMIN))):
    users = get_user_store()
    return {
        "users": [
            {"username": u, "display_name": d.get("display_name", u),
             "role": d.get("role", "viewer"), "enabled": d.get("enabled", True),
             "created_at": d.get("created_at", "")}
            for u, d in users.items()
        ]
    }


@router.put("/users/{username}/role")
async def change_role(username: str, request: RoleChangeRequest,
                      _admin: User = Depends(require_role(Role.ADMIN))):
    users = get_user_store()
    if username not in users:
        raise HTTPException(404, "用户不存在")
    if request.role not in ("admin", "operator", "viewer"):
        raise HTTPException(400, "角色无效")
    users[username]["role"] = request.role
    from .middleware import _save_users
    _save_users(users)
    return {"status": "updated", "username": username, "role": request.role}


@router.delete("/users/{username}")
async def disable_user(username: str,
                       _admin: User = Depends(require_role(Role.ADMIN))):
    delete_user(username)
    return {"status": "disabled", "username": username}


@router.get("/me")
async def current_user_info(user: User = Depends(get_current_user)):
    return {
        "username": user.username,
        "role": user.role.value,
        "display_name": user.display_name,
    }
