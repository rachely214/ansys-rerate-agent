"""CFD calibration against measured baseline data. Pure functions (unit-tested).

A CFD model is CALIBRATED only if a converged baseline (unmodified geometry) run at the measured operating point
matches every measured quantity within the case tolerances (cfd.calibration.*). Anything else (not converged, a
quantity out of tolerance, or a measured value missing from the case) is NOT CALIBRATED. Tolerances and measured
values come only from the approved case; nothing here scales or corrects the CFD result.

Measured reference (cfd.calibration.pr_reference):
  impeller -> baseline.impeller_pressure_ratio, baseline.impeller_efficiency_tt (model without diffuser)
  stage    -> baseline.pressure_ratio, baseline.efficiency_tt
Flow is always baseline.corrected_flow.
"""
from __future__ import annotations

from .case import Case

CALIBRATED = "CALIBRATED"
NOT_CALIBRATED = "NOT CALIBRATED"


def _item(name, measured, model, tol, kind, source):
    if measured is None:
        return {"quantity": name, "measured": None, "model": model, "tolerance": tol, "error": None,
                "result": "NOT CHECKABLE", "note": f"no measured value in the case ({source})"}
    if model is None:
        return {"quantity": name, "measured": measured, "model": None, "tolerance": tol, "error": None,
                "result": "NOT CHECKABLE", "note": "no model value"}
    err = (model - measured) / measured if kind == "relative" else model - measured
    return {"quantity": name, "measured": measured, "model": model, "tolerance": tol, "error": err,
            "kind": kind, "result": "WITHIN" if abs(err) <= tol else "OUTSIDE", "note": source}


def evaluate(case: Case, cfd: dict, baseline_run: str) -> dict:
    """Compare a baseline CFD result (stage 'cfd' of an unmodified-geometry run) with the case's measured data."""
    fu = case.raw("baseline.corrected_flow")["unit"]
    ref = str(case.val("cfd.calibration.pr_reference"))
    pr_key, eta_key = (("baseline.impeller_pressure_ratio", "baseline.impeller_efficiency_tt") if ref == "impeller"
                       else ("baseline.pressure_ratio", "baseline.efficiency_tt"))
    ok_run = cfd.get("status") in ("ok", "partial")
    items = [
        _item("corrected flow", case.q("baseline.corrected_flow", fu),
              (cfd.get("corrected_flow") or {}).get(fu) if ok_run else None,
              case.q("cfd.calibration.flow_tol", "-"), "relative", "baseline.corrected_flow"),
        _item(f"total pressure ratio ({ref})", case.opt(pr_key, "-"), cfd.get("PR_tt") if ok_run else None,
              case.q("cfd.calibration.pr_tol", "-"), "relative", pr_key),
        _item(f"t-t efficiency ({ref})", case.opt(eta_key, "-"), cfd.get("eta_isen_tt") if ok_run else None,
              case.q("cfd.calibration.eta_tol", "-"), "absolute", eta_key),
    ]
    reasons = []
    if not cfd.get("converged"):
        reasons.append("baseline CFD not converged")
    for it in items:
        if it["result"] != "WITHIN":
            reasons.append(f"{it['quantity']}: {it['result'].lower()}" +
                           (f" ({it['note']})" if it["result"] == "NOT CHECKABLE" else ""))
    return {"status": NOT_CALIBRATED if reasons else CALIBRATED, "reasons": reasons, "items": items,
            "pr_reference": ref, "baseline_run": baseline_run, "flow_unit": fu,
            "model": {k: cfd.get(k) for k in ("iterations", "converged", "outlet_static_pressure_pa")},
            "fidelity": cfd.get("fidelity")}


def model_signature(stages: dict, case: Case) -> dict:
    """What defines 'the same CFD model': mesh topology/splitter, size factor, turbulence, rotation sign, outlet
    radius ratio. A calibration applies to another run only if these match."""
    m = stages.get("meshing") or {}
    return {"topology": m.get("topology"), "with_splitter": m.get("with_splitter"),
            "size_factor": m.get("size_factor"), "tip_clearance_m": m.get("tip_clearance_m"), "turbulence": str(case.val("cfd.turbulence_model")),
            "rotation_sign": int(case.val("operating_point.rotation_sign")),
            "outlet_radius_ratio": case.q("cfd.outlet_radius_ratio", "-")}


def applies(cal: dict | None, signature: dict) -> tuple[bool, str]:
    if not cal:
        return False, "no baseline calibration linked to this run"
    if cal.get("signature") != signature:
        diff = [k for k in signature if (cal.get("signature") or {}).get(k) != signature[k]]
        return False, f"calibration was done with a different CFD model ({', '.join(diff)})"
    return True, ""
