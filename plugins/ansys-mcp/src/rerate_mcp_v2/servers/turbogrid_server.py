"""turbogrid_v2 MCP server: mesh one blade passage in TurboGrid from this run's main-blade curve set.

Tools (none blocks on the app)
- mesh_start {topology}: background job (headless engine): mesh, quality check, save <run>/passage.gtm + .tst.
- job_status {}: running / finished / error / timeout, with the result.
- show_gui {}: open the saved state in a visible TurboGrid window for the audience (skipped when headless).
- close {}: quit engine and window.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from fastmcp import FastMCP

from .. import config, runs
from .common import close_apps, enter_work_dir, find_windows, free_seat_for, license_denials, ps, run_server
from .jobs import Job, gui_guard, gui_mode, job_timeout, launch_timeout

mcp = FastMCP("turbogrid-v2")
_state: dict = {"tg": None}
JOB = Job("turbogrid")


def _release():
    if _state["tg"] is not None:
        try:
            _state["tg"].quit()
        except Exception:
            pass
    _state["tg"] = None


def _connect(job: Job):
    """Start the TurboGrid engine (always headless). The PyTurboGrid launcher has no timeout argument, so it runs in a
    thread and is abandoned (and its processes closed) after apps.turbogrid.launch_timeout_s."""
    from ansys.turbogrid.core.launcher.launcher import launch_turbogrid
    tmo = launch_timeout("turbogrid")
    box: dict = {}

    def go():
        try:
            box["tg"] = launch_turbogrid()
        except Exception as e:
            box["err"] = str(e)[:300]
    errs = []
    for attempt in (1, 2):
        job.set_step(f"launching TurboGrid engine (attempt {attempt}, timeout {tmo} s)")
        box.clear()
        th = threading.Thread(target=go, daemon=True)
        th.start()
        th.join(tmo)
        if "tg" in box:
            _state["tg"] = box["tg"]
            return
        errs.append(box.get("err") or f"no answer within {tmo} s")
        close_apps(["turbogrid"])
        time.sleep(3)
    raise RuntimeError("TurboGrid engine did not start: " + " | ".join(errs) + f" | denials: {license_denials()}")


def _mesh(job: Job, topology: str, with_splitter: bool) -> dict:
    t0 = time.time()
    run = runs.active_run()
    c = runs.run_case(run)
    c.require_stage("meshing")
    gc = runs.stage("geometry_curves") or {}
    inf = gc.get("passage_with_splitter_inf") if with_splitter else gc.get("main_only_inf")
    if not inf or not Path(inf).exists():
        raise RuntimeError("no curve set for this passage in the run; run apply_exit_height_change")
    job.set_step("freeing license seat")
    free_seat_for("turbogrid")
    _release()
    _connect(job)
    tg = _state["tg"]
    job.set_step("reading curves and building topology")
    tg.read_inf(inf)
    tg.set_topology_choice(topology)
    tg.unsuspend(object="/TOPOLOGY SET")
    # Shroud tip gap from the case (constant along the tip). 0 = shrouded impeller / no gap.
    gap_m = float(c.q("geometry.tip_clearance", "m"))
    if gap_m > 0:
        job.set_step(f"applying shroud tip clearance {gap_m * 1e3:.4f} mm")
        tg.set_obj_param(object="/GEOMETRY/BLADE SET/SHROUD TIP",
                         param_val_pairs=f"Option=Constant Span, Tip Clearance={gap_m!r} [m]")
        tg.unsuspend(object="/TOPOLOGY SET")
    size = float(c.val("cfd.mesh_size_factor"))
    job.set_step("meshing")
    tg.set_global_size_factor(size)
    st = tg.query_mesh_statistics()
    if "Elements" not in st:
        raise RuntimeError("TurboGrid could not build a mesh (no element statistics)")
    gtm, tst = run / "passage.gtm", run / "passage.tst"
    job.set_step("saving mesh")
    tg.save_mesh(str(gtm))
    tg.save_state(str(tst))
    for _ in range(30):
        if gtm.exists() and gtm.stat().st_size > 0:
            break
        time.sleep(1)
    neg = st.get("Minimum Volume", {}).get("Percent Bad", 0) or 0
    n = st["Elements"]["Count"]
    res = {"status": "ok" if (not neg and gtm.exists()) else "error", "mesh_file": str(gtm),
           "state_file": str(tst), "elements": n, "size_factor": size, "topology": topology,
           "skew_percent_bad": round(st["Skewness"]["Percent Bad"], 3), "negative_volume_percent": neg,
           "student_cell_limit_ok": n < 1_000_000 if config.license_mode() == "student" else None,
           "with_splitter": with_splitter, "tip_clearance_m": gap_m,
           "seconds": round(time.time() - t0)}
    if config.license_mode() == "student" and n >= 1_000_000:
        res["status"] = "error"
        res["message"] = "mesh exceeds the Student 1M-cell limit; lower cfd.mesh_size_factor (state why)"
    runs.record("meshing", res, fidelity=["single passage, " + (
        "main blade and splitter" if with_splitter else "main blade only (splitter not meshed)"),
        f"shroud tip gap {gap_m * 1e3:.3f} mm, constant along the tip" if gap_m > 0 else "no tip clearance gap"])
    return res


@mcp.tool
def mesh_start(topology: str, with_splitter: bool = True) -> dict:
    """Start meshing this run's blade passage as a background job (engine is headless; returns at once, poll
    job_status). with_splitter: mesh the full passage with the splitter blade (default; the real passage has one).
    topology: a TurboGrid ATM topology name, e.g. 'Single Splitter' with a splitter or 'Single Round Cutoff
    Symmetric' without (state why). Size factor comes from the case (cfd.mesh_size_factor)."""
    return JOB.start(lambda job: _mesh(job, topology, with_splitter), job_timeout("turbogrid"))


