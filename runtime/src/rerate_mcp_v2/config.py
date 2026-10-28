"""Machine configuration: every path, port and license option comes from ONE config file.

Lookup order for the config file:
  1. env RERATE_V2_CONFIG (absolute path)
  2. <repo>/.local/rerate.config.yaml   (written by setup.ps1, ignored by git)
Nothing machine-specific is hard-coded here; if a key is missing, the error says which one.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PKG_DIR = Path(__file__).resolve().parent
# <repo>/plugins/ansys-mcp/src/rerate_mcp_v2 -> repo root is 4 levels up
REPO_ROOT = PKG_DIR.parents[3]


class ConfigError(RuntimeError):
    pass


def config_path() -> Path:
    env = os.environ.get("RERATE_V2_CONFIG")
    return Path(env) if env else REPO_ROOT / ".local" / "rerate.config.yaml"


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        raise ConfigError(f"config not found at {p}. Run setup.ps1 (or copy "
                          "harnesses/hermes/rerate.config.template.yaml there and fill it in).")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def get(key: str, cfg: dict | None = None, required: bool = True) -> Any:
    cur: Any = cfg if cfg is not None else load_config()
    for k in key.split("."):
        if not isinstance(cur, dict) or k not in cur or cur[k] in (None, ""):
            if required:
                raise ConfigError(f"config key '{key}' is not set in {config_path()}")
            return None
        cur = cur[k]
    return cur


def _repo_rel(p: str) -> Path:
    q = Path(os.path.expandvars(os.path.expanduser(p)))
    return q if q.is_absolute() else (REPO_ROOT / q)


def ansys_root(cfg: dict | None = None) -> Path:
    """Ansys version root, e.g. the folder that contains Framework/, fluent/, TurboGrid/."""
    return _repo_rel(str(get("ansys.root", cfg)))


def ansys_version(cfg: dict | None = None) -> int:
    return int(get("ansys.version", cfg))


def runs_root(cfg: dict | None = None) -> Path:
    d = _repo_rel(str(get("paths.runs_dir", cfg)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def work_root(cfg: dict | None = None) -> Path:
    d = _repo_rel(str(get("paths.work_dir", cfg)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def license_mode(cfg: dict | None = None) -> str:
    """'student' (one app at a time) or 'commercial' (concurrent apps allowed)."""
    m = str(get("license.mode", cfg))
    if m not in ("student", "commercial"):
        raise ConfigError("license.mode must be 'student' or 'commercial'")
    return m


def exclusive_apps(cfg: dict | None = None) -> bool:
    return license_mode(cfg) == "student" or bool(get("license.exclusive_apps", cfg, required=False))


def server_transport(name: str, cfg: dict | None = None) -> dict:
    """{'transport': 'stdio'|'http', 'host': ..., 'port': ...} for MCP server `name`."""
    cfg = cfg if cfg is not None else load_config()
    t = dict(get("mcp.defaults", cfg, required=False) or {"transport": "stdio"})
    t.update(get(f"mcp.servers.{name}", cfg, required=False) or {})
    if t.get("transport") == "http":
        for k in ("host", "port"):
            if not t.get(k):
                raise ConfigError(f"mcp.servers.{name}.{k} required for http transport")
    return t
