"""Developer test (no LLM): back-pressure continuation for the calibration baseline, in small steps.

  python dev/stability_test.py <case_path> <attempt_name> <blend_start_fraction> <p_start_pa> <p_step1_pa> [...]

blend_start_fraction only labels the unchanged geometry (scale 1.0); it has no effect on the shape.

Starts a new run from the approved case, builds unchanged geometry (scale 1.0), meshes the passage with the
splitter, sets up Fluent at the case values, solves a start field at p_start (reinitialised), then steps the
outlet static pressure through each p_step without reinitialising. Each step must converge (case rule) before the
next; then restore_case_back_pressure and a final solve at the case value (recorded as stage 'cfd').
Nothing in the case is changed. Needs the broker: python dev/mcp_call.py --broker.
Progress goes to <install home>/work/stability_<attempt>.json after every poll.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_call import call  # noqa: E402
from rerate_mcp_v2 import config  # noqa: E402

CHUNK = 50
T_START = 3600         # s, start field cap
T_STEP = 2700          # s, per pressure step cap
T_FINAL = 3600         # s, final solve at the case value


def tool(server, name, args=None):
    r = call(server, name, args or {})
    if not r.get("ok"):
        raise RuntimeError(f"{server}.{name}: {r}")
    try:
        return json.loads(r["result"])
    except Exception:
        return {"raw": r["result"]}


def wait_job(server, status_tool, label, log, poll=20):
    while True:
        s = tool(server, status_tool)
        st = s.get("state")
        if st in ("finished", "error", "timeout") or s.get("status") == "error":
            log(label, s)
            if st != "finished":
                raise RuntimeError(f"{label}: {json.dumps(s)[:800]}")
            return s
        time.sleep(poll)


def solve(label, t_lim, log):
    r = tool("fluent_v2", "solve_start", {"chunk": CHUNK, "time_limit_s": t_lim})
    if r.get("status") != "ok":
        raise RuntimeError(f"solve_start: {r}")
    while True:
        time.sleep(60)
        s = tool("fluent_v2", "solve_status")
        log(label, {k: s.get(k) for k in ("state", "iterations", "converged", "stop_reason", "convergence",
                                           "last", "error", "elapsed_s")}, quiet=True)
        if s.get("state") in ("finished", "error"):
            break
    f = tool("fluent_v2", "solve_fetch")
    keep = {k: f.get(k) for k in ("converged", "stop_reason", "iterations", "PR_tt", "eta_isen_tt", "corrected_flow",
                                  "reversed_inlet_pct", "outlet_static_pressure_pa", "convergence")}
    log(label + " result", keep)
    return keep


def main():
    case_path, name, blend, p0 = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    steps = [float(x) for x in sys.argv[5:]]
    out = config.config_dir() / "work" / f"stability_{name}.json"
    rec = {"attempt": name, "case": case_path, "p_start_pa": p0, "steps_pa": steps, "started": time.ctime(),
           "events": [], "state": "running"}

    def log(label, data, quiet=False):
        ev = {"t": time.strftime("%H:%M:%S"), "label": label, "data": data}
        if quiet and rec["events"] and rec["events"][-1]["label"] == label:
            rec["events"][-1] = ev
        else:
            rec["events"].append(ev)
        out.write_text(json.dumps(rec, indent=1), encoding="utf-8")

    try:
        r = tool("case_v2", "start_run", {"case_path": case_path}); log("start_run", r)
        rec["run_dir"] = r.get("run_dir") or r.get("run")
        r = tool("geometry_v2", "apply_exit_height_change",
                 {"blend_start_fraction": blend, "scale": 1.0, "reason": f"stability test {name}: unchanged geometry"})
        log("geometry", {k: r.get(k) for k in ("status", "exit_blade_height", "message")})
        r = tool("turbogrid_v2", "mesh_start", {"topology": "Single Splitter", "with_splitter": True}); log("mesh_start", r)
        m = wait_job("turbogrid_v2", "job_status", "mesh", log)
        tool("turbogrid_v2", "close")
        r = tool("fluent_v2", "connect_start"); log("connect_start", r)
        if r.get("note") != "already connected":
            wait_job("fluent_v2", "prep_status", "connect", log)
        tool("fluent_v2", "setup_start")
        wait_job("fluent_v2", "prep_status", "setup", log)
        tool("fluent_v2", "set_back_pressure", {"outlet_static_pressure_pa": p0, "reinitialize": True,
                                               "reason": f"{name}: start field on the choke side"})
        res = solve(f"start {p0:.0f} Pa", T_START, log)
        if not res["converged"]:
            raise RuntimeError(f"start field at {p0:.0f} Pa did not converge")
        for p in steps:
            tool("fluent_v2", "set_back_pressure", {"outlet_static_pressure_pa": p, "reinitialize": False,
                                                   "reason": f"{name}: continuation step"})
            res = solve(f"step {p:.0f} Pa", T_STEP, log)
            if not res["converged"]:
                raise RuntimeError(f"step at {p:.0f} Pa did not converge")
        r = tool("fluent_v2", "restore_case_back_pressure", {"reason": f"{name}: continuation from {steps[-1]:.0f} Pa"})
        log("restore", r)
        res = solve("case value", T_FINAL, log)
        rec["state"] = "converged at case value" if res["converged"] else "not converged at case value"
    except Exception as e:
        rec["state"] = "stopped"
        rec["error"] = str(e)[-1500:]
    rec["ended"] = time.ctime()
    out.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print(rec["state"], rec.get("error", ""))


if __name__ == "__main__":
    main()
