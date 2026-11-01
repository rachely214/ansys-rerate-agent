"""Shared helpers for the V2 MCP servers: environment repair, app process control, transport.

Policy: servers expose SPECIFIC actions only. There is deliberately no tool that executes agent-supplied
Python or scripts inside an Ansys app.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from .. import config

NOWIN = 0x08000000 if os.name == "nt" else 0


def _repair_env() -> None:
    """MCP hosts may start stdio servers with a filtered environment and cwd = System32. Restore basics from
    the current user's profile (derived at run time; nothing user-specific is stored)."""
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    sysroot = os.environ.get("SystemRoot") or os.environ.get("windir") or "C:\\Windows"
    defaults = {"USERPROFILE": home, "HOME": home, "SystemRoot": sysroot, "windir": sysroot,
                "LOCALAPPDATA": str(Path(home) / "AppData" / "Local"),
                "APPDATA": str(Path(home) / "AppData" / "Roaming"),
                "TEMP": str(Path(home) / "AppData" / "Local" / "Temp"),
                "TMP": str(Path(home) / "AppData" / "Local" / "Temp"),
                "USERNAME": Path(home).name}
    for k, v in defaults.items():
        if not os.environ.get(k):
            os.environ[k] = v
    sys32 = str(Path(sysroot) / "System32")
    if sys32.lower() not in os.environ.get("PATH", "").lower():
        os.environ["PATH"] = os.pathsep.join([sys32, sysroot, str(Path(sys32) / "WindowsPowerShell" / "v1.0"),
                                              os.environ.get("PATH", "")])


_repair_env()


def powershell() -> str:
    return str(Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")


def ps(cmd: str, timeout: int = 90) -> str:
    r = subprocess.run([powershell(), "-NoProfile", "-Command", cmd], stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=timeout, creationflags=NOWIN)
    return r.stdout.strip()


def enter_work_dir() -> Path:
    """Startup hook used by every server: set AWP_ROOT<ver> from the machine config if missing (so the MCP host
    only has to pass RERATE_CONFIG), then change into the work folder."""
    config.ensure_awp_root()
    w = config.work_root()
    os.chdir(w)
    return w


# Process names per app (used only to free license seats / clean up orphans).
APP_PROCESSES = {
    "fluent": ["cx*", "fl2*", "fluent*", "mpiexec", "hydra_pmi_proxy"],
    "turbogrid": ["cfxtg*", "TurboGrid*", "TGGui*", "TGEngine*"],
    "workbench": ["AnsysWBU", "RunWB2", "AnsysFW*", "Ansys.ACT*"],
    "discovery": ["Discovery", "SpaceClaim", "apip-standalone-service"],
}


def close_apps(apps: list[str] | None = None) -> str:
    names = [n for a in (apps or APP_PROCESSES) for n in APP_PROCESSES[a]]
    q = ",".join(f"'{n}'" for n in names)
    out = ps(f"$p=Get-Process -Name @({q}) -EA SilentlyContinue; $p | Stop-Process -Force -EA SilentlyContinue; "
             "($p | Select-Object -ExpandProperty ProcessName | Sort-Object -Unique) -join ','")
    return out or "nothing running"


def free_seat_for(app: str) -> str:
    """On a Student (exclusive) license close every other Ansys app; on commercial, do nothing."""
    if config.exclusive_apps():
        return close_apps([a for a in APP_PROCESSES if a != app])
    return "skipped (commercial license: concurrent apps allowed)"


def license_denials(tail: int = 5, max_age_s: int = 3600) -> list[str]:
    """License DENIED lines from the Ansys client logs written in the last `max_age_s` seconds."""
    import datetime as _dt
    d = Path(os.environ.get("TEMP", "")) / ".ansys"
    cutoff = _dt.datetime.now() - _dt.timedelta(seconds=max_age_s)
    lines: list[str] = []
    for f in sorted(d.glob("licdebug.*.out"), key=lambda p: p.stat().st_mtime, reverse=True)[:4]:
        txt = f.read_text(errors="ignore").splitlines()
        for i, l in enumerate(txt):
            if "DENIED" in l:
                try:
                    t = _dt.datetime.strptime(" ".join(l.split()[:2]), "%Y/%m/%d %H:%M:%S")
                    if t < cutoff:
                        continue
                except ValueError:
                    pass
                lines.append(f"{f.name}: {' '.join(l.split()[:4])} | {txt[i + 1].strip() if i + 1 < len(txt) else ''}")
    return lines[-tail:]


def find_windows() -> list[tuple[int, str, str]]:
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    out = []

    def cb(h, _l):
        if u.IsWindowVisible(h):
            n = u.GetWindowTextLengthW(h)
            b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1)
            c = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, c, 256)
            out.append((h, b.value, c.value))
        return True
    u.EnumWindows(proc(cb), 0)
    return out


def wait_window(pattern: str, seconds: int = 120) -> str:
    t_end = time.time() + seconds
    while time.time() < t_end:
        hits = [t for (_, t, _) in find_windows() if pattern.lower() in t.lower()]
        if hits:
            return hits[0]
        time.sleep(3)
    return ""


def run_server(mcp, name: str) -> None:
    """Start an MCP server with the transport from config (stdio default, or http host/port)."""
    try:
        t = config.server_transport(name)
    except config.ConfigError:
        t = {"transport": "stdio"}
    if t.get("transport") == "http":
        mcp.run(transport="http", host=str(t["host"]), port=int(t["port"]))
    else:
        mcp.run()
