"""Trim the meridional flowpath of a neutral impeller at a given radius (outlet placement for the CFD model).

The CFD outlet must sit where the outlet static pressure was measured. The flowpath is cut (or extended radially
at constant axial position) so its last point is at radius r_out on both hub and shroud. Pure function, tested.
"""
from __future__ import annotations

import copy

import numpy as np

from . import NeutralImpeller


def _cut(curve: np.ndarray, r_out: float) -> np.ndarray:
    z, r = curve[:, 0], curve[:, 1]
    keep = r <= r_out
    idx = np.where(keep)[0]
    if len(idx) < 5:
        raise ValueError("outlet radius leaves fewer than 5 flowpath points")
    last = idx[-1]
    pts = curve[: last + 1]
    if last + 1 < len(curve) and r[last] < r_out < r[last + 1]:
        t = (r_out - r[last]) / (r[last + 1] - r[last])
        pts = np.vstack([pts, curve[last] + t * (curve[last + 1] - curve[last])])
    elif r_out > r.max() + 1e-12:
        ext = np.linspace(r[last], r_out, 8)[1:]
        pts = np.vstack([pts, np.column_stack([np.full_like(ext, z[last]), ext])])
    return pts


def set_outlet_radius(imp: NeutralImpeller, r_out_m: float) -> NeutralImpeller:
    """Return a copy whose hub and shroud end at r_out_m (must exceed the blade trailing-edge radius)."""
    r_te = float(imp.meta.get("r_te_m") or 0)
    if r_te and r_out_m <= r_te:
        raise ValueError("outlet radius must be outside the blade trailing edge")
    out = copy.deepcopy(imp)
    out.hub = _cut(imp.hub, r_out_m)
    out.shroud = _cut(imp.shroud, r_out_m)
    out.meta = dict(imp.meta, outlet_radius_m=r_out_m)
    return out
