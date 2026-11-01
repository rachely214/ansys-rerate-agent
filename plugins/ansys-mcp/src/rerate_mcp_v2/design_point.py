"""Design operating point: pure functions (unit-tested) for evaluating a re-rated design at its target flow.

Why: the measured impeller-exit static belongs to the baseline duty; a re-rated design at a new flow has no measured
exit pressure, and applying the baseline value stalls the passage (PROGRESS C29, B8). The design is instead run at
its TARGET FLOW (a mass-flow outlet condition), and pressure ratio and efficiency are read there (DEC-19).

All values come from the approved case; nothing here is machine-specific.
"""
from __future__ import annotations

import math


def target_passage_mass_flow(corrected_kg_s: float, n_passages: int, pt_in_pa: float, tt_in_k: float,
                             p_ref_pa: float, t_ref_k: float) -> float:
    """Physical mass flow per passage (kg/s) that gives the wheel corrected flow `corrected_kg_s` at the case inlet.
    Inverse of corrected = m * sqrt(Tt/Tref) / (Pt/Pref)."""
    m_wheel = corrected_kg_s * (pt_in_pa / p_ref_pa) / math.sqrt(tt_in_k / t_ref_k)
    return m_wheel / n_passages


def choke_verdict(hist: list[dict], target_kg_s: float, flow_tol: float, window: int) -> dict:
    """Classify a targeted-mass-flow run from its history (iters, mdot_in, p_out_pa).
    reached      : last flow within flow_tol of the target
    choked       : flow short of target, the outlet pressure has stopped falling (at its lower bound or flat),
                   and the flow is flat over the window -> the passage cannot pass more flow (max flow = last)
    not_settled  : anything else (still moving)"""
    if not hist:
        return {"state": "not_settled", "reason": "no history"}
    last = hist[-1]
    err = (abs(last["mdot_in"]) - target_kg_s) / target_kg_s
    if abs(err) <= flow_tol:
        return {"state": "reached", "flow_error": err}
    win = [h for h in hist if h["iters"] >= last["iters"] - window]
    if len(win) < 3:
        return {"state": "not_settled", "flow_error": err, "reason": "history shorter than the window"}
    f = [abs(h["mdot_in"]) for h in win]
    p = [h.get("p_out_pa") for h in win if h.get("p_out_pa") is not None]
    flow_flat = (max(f) - min(f)) / max(abs(f[-1]), 1e-12) <= flow_tol / 5
    p_stalled = bool(p) and (last.get("at_lower_bound") or (max(p) - min(p)) / max(abs(p[-1]), 1e-12) <= 0.005)
    if err < 0 and flow_flat and p_stalled:
        return {"state": "choked", "flow_error": err, "max_flow_kg_s": abs(last["mdot_in"])}
    return {"state": "not_settled", "flow_error": err}


def interpolate_at_flow(points: list[dict], target: float) -> dict:
    """Speedline fallback: points [{mdot, PR, eta, p_out_pa}] from converged back-pressure runs. Linear
    interpolation in flow between the two points that bracket the target. No extrapolation: if the target is
    outside the converged range, returns status 'out_of_range' with the range."""
    pts = sorted((p for p in points if p.get("mdot") is not None), key=lambda p: p["mdot"])
    if len(pts) < 2:
        return {"status": "insufficient", "n_points": len(pts)}
    lo, hi = pts[0]["mdot"], pts[-1]["mdot"]
    if not (lo <= target <= hi):
        return {"status": "out_of_range", "flow_range": [lo, hi], "target": target}
    for a, b in zip(pts, pts[1:]):
        if a["mdot"] <= target <= b["mdot"]:
            t = 0.0 if b["mdot"] == a["mdot"] else (target - a["mdot"]) / (b["mdot"] - a["mdot"])
            return {"status": "ok", "PR": a["PR"] + t * (b["PR"] - a["PR"]),
                    "eta": a["eta"] + t * (b["eta"] - a["eta"]),
                    "p_out_pa": a["p_out_pa"] + t * (b["p_out_pa"] - a["p_out_pa"]),
                    "bracket": [a["mdot"], b["mdot"]]}
    return {"status": "out_of_range", "flow_range": [lo, hi], "target": target}
