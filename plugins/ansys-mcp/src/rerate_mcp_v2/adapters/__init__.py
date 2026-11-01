"""Geometry adapter interface.

An adapter turns a customer's impeller description into the neutral form every downstream stage uses:

    NeutralImpeller
      hub, shroud      : (N, 2) arrays of meridional (axial z, radius r) points, inlet -> exit, in metres
      blades           : list of blade rows (main first, then splitter), each a list of spanwise sections
                         hub -> shroud; each section is an (M, 3) array of (x, y, z) points in metres,
                         rotation axis +z, flow toward +z, impeller exit plane at z = 0
      n_sets           : number of blade sets (main blades)
      exit_blade_height: metres (measured from the flowpath at the exit)

Design changes are applied on the neutral form (adapters.modify), so they work for any source format.
Writers export the neutral form to the files the Ansys apps read (BladeGen .inf curve set for TurboGrid and the
Discovery build script).

Adapters carry NO engineering numbers: anything specific to a source (file names, axis conventions, mirror
flags) comes from case.yaml `geometry.adapter_options`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class NeutralImpeller:
    hub: np.ndarray
    shroud: np.ndarray
    blades: list[list[np.ndarray]]
    n_sets: int
    meta: dict = field(default_factory=dict)

    @property
    def exit_radius(self) -> float:
        return float(max(self.hub[:, 1].max(), self.shroud[:, 1].max()))

    def exit_blade_height(self, r_at: float | None = None) -> float:
        """Axial gap between hub and shroud at radius r_at (default: smaller of the two max radii)."""
        r = r_at if r_at is not None else min(self.hub[:, 1].max(), self.shroud[:, 1].max())
        return abs(z_at_r(self.hub, r) - z_at_r(self.shroud, r))


def z_at_r(curve: np.ndarray, r: float) -> float:
    """Axial position of a meridional curve at radius r (uses the radial leg: last monotonic part)."""
    zr = curve[np.argsort(curve[:, 1])]
    return float(np.interp(r, zr[:, 1], zr[:, 0]))


class AdapterError(ValueError):
    pass


def get_adapter(name: str):
    if name == "nasa_tables":
        from .nasa_tables import read
        return read
    if name == "bladegen_inf":
        from .bladegen_inf import read
        return read
    if name == "step":
        raise AdapterError(
            "STEP adapter is not implemented. A STEP solid has no blade sections, hub/shroud curves or blade "
            "count in a form the meshing stage can use. See docs/DECISIONS.md (DEC-04) for what it needs: "
            "section extraction by cutting the blade surfaces at spanwise stations, plus a hub/shroud meridional "
            "trace. Use bladegen_inf (export from BladeGen/BladeEditor/CFturbo) or nasa_tables for now.")
    raise AdapterError(f"unknown geometry adapter '{name}'. Available: nasa_tables, bladegen_inf, step (documented)")


def read_geometry(adapter: str, source: Path, options: dict | None = None) -> NeutralImpeller:
    imp = get_adapter(adapter)(Path(source), options or {})
    check(imp)
    return imp


def check(imp: NeutralImpeller) -> None:
    """Basic sanity, independent of format. Raises AdapterError with a plain explanation."""
    if imp.hub.ndim != 2 or imp.hub.shape[1] != 2 or len(imp.hub) < 5:
        raise AdapterError("hub curve must have at least 5 (z, r) points")
    if imp.shroud.ndim != 2 or imp.shroud.shape[1] != 2 or len(imp.shroud) < 5:
        raise AdapterError("shroud curve must have at least 5 (z, r) points")
    if not imp.blades or any(len(row) < 2 for row in imp.blades):
        raise AdapterError("need at least one blade row with 2 or more spanwise sections")
    if imp.n_sets < 1:
        raise AdapterError("n_sets must be >= 1")
    for row in imp.blades:
        for s in row:
            if s.ndim != 2 or s.shape[1] != 3 or len(s) < 8:
                raise AdapterError("each blade section must be an (M>=8, 3) xyz array")
    if imp.exit_blade_height() <= 0:
        raise AdapterError("hub and shroud do not form a passage at the exit (zero/negative height)")
