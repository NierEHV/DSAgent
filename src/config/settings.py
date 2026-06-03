"""
DS Agent v3.0 全局配置加载
支持 YAML + 环境变量, 优先级: 环境变量 > YAML > 默认值
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _find_config() -> Optional[Path]:
    """查找 config.yaml, 优先级: 环境变量 > 项目根 > src 目录"""
    env_path = os.environ.get("DSAGENT_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
    candidates = [
        PROJECT_ROOT / "config.yaml",
        Path.cwd() / "config.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # 无 pyyaml 时用 JSON 兼容模式
        import json
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # 简单 YAML 转 JSON (只支持我们的配置格式)
        return _simple_yaml_parse(content)


def _simple_yaml_parse(content: str) -> dict:
    """轻量 YAML 解析 — 仅支持 config.yaml 的简单格式, 无依赖"""
    import re
    result: dict[str, Any] = {}
    current_section: Optional[str] = None
    current_list: Optional[list] = None
    current_list_item: Optional[dict] = None

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # 顶级 key: value
        if not line.startswith(" ") and ":" in stripped and not stripped.startswith("-"):
            if current_list_item is not None and current_list is not None:
                current_list.append(current_list_item)
                current_list_item = None
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val:
                result[key] = _convert_value(val)
                current_section = key
            else:
                result[key] = {}
                current_section = key
            current_list = None
            continue

        # 二级 key: value
        if line.startswith("  ") and not stripped.startswith("- ") and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if current_section and isinstance(result.get(current_section), dict):
                if val:
                    result[current_section][key] = _convert_value(val)
                else:
                    result[current_section][key] = {}
            continue

        # 列表项 - name:
        if stripped.startswith("- ") and ":" in stripped:
            if current_list_item is not None and current_list is not None:
                current_list.append(current_list_item)
            item_text = stripped[2:]
            key, _, val = item_text.partition(":")
            current_list_item = {key.strip(): val.strip().strip('"').strip("'")}
            if current_list is None:
                current_list = []
                # 找到当前 section
                for k, v in result.items():
                    if isinstance(v, list):
                        current_list = v
                        break
            continue

        # 列表项子字段
        if line.startswith("    ") and ":" in stripped and current_list_item is not None:
            key, _, val = stripped.partition(":")
            current_list_item[key.strip()] = val.strip().strip('"').strip("'")
            continue

        # 列表 end
        if not stripped.startswith("-") and not stripped.startswith("  ") and current_list_item is not None and current_list is not None:
            current_list.append(current_list_item)
            current_list_item = None
            current_list = None

    if current_list_item is not None and current_list is not None:
        current_list.append(current_list_item)

    return result


def _convert_value(val: str) -> Any:
    if val.lower() in ("true", "yes"):
        return True
    if val.lower() in ("false", "no"):
        return False
    if val.isdigit():
        return int(val)
    try:
        return float(val)
    except ValueError:
        return val


def _resolve_env_vars(data: Any) -> Any:
    """递归解析 ${VAR} 和 ${VAR:-default} 环境变量引用"""
    import re
    if isinstance(data, dict):
        return {k: _resolve_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_env_vars(v) for v in data]
    if isinstance(data, str):
        pattern = r'\$\{(\w+)(?::-([^}]*))?\}'
        def _replace(m):
            var = m.group(1)
            default = m.group(2)
            return os.environ.get(var, default or "")
        return re.sub(pattern, _replace, data)
    return data


class Settings:
    """全局配置单例"""

    _instance: Optional["Settings"] = None

    def __init__(self):
        if Settings._instance is not None:
            return
        Settings._instance = self

        self._config: dict[str, Any] = {}
        self._config_path: Optional[Path] = _find_config()
        if self._config_path:
            self._config = _resolve_env_vars(_load_yaml(self._config_path))
        else:
            self._config_path = PROJECT_ROOT / "config.yaml"
            self._config = self._defaults()

        # 环境变量最高优先级覆盖
        self._apply_env_overrides()

    @staticmethod
    def _defaults() -> dict:
        return {
            "llm": {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "api_key": "",
                "base_url": "https://api.deepseek.com/v1",
                "max_tokens": 4096,
                "temperature": 0.3,
            },
            "datasources": [],
            "routing": {
                "inventory": ["lingxing", "sellersprite"],
                "sales": ["lingxing", "sellersprite", "sorftime"],
                "advertising": ["lingxing", "sellersprite"],
                "competitor": ["sellersprite", "sorftime"],
                "keyword": ["sellersprite", "sorftime"],
                "market": ["sellersprite", "sorftime"],
                "review": ["sellersprite", "sorftime"],
                "profit": ["lingxing"],
                "product": ["sellersprite", "sorftime", "lingxing"],
            },
            "scheduler": {"interval_minutes": 5, "auto_approve_low_risk": True},
            "alert": {"channels": []},
            "mock_mode": True,
        }

    def _apply_env_overrides(self):
        """环境变量覆盖 YAML 配置"""
        overrides = {
            "llm.provider": "LLM_PROVIDER",
            "llm.model": "LLM_MODEL",
            "llm.api_key": "LLM_API_KEY",
            "llm.base_url": "LLM_BASE_URL",
            "llm.max_tokens": "LLM_MAX_TOKENS",
            "scheduler.interval_minutes": "POLL_INTERVAL",
            "mock_mode": "MOCK_MODE",
        }
        for key_path, env_var in overrides.items():
            env_val = os.environ.get(env_var)
            if env_val is not None:
                self._set_nested(key_path, _convert_value(env_val))

    def _set_nested(self, key_path: str, value: Any):
        keys = key_path.split(".")
        d = self._config
        for key in keys[:-1]:
            if key not in d:
                d[key] = {}
            d = d[key]
        d[keys[-1]] = value

    # ──── 公共 API ────

    @property
    def llm_config(self) -> dict: return self._config.get("llm", {})

    @property
    def datasources(self) -> list[dict]: return self._config.get("datasources", [])

    def get_enabled_datasources(self) -> list[dict]:
        return [ds for ds in self.datasources if ds.get("enabled", True)]

    @property
    def routing(self) -> dict: return self._config.get("routing", {})

    @property
    def scheduler_config(self) -> dict: return self._config.get("scheduler", {})

    @property
    def alert_rules(self) -> dict: return self._config.get("alert_rules", {})

    @property
    def notify_config(self) -> dict: return self._config.get("notify", {})

    @property
    def monitor_config(self) -> dict: return self._config.get("monitor", {})

    @property
    def storage_config(self) -> dict: return self._config.get("storage", {})

    @property
    def ui_config(self) -> dict: return self._config.get("ui", {})

    @property
    def mock_mode(self) -> bool: return self._config.get("mock_mode", True)

    def get(self, key: str, default: Any = None) -> Any: return self._config.get(key, default)

    @property
    def as_dict(self) -> dict:
        return dict(self._config)

    def update(self, section: str, data: dict):
        """更新配置节并持久化"""
        if section not in self._config:
            self._config[section] = {}
        if isinstance(self._config[section], dict):
            self._config[section].update(data)
        self.save()

    def add_datasource(self, ds: dict):
        """添加或更新数据源"""
        existing = [i for i, d in enumerate(self._config.get("datasources", []))
                    if d.get("name") == ds.get("name")]
        if existing:
            self._config["datasources"][existing[0]].update(ds)
        else:
            self._config.setdefault("datasources", []).append(ds)
        self.save()

    def save(self):
        """保存配置到 config.yaml"""
        if not self._config_path:
            return
        import os as _os
        content = self._to_yaml(self._config)
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            f.write(content)

    def reload(self):
        """重新从文件加载配置"""
        if self._config_path and self._config_path.exists():
            self._config = _resolve_env_vars(_load_yaml(self._config_path))
        self._apply_env_overrides()

    @staticmethod
    def _to_yaml(data: dict, indent: int = 0) -> str:
        """将配置 dict 序列化为 YAML"""
        lines = []
        prefix = "  " * indent
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(Settings._to_yaml(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        item_name = item.get('name', '')
                        lines.append(f"{prefix}  - {item_name}:")
                        for k, v in item.items():
                            if k == 'name':
                                continue
                            lines.append(f"{prefix}      {k}: {_yaml_value(v)}")
                    else:
                        lines.append(f"{prefix}  - {_yaml_value(item)}")
            elif isinstance(value, bool):
                lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
            elif isinstance(value, str):
                if "\n" in value or "${" in value:
                    lines.append(f'{prefix}{key}: "{value}"')
                else:
                    lines.append(f"{prefix}{key}: {value}")
            elif value is None:
                lines.append(f"{prefix}{key}:")
            else:
                lines.append(f"{prefix}{key}: {value}")
        return "\n".join(lines)


def _yaml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return f'"{v}"' if (" " in v or ":" in v) else v
    return str(v)


# 全局单例
settings = Settings()
