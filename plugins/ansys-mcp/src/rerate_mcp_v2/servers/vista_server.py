"""vista_v2 MCP server: 1D centrifugal sizing in Ansys Vista CCD (via Workbench batch journals).

All duty values come from the active run's approved case. The agent chooses nothing hidden here: the tool runs
two Vista designs (baseline duty and target duty) with the case's speed and blade counts, and reports the exit
blade height ratio. Optional Vista inputs (e.g. backsweep) may be passed as `extra_inputs` and are recorded.

Tools (none blocks): size_start {extra_inputs?} + job_status {}, open_gui {} (demo window), status {}
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from fastmcp import FastMCP

from .. import config, runs
from .common import close_apps, enter_work_dir, free_seat_for, license_denials, ps, run_server, wait_window
from .jobs import Job, gui_guard, gui_mode, job_timeout, launch_timeout

mcp = FastMCP("vista-v2")
JOB = Job("vista")

OUTPUT_KEYS = ["MassFlow", "PressureRatio", "Omega", "D5", "B5", "BetaBlade5", "EtaIsen", "EtaPoly", "NMain",
               "NSplit", "D3Hub", "D3ShrUser", "MrelLEshr", "MachU5", "Ns", "Diffuser", "Impeller"]

JOURNAL = r'''# encoding: utf-8
import json, traceback
out = {"ok": False}
try:
    s = GetTemplate(TemplateName="VistaCCD").CreateSystem()
    c = s.GetContainer(ComponentName="Blade Design")
    p = c.GetVistaCCDBladeDesignProperties()
    inputs = json.loads(r"""__INPUTS__""")
    for k, v in inputs.items():
        setattr(p, k, v)
    s.Update()
    res = {}
    for k in __KEYS__:
        try: res[k] = str(getattr(p, k))
        except Exception as e: res[k] = "ERR " + str(e)
    out = {"ok": True, "inputs": inputs, "outputs": res}
    Save(FilePath=r"__PROJECT__", Overwrite=True)
    out["project"] = r"__PROJECT__"
except Exception:
    out["error"] = traceback.format_exc()
f = open(r"__RESULT__", "w"); f.write(json.dumps(out)); f.close()
'''


def _runwb2() -> Path:
    return config.ansys_root() / "Framework" / "bin" / "Win64" / "RunWB2.exe"


def _num(s) -> float:
    return float(str(s).split()[0])


def _design(name: str, inputs: dict, out_dir: Path) -> dict:
    free_seat_for("workbench")
    close_apps(["workbench"])  # a visible Vista window would lock the project
    res, proj, jf = out_dir / f"{name}.json", out_dir / f"{name}.wbpj", out_dir / f"{name}.wbjn"
    jf.write_text(JOURNAL.replace("__INPUTS__", json.dumps(inputs)).replace("__KEYS__", repr(OUTPUT_KEYS))
                  .replace("__RESULT__", str(res)).replace("__PROJECT__", str(proj)))
    last: dict = {}
    for attempt in (1, 2):
        res.unlink(missing_ok=True)
        p = subprocess.run([str(_runwb2()), "-B", "-R", str(jf)], stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=job_timeout("vista"))
        if res.exists():
            d = json.loads(res.read_text())
            if d.get("ok"):
                return {"status": "ok", "attempts": attempt, **d}
            last = d
        else:
            last = {"message": "Workbench produced no result file", "stdout": p.stdout[-800:]}
        close_apps(["workbench"])
        time.sleep(3)
    return {"status": "error", **last, "license_denials": license_denials()}


def _size(job: Job, extra_inputs: dict | None) -> dict:
    t0 = time.time()
    if True:
        run = runs.active_run()
        c = runs.run_case(run)
        c.require_stage("sizing")
        rpm = c.q("operating_point.speed", "rpm")
        m_base = c.q("baseline.mass_flow", "kg/s")
        f_ratio = c.q("targets.corrected_flow_min", "kg/s") / c.q("baseline.corrected_flow", "kg/s")
        m_tgt = m_base * f_ratio
        common = {"NMain": int(c.val("geometry.main_blades")), "NSplit": int(c.val("geometry.splitter_blades")),
                  "Omega": f"{rpm} [rev min^-1]", **(extra_inputs or {})}
        out_dir = run / "sizing"
        out_dir.mkdir(exist_ok=True)
        job.set_step("Vista batch: baseline duty")
        b = _design("baseline", dict(common, MassFlow=f"{m_base:.5g} [kg s^-1]",
                                     PressureRatio=c.q("baseline.pressure_ratio", "-")), out_dir)
        if b["status"] != "ok":
            runs.record("sizing", {"status": "error", "step": "baseline", **b})
            return {"status": "error", "step": "baseline design", **b}
        job.set_step("Vista batch: target duty")
        t = _design("target", dict(common, MassFlow=f"{m_tgt:.5g} [kg s^-1]",
                                   PressureRatio=c.q("targets.pressure_ratio_min", "-")), out_dir)
        if t["status"] != "ok":
            runs.record("sizing", {"status": "error", "step": "target", **t})
            return {"status": "error", "step": "target design", **t}
        ratio = _num(t["outputs"]["B5"]) / _num(b["outputs"]["B5"])
        lu = c.raw("geometry.exit_blade_height")["unit"]
        h0 = c.q("geometry.exit_blade_height", lu)
        hmax = c.q("limits.exit_blade_height_max", lu)
        out = {"status": "ok", "speed_rpm": rpm, "mass_flow_kg_s": {"baseline": m_base, "target": round(m_tgt, 5)},
               "flow_gain_pct": round((f_ratio - 1) * 100, 2), "exit_height_scale": round(ratio, 5),
               "exit_blade_height": {lu: round(h0 * ratio, 4), "baseline_" + lu: h0, "limit_" + lu: hmax},
               "fits_casing": h0 * ratio <= hmax,
               "vista_eta_isen": {"baseline": _num(b["outputs"]["EtaIsen"]), "target": _num(t["outputs"]["EtaIsen"])},
               "inducer_tip_rel_mach": {"baseline": b["outputs"].get("MrelLEshr"),
                                        "target": t["outputs"].get("MrelLEshr")},
               "extra_inputs": extra_inputs or {}, "project": t.get("project"),
               "seconds": round(time.time() - t0)}
        runs.record("sizing", out, fidelity=["1D meanline correlation (Vista CCD)",
                                             "exit height scaled by Vista B5 ratio, applied to case geometry"])
        return out


@mcp.tool
def size_start(extra_inputs: dict | None = None) -> dict:
    """Start Vista CCD sizing in the background (always Workbench batch, no window): baseline duty and target duty
    from the approved case. Returns at once; poll job_status. The result gives the exit blade height ratio
    (new/old), the new exit height and whether it fits the casing limit, and is recorded as stage 'sizing'.
    extra_inputs: optional additional Vista properties applied to BOTH designs (recorded in the run)."""
    return JOB.start(lambda job: _size(job, extra_inputs), 2 * job_timeout("vista") + 60)


@mcp.tool
def job_status() -> dict:
    """State of the current Vista job; returns immediately. Includes the result when finished."""
    return JOB.status()


@mcp.tool
def open_gui() -> dict:
    """Open the target-duty Vista design in a visible Vista CCD window for the audience. Skipped in headless mode;
    fails at once on a disconnected/locked desktop; waits at most apps.vista.launch_timeout_s (capped at 150 s)."""
    try:
        if gui_mode("vista") == "headless":
            return {"status": "ok", "skipped": "apps.vista.mode is headless; no window shown"}
        bad = gui_guard("vista")
        if bad:
            return bad
        st = runs.stage("sizing") or {}
        proj = st.get("project")
        if not proj:
            return {"status": "error", "message": "no sizing project in this run; run size_start first"}
        free_seat_for("workbench")
        close_apps(["workbench"])
        lk = Path(str(proj).replace(".wbpj", "_files")) / ".lock"
        lk.unlink(missing_ok=True)
        jf = Path(proj).with_name("open_gui.wbjn")
        jf.write_text(f'# encoding: utf-8\nOpen(FilePath=r"{proj}")\n'
                      'GetAllSystems()[0].GetContainer(ComponentName="Blade Design").Edit()\n')
        ps(f"Start-Process -FilePath '{_runwb2()}' -ArgumentList '-I','-R','\"{jf}\"'")
        tmo = min(launch_timeout("vista"), 150)
        title = wait_window("Vista", tmo)
        return {"status": "ok" if title else "error", "window": title or f"no Vista window within {tmo} s"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool
def status() -> dict:
    """Vista install check and this run's sizing record."""
    try:
        return {"status": "ok", "runwb2_found": _runwb2().exists(), "sizing": runs.stage("sizing")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def main():
    enter_work_dir()
    run_server(mcp, "vista_v2")


if __name__ == "__main__":
    main()
