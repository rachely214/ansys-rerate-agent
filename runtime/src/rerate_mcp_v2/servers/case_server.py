"""case_v2 MCP server: case file validation/approval, run start, report. No Ansys app needed.

Tools
- case_validate {case_path}: blocking issues + warnings + a table of every value with unit and source.
- case_approve {case_path, approved_by}: ONLY after the engineer explicitly approved the shown values.
- start_run {case_path}: new run folder bound to the approved case (refuses unapproved/edited cases).
- run_status {}: active run, stage statuses.
- build_report {}: scorecard + REPORT.md from the active run only.
"""
from __future__ import annotations

from fastmcp import FastMCP

from .. import case as casemod
from .. import report, runs
from .common import enter_work_dir, run_server

mcp = FastMCP("case-v2")


def _err(e: Exception) -> dict:
    return {"status": "error", "message": str(e)}


@mcp.tool
def case_validate(case_path: str) -> dict:
    """Check a case.yaml against the schema. Returns blocking issues (must be fixed or asked about),
    warnings (e.g. missing source), approval state, and every value with its unit and source."""
    try:
        c = casemod.load(case_path)
        return {"status": "ok", "case": c.name if c.raw("case.name") else None, "path": str(c.path),
                "blocking_issues": c.issues, "warnings": getattr(c, "warnings", []), "approved": c.approved,
                "values": casemod.summary_table(c)}
    except Exception as e:
        return _err(e)


@mcp.tool
def case_approve(case_path: str, approved_by: str) -> dict:
    """Record the engineer's approval of case.yaml (stores a content hash). Call ONLY after the engineer said
    they approve the values you showed them. Any later edit invalidates the approval."""
    try:
        return {"status": "ok", "approval": casemod.approve(case_path, approved_by)}
    except Exception as e:
        return _err(e)


@mcp.tool
def start_run(case_path: str) -> dict:
    """Start a new run folder for an APPROVED case. Every later stage tool uses this run and this case."""
    try:
        d = runs.start_run(case_path)
        return {"status": "ok", "run_dir": str(d), "case": runs.read(d)["case_name"]}
    except Exception as e:
        return _err(e)


@mcp.tool
def run_status() -> dict:
    """Active run folder, case, and the recorded status/fidelity of each stage."""
    try:
        d = runs.active_run()
        rec = runs.read(d)
        return {"status": "ok", "run_dir": str(d), "case": rec["case_name"],
                "stages": {k: {"status": v.get("status"), "fidelity": v.get("fidelity")}
                           for k, v in rec["stages"].items()}}
    except Exception as e:
        return _err(e)


@mcp.tool
def calibrate_cfd(baseline_run_dir: str) -> dict:
    """Compare a finished BASELINE run (unmodified geometry, stage 'cfd' recorded, converged or not) with the
    measured baseline data and tolerances in that run's approved case. Records stage 'cfd_calibration' in the
    baseline run AND links it into the active run (the design run) so its report can gate CFD results.
    Result: CALIBRATED only if converged and every measured quantity is within tolerance; else NOT CALIBRATED
    with reasons. Never changes tolerances or measured values."""
    try:
        from pathlib import Path
        from .. import calibration
        b = Path(baseline_run_dir)
        rec = runs.read(b)
        cb = runs.run_case(b)
        cfd = rec["stages"].get("cfd")
        if not cfd:
            return {"status": "error", "message": "the baseline run has no 'cfd' stage (diagnostic points do not count)"}
        gc = rec["stages"].get("geometry_curves") or {}
        if abs(float(gc.get("scale", 0)) - 1.0) > 1e-12:
            return {"status": "error", "message": "baseline run geometry is modified (scale != 1); not a baseline"}
        cal = calibration.evaluate(cb, cfd, str(b))
        cal["signature"] = calibration.model_signature(rec["stages"], cb)
        runs.record("cfd_calibration", cal, run=b)
        act = runs.active_run()
        if act.resolve() != b.resolve():
            runs.record("cfd_calibration", cal, run=act)
        return {"status": "ok", **cal}
    except Exception as e:
        return _err(e)


@mcp.tool
def build_report() -> dict:
    """Build the pass/fail scorecard and REPORT.md for the active run from its recorded stages only.
    Targets come from the approved case. Rows from simplified models are labelled with their fidelity."""
    try:
        d = runs.active_run()
        c = runs.run_case(d)
        rec = runs.read(d)
        rows = report.scorecard(c, rec["stages"])
        path = report.write_markdown(c, d, rec, rows)
        runs.record("report", {"status": "ok", "verdict": report.verdict(rows), "path": str(path)}, run=d)
        return {"status": "ok", "verdict": report.verdict(rows), "scorecard": rows, "report": str(path),
                "images": sorted(str(p) for p in d.glob("*.png"))}
    except Exception as e:
        return _err(e)


def main():
    enter_work_dir()
    run_server(mcp, "case_v2")


if __name__ == "__main__":
    main()
