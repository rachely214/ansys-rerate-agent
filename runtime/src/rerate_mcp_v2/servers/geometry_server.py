"""geometry_v2 MCP server: read the case geometry through its adapter, apply the design change, write the
curve sets for meshing, and build the solids in a visible Ansys Discovery.

Tools
- inspect_geometry {}: read the case geometry, report blade rows, sections, exit radius and exit blade height
  (lets the agent cross-check the adapter against the datasheet before changing anything).
- apply_exit_height_change {scale?, blend_start_fraction}: scale defaults to the sizing stage's ratio; the blend
  start is a design choice the agent states. Writes <run>/geometry/{full,main_only}/BladeGen.inf.
- build_start {stride, theta_margin_deg, le_pad}: background job in Discovery (full impeller + single blade STEP);
  poll job_status.  - job_status {}
- screenshot {}: screen capture with Discovery in front.  - close_discovery {}
Script arguments that are pure modelling technique (loft point stride, single-blade theta margin) are explicit
tool parameters, recorded in the run. Geometry tolerances come from the config file.
"""
from __future__ import annotations

import time
from pathlib import Path

from fastmcp import FastMCP

from .. import config, runs
from ..adapters import bladegen_inf, read_geometry
from ..adapters.modify import scale_exit_height
from ..units import convert
from .common import close_apps, enter_work_dir, free_seat_for, ps, run_server
from .jobs import Job, gui_guard, gui_mode, job_timeout, launch_timeout

mcp = FastMCP("geometry-v2")
SCRIPTS = Path(__file__).resolve().parents[1] / "app_scripts"
_state: dict = {"m": None}
JOB = Job("discovery")


def _case_geometry():
    run = runs.active_run()
    c = runs.run_case(run)
    c.require_stage("geometry")
    imp = read_geometry(str(c.val("geometry.adapter")), c.resolve_path("geometry.source"),
                        c.raw("geometry.adapter_options") or {})
    return run, c, imp


@mcp.tool
def inspect_geometry() -> dict:
    """Read the case geometry through its adapter and report what was found (no changes made)."""
    try:
        run, c, imp = _case_geometry()
        lu = c.raw("geometry.exit_blade_height")["unit"]
        r_te = imp.meta["r_te_m"]
        b2 = convert(imp.exit_blade_height(r_te), "m", lu)
        stated = c.q("geometry.exit_blade_height", lu)
        return {"status": "ok", "adapter": imp.meta.get("adapter"), "blade_rows": len(imp.blades),
                "sections_per_row": [len(r) for r in imp.blades], "n_sets": imp.n_sets,
                "trailing_edge_diameter": {lu: round(convert(2 * r_te, "m", lu), 4)},
                "exit_blade_height_from_geometry": {lu: round(b2, 4)},
                "exit_blade_height_in_case": {lu: stated},
                "difference_pct": round((b2 / stated - 1) * 100, 2),
                "blade_count_matches_case": imp.n_sets == int(c.val("geometry.main_blades"))}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def apply_exit_height_change(blend_start_fraction: float, scale: float | None = None, reason: str = "") -> dict:
    """Scale the impeller exit blade height (inlet unchanged) and write BladeGen curve sets for this run.
    scale: new/old exit height; omit to use the sizing stage's ratio. blend_start_fraction: radius fraction of the
    trailing-edge radius where the shroud starts to move (design choice, give `reason`)."""
    try:
        run, c, imp = _case_geometry()
        if scale is None:
            sz = runs.stage("sizing") or {}
            if sz.get("status") != "ok":
                return {"status": "error", "message": "no successful sizing stage; run sizing or pass scale"}
            scale = float(sz["exit_height_scale"])
        new = scale_exit_height(imp, scale, blend_start_fraction) if abs(scale - 1.0) > 1e-12 else imp
        lu = c.raw("geometry.exit_blade_height")["unit"]
        out = run / "geometry"
        full = bladegen_inf.write(new, out / "full", unit=lu)
        # CFD passage curves: flowpath ends at the radius where the outlet static pressure was measured
        # (case cfd.outlet_radius_ratio x trailing-edge radius), so the outlet BC is applied where it is known.
        from ..adapters.outlet import set_outlet_radius
        r_out = float(c.q("cfd.outlet_radius_ratio", "-")) * new.meta["r_te_m"]
        cfd_imp = set_outlet_radius(new, r_out)
        main = bladegen_inf.write(cfd_imp, out / "main_only", rows=[0], unit=lu)
        passage = bladegen_inf.write(cfd_imp, out / "passage_with_splitter", unit=lu) if len(new.blades) > 1 else None
        r_te = new.meta["r_te_m"]
        res = {"status": "ok", "scale": scale, "blend_start_fraction": blend_start_fraction, "reason": reason,
               "exit_blade_height": {lu: round(convert(new.exit_blade_height(r_te), "m", lu), 4)},
               "trailing_edge_radius": {lu: round(convert(r_te, "m", lu), 4)},
               "cfd_outlet_radius": {lu: round(convert(r_out, "m", lu), 4)},
               "full_inf": str(full), "main_only_inf": str(main),
               "passage_with_splitter_inf": str(passage) if passage else None, "unit": lu}
        runs.record("geometry_curves", res)
        return res
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _launch(job: Job) -> None:
    from ansys.geometry.core import launch_modeler_with_discovery
    if gui_mode("discovery") == "headless":
        raise RuntimeError("Discovery has no supported headless mode for scripted geometry. Set "
                           "apps.discovery.mode: gui and use a connected desktop session.")
    tmo = launch_timeout("discovery")
    errs = []
    for attempt in (1, 2):
        job.set_step(f"launching Discovery (attempt {attempt}, timeout {tmo} s)")
        close_apps(["discovery"])
        time.sleep(3)
        try:
            # V0 protocol: with geometry-core 0.18's default V1 protocol, run_script_file fails on Discovery 2026 R1
            _state["m"] = launch_modeler_with_discovery(version=config.ansys_version(), hidden=False, timeout=tmo,
                                                        proto_version="v0")
            return
        except Exception as e:
            errs.append(f"attempt {attempt}: {str(e)[:300]}")
            _state["m"] = None
    raise RuntimeError("Discovery did not start: " + " | ".join(errs))


