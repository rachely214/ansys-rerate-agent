"""Adapter + writer: BladeGen-style curve set (.inf + hub.crv + shroud.crv + profile.crv), as exported by
BladeGen / BladeEditor / many 3rd-party tools and read by TurboGrid.

Reader expects: rotation axis Z, Cartesian x y z, units from the .inf ("Geometry Units: IN|MM|M|CM").
The reader shifts z so the impeller exit (hub at max radius of the main blade TE) is at z = 0 (neutral form).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from . import AdapterError, NeutralImpeller
from ..units import convert

_UNIT = {"IN": "in", "MM": "mm", "M": "m", "CM": "cm", "FT": "ft"}


def _parse_inf(inf: Path) -> dict:
    d = {}
    for line in inf.read_text(errors="ignore").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            d[k.strip().lower()] = v.strip()
    return d


def _xyz(f: Path) -> np.ndarray:
    pts = [tuple(float(v) for v in l.split()) for l in f.read_text().splitlines() if len(l.split()) == 3]
    return np.array(pts)


def _profiles(f: Path) -> list[list[np.ndarray]]:
    rows: list[list[list]] = []
    for l in f.read_text().splitlines():
        if l.startswith("##"):
            rows.append([])
        elif l.startswith("#"):
            if not rows:
                rows.append([])
            rows[-1].append([])
        elif len(l.split()) == 3 and rows and rows[-1]:
            rows[-1][-1].append(tuple(float(v) for v in l.split()))
    return [[np.array(s) for s in r if s] for r in rows]


def read(source: Path, opt: dict) -> NeutralImpeller:
    inf = source if source.suffix.lower() == ".inf" else source / "BladeGen.inf"
    if not inf.exists():
        raise AdapterError(f"BladeGen .inf not found: {inf}")
    h = _parse_inf(inf)
    if h.get("axis of rotation", "Z").upper() != "Z":
        raise AdapterError("only 'Axis of Rotation: Z' is supported")
    u = _UNIT.get(h.get("geometry units", "").upper())
    if not u:
        raise AdapterError("'.inf' has no recognised 'Geometry Units' line; add it (IN/MM/M/CM)")
    s = convert(1.0, u, "m")
    folder = inf.parent
    hub = _xyz(folder / h.get("hub data file", "hub.crv"))
    shr = _xyz(folder / h.get("shroud data file", "shroud.crv"))
    rows = _profiles(folder / h.get("profile data file", "profile.crv"))
    n_sets = int(re.findall(r"\d+", h.get("number of blade sets", "0"))[0])
    to_m = lambda c: np.column_stack([c[:, 2], np.hypot(c[:, 0], c[:, 1])])  # (z, r)
    hub_m, shr_m = to_m(hub), to_m(shr)
    r_te = max(float(np.hypot(s_[:, 0], s_[:, 1]).max()) for s_ in rows[0])
    hz = hub_m[np.argsort(hub_m[:, 1])]
    z_exit = float(np.interp(r_te, hz[:, 1], hz[:, 0]))
    shift = np.array([0.0, 0.0, z_exit])
    return NeutralImpeller(hub=(hub_m - [z_exit, 0]) * s, shroud=(shr_m - [z_exit, 0]) * s,
                           blades=[[(sec - shift) * s for sec in row] for row in rows], n_sets=n_sets,
                           meta={"adapter": "bladegen_inf", "source": str(inf), "r_te_m": r_te * s})


def write(imp: NeutralImpeller, out_dir: Path, rows: list[int] | None = None, unit: str = "in",
          section_extension: float = 0.3) -> Path:
    """Write the neutral impeller as a BladeGen curve set for TurboGrid / Discovery.

    rows: which blade rows to write (default all; [0] = main blade only).
    section_extension: first/last sections are extrapolated beyond hub/shroud by this fraction of the
    neighbouring section spacing, so TurboGrid can cut the blade at the flowpath (sections lying exactly on the
    walls give 'V value outside bounds'). This is a meshing technique, not machine data.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    k = convert(1.0, "m", unit)
    rows = rows if rows is not None else list(range(len(imp.blades)))
    for name, c in (("hub", imp.hub), ("shroud", imp.shroud)):
        z, r = c[:, 0] * k, c[:, 1] * k
        np.savetxt(out_dir / f"{name}.crv", np.column_stack([r, np.zeros_like(r), z]), fmt="%16.9f")
    lines = []
    for b, ri in enumerate(rows):
        secs = [sec * k for sec in imp.blades[ri]]
        if section_extension > 0:
            secs = [secs[0] + section_extension * (secs[0] - secs[1])] + secs + \
                   [secs[-1] + section_extension * (secs[-1] - secs[-2])]
        lines.append(f"## ExportPoints{b}")
        for j, sec in enumerate(secs):
            lines.append(f"# Profile {j + 1} at {100.0 * j / (len(secs) - 1):10.4f}%")
            lines += [f"{a:16.9f}{bb:16.9f}{cc:16.9f}" for a, bb, cc in sec]
            lines.append("")
    (out_dir / "profile.crv").write_text("\n".join(lines) + "\n")
    inv = {v: kk for kk, v in _UNIT.items()}
    inf = ["!======  CFX-BladeGen Export  ========", "Axis of Rotation: Z", f"Number of Blade Sets: {imp.n_sets}",
           f"Number of Blades Per Set: {len(rows)}", "Blade Loft Direction: Spanwise",
           f"Geometry Units: {inv[unit]}", "Coordinate System Orientation: Righthanded"]
    for b in range(len(rows)):
        inf += [f"Blade {b} LE: EllipseEnd", f"Blade {b} TE: CutOffEnd"]
    inf += ["Hub Data File: hub.crv", "Shroud Data File: shroud.crv", "Profile Data File: profile.crv"]
    (out_dir / "BladeGen.inf").write_text("\n".join(inf) + "\n")
    return out_dir / "BladeGen.inf"