@mcp.tool
def job_status() -> dict:
    """State of the current TurboGrid job; returns immediately. Includes the result when finished."""
    return JOB.status()


@mcp.tool
def show_gui() -> dict:
    """Open this run's saved TurboGrid state in a visible window (demo view). Skipped in headless mode; fails at once
    on a disconnected/locked desktop. Waits at most apps.turbogrid.launch_timeout_s, then reports."""
    try:
        if gui_mode("turbogrid") == "headless":
            return {"status": "ok", "skipped": "apps.turbogrid.mode is headless; no window shown"}
        bad = gui_guard("turbogrid")
        if bad:
            return bad
        st = Path((runs.stage("meshing") or {}).get("state_file", ""))
        if not st.exists():
            return {"status": "error", "message": "no saved TurboGrid state in this run"}
        _release()
        close_apps(["turbogrid"])
        cfxtg = config.ansys_root() / "TurboGrid" / "bin" / "cfxtg.exe"
        ps(f"Start-Process -WindowStyle Hidden -FilePath '{cfxtg}' -ArgumentList '-gui','-state','\"{st}\"' "
           f"-WorkingDirectory '{st.parent}'")
        import ctypes
        u = ctypes.windll.user32
        title, dismissed, seen = "", 0, None
        tmo = min(launch_timeout("turbogrid"), 150)  # stays well under an MCP call limit
        t_end = time.time() + tmo
        while time.time() < t_end:
            time.sleep(2)
            for h, t, cls in find_windows():
                if t == "Warning" and cls.startswith("Qt"):  # trailing-edge info dialog: press its default button
                    u.SetForegroundWindow(h); time.sleep(0.4)
                    u.keybd_event(0x0D, 0, 0, 0); u.keybd_event(0x0D, 0, 2, 0); dismissed += 1
                if not title and t == "TurboGrid" and cls.startswith("Qt"):
                    title, seen = t, time.time()
            if seen and time.time() - seen > 30:
                break
        return {"status": "ok" if title else "error", "window": title or f"no TurboGrid window within {tmo} s",
                "dismissed_dialogs": dismissed}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def close() -> dict:
    """Quit the TurboGrid engine and close any TurboGrid window."""
    _release()
    return {"status": "ok", "closed": close_apps(["turbogrid"])}


def main():
    enter_work_dir()
    run_server(mcp, "turbogrid_v2")


if __name__ == "__main__":
    main()
