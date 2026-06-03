"""
用户权限模型
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


@dataclass
class User:
    username: str
    password_hash: str
    role: Role = Role.VIEWER
    display_name: str = ""
    enabled: bool = True
    created_at: str = ""