def _script(name: str, args: dict) -> dict:
    t = time.time()
    r = _state["m"].run_script_file(str(SCRIPTS / name), script_args={k: str(v) for k, v in args.items()})
    r = r[0] if isinstance(r, tuple) else r
    out = {"seconds": round(time.time() - t, 1), **(dict(r) if r else {})}
    if out.get("error"):
        raise RuntimeError(f"{name}: {out['error']} | log: {out.get('log', '')} | {out.get('trace', '')[-600:]}")
    return out


def _shot(png: Path, title: str) -> bool:
    ps("Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
       "Add-Type 'using System;using System.Runtime.InteropServices;public class W{[DllImport(\"user32.dll\")]"
       "public static extern bool SetForegroundWindow(IntPtr h);[DllImport(\"user32.dll\")]"
       "public static extern bool ShowWindow(IntPtr h,int c);}'; "
       f"$p=Get-Process | ? {{ $_.MainWindowTitle -match '{title}' }} | select -First 1; "
       "if($p){[W]::ShowWindow($p.MainWindowHandle,3)|Out-Null;[W]::SetForegroundWindow($p.MainWindowHandle)|Out-Null;"
       "Start-Sleep 2}; $b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
       "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height; $g=[System.Drawing.Graphics]::FromImage($bmp); "
       f"$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size); $bmp.Save('{png}')", timeout=60)
    return png.exists()


