"""Machine configuration: every path, port and license option comes from ONE config file.

Lookup order for the config file:
  1. env RERATE_CONFIG (absolute path)
  2. env RERATE_V2_CONFIG (older name, still accepted)
  3. %LOCALAPPDATA%/ansys-rerate-agent/machine.config.yaml on Windows,
     ~/.ansys-rerate-agent/machine.config.yaml elsewhere
Relative paths inside the config resolve against the folder that holds the config file, never against the
package or a repository. Nothing machine-specific is hard-coded here; if a key is missing, the error says which.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PKG_DIR = Path(__file__).resolve().parent
CONFIG_NAME = "machine.config.yaml"
INSTALL_DIR_NAME = "ansys-rerate-agent"


class ConfigError(RuntimeError):
    pass


def install_home() -> Path:
    """Default per-user install folder (holds the machine config, venv, runs, example data)."""
    if os.name == "nt":
        lad = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(lad) / INSTALL_DIR_NAME
    return Path.home() / f".{INSTALL_DIR_NAME}"


def config_path() -> Path:
    for var in ("RERATE_CONFIG", "RERATE_V2_CONFIG"):
        env = os.environ.get(var)
        if env:
            return Path(os.path.expandvars(os.path.expanduser(env)))
    return install_home() / CONFIG_NAME


def config_dir() -> Path:
    return config_path().resolve().parent


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        raise ConfigError(f"machine config not found at {p}. This computer is not set up yet; "
                          "the setup step writes this file.")
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


def resolve(p: str | os.PathLike) -> Path:
    """Expand ~ and env vars; a relative path resolves against the config file's folder."""
    q = Path(os.path.expandvars(os.path.expanduser(str(p))))
    return q if q.is_absolute() else (config_dir() / q)


def ansys_root(cfg: dict | None = None) -> Path:
    """Ansys version root, e.g. the folder that contains Framework/, fluent/, TurboGrid/."""
    return resolve(str(get("ansys.root", cfg)))


def ansys_version(cfg: dict | None = None) -> int:
    return int(get("ansys.version", cfg))


def ensure_awp_root(cfg: dict | None = None) -> str | None:
    """Set AWP_ROOT<ver> (e.g. AWP_ROOT261) in this process from ansys.root / ansys.version if it is missing.
    Returns the variable name, or None if the config does not give both keys."""
    try:
        cfg = cfg if cfg is not None else load_config()
        ver = ansys_version(cfg)
        root = ansys_root(cfg)
    except (ConfigError, ValueError, TypeError):
        return None
    name = f"AWP_ROOT{ver}"
    if not os.environ.get(name):
        os.environ[name] = str(root)
    return name


def runs_root(cfg: dict | None = None) -> Path:
    d = resolve(str(get("paths.runs_dir", cfg)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def work_root(cfg: dict | None = None) -> Path:
    d = resolve(str(get("paths.work_dir", cfg)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def example_data_root(cfg: dict | None = None) -> Path | None:
    """Folder holding downloaded example data (one subfolder per example), or None if not configured."""
    try:
        v = get("paths.example_data", cfg, required=False)
    except ConfigError:
        return None
    return resolve(str(v)) if v else None


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
