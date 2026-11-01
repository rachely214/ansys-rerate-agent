"""Design changes applied to the neutral impeller. Works for any adapter.

Each function takes explicit parameters chosen by the agent (and stated in the run record). There are no
built-in numbers for a particular machine.
"""
from __future__ import annotations

import copy

import numpy as np

from . import NeutralImpeller, z_at_r


def scale_exit_height(imp: NeutralImpeller, scale: float, blend_start_fraction: float) -> NeutralImpeller:
    """Change the impeller exit blade height by `scale` (new/old), keeping the inlet unchanged.

    The shroud is moved axially in the radial part of the impeller. The move is blended linearly from zero at
    r = blend_start_fraction * r_te up to the full move at the trailing-edge radius r_te, so the inducer and the
    inlet radii stay fixed. Blade sections are stretched between hub and the new shroud with span fraction kept.
    blend_start_fraction: 0 < f < 1. It is a design choice; record why it was chosen.
    """
    if not (0.0 < blend_start_fraction < 1.0):
        raise ValueError("blend_start_fraction must be between 0 and 1")
    if scale <= 0:
        raise ValueError("scale must be > 0")
    out = copy.deepcopy(imp)
    r_te = float(imp.meta.get("r_te_m") or max(np.hypot(s[:, 0], s[:, 1]).max() for s in imp.blades[0]))
    b0 = abs(z_at_r(imp.hub, r_te) - z_at_r(imp.shroud, r_te))
    sign = np.sign(z_at_r(imp.hub, r_te) - z_at_r(imp.shroud, r_te)) or 1.0
    dz = (scale - 1.0) * b0
    r_lo = blend_start_fraction * r_te
    old_shr = imp.shroud
    w = np.clip((old_shr[:, 1] - r_lo) / (r_te - r_lo), 0, 1)
    new_shr = old_shr.copy()
    new_shr[:, 0] = old_shr[:, 0] - sign * w * dz
    out.shroud = new_shr

    for ri, row in enumerate(imp.blades):
        new_row = []
        for sec in row:
            R = np.hypot(sec[:, 0], sec[:, 1])
            Z = sec[:, 2]
            zh = np.array([z_at_r(imp.hub, r) for r in R])
            zs_old = np.array([z_at_r(old_shr, r) for r in R])
            zs_new = np.array([z_at_r(new_shr, r) for r in R])
            den = zh - zs_old
            frac = np.where(np.abs(den) > 1e-12, (zh - Z) / np.where(np.abs(den) > 1e-12, den, 1.0), 0.0)
            s2 = sec.copy()
            s2[:, 2] = zh - frac * (zh - zs_new)
            new_row.append(s2)
        out.blades[ri] = new_row
    out.meta = dict(imp.meta, exit_height_scale=scale, blend_start_fraction=blend_start_fraction,
                    exit_blade_height_m_before=b0, exit_blade_height_m_after=b0 * scale)
    return out
