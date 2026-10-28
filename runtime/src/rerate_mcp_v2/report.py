"""Scorecard and REPORT.md from ONE run record + its approved case. Pure functions (unit-tested).

Result labels:
  PASS / FAIL            measured value vs case target
  FAIL (model-limited)   FAIL where the stage that produced the number declared fidelity limitations
                         (e.g. single passage, no diffuser, not converged). The FAIL stands; the label says
                         the simplified model may be the cause, so a human must judge.
  NOT CHECKED            no stage produced the value (never counted as PASS)
  NOT REQUESTED          the case has no target for it
"""
from __future__ import annotations

import time
from pathlib import Path

from .case import Case


def _row(check, target, value, source, ok, fidelity=None, note=""):
    if ok is None:
        res = "NOT CHECKED"
    elif ok:
        res = "PASS"
    else:
        res = "FAIL (model-limited)" if fidelity else "FAIL"
    return {"check": check, "target": target, "this_run": value, "source": source, "result": res,
            "fidelity": "; ".join(fidelity) if fidelity else "", "note": note}


def _fmt(x, nd=3):
    return "missing" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def scorecard(case: Case, stages: dict) -> list[dict]:
    rows = []
    sz, geo, cfd, st = (stages.get(k) or {} for k in ("sizing", "geometry", "cfd", "structural"))
    lu = "in"  # display unit for lengths follows the case's own unit
    if case.raw("limits.exit_blade_height_max"):
        lu = case.raw("limits.exit_blade_height_max")["unit"]

    # 1 casing fit (exit blade height from sizing)
    hmax = case.q("limits.exit_blade_height_max", lu)
    h = sz.get("exit_blade_height", {}).get(lu) if sz.get("status") == "ok" else None
    # A casing-fit FAIL is a real FAIL: the required exit height already exceeds the casing limit at the sizing
    # stage, so no higher-fidelity model can make it fit. The 1D fidelity note is therefore not attached here.
    rows.append(_row("Fits casing (impeller exit blade height)", f"<= {hmax:.4g} {lu}",
                     f"{h:.4g} {lu}" if h is not None else "missing", "sizing (1D)",
                     None if h is None else h <= hmax + 1e-12, None,
                     note="geometric limit; the 1D sizing already exceeds it" if h is not None and h > hmax else ""))

    # 2 speed: every simulation stage must report the case speed
    rpm = case.q("operating_point.speed", "rpm")
    used = {k: (stages.get(k) or {}).get("speed_rpm") for k in ("sizing", "cfd")}
    have = {k: v for k, v in used.items() if v is not None}
    ok = None if not have else all(abs(v - rpm) < 0.5 for v in have.values())
    rows.append(_row("Speed unchanged", f"{rpm:,.0f} rpm",
                     ", ".join(f"{k} {v:,.0f}" for k, v in have.items()) or "missing", "sizing, CFD", ok))

    # 3-5 aero from CFD. Gate: unless a matching baseline calibration says CALIBRATED, the CFD numbers are not
    # decision-grade: a would-be PASS becomes NOT CHECKED and a FAIL is labelled model-limited, both noted
    # "model not calibrated" (never a PASS from an uncalibrated model).
    from . import calibration as calmod
    cal = stages.get("cfd_calibration")
    cal_ok, cal_why = calmod.applies(cal, calmod.model_signature(stages, case)) if cfd else (False, "")
    if cal_ok and cal.get("status") != calmod.CALIBRATED:
        cal_ok, cal_why = False, "baseline NOT CALIBRATED: " + "; ".join(cal.get("reasons") or [])
    fu = case.raw("targets.corrected_flow_min")["unit"]
    fmin = case.q("targets.corrected_flow_min", fu)
    cf = cfd.get("corrected_flow", {}).get(fu) if cfd.get("status") in ("ok", "partial") else None
    fid = list(cfd.get("fidelity") or [])
    if cfd and not cal_ok:
        fid.append("model not calibrated")
    gnote = "" if cal_ok or not cfd else f"model not calibrated ({cal_why})"
    # A non-converged CFD result is not a solution of the model: its numbers are shown but never scored
    # (NOT CHECKED), whatever the calibration status.
    conv_ok = bool(cfd.get("converged"))
    if cfd and not conv_ok:
        gnote = "CFD not converged: values are not a solution" + (f"; {gnote}" if gnote else "")

    def gate(ok):
        if cfd and not conv_ok:
            return None
        return None if (ok and not cal_ok) else ok
    # Design-point runs (DEC-19): flow is imposed at the target, so the flow row reports whether the target was
    # REACHED; a passage that chokes below the target is a real FAIL with the maximum flow achieved. Because the
    # model over-predicts baseline flow (calibration), a model choke below target is not an optimistic artefact.
    if cfd.get("choked"):
        rows.append(_row("Inlet corrected flow", f">= {fmin:.4g} {fu}",
                         f"choked at {cf:.4g} {fu} (maximum flow of the passage)", "CFD (design flow target)",
                         False, None, note="passage chokes below the target flow"))
        for lbl, tgt in (("Total pressure ratio", f">= {case.q('targets.pressure_ratio_min', '-'):.3f}"),
                         ("Adiabatic efficiency (t-t)", f">= {case.q('targets.efficiency_tt_min', '-'):.3f}")):
            rows.append(_row(lbl, tgt, "not reached (target flow not achieved)", "CFD", None, fid,
                             note="no operating point at the target flow"))
        return _rows_tail(case, stages, rows)
    flow_src = "CFD (design flow target)" if cfd.get("outlet_condition", "").startswith("design flow target") else \
        ("CFD (speedline at target flow)" if cfd.get("outlet_condition", "").startswith("speedline") else "CFD")
    if cfd.get("outlet_condition", "").startswith("speedline") and not conv_ok:
        mx = (cfd.get("max_converged_flow") or {}).get(fu)
        v = (f"max converged flow {mx:.4g} {fu} (>= target); no converged point AT the target" if mx is not None
             else "no converged speedline point")
        note = (cfd.get("note") or "no converged speedline bracket around the target flow") + (
            f"; {gnote}" if gnote else "")
        for lbl, tgt in (("Inlet corrected flow", f">= {fmin:.4g} {fu}"),
                         ("Total pressure ratio", f">= {case.q('targets.pressure_ratio_min', '-'):.3f}"),
                         ("Adiabatic efficiency (t-t)", f">= {case.q('targets.efficiency_tt_min', '-'):.3f}")):
            rows.append(_row(lbl, tgt, v if lbl.startswith("Inlet") else "not available at the target flow",
                             flow_src, None, fid, note=note))
        return _rows_tail(case, stages, rows)
    rows.append(_row("Inlet corrected flow", f">= {fmin:.4g} {fu}", f"{cf:.4g} {fu}" if cf is not None else "missing",
                     flow_src, gate(None if cf is None else cf >= fmin), fid, note=gnote))
    prmin = case.q("targets.pressure_ratio_min", "-")
    pr = cfd.get("PR_tt") if cfd.get("status") in ("ok", "partial") else None
    rows.append(_row("Total pressure ratio", f">= {prmin:.3f}", _fmt(pr), flow_src,
                     gate(None if pr is None else pr >= prmin), fid, note=gnote))
    emin = case.q("targets.efficiency_tt_min", "-")
    eta = cfd.get("eta_isen_tt") if cfd.get("status") in ("ok", "partial") else None
    rows.append(_row("Adiabatic efficiency (t-t)", f">= {emin:.3f}", _fmt(eta), flow_src,
                     gate(None if eta is None else eta >= emin), fid, note=gnote))
    return _rows_tail(case, stages, rows)