def _build(job: Job, stride: int, theta_margin_deg: float, le_pad: float, root_fillet: bool = True) -> dict:
    t0 = time.time()
    run = runs.active_run()
    c = runs.run_case(run)
    gc = runs.stage("geometry_curves") or {}
    if gc.get("status") != "ok":
        raise RuntimeError("no changed curves in this run; call apply_exit_height_change")
    lu = gc["unit"]
    to_m = convert(1.0, lu, "m")
    r_te = gc["trailing_edge_radius"][lu]
    depth = c.q("structural.hub_slice_depth", lu)
    fil = (c.opt("structural.root_fillet_radius", lu) or 0.0) if root_fillet else 0.0
    tol = {"te_inset": float(config.get("geometry_tolerances.hub_cut_te_inset_fraction")),
           "fit_tol_m": float(config.get("geometry_tolerances.curve_fit_tolerance_m"))}
    job.set_step("freeing license seat")
    free_seat_for("discovery")
    if _state["m"] is None:
        _launch(job)
    geo_full = str(Path(gc["full_inf"]).parent)
    common = {"geo": geo_full, "to_m": to_m, "depth": depth, "r_te": r_te, "stride": stride, **tol}
    job.set_step("building full impeller")
    imp = _script("discovery_impeller.py", {**common, "n_sets": int(c.val("geometry.main_blades"))})
    if imp.get("closed") != "True":
        res = {"status": "error", "step": "full impeller solid is not closed", **imp}
        runs.record("geometry", res)
        return res
    png = run / "geometry_impeller.png"
    if gui_mode("discovery") == "gui":
        job.set_step("screenshot")
        _shot(png, "Discovery")
    job.set_step("building single blade for structural")
    out = str(run / "single_blade")
    sb = _script("discovery_single_blade.py", {**common, "out": out, "fillet": fil,
                                               "theta_margin_deg": theta_margin_deg, "le_pad": le_pad})
    ok = sb.get("closed") == "True" and Path(out + ".stp").exists()
    job.set_step("showing full impeller again")
    _script("discovery_impeller.py", {**common, "n_sets": int(c.val("geometry.main_blades"))})
    vol = float(imp["volume_m3"])
    res = {"status": "ok" if ok else "error", "impeller_closed": True, "impeller_manifold": imp.get("manifold"),
           "impeller_volume": {lu + "3": round(vol / to_m ** 3, 3)}, "impeller_log": imp.get("log"),
           "single_blade_step": out + ".stp" if ok else None, "single_blade_log": sb.get("log"),
           "screenshot": str(png) if png.exists() else None,
           "parameters": {"stride": stride, "theta_margin_deg": theta_margin_deg, "le_pad": le_pad,
                          "hub_slice_depth": depth, "root_fillet": fil, **tol},
           "seconds": round(time.time() - t0)}
    runs.record("geometry", res, fidelity=["simplified hub disk (no bore/back-face detail)",
                                          "single blade on hub slice for structural"] +
                ([] if fil else ["no root fillet (sharp blade root: stress there is a singularity)"]))
    return res


@mcp.tool
def build_start(stride: int, theta_margin_deg: float, le_pad: float, root_fillet: bool = True) -> dict:
    """Start building the solids in Discovery as a background job (returns at once; poll job_status).
    Builds (1) the full impeller from this run's changed curves (blades orange) with a screenshot, then (2) one main
    blade on a hub slice saved as STEP for the structural stage. Fails at once if the desktop is disconnected.
    Modelling-technique arguments (state them to the user):
      stride: use every Nth resampled section point for lofting (4 is a good start; lower = finer)
      theta_margin_deg: hub-slice extent beyond the blade on each side
      le_pad: hub-slice start below the blade leading-edge hub radius, in the case length unit
      root_fillet: apply the case's structural.root_fillet_radius (default). Set false only if the structural
        stage cannot mesh the filleted blade; the run then records "no root fillet" as a fidelity limit.
    Hub-slice depth and root fillet radius come from the case; geometry tolerances from the config."""
    bad = gui_guard("discovery")
    if bad:
        return bad
    return JOB.start(lambda job: _build(job, stride, theta_margin_deg, le_pad, root_fillet), job_timeout("discovery"))


@mcp.tool
def job_status() -> dict:
    """State of the current Discovery job; returns immediately. Includes the result when finished."""
    return JOB.status()


@mcp.tool
def screenshot(name: str = "discovery") -> dict:
    """Full-screen PNG with Discovery maximised in front, saved in the run folder."""
    try:
        png = runs.active_run() / f"{name}.png"
        return {"status": "ok" if _shot(png, "Discovery") else "error", "png": str(png)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def close_discovery() -> dict:
    """Close Discovery and free its license."""
    try:
        if _state["m"] is not None:
            _state["m"].exit()
    except Exception:
        pass
    _state["m"] = None
    return {"status": "ok", "closed": close_apps(["discovery"])}


def main():
    enter_work_dir()
    run_server(mcp, "geometry_v2")


if __name__ == "__main__":
    main()
