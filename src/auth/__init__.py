"""
Auth 模块 — JWT 认证 + 角色权限
"""

from __future__ import annotations

from .models import User, Role
from .middleware import (
    create_access_token, decode_token, get_current_user,
    require_role, optional_user,
)
from .router import router