def _rows_tail(case: Case, stages: dict, rows: list[dict]) -> list[dict]:
    """Strength, sizing estimate and roadmap rows (shared by every aero outcome)."""
    sz, st = (stages.get(k) or {} for k in ("sizing", "structural"))
    fu = case.raw("targets.corrected_flow_min")["unit"]
    fmin = case.q("targets.corrected_flow_min", fu)

    # 6 strength: judged on the mesh-converged body stress (away from sharp edges). The peak at sharp edges is a
    # singularity when it keeps rising with refinement; it is shown, not used. Unconverged or failed hand check ->
    # NOT CHECKED (never PASS).
    sf = case.q("structural.safety_factor_min", "-")
    ys = case.q("material.yield_strength", "Pa")
    su = case.raw("material.yield_strength")["unit"]
    from .units import convert
    allow = convert(ys / sf, "Pa", su)
    ok_st = st.get("status") == "ok"
    body = st.get("body_stress_Pa") if ok_st else None
    fil = st.get("fillet_stress_Pa") if ok_st else None
    gov = st.get("governing_stress_Pa") if ok_st else None
    pk = st.get("peak_stress_Pa") if ok_st else None
    # DEC-15: judged on the higher of bulk and root/fillet stress; both mesh-converged, hand check not failed.
    trusted = bool(gov) and st.get("governing_converged") and st.get("hand_check_ok") is not False
    val = "missing"
    cv = lambda x: f"{convert(x, 'Pa', su):,.0f} {su}"
    if gov:
        val = (f"governing {cv(gov)} at {st.get('governing_location')} (SF {ys / gov:.2f}); bulk {cv(body)}; "
               f"root/fillet {cv(fil)}; single-node peak {cv(pk)}"
               f"{' (not mesh-converged)' if not st.get('peak_converged') else ''}")
    elif body:
        val = f"bulk {cv(body)}; root/fillet stress missing"
    note = ""
    if body and not fil:
        note = "root/fillet zone not evaluated"
    elif gov and not st.get("body_converged"):
        note = "bulk stress not mesh-converged"
    elif gov and not st.get("fillet_converged"):
        note = "root/fillet stress not mesh-converged"
    elif gov and st.get("hand_check_ok") is False:
        note = "FE disagrees with hand calculation by more than 10x"
    rows.append(_row(f"Strength at overspeed, SF >= {sf:g}", f"< {allow:,.0f} {su}", val, "structural",
                     (ys / gov >= sf) if trusted else None, st.get("fidelity"), note=note))

    # 7 sizing estimate (clearly an estimate)
    fb = case.q("baseline.corrected_flow", fu)
    gain_t = (fmin / fb - 1) * 100
    g = sz.get("flow_gain_pct") if sz.get("status") == "ok" else None
    rows.append(_row("Flow increase at sizing (1D ESTIMATE)", f">= {gain_t:+.1f}%",
                     f"{g:+.1f}%" if g is not None else "missing", "sizing (1D)",
                     # the sizing stage stores the gain rounded to 0.01 %; compare at that resolution
                     None if g is None else g >= round(gain_t, 2) - 0.005, sz.get("fidelity")))

    # roadmap items: never PASS
    for label, key, why in (("Surge margin", "targets.surge_margin_min", "needs a speedline (several CFD points)"),
                            ("Shaft power increase", "targets.shaft_power_increase_max", "not computed in V2"),
                            ("Running tip clearance", "mechanical_criteria.tip_clearance_min",
                             "needs thermal + deformation run (roadmap)"),
                            ("Campbell diagram", "mechanical_criteria.campbell_margin", "needs modal run (roadmap)")):
        if case.raw(key) is None:
            rows.append(_row(label, "not in case", "-", "-", None) | {"result": "NOT REQUESTED"})
        else:
            v = case.raw(key)
            rows.append(_row(label, f"{v['value']} {v['unit']}", "not simulated", why, None))
    return rows


