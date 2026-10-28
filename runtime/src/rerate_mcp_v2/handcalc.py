"""Hand calculations used as order-of-magnitude checks on the structural result (pure functions, unit-tested).

Centrifugal stress in a radial blade (constant cross-section, rotating about the axis, root at r_hub, tip at
r_tip). A strip of blade at radius r carries the centrifugal force of everything outboard of it:
    sigma(r) = rho * omega^2 * (r_tip^2 - r^2) / 2
so the root (r = r_hub) stress is
    sigma_root = rho * omega^2 * (r_tip^2 - r_hub^2) / 2
For a centrifugal impeller blade the "tip" is the trailing-edge radius and the root runs along the hub, so this is
a crude upper-bound style estimate for the blade pull stress; bending from blade lean and the hub disk are ignored.
A second reference is the free-rotating thin-ring hoop stress at the tip radius, sigma = rho * (omega * r)^2,
which bounds the rim stress of the hub material.
"""
from __future__ import annotations

import math


def blade_pull_stress(rho: float, omega: float, r_root: float, r_tip: float) -> float:
    if r_tip <= r_root:
        raise ValueError("r_tip must exceed r_root")
    return rho * omega ** 2 * (r_tip ** 2 - r_root ** 2) / 2.0


def ring_hoop_stress(rho: float, omega: float, r: float) -> float:
    return rho * (omega * r) ** 2


def rpm_to_rad_s(rpm: float) -> float:
    return rpm * 2.0 * math.pi / 60.0


def centrifugal_check(rho: float, rpm: float, r_root: float, r_tip: float) -> dict:
    w = rpm_to_rad_s(rpm)
    return {"omega_rad_s": w, "tip_speed_m_s": w * r_tip,
            "blade_pull_Pa": blade_pull_stress(rho, w, r_root, r_tip),
            "ring_hoop_tip_Pa": ring_hoop_stress(rho, w, r_tip),
            "formula": "sigma_root = rho*omega^2*(r_tip^2 - r_root^2)/2; ring: rho*(omega*r_tip)^2"}


def within_order_of_magnitude(fe: float, hand: float) -> bool:
    return fe > 0 and hand > 0 and 0.1 <= fe / hand <= 10.0
