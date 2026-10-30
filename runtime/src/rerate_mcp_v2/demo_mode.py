"""Demo mode: hard effort limits for Fluent, read from the machine config (section demo_mode).

Pure helpers (unit-tested). The limits only shorten or refuse solves; a capped solve stays unconverged and its
checks end NOT CHECKED. They never change a target, tolerance or result.
"""
from __future__ import annotations

from . import config


def settings(cfg: dict | None = None) -> dict:
    d = config.get("demo_mode", cfg, required=False) or {}
    return {"enabled": bool(d.get("enabled", False)),
            "solve_cap_s": float(d.get("cfd_solve_cap_s") or 0) or None,
            "total_budget_s": float(d.get("cfd_total_budget_s") or 0) or None,
            "allow_speedline": bool(d.get("allow_speedline", True))}


def used_solve_seconds(stages: dict) -> float:
    """Fluent wall time already spent in this run folder (stage cfd + every diagnostic point)."""
    def t(p):
        h = (p or {}).get("history_last") or []
        return float(h[-1].get("t_s") or 0) if h else 0.0
    pts = ((stages.get("cfd_diagnostic") or {}).get("points")) or []
    return sum(t(p) for p in pts) + t(stages.get("cfd"))


def plan_solve(requested_s: float, stages: dict, d: dict) -> tuple[float | None, str | None]:
    """(time limit to use, refusal reason). Demo mode off: the request unchanged."""
    if not d["enabled"]:
        return float(requested_s), None
    lim = float(requested_s)
    if d["solve_cap_s"]:
        lim = min(lim, d["solve_cap_s"])
    if d["total_budget_s"]:
        left = d["total_budget_s"] - used_solve_seconds(stages)
        if left <= 60:
            return None, (f"demo mode: the CFD time budget of this run ({d['total_budget_s']:.0f} s) is used up. "
                          "Record the remaining CFD checks as NOT CHECKED (reason: demo time budget) and continue "
                          "with the next stage.")
        lim = min(lim, left)
    return lim, None