def verdict(rows: list[dict]) -> str:
    checked = [r for r in rows if r["result"].startswith(("PASS", "FAIL"))]
    fails = [r for r in checked if r["result"].startswith("FAIL")]
    open_ = [r for r in rows if r["result"] == "NOT CHECKED"]
    if not checked:
        return "INCOMPLETE: no checks were run"
    if fails:
        ml = sum(1 for r in fails if "model-limited" in r["result"])
        s = f"FAIL: {len(fails)} of {len(checked)} checks fail ({', '.join(r['check'] for r in fails)})"
        if ml:
            s += f"; {ml} of these come from a simplified model and need engineering review"
        return s
    if open_:
        return f"PASS ON CHECKED ITEMS ONLY: {len(checked)} pass, {len(open_)} not checked (not a release PASS)"
    return f"PASS: all {len(checked)} checks pass"


def structural_section(st: dict) -> list[str]:
    """Mesh study table and hand calculation for REPORT.md (empty when no structural study was recorded)."""
    study = st.get("mesh_study") or []
    if not study:
        return []
    L = ["", "## Structural: mesh study and hand check", "",
         "| Element size (mm) | Nodes | Single-node peak (MPa) | Bulk p99 (MPa) | Root/fillet p99 (MPa) | Solve |",
         "|---|---|---|---|---|---|"]
    for s in study:
        f = lambda k: f"{s[k] / 1e6:,.1f}" if s.get(k) else "-"
        L.append(f"| {s['size_m'] * 1e3:.2f} | {s.get('nodes', '-'):,} | {f('peak_Pa')} | {f('body_p99_Pa')} | "
                 f"{f('fillet_p99_Pa')} | {s.get('solve', s.get('skipped', '-'))} |")
    pc, bc, fc = st.get("peak_change"), st.get("body_change"), st.get("fillet_change")
    pct = lambda x: f"{x:.1%}" if x is not None else "n/a"
    L += ["", f"Change between the two finest meshes: peak {pct(pc)}, bulk {pct(bc)}, root/fillet {pct(fc)} "
              f"(tolerance {st.get('convergence_tol', 0):.0%}).",
          f"Excluded (singular modelling cuts only): nodes within {st.get('exclude_m', 0) * 1e3:.1f} mm of the "
          "hub-slice cut planes and the fixed-support face. The blade root and fillet are NOT excluded: nodes within "
          f"{st.get('root_zone_m', 0) * 1e3:.1f} mm of the root line form the root/fillet zone; all other blade "
          "nodes form the bulk. The check uses the higher of the two (99th percentile each)."]
    h = st.get("hand_check")
    if h:
        L += ["", "Hand calculation (radial blade pull, upper-bound estimate): "
              f"sigma = rho * omega^2 * (r_tip^2 - r_root^2) / 2 with omega = {h['omega_rad_s']:.1f} rad/s, tip speed "
              f"{h['tip_speed_m_s']:.0f} m/s gives {h['blade_pull_Pa'] / 1e6:,.0f} MPa. FE body stress / hand = "
              f"{st.get('hand_check_ratio', 0):.2f} ({'within' if st.get('hand_check_ok') else 'NOT within'} an order "
              "of magnitude). The hand value is higher because it assumes a straight radial blade carrying its full "
              "length in tension; the real blade root spreads load into the hub."]
    return L


