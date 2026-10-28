"""Adapter: NASA-style coordinate tables (NASA contractor-report format: X, R*THETA, R section loops).

Source folder layout (file names come from case.yaml geometry.adapter_options, not from code):
  hub_file / shroud_file : two columns  (x, r)           meridional flowpath, header line skipped
  main_sections          : list of files (hub -> tip)    columns (X, R*THETA, R), one closed loop per file
  splitter_sections      : list of files (optional)

Required adapter_options (no defaults; the agent reads them from the source documentation):
  units                : length unit of the tables ("in", "mm", "m")
  mirror_theta         : true/false, flip the wrap direction so blades wrap toward -theta (TurboGrid convention)
  inlet_axial_trim     : drop flowpath points upstream of this x (table units)
  exit_radius_extent   : keep the flowpath up to this radius (table units); extended radially if beyond the table
  te_cap_tolerance     : points within this radius of the section max radius are treated as the rounded TE cap
                         and reduced to a blunt cut-off TE (table units); 0 keeps the raw loop
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import AdapterError, NeutralImpeller
from ..units import convert

REQUIRED = ("units", "mirror_theta", "inlet_axial_trim", "exit_radius_extent", "te_cap_tolerance",
            "hub_file", "shroud_file", "main_sections")


def _load(folder: Path, name: str) -> np.ndarray:
    f = folder / name
    if not f.exists():
        hits = sorted(folder.glob(name))
        if not hits:
            raise AdapterError(f"table not found: {f}")
        f = hits[0]
    return np.loadtxt(f, skiprows=1)


def _trim_flowpath(c: np.ndarray, x_in: float, r_out: float) -> np.ndarray:
    x, r = c[:, 0], c[:, 1]
    keep = (x >= x_in) & (r <= r_out)
    idx = np.where(keep)[0]
    if len(idx) < 5:
        raise AdapterError("flowpath trim leaves fewer than 5 points; check inlet_axial_trim/exit_radius_extent")
    last = idx[-1]
    pts = c[keep]
    if last + 1 < len(c) and r[last] < r_out < r[last + 1]:
        t = (r_out - r[last]) / (r[last + 1] - r[last])
        pts = np.vstack([pts, c[last] + t * (c[last + 1] - c[last])])
    elif r_out > r.max():
        ext = np.linspace(r[last], r_out, 12)[1:]
        pts = np.vstack([pts, np.column_stack([np.full_like(ext, x[last]), ext])])
    return pts


def _clean_section(d: np.ndarray, tol: float) -> np.ndarray:
    """Closed loop -> open loop starting at the TE, rounded TE cap reduced to its two end points."""
    if tol <= 0:
        return d
    i0 = int(np.argmax(d[:, 2]))
    d = np.roll(d, -i0, axis=0)
    R = d[:, 2]
    cap = R > R.max() - tol
    keep = ~cap
    keep[0] = True
    hi = np.where(cap)[0]
    hi = hi[hi > len(d) // 2]
    keep[hi.min() if len(hi) else -1] = True
    return d[keep]


def read(source: Path, opt: dict) -> NeutralImpeller:
    missing = [k for k in REQUIRED if k not in opt]
    if missing:
        raise AdapterError(f"nasa_tables adapter needs adapter_options: {missing} (no defaults by design)")
    if not source.is_dir():
        raise AdapterError(f"geometry.source must be the folder holding the tables: {source}")
    u = str(opt["units"])
    s = convert(1.0, u, "m")
    sign = -1.0 if opt["mirror_theta"] else 1.0
    x_in, r_out, tol = float(opt["inlet_axial_trim"]), float(opt["exit_radius_extent"]), float(opt["te_cap_tolerance"])

    hub = _trim_flowpath(_load(source, opt["hub_file"]), x_in, r_out)
    shr = _trim_flowpath(_load(source, opt["shroud_file"]), x_in, r_out)

    rows_raw = [[_clean_section(_load(source, f), tol) for f in opt["main_sections"]]]
    if opt.get("splitter_sections"):
        rows_raw.append([_clean_section(_load(source, f), tol) for f in opt["splitter_sections"]])

    # exit plane: hub axial position at the main blade trailing-edge radius (derived, not hard-coded)
    r_te = max(float(sec[:, 2].max()) for sec in rows_raw[0])
    hz = hub[np.argsort(hub[:, 1])]
    x_exit = float(np.interp(r_te, hz[:, 1], hz[:, 0]))

    def to_xyz(X, R, TH):
        return np.column_stack([R * np.cos(TH), sign * R * np.sin(TH), X - x_exit]) * s

    blades = []
    for row in rows_raw:
        secs = []
        for d in row:
            X, RT, R = d[:, 0], d[:, 1], d[:, 2]
            xyz = to_xyz(X, R, RT / R)
            if np.linalg.norm(xyz[0] - xyz[-1]) < 1e-9:
                xyz = xyz[:-1]
            secs.append(xyz)
        blades.append(secs)

    n_sets = int(opt.get("n_sets") or 0)
    if n_sets < 1:
        raise AdapterError("nasa_tables needs adapter_options.n_sets (number of main blades); tables do not say")
    return NeutralImpeller(hub=np.column_stack([hub[:, 0] - x_exit, hub[:, 1]]) * s,
                           shroud=np.column_stack([shr[:, 0] - x_exit, shr[:, 1]]) * s,
                           blades=blades, n_sets=n_sets,
                           meta={"adapter": "nasa_tables", "source": str(source), "r_te_m": r_te * s})
