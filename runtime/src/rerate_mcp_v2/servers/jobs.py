"""Background jobs and guards shared by every app server.

- Job: run a long app action in a worker thread; tools return at once and the agent polls job_status.
  The result is recorded to the run (runs.record) by the worker itself, so it survives a client disconnect.
- desktop_check(): fail fast when GUI mode is requested but the Windows session is disconnected or locked.
- launch_timeout(app): per-app launch timeout from config (apps.<app>.launch_timeout_s), required.
- gui_mode(app): 'gui' or 'headless' from config (apps.<app>.mode).
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import threading
import time
import traceback
from typing import Callable

from .. import config

NOWIN = 0x08000000 if os.name == "nt" else 0


class Job:
    """One background job per server at a time (Ansys apps are single-session)."""

    def __init__(self, name: str):
        self.name = name
        self.lock = threading.Lock()
        self.state = "idle"      # idle | running | finished | error | timeout
        self.step = ""
        self.result: dict | None = None
        self.error: str | None = None
        self.t0: float | None = None
        self.deadline: float | None = None
        self.thread: threading.Thread | None = None

    def set_step(self, step: str) -> None:
        with self.lock:
            self.step = step

    def start(self, fn: Callable[["Job"], dict], timeout_s: float) -> dict:
        with self.lock:
            if self.state == "running":
                return {"status": "error", "message": f"{self.name} job already running ({self.step}); poll job_status"}
            self.state, self.step, self.result, self.error = "running", "starting", None, None
            self.t0, self.deadline = time.time(), time.time() + timeout_s

        def run():
            try:
                res = fn(self)
                with self.lock:
                    if self.state == "running":
                        self.state, self.result = "finished", res
            except Exception as e:
                msg = str(e)
                # Keep the cause: Ansys gRPC errors put the real message (e.g. "AttributeError: ...") in the middle of
                # a long .NET stack trace. Collect lines that look like Python/.NET exception messages.
                key = [ln.strip() for ln in msg.replace("\\r", "").replace("\\n", "\n").splitlines()
                       if any(t in ln for t in ("Error:", "Exception:", "error_string", "details ="))
                       and not ln.strip().startswith("at ")]
                with self.lock:
                    if self.state == "running":
                        self.state = "error"
                        self.error = (" | ".join(key)[:1500] or msg[:1200]) + " || tail: " + msg[-400:]

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        return {"status": "ok", "state": "running", "job": self.name, "timeout_s": timeout_s,
                "next": "poll job_status every 30 to 120 s"}

    def status(self) -> dict:
        with self.lock:
            if self.state == "running" and self.deadline and time.time() > self.deadline:
                self.state = "timeout"
                self.error = f"no result within {round(self.deadline - self.t0)} s (step: {self.step})"
            el = round(time.time() - self.t0) if self.t0 else 0
            out = {"status": "ok", "job": self.name, "state": self.state, "step": self.step, "elapsed_s": el}
            if self.state == "finished":
                out["result"] = self.result
            if self.state in ("error", "timeout"):
                out["error"] = self.error
            return out


def parse_session_state(query_output: str, session_id: int) -> str | None:
    """State column ('Active', 'Disc', ...) of `query session` output for one session id. Pure, unit-tested."""
    for line in query_output.splitlines():
        parts = line.replace(">", " ").split()
        if str(session_id) in parts:
            i = parts.index(str(session_id))
            if i + 1 < len(parts):
                return parts[i + 1]
    return None


def desktop_check() -> dict | None:
    """None if a GUI app can be shown; otherwise an error dict explaining why (fail fast, never hang)."""
    if os.name != "nt":
        return None
    sid = ctypes.c_ulong()
    ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sid))
    out = subprocess.run(["query", "session"], capture_output=True, text=True, creationflags=NOWIN).stdout
    state = parse_session_state(out, sid.value)
    if state and state.lower().startswith("disc"):
        return {"status": "error", "reason": "desktop_disconnected",
                "message": f"Windows session {sid.value} is disconnected (Remote Desktop closed). GUI apps cannot "
                           "draw and would hang. Reconnect and keep the session open, or set apps.<app>.mode: "
                           "headless in the config."}
    # locked screen: no input desktop available to this session
    h = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0100)
    if not h:
        return {"status": "error", "reason": "desktop_locked",
                "message": "The Windows desktop is locked. Unlock it, or set apps.<app>.mode: headless."}
    ctypes.windll.user32.CloseDesktop(h)
    return None


def gui_mode(app: str) -> str:
    m = str(config.get(f"apps.{app}.mode"))
    if m not in ("gui", "headless"):
        raise config.ConfigError(f"apps.{app}.mode must be 'gui' or 'headless'")
    return m


def launch_timeout(app: str) -> int:
    return int(config.get(f"apps.{app}.launch_timeout_s"))


def job_timeout(app: str) -> int:
    return int(config.get(f"apps.{app}.job_timeout_s"))


def gui_guard(app: str) -> dict | None:
    """Desktop check only when this app runs with a GUI."""
    return desktop_check() if gui_mode(app) == "gui" else None
