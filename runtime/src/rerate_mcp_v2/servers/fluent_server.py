"""fluent_v2 MCP server: passage CFD. No tool blocks on Fluent:
- connect_start {} / setup_start {}: background jobs; poll prep_status. Cores, GPU and GUI/no-GUI from the config.
- solve_start {chunk, time_limit_s}: starts iterating in a background thread and returns immediately.
- solve_status {}: progress (iterations done, last PR/eta/mass imbalance, running/finished/error).
- solve_stop {}: ask the background solve to stop after the current chunk.
- solve_fetch {}: final performance + convergence verdict (also recorded automatically when the solve ends).
- images {}: pressure contour on blade + hub, instanced around the wheel.   - disconnect {}
"""
from __future__ import annotations

import contextlib
import io
import threading
import time
from pathlib import Path

from fastmcp import FastMCP

from .. import config, fluent_setup as fs, runs
from ..units import convert
from .common import close_apps, enter_work_dir, free_seat_for, license_denials, run_server
from .jobs import Job, gui_guard, gui_mode, launch_timeout

mcp = FastMCP("fluent-v2")
_S: dict = {"s": None, "solver_desc": None}
_JOB: dict = {"thread": None, "state": "idle", "stop": False, "hist": [], "done": 0, "error": None,
              "t0": None, "max": 0, "converged": False, "stop_reason": None}
_LOCK = threading.Lock()


def _alive() -> bool:
    try:
        _S["s"].get_fluent_version()
        return True
    except Exception:
        return False


PREP = Job("fluent-prep")  # connect + setup run here; the solve keeps its own iteration loop below


def _connect_job(job: Job) -> dict:
    import ansys.fluent.core as pf
    n = int(config.get("fluent.processors"))
    gpu = bool(config.get("fluent.gpu", required=False))
    ui = "gui" if gui_mode("fluent") == "gui" else "no_gui"
    job.set_step("freeing license seat")
    free_seat_for("fluent")
    errs = []
    for attempt in (1, 2):
        job.set_step(f"launching Fluent ({ui}, attempt {attempt})")
        try:
            kw = dict(mode="solver", ui_mode=ui, dimension=3, precision="double", processor_count=n,
                      cwd=str(runs.active_run()), start_timeout=launch_timeout("fluent"))
            if gpu:
                kw["gpu"] = True
            _S["s"] = pf.launch_fluent(**kw)
            _S["solver_desc"] = f"{'GPU' if gpu else 'CPU'}, {n} processes, {ui}"
            return {"status": "ok", "attempts": attempt, "solver": _S["solver_desc"],
                    "version": _S["s"].get_fluent_version(), "license_denials": license_denials()}
        except Exception as e:
            errs.append(str(e)[:300])
            _S["s"] = None
            close_apps(["fluent"])
            time.sleep(3)
    raise RuntimeError("Fluent did not start: " + " | ".join(errs) + f" | denials: {license_denials()}")


@mcp.tool
def connect_start() -> dict:
    """Start launching Fluent 3D double precision in the background (GUI or no-GUI per apps.fluent.mode; cores and
    GPU from the config). Returns at once; poll prep_status. Fails at once on a disconnected desktop in GUI mode."""
    if _S["s"] is not None and _alive():
        return {"status": "ok", "note": "already connected", "solver": _S["solver_desc"]}
    bad = gui_guard("fluent")
    if bad:
        return bad
    return PREP.start(_connect_job, launch_timeout("fluent") * 2 + 60)


