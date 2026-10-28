"""Run folders and the per-run record. A run is bound to exactly one approved case file.

<runs_dir>/<case-name>_<timestamp>/
    run.json        case path + approved hash + stage records (results, fidelity, status)
    case.snapshot.yaml   copy of the approved case at run start
Stages record their outputs here; the report reads ONLY this file (never older runs).
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from . import config
from .case import Case, CaseError, content_hash, load

ACTIVE = "active_run.txt"


def _active_file() -> Path:
    return config.runs_root() / ACTIVE


def start_run(case_path: str | Path) -> Path:
    c = load(case_path)
    c.require_approved()
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", c.name)[:40]
    d = config.runs_root() / f"{safe}_{time.strftime('%Y%m%d_%H%M%S')}"
    d.mkdir(parents=True, exist_ok=False)
    shutil.copy2(c.path, d / "case.snapshot.yaml")
    rec = {"case_path": str(c.path), "case_name": c.name, "case_sha256": content_hash(c.path),
           "started": time.strftime("%Y-%m-%d %H:%M:%S"), "stages": {}}
    (d / "run.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    _active_file().write_text(str(d), encoding="utf-8")
    return d


def active_run() -> Path:
    f = _active_file()
    if not f.exists():
        raise CaseError("no active run. Call case_v2 start_run with an approved case first.")
    d = Path(f.read_text(encoding="utf-8").strip())
    if not (d / "run.json").exists():
        raise CaseError(f"active run folder {d} is missing run.json; start a new run")
    return d


def read(run: Path | None = None) -> dict:
    run = run or active_run()
    return json.loads((run / "run.json").read_text(encoding="utf-8"))


def run_case(run: Path | None = None) -> Case:
    """The approved case of the active run. Fails if the case file changed since the run started."""
    rec = read(run)
    c = load(rec["case_path"])
    if content_hash(c.path) != rec["case_sha256"]:
        raise CaseError("case.yaml changed after this run started. Re-approve and start a new run.")
    c.require_approved()
    return c


def record(stage: str, data: dict, fidelity: list[str] | None = None, run: Path | None = None) -> None:
    """Store a stage result. `status` must be one of ok / error / partial; fidelity lists model simplifications."""
    run = run or active_run()
    rec = read(run)
    entry = {"time": time.strftime("%H:%M:%S"), **data}
    if fidelity is not None:
        entry["fidelity"] = fidelity
    rec["stages"][stage] = entry
    (run / "run.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")


def stage(name: str, run: Path | None = None) -> dict | None:
    return read(run)["stages"].get(name)