def calibration_section(cal: dict | None) -> list[str]:
    """CFD calibration table for REPORT.md. Always present: says plainly when no calibration exists."""
    L = ["", "## CFD calibration against measured baseline", ""]
    if not cal:
        return L + ["No baseline calibration linked to this run: CFD results are **model not calibrated**."]
    L += [f"Status: **{cal['status']}** (baseline run `{Path(cal['baseline_run']).name}`, measured reference: "
          f"{cal['pr_reference']}).", "",
          "| Quantity | Measured (case) | Baseline model | Error | Tolerance (case) | Result |", "|---|---|---|---|---|---|"]
    for it in cal["items"]:
        rel = it.get("kind") == "relative"
        f = lambda x: "-" if x is None else f"{x:.4g}"
        err = "-" if it["error"] is None else (f"{it['error']:+.1%}" if rel else f"{it['error']:+.3f}")
        tol = f"{it['tolerance']:.0%}" if rel else f"{it['tolerance']:.3f}"
        L.append(f"| {it['quantity']} | {f(it['measured'])} | {f(it['model'])} | {err} | {tol} | {it['result']} |")
    if cal.get("reasons"):
        L += ["", "Reasons: " + "; ".join(cal["reasons"]) + "."]
    return L


def write_markdown(case: Case, run_dir: Path, rec: dict, rows: list[dict]) -> Path:
    v = verdict(rows)
    L = [f"# Re-rate report: {case.name}", "",
         f"Run folder: `{run_dir.name}`  ", f"Case approved by: {(case.data.get('approval') or {}).get('approved_by')}  ",
         f"Generated {time.strftime('%Y-%m-%d %H:%M')} from this run's recorded stage outputs only.", "",
         f"## Verdict: {v}", "",
         "| Check | Target (case) | This run | Source | Result | Model fidelity |", "|---|---|---|---|---|---|"]
    L += [f"| {r['check']} | {r['target']} | {r['this_run']} | {r['source']} | **{r['result']}** | {r['fidelity']} |"
          for r in rows]
    L += [f"\nNote: {r['check']}: {r['note']}" for r in rows if r.get("note")]
    L += calibration_section(rec.get("stages", {}).get("cfd_calibration"))
    L += structural_section(rec.get("stages", {}).get("structural") or {})
    L += ["", "## Stage status", ""]
    for name, s in rec.get("stages", {}).items():
        L.append(f"- **{name}**: {s.get('status')}"
                 + (f"; fidelity: {'; '.join(s['fidelity'])}" if s.get("fidelity") else "")
                 + (f"; note: {s['note']}" if s.get("note") else ""))
    L += ["", "## Needs human review", "",
          "- Any row marked FAIL (model-limited) or NOT CHECKED.",
          "- Every case value marked as an engineering assumption in case.yaml (see its `source`).",
          "- This report is a screening result, not a release to manufacturing.", ""]
    imgs = sorted(p.name for p in run_dir.glob("*.png"))
    if imgs:
        L += ["## Images", ""] + [f"![{i}]({i})" for i in imgs]
    out = run_dir / "REPORT.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return out