def _setup_job(job: Job) -> dict:
    run = runs.active_run()
    c = runs.run_case(run)
    c.require_stage("cfd")
    gtm = run / "passage.gtm"
    if not gtm.exists():
        raise RuntimeError("no passage.gtm in this run; run the meshing stage")
    if _S["s"] is None or not _alive():
        raise RuntimeError("Fluent is not connected; call connect_start and wait for finished")
    rpm = c.q("operating_point.speed", "rpm") * int(c.val("operating_point.rotation_sign"))
    args = dict(rpm=rpm, pt_in_pa=c.q("operating_point.inlet_total_pressure", "Pa"),
                tt_in_k=c.q("operating_point.inlet_total_temperature", "K"),
                p_out_pa=c.q("cfd.outlet_static_pressure", "Pa"), turbulence=str(c.val("cfd.turbulence_model")))
    air = config.get("fluent.air", required=False)
    job.set_step("importing mesh and setting up the passage")
    log = fs.setup_passage(_S["s"], str(gtm), **args, air=air)
    _S["air"] = air
    job.set_step("hybrid initialisation")
    _S["s"].settings.solution.initialization.hybrid_initialize()
    res = {"status": "ok", **args, "log": log, "initialized": "hybrid", "solver": _S["solver_desc"]}
    _S["diag_p_out"] = None
    _S["start_path"] = None
    _S["design_target"] = None
    _S["speedline_since"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _S["with_splitter"] = bool((runs.stage("meshing") or {}).get("with_splitter"))
    runs.record("cfd_setup", res)
    with _LOCK:
        _JOB.update(state="ready", hist=[], done=0, error=None, converged=False, stop_reason=None)
    return res


@mcp.tool
def setup_start() -> dict:
    """Start importing this run's passage mesh and setting up the rotating passage from the approved case (speed,
    inlet total pressure/temperature, outlet static pressure, turbulence model) in the background. Poll
    prep_status. Records stage 'cfd_setup'."""
    return PREP.start(_setup_job, 900)


@mcp.tool
def prep_status() -> dict:
    """State of the current connect/setup job; returns immediately."""
    return PREP.status()


def _conv_settings() -> dict:
    c = runs.run_case()
    return {"imb": c.q("cfd.convergence.mass_imbalance_max", "-"), "stab": c.q("cfd.convergence.stability_tol", "-"),
            "window": int(c.val("cfd.convergence.window_iterations"))}


def converged(hist: list[dict], imb_max: float, stab: float, window: int) -> tuple[bool, dict]:
    """Pure check (unit-tested) over the last `window` iterations (all samples from the reference point, which
    is the latest sample at least `window` iterations before the last one):
    - mass imbalance <= imb_max on EVERY sample in the window (not only the last one), and
    - flow, PR and eta each have a relative max-min spread <= `stab` over the window (an oscillation that happens
      to return to its start value does not pass)."""
    if not hist:
        return False, {}
    last = hist[-1]
    old = [h for h in hist if h["iters"] <= last["iters"] - window]
    if not old:
        return False, {"reason": "fewer iterations than the stability window"}
    ref = old[-1]
    win = [h for h in hist if h["iters"] >= ref["iters"]]
    d = {}
    for k in ("mdot_in", "PR", "eta"):
        v = [h[k] for h in win]
        if any(x != x for x in v):  # NaN (e.g. no throughflow)
            d[k] = float("inf")
        else:
            d[k] = (max(v) - min(v)) / max(abs(ref[k]), 1e-12)
    imb_worst = max(h["imbalance"] for h in win)
    ok = imb_worst <= imb_max and all(v <= stab for v in d.values())
    return ok, {"imbalance": last["imbalance"], "imbalance_max_in_window": imb_worst,
                "spread_over_window": {k: round(v, 5) for k, v in d.items()},
                "window_from_iter": ref["iters"], "samples_in_window": len(win)}


def _reversed_inlet_pct() -> float | None:
    """Latest 'Reversed flow on N faces (X% area) of pressure-inlet' from this run's Fluent transcript; 0 if the
    last chunk printed none. Fluent prints it only when reversal exists."""
    import re as _re
    trn = sorted(runs.active_run().glob("fluent-*.trn"), key=lambda p: p.stat().st_mtime)
    if not trn:
        return None
    tail = trn[-1].read_text(errors="ignore")[-20000:]
    lines = tail.splitlines()
    it_lines = [i for i, l in enumerate(lines) if _re.match(r"^\s+\d+\s+\d\.\d+e", l)]
    if not it_lines:
        return None
    seg = lines[it_lines[-2] if len(it_lines) > 1 else 0:]
    m = [float(x) for x in _re.findall(r"Reversed flow on \d+ faces \(([\d.]+)% area\) of pressure-inlet", "\n".join(seg))]
    return m[-1] if m else 0.0


def _worker(chunk: int, n_max: int, t_lim: float):
    s = _S["s"]
    so = s.settings.solution
    cs = _conv_settings()
    try:
        while True:
            with _LOCK:
                if _JOB["stop"]:
                    _JOB["stop_reason"] = "stopped by request"; break
                if _JOB["done"] >= n_max:
                    _JOB["stop_reason"] = "iteration limit"; break
                if time.time() - _JOB["t0"] > t_lim:
                    _JOB["stop_reason"] = "time limit"; break
            with contextlib.redirect_stdout(io.StringIO()):
                so.run_calculation.iterate(iter_count=chunk)
            pf = fs.performance(s, air=_S.get("air"))
            imb = abs(abs(pf["mdot_in"]) - abs(pf["mdot_out"])) / max(abs(pf["mdot_in"]), 1e-12)
            p_out = fs.outlet_static(s)
            with _LOCK:
                _JOB["done"] += chunk
                h = _JOB["hist"]
                h.append({"iters": _JOB["done"], "PR": pf["PR_tt"], "eta": pf["eta_isen_tt"],
                          "mdot_in": pf["mdot_in"], "imbalance": round(imb, 5), "t_s": round(time.time() - _JOB["t0"]),
                          "reversed_inlet_pct": _reversed_inlet_pct(), "p_out_pa": p_out})
                ok, info = converged(h, cs["imb"], cs["stab"], cs["window"])
                dt = _S.get("design_target")
                if dt:  # targeted-mass-flow run: also require the flow ON target, else detect choke
                    from .. import design_point as dpm
                    if h[-1]["p_out_pa"] is not None and h[-1]["p_out_pa"] <= dt["p_min_pa"] * 1.001:
                        h[-1]["at_lower_bound"] = True
                    v = dpm.choke_verdict(h, dt["mdot_passage_kg_s"], dt["flow_tol"], cs["window"])
                    info = dict(info, design_target=v)
                    if v["state"] == "choked":
                        _JOB["conv_info"] = info
                        _JOB["stop_reason"] = "choked below target flow"
                        break
                    ok = ok and v["state"] == "reached"
                _JOB["conv_info"] = info
                if ok:
                    _JOB["converged"] = True
                    _JOB["stop_reason"] = "converged"
                    break
        with _LOCK:
            _JOB["state"] = "finished"
        try:  # record immediately, so the result survives a client disconnect before solve_fetch
            _record_result()
        except Exception as e:
            with _LOCK:
                _JOB["error"] = f"auto-record failed: {str(e)[-300:]}"
    except Exception as e:
        with _LOCK:
            _JOB.update(state="error", error=str(e)[-1500:])


@mcp.tool
def solve_start(chunk: int, time_limit_s: int) -> dict:
    """Start iterating in the background and return at once. chunk: iterations between progress checks
    (e.g. 50). time_limit_s: wall-clock cap for the whole solve. Iteration cap is cfd.max_iterations (case).
    Poll with solve_status every few minutes; call solve_fetch when it reports finished."""
    try:
        c = runs.run_case()
        if _S["s"] is None or not _alive():
            return {"status": "error", "message": "Fluent is not connected"}
        with _LOCK:
            if _JOB["state"] == "running":
                return {"status": "error", "message": "a solve is already running; poll solve_status"}
            if _JOB["state"] not in ("ready", "finished"):
                return {"status": "error", "message": "call setup first"}
            n_max = int(c.val("cfd.max_iterations"))
            _JOB.update(state="running", stop=False, t0=time.time(), max=n_max, error=None)
        th = threading.Thread(target=_worker, args=(int(chunk), n_max, float(time_limit_s)), daemon=True)
        _JOB["thread"] = th
        th.start()
        return {"status": "ok", "state": "running", "max_iterations": n_max, "chunk": chunk,
                "time_limit_s": time_limit_s, "next": "poll solve_status"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def set_back_pressure(outlet_static_pressure_pa: float, reason: str, reinitialize: bool = False) -> dict:
    """DIAGNOSTIC ONLY (e.g. back-pressure sweep): change the outlet static pressure of the set-up passage. By
    default the next solve_start continues from the current solution; reinitialize=True runs hybrid initialisation
    first (use after a stalled point). The value is recorded as a diagnostic point; it does not replace the case
    value used for calibration and reports."""
    try:
        if _S["s"] is None or not _alive():
            return {"status": "error", "message": "Fluent is not connected"}
        with _LOCK:
            if _JOB["state"] == "running":
                return {"status": "error", "message": "a solve is running; wait for finished"}
            _JOB.update(state="ready", hist=[], done=0, error=None, converged=False, stop_reason=None)
        po = _S["s"].settings.setup.boundary_conditions.pressure_outlet["outlet"]
        po.momentum.gauge_pressure.value = float(outlet_static_pressure_pa)
        try:
            po.momentum.target_mass_flow_rate = False
        except Exception:
            pass
        _S["design_target"] = None
        _S["diag_p_out"] = float(outlet_static_pressure_pa)
        if reinitialize:
            _S["s"].settings.solution.initialization.hybrid_initialize()
        return {"status": "ok", "outlet_static_pressure_pa": float(outlet_static_pressure_pa), "reason": reason,
                "next": "solve_start, then solve_fetch records a diagnostic point (not the calibration result)"}
    except Exception as e:
        return {"status": "error", "message": str(e)[-800:]}


@mcp.tool
def restore_case_back_pressure(reason: str, force_unconverged_start: bool = False) -> dict:
    """Set the outlet back to the APPROVED case value after a converged start field at a lower back pressure
    (back-pressure continuation). Refuses if the start field has not met the convergence rule (unless
    force_unconverged_start, which must be stated to the user). The next solve continues from the current solution
    and is recorded as the real stage 'cfd'. Only the initial field differs; the boundary condition is the case
    value."""
    try:
        if _S["s"] is None or not _alive():
            return {"status": "error", "message": "Fluent is not connected"}
        with _LOCK:
            if _JOB["state"] == "running":
                return {"status": "error", "message": "a solve is running; wait for finished"}
            # A start field must be a converged solution before stepping up: stepping from a still-moving field
            # can land on the stall side (a 250-iteration start field stalled where a converged one did not).
            if not force_unconverged_start and not (_JOB.get("converged") and _S.get("diag_p_out") is not None):
                return {"status": "error", "reason": "start_field_not_converged",
                        "message": ("The start field at the lower back pressure has not met the convergence rule "
                                    "yet. Run solve_start on the start field and wait until solve_status reports "
                                    "converged (or stop_reason 'converged'), then call this again.")}
            _JOB.update(state="ready", hist=[], done=0, error=None, converged=False, stop_reason=None)
        p = runs.run_case().q("cfd.outlet_static_pressure", "Pa")
        mo = _S["s"].settings.setup.boundary_conditions.pressure_outlet["outlet"].momentum
        mo.gauge_pressure.value = p
        try:
            mo.target_mass_flow_rate = False
        except Exception:
            pass
        _S["design_target"] = None
        _S["diag_p_out"] = None
        _S["start_path"] = reason
        return {"status": "ok", "outlet_static_pressure_pa": p, "reason": reason,
                "next": "solve_start; the result is recorded as stage 'cfd'"}
    except Exception as e:
        return {"status": "error", "message": str(e)[-800:]}


@mcp.tool
def set_design_flow_target(reason: str) -> dict:
    """DESIGN POINT (DEC-19): switch the outlet to a targeted mass flow equal to the case corrected-flow target
    (targets.corrected_flow_min), converted to physical flow per passage at the case inlet conditions. The outlet
    static pressure floats; PR and efficiency are read at the target flow. Pressure bounds: lower =
    config fluent.design_point.min_static_to_inlet_total x inlet total, upper = max_pressure_ratio x inlet total.
    The solve stops when converged ON target, or as 'choked below target flow' when the flow cannot reach it.
    Continue from a converged start field (e.g. a low back-pressure solution)."""
    try:
        from .. import design_point as dpm
        if _S["s"] is None or not _alive():
            return {"status": "error", "message": "Fluent is not connected"}
        with _LOCK:
            if _JOB["state"] == "running":
                return {"status": "error", "message": "a solve is running; wait for finished"}
            _JOB.update(state="ready", hist=[], done=0, error=None, converged=False, stop_reason=None)
        c = runs.run_case()
        fu = c.raw("targets.corrected_flow_min")["unit"]
        pt = c.q("operating_point.inlet_total_pressure", "Pa")
        m_t = dpm.target_passage_mass_flow(
            c.q("targets.corrected_flow_min", "kg/s"), int(c.val("geometry.main_blades")), pt,
            c.q("operating_point.inlet_total_temperature", "K"), c.q("operating_point.reference_pressure", "Pa"),
            c.q("operating_point.reference_temperature", "K"))
        dcfg = config.get("fluent.design_point")
        p_min = pt * float(dcfg["min_static_to_inlet_total"])
        p_max = pt * float(dcfg["max_pressure_ratio"])
        m = _S["s"].settings.setup.boundary_conditions.pressure_outlet["outlet"].momentum
        m.target_mass_flow_rate = True
        m.target_mass_flow = {"option": "value", "value": m_t}
        m.lower_limit_of_abs_pressure = p_min
        m.upper_limit_of_abs_pressure = p_max
        _S["diag_p_out"] = None
        _S["design_target"] = {"mdot_passage_kg_s": m_t, "corrected": c.q("targets.corrected_flow_min", fu),
                               "unit": fu, "flow_tol": float(dcfg["flow_tol"]), "p_min_pa": p_min, "p_max_pa": p_max}
        _S["start_path"] = reason
        return {"status": "ok", "method": "targeted mass flow at the outlet", **_S["design_target"],
                "next": "solve_start; the result is recorded as stage cfd with the design-flow-target condition"}
    except Exception as e:
        return {"status": "error", "message": str(e)[-800:]}


@mcp.tool
def speedline_result(reason: str, since: str | None = None) -> dict:
    """SPEEDLINE FALLBACK (DEC-19 step 3): use the CONVERGED diagnostic back-pressure points recorded in this run
    (stage cfd_diagnostic, from set_back_pressure + solve_start) as a speedline, and interpolate PR and efficiency
    linearly at the case flow target between the two bracketing points. No extrapolation. Records stage 'cfd'
    (outlet_condition 'speedline at target flow'); unconverged points are ignored and listed.
    since: 'YYYY-mm-dd HH:MM:SS'; only points recorded at or after this time (default: the current Fluent
    set-up)."""
    try:
        from .. import design_point as dpm
        c = runs.run_case()
        fu = c.raw("targets.corrected_flow_min")["unit"]
        target = c.q("targets.corrected_flow_min", fu)
        pts_all = (runs.stage("cfd_diagnostic") or {}).get("points", [])
        # only points from the current speedline (same set-up session): earlier diagnostic points of this run
        # may come from a different start or model state
        since = since or _S.get("speedline_since") or ""
        pts_all = [p for p in pts_all if str(p.get("recorded_at", "")) >= since]
        conv = [p for p in pts_all if p.get("converged")]
        pts = [{"mdot": (p.get("corrected_flow") or {}).get(fu), "PR": p.get("PR_tt"), "eta": p.get("eta_isen_tt"),
                "p_out_pa": p.get("outlet_static_pressure_pa")} for p in conv]
        r = dpm.interpolate_at_flow(pts, target)
        ignored = [p.get("outlet_static_pressure_pa") for p in pts_all if not p.get("converged")]
        msh = runs.stage("meshing") or {}
        gap = float(msh.get("tip_clearance_m") or 0.0)
        fid = ["single impeller passage, no vaned diffuser",
               f"shroud tip gap {gap * 1e3:.3f} mm" if gap > 0 else "no tip clearance gap",
               "main blade and splitter" if msh.get("with_splitter") else "main blade only (no splitter)",
               "PR/eta interpolated linearly on a speedline"]
        res = {"status": "ok" if r["status"] == "ok" else "partial", "converged": r["status"] == "ok",
               "outlet_condition": "speedline at target flow (DEC-19 fallback)", "reason": reason,
               "speed_rpm": c.q("operating_point.speed", "rpm"),
               "corrected_flow": {fu: target} if r["status"] == "ok" else {},
               "PR_tt": r.get("PR"), "eta_isen_tt": r.get("eta"), "outlet_static_pressure_pa": r.get("p_out_pa"),
               "speedline": pts, "interpolation": r, "ignored_unconverged_points_pa": ignored}
        # Choke below target: the highest converged flow is a choked point (flow insensitive to back pressure)
        # and still below the target -> real FAIL with the maximum flow (DEC-19 step 2).
        if pts and max(x["mdot"] for x in pts) < target:
            best = max(pts, key=lambda x: x["mdot"])
            res.update(choked=True, corrected_flow={fu: best["mdot"]},
                       note="target flow above the highest converged (choke) flow")
        elif r["status"] != "ok":
            res["max_converged_flow"] = {fu: max(x["mdot"] for x in pts)} if pts else None
            res["note"] = ("no converged speedline bracket around the target flow; unconverged points ignored: "
                           f"{len(ignored)}")
        runs.record("cfd", res, fidelity=fid)
        return res
    except Exception as e:
        return {"status": "error", "message": str(e)[-800:]}


@mcp.tool
def model_check() -> dict:
    """Read-only diagnostics of the set-up passage: domain extents (m), rotation axis and speed, and mass-weighted
    velocities (absolute/relative tangential, radial, axial) at inlet and outlet. Use to verify units/scale,
    rotation direction vs blade orientation (absolute outlet swirl must have the sign of the rotation) and the
    inlet condition (absolute inlet swirl should be near zero for an axial inlet)."""
    try:
        s = _S["s"]
        rd = s.settings.solution.report_definitions
        cz = list(s.settings.setup.cell_zone_conditions.fluid.keys())
        names = []
        for ax in ("x", "y", "z"):
            for kind in ("min", "max"):
                n = f"chk_{ax}_{kind}"
                if n not in rd.volume.keys():
                    rd.volume[n] = {}
                r = rd.volume[n]; r.report_type = f"volume-{kind}"; r.field = f"{ax}-coordinate"; r.cell_zones = cz
                names.append(n)
        for fld, z in (("tangential-velocity", "inlet"), ("axial-velocity", "inlet"),
                       ("tangential-velocity", "outlet"), ("rel-tangential-velocity", "outlet"),
                       ("radial-velocity", "outlet"), ("absolute-pressure", "outlet"), ("mach-number", "inlet")):
            n = f"chk_{fld}_{z}".replace("-", "_")
            if n not in rd.surface.keys():
                rd.surface[n] = {}
            r = rd.surface[n]; r.report_type = "surface-massavg"; r.field = fld; r.surface_names = [z]
            names.append(n)
        vals = rd.compute(report_defs=names)
        res = {list(v)[0]: round(list(v.values())[0][0], 5) for v in vals}
        rf = s.settings.setup.cell_zone_conditions.fluid[cz[0]].reference_frame
        res["axis"] = list(rf.reference_frame_axis_direction())
        res["omega_rad_s"] = rf.mrf_omega.value()
        return {"status": "ok", **res}
    except Exception as e:
        return {"status": "error", "message": str(e)[-1200:]}


@mcp.tool
def solve_status() -> dict:
    """Progress of the background solve. Safe to call any time; returns immediately."""
    with _LOCK:
        h = list(_JOB["hist"])
        el = round(time.time() - _JOB["t0"]) if _JOB["t0"] else 0
        return {"status": "ok", "state": _JOB["state"], "iterations": _JOB["done"], "max_iterations": _JOB["max"],
                "elapsed_s": el, "s_per_iteration": round(el / _JOB["done"], 2) if _JOB["done"] else None,
                "last": h[-3:], "converged": _JOB["converged"], "stop_reason": _JOB["stop_reason"],
                "convergence": _JOB.get("conv_info"), "error": _JOB["error"]}


@mcp.tool
def solve_stop() -> dict:
    """Ask the running solve to stop after the current chunk."""
    with _LOCK:
        _JOB["stop"] = True
    return {"status": "ok", "note": "stop requested; poll solve_status until finished"}


def _record_result() -> dict:
    """Compute final performance, record stage 'cfd', and save case+data in the run folder."""
    with _LOCK:
        hist, conv, why, done = list(_JOB["hist"]), _JOB["converged"], _JOB["stop_reason"], _JOB["done"]
    c = runs.run_case()
    pf = fs.performance(_S["s"], air=_S.get("air"))
    cf = fs.corrected_flow_kg_s(pf["mdot_in"], int(c.val("geometry.main_blades")),
                                c.q("operating_point.inlet_total_pressure", "Pa"),
                                c.q("operating_point.inlet_total_temperature", "K"),
                                c.q("operating_point.reference_pressure", "Pa"),
                                c.q("operating_point.reference_temperature", "K"))
    fu = c.raw("targets.corrected_flow_min")["unit"]
    msh = runs.stage("meshing") or {}
    gap = float(msh.get("tip_clearance_m") or 0.0)
    fid = ["single impeller passage, no vaned diffuser",
           f"shroud tip gap {gap * 1e3:.3f} mm" if gap > 0 else "no tip clearance gap"]
    fid.append("main blade and splitter" if _S.get("with_splitter") else "main blade only (no splitter)")
    if not conv:
        fid.append(f"NOT converged ({why}, {done} iterations)")
    diag = _S.get("diag_p_out")
    stage = "cfd_diagnostic" if diag is not None else "cfd"
    saved = None
    try:
        f = runs.active_run() / (f"cfd_diag_{int(diag)}Pa.cas.h5" if diag is not None else "cfd_result.cas.h5")
        _S["s"].settings.file.write_case_data(file_name=str(f))
        saved = str(f)
    except Exception as e:
        saved = f"not saved: {str(e)[-200:]}"
    with _LOCK:
        info = _JOB.get("conv_info")
    res = {"status": "ok" if conv else "partial", "converged": conv, "stop_reason": why, "iterations": done,
           "speed_rpm": c.q("operating_point.speed", "rpm"), "PR_tt": pf["PR_tt"], "eta_isen_tt": pf["eta_isen_tt"],
           "corrected_flow": {fu: round(convert(cf, "kg/s", fu), 4), "kg/s": round(cf, 5)},
           "performance_per_passage": pf, "history_last": hist[-4:], "solver": _S["solver_desc"],
           "convergence": info, "reversed_inlet_pct": hist[-1].get("reversed_inlet_pct") if hist else None,
           "outlet_static_pressure_pa": diag if diag is not None else c.q("cfd.outlet_static_pressure", "Pa"),
           "case_data_file": saved, "start_path": _S.get("start_path") or "hybrid initialisation at the case value"}
    dt = _S.get("design_target")
    if dt:
        res["outlet_condition"] = "design flow target (targeted mass flow, DEC-19)"
        res["design_target"] = dt
        res["outlet_static_pressure_pa"] = hist[-1].get("p_out_pa") if hist else None
        res["design_target_state"] = ((info or {}).get("design_target") or {}).get("state")
        res["choked"] = why == "choked below target flow"
    else:
        res["outlet_condition"] = "case outlet static pressure"
    if stage == "cfd_diagnostic":
        prev = (runs.stage("cfd_diagnostic") or {}).get("points", [])
        res["recorded_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        runs.record(stage, {"status": "ok", "points": prev + [res]})
    else:
        runs.record("cfd", res, fidelity=fid)
    return res


@mcp.tool
def solve_fetch() -> dict:
    """After the solve finished: final performance, corrected flow in the case unit, convergence verdict.
    Records stage 'cfd' (also recorded automatically when the solve ends) with the model-fidelity list."""
    try:
        with _LOCK:
            if _JOB["state"] != "finished":
                return {"status": "error", "message": f"solve state is '{_JOB['state']}'; wait for finished",
                        "error": _JOB["error"]}
        return _record_result()
    except Exception as e:
        return {"status": "error", "message": str(e)[-1500:]}


@mcp.tool
def images() -> dict:
    """Pressure contour on hub + blade, instanced around the full wheel; PNGs into the run folder."""
    try:
        s = _S["s"]
        run = runs.active_run()
        g = s.settings.results.graphics
        pi = g.periodic_instances
        for n in list(pi.get_object_names()):
            pi.delete(name_list=[n])
        pi.detect_surfaces(clear_current_instances=True)
        if "v2_p" in g.contour.get_object_names():
            g.contour.delete(name_list=["v2_p"])
        g.contour.create(name="v2_p")
        cn = g.contour["v2_p"]
        allowed = cn.surfaces_list.allowed_values()
        walls = ["hub"] + [z for z in allowed if z.startswith(("bld-", "exportpoints")) and "ggi" not in z]
        cn.field = "pressure"
        cn.surfaces_list = walls
        cn.display()
        g.views.auto_scale()
        files = []
        for view in ("front", "isometric"):
            try:
                g.views.restore_view(view_name=view)
            except Exception:
                pass
            g.views.auto_scale()
            f = run / f"cfd_pressure_{view}.png"
            g.picture.save_picture(file_name=str(f))
            files.append(str(f))
        return {"status": "ok", "files": files, "surfaces": walls}
    except Exception as e:
        return {"status": "error", "message": str(e)[-1500:]}


@mcp.tool
def disconnect() -> dict:
    """Stop any running solve, close Fluent and its MPI helpers."""
    with _LOCK:
        _JOB["stop"] = True
    th = _JOB.get("thread")
    if th is not None and th.is_alive():
        th.join(timeout=120)
    try:
        if _S["s"] is not None:
            _S["s"].exit()
    except Exception:
        pass
    _S["s"] = None
    with _LOCK:
        _JOB.update(state="idle", thread=None)
    return {"status": "ok", "closed": close_apps(["fluent"])}


def main():
    enter_work_dir()
    run_server(mcp, "fluent_v2")


if __name__ == "__main__":
    main()
