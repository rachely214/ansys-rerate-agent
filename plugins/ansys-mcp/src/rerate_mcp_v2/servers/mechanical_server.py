"""mechanical_v2 MCP server: spin-stress check of the single blade at the case overspeed.

Non-blocking: every tool returns within seconds; long work runs as a background job.
- connect_start {}: launch Mechanical (GUI or batch per config apps.mechanical.mode) in the background.
- spin_stress_start {mesh_sizes, max_nodes?}: background job; imports this run's single-blade STEP, material from
  the case library file, rotational velocity = speed x limits.speed_max_fraction, fixed hub-slice bottom.
  The job records stage 'structural' itself (survives a client disconnect).
- job_status {}: state of the current job (running / finished / error / timeout) with the result when done.
- disconnect {}
The in-app script is a fixed file shipped with this package; only a JSON argument block is substituted.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from fastmcp import FastMCP

from .. import runs
from ..units import convert
from .common import close_apps, enter_work_dir, free_seat_for, license_denials, run_server
from .jobs import Job, gui_guard, gui_mode, job_timeout, launch_timeout

mcp = FastMCP("mechanical-v2")
SCRIPT = Path(__file__).resolve().parents[1] / "app_scripts" / "mechanical_spin_stress.py"
_S: dict = {"m": None}
JOB = Job("mechanical")
FIDELITY = ["one blade on a hub slice, fixed slice bottom (no disk)",
            "centrifugal load only (no aero pressure, no thermal)"]


def _launch(job: Job) -> dict:
    import ansys.mechanical.core as pymech
    job.set_step("freeing license seat")
    free_seat_for("workbench")
    batch = gui_mode("mechanical") == "headless"
    job.set_step(f"launching Mechanical ({'batch' if batch else 'GUI'})")
    _S["m"] = pymech.launch_mechanical(batch=batch, cleanup_on_exit=True,
                                       start_timeout=launch_timeout("mechanical"))
    job.set_step("checking Mechanical answers")
    _S["m"].run_python_script("1")
    return {"status": "ok", "version": _S["m"].version, "mode": "batch" if batch else "gui"}


@mcp.tool
def connect_start() -> dict:
    """Start launching Mechanical in the background (GUI or batch from config). Poll job_status until finished.
    Fails at once with a clear message if GUI mode is set and the desktop is disconnected or locked."""
    bad = gui_guard("mechanical")
    if bad:
        return bad
    if _S["m"] is not None:
        return {"status": "ok", "note": "already connected"}
    return JOB.start(_launch, launch_timeout("mechanical"))


def _spin(job: Job, mesh_sizes: list[float], max_nodes: int | None) -> dict:
    run = runs.active_run()
    c = runs.run_case(run)
    c.require_stage("structural")
    step = (runs.stage("geometry") or {}).get("single_blade_step")
    if not step or not Path(step).exists():
        raise RuntimeError("no single-blade STEP in this run; run the geometry stage")
    lu = c.raw("geometry.exit_blade_height")["unit"]
    nmax = max_nodes or c.opt("structural.max_mesh_nodes")
    if not nmax:
        raise RuntimeError("no node limit: pass max_nodes or set structural.max_mesh_nodes")
    rpm_over = c.q("operating_point.speed", "rpm") * c.q("limits.speed_max_fraction", "-")
    from .. import materials
    mat_xml, mat_props = materials.ensure_xml(c.resolve_path("material.library_file"), run / "materials")
    if mat_props and abs(mat_props["tensile_yield_pa"] - c.q("material.yield_strength", "Pa")) > \
            1e-6 * mat_props["tensile_yield_pa"]:
        raise RuntimeError("material file yield strength differs from case material.yield_strength; fix one source")
    from .. import config, handcalc
    gc = runs.stage("geometry_curves") or {}
    r_te_m = convert(gc["trailing_edge_radius"][gc["unit"]], gc["unit"], "m")
    ms = config.get("structural_meshing")
    meshing = {"method": ms["method"], "min_size_ratio": float(ms["min_size_ratio"]),
               "refinement": int(ms["refinement"]), "growth": float(ms["growth_rate"]),
               "defeature_m": float(ms["defeature_fraction"]) * r_te_m, "element_order": ms["element_order"]}
    # Root/fillet zone (DEC-15): within root_zone_fillet_multiple x fillet radius of the hub-side root line, so it
    # covers the fillet surface and the blade just above it. Without a fillet the same width in the case unit is
    # taken from the exclusion distance (sharp root: expected singular, so the check ends NOT CHECKED).
    geo = runs.stage("geometry") or {}
    fil_m = convert(float((geo.get("parameters") or {}).get("root_fillet") or 0.0), lu, "m")
    excl_m = float(ms["body_stress_exclusion_fraction"]) * r_te_m
    root_zone_m = float(ms["root_zone_fillet_multiple"]) * fil_m if fil_m > 0 else excl_m
    args = {"step": step, "material_file": str(mat_xml),
            "material_name": str(c.val("material.name")), "out_dir": str(run),
            "omega_rad_s": rpm_over * 2 * math.pi / 60, "mesh_sizes_m": [convert(x, lu, "m") for x in mesh_sizes],
            "max_nodes": int(nmax), "meshing": meshing,
            "exclude_m": excl_m, "root_zone_m": root_zone_m}
    job.set_step("mesh study: import, mesh, solve per size in Mechanical")
    r = json.loads(_S["m"].run_python_script(SCRIPT.read_text(encoding="utf-8")
                                             .replace("__ARGS_JSON__", json.dumps(args))))
    ys = c.q("material.yield_strength", "Pa")
    done = [x for x in r["study"] if x.get("solve") == "Done" and x.get("peak_Pa", 0) > 0]
    tol = float(ms["mesh_convergence_tol"])
    def change(key):
        if len(done) < 2 or not done[-1].get(key) or not done[-2].get(key):
            return None
        return abs(done[-1][key] - done[-2][key]) / done[-2][key]
    d_peak, d_body = change("peak_Pa"), change("body_p99_Pa")
    d_fil = change("fillet_p99_Pa")
    finest = min(done, key=lambda x: x["size_m"]) if done else {}
    # hand check: radial blade pull from the blade root (smallest blade radius, from the geometry) to the TE radius
    r_root = float(r.get("r_root_m") or 0)
    if not mat_props:
        # Engineering Data XML supplied directly: density is not known to the server; read it from the XML
        mat_props = materials.props_from_xml(mat_xml)
    rho = (mat_props or {}).get("density_kg_m3")
    hand = handcalc.centrifugal_check(rho, rpm_over, r_root, r_te_m) if (rho and 0 < r_root < r_te_m) else None
    body = finest.get("body_p99_Pa")
    fillet = finest.get("fillet_p99_Pa")
    body_conv = d_body is not None and d_body <= tol
    fil_conv = d_fil is not None and d_fil <= tol
    # Governing stress (DEC-15): the HIGHER of bulk and root/fillet stress. Both must be mesh-converged, else the
    # check is not trusted. A missing fillet zone value is not silently ignored.
    gov = max(body, fillet) if (body and fillet) else None
    gov_where = (("root/fillet" if fillet >= body else "bulk") if gov else None)
    status = "ok" if done else "error"
    res = {"status": status, "speed_rpm_overspeed": round(rpm_over, 1), "material": c.val("material.name"),
           "mesh_study": r["study"], "peak_change": d_peak, "body_change": d_body, "fillet_change": d_fil,
           "convergence_tol": tol, "body_converged": body_conv, "fillet_converged": fil_conv,
           "peak_converged": d_peak is not None and d_peak <= tol,
           "peak_stress_Pa": finest.get("peak_Pa"), "body_stress_Pa": body, "fillet_stress_Pa": fillet,
           "root_fillet_m": fil_m, "root_zone_m": root_zone_m,
           "governing_stress_Pa": gov, "governing_location": gov_where,
           "governing_converged": bool(gov) and body_conv and fil_conv,
           "safety_factor_on_yield": round(ys / gov, 3) if gov else None,
           "safety_factor_on_yield_bulk": round(ys / body, 3) if body else None,
           "safety_factor_on_yield_fillet": round(ys / fillet, 3) if fillet else None,
           "safety_factor_on_yield_at_peak": round(ys / finest["peak_Pa"], 3) if finest.get("peak_Pa") else None,
           "safety_factor_min": c.q("structural.safety_factor_min", "-"),
           "hand_check": hand, "hand_check_ratio": (body / hand["blade_pull_Pa"]) if (hand and body) else None,
           "hand_check_ok": handcalc.within_order_of_magnitude(body, hand["blade_pull_Pa"]) if (hand and body) else None,
           "image": r.get("image"), "mechanical_errors": r.get("errors"), "meshing": meshing,
           "exclude_m": args["exclude_m"], "n_root_edges": r.get("n_root_edges")}
    fid = list(FIDELITY)
    if done and not res["peak_converged"]:
        fid.append("peak stress at the hub-slice cut / support edges not mesh-converged (modelling-cut singularity)")
    if done and not body_conv:
        fid.append("bulk blade stress not mesh-converged within tolerance")
    if done and not fil_conv:
        fid.append("root/fillet stress not mesh-converged within tolerance" +
                   ("" if fil_m > 0 else " (no root fillet: sharp root is singular)"))
    runs.record("structural", res, fidelity=fid)
    return res


def _diag(job: Job, step_path: str | None) -> dict:
    from .. import config
    run = runs.active_run()
    step = step_path or (runs.stage("geometry") or {}).get("single_blade_step")
    if not step or not Path(step).exists():
        raise RuntimeError("no single-blade STEP in this run; run the geometry stage")
    r_te_m = None
    gc = runs.stage("geometry_curves") or {}
    if gc.get("trailing_edge_radius"):
        u = gc["unit"]
        r_te_m = convert(gc["trailing_edge_radius"][u], u, "m")
    if not r_te_m:
        raise RuntimeError("no trailing-edge radius in this run (geometry_curves stage)")
    short = float(config.get("structural_meshing.short_edge_fraction")) * r_te_m
    args = {"step": step, "short_edge_m": short, "small_face_m2": short ** 2}
    job.set_step("geometry diagnostics in Mechanical")
    script = (Path(__file__).resolve().parents[1] / "app_scripts" / "mechanical_geom_diag.py").read_text("utf-8")
    r = json.loads(_S["m"].run_python_script(script.replace("__ARGS_JSON__", json.dumps(args))))
    res = {"status": "ok", "step": step, "thresholds": args, "n_faces": r["n_faces"], "n_edges": r["n_edges"],
           "flags": r["flags"], "faces": r["faces"], "edges": r["edges"]}
    (run / "geometry_diagnostics.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    runs.record("geometry_diagnostics", {k: res[k] for k in ("status", "n_faces", "n_edges", "flags", "thresholds")})
    return res


@mcp.tool
def geometry_diagnostics_start(step_path: str | None = None) -> dict:
    """Background job: import the single-blade STEP and report short edges, small faces, near-tangent (sliver) and
    knife-edge face pairs. Thresholds from config structural_meshing.short_edge_fraction x trailing-edge radius.
    Writes <run>/geometry_diagnostics.json. Poll job_status."""
    if _S["m"] is None:
        return {"status": "error", "message": "Mechanical not connected; call connect_start and wait for finished"}
    return JOB.start(lambda job: _diag(job, step_path), 600)


@mcp.tool
def spin_stress_start(mesh_sizes: list[float], max_nodes: int | None = None) -> dict:
    """Start the overspeed spin-stress job (returns at once; poll job_status).
    mesh_sizes: element sizes to try in order, in the case length unit (first that meshes under the node limit
    is used). max_nodes: defaults to structural.max_mesh_nodes from the case."""
    if _S["m"] is None:
        return {"status": "error", "message": "Mechanical not connected; call connect_start and wait for finished"}
    return JOB.start(lambda job: _spin(job, mesh_sizes, max_nodes), job_timeout("mechanical"))


@mcp.tool
def job_status() -> dict:
    """State of the current Mechanical job. Returns immediately. On error/timeout includes license denials."""
    st = JOB.status()
    if st["state"] in ("error", "timeout"):
        st["license_denials"] = license_denials()
        st["next"] = "report this to the user; call disconnect before retrying"
    return st


@mcp.tool
def disconnect() -> dict:
    """Close Mechanical (and its processes if it does not answer)."""
    try:
        if _S["m"] is not None:
            _S["m"].exit()
    except Exception:
        pass
    _S["m"] = None
    return {"status": "ok", "closed": close_apps(["workbench"])}


def main():
    enter_work_dir()
    run_server(mcp, "mechanical_v2")


if __name__ == "__main__":
    main()
