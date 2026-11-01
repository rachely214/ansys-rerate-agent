"""Unit conversion for case values. Every case quantity is stored as {value, unit, source}; code converts to
the unit it needs here. Only conversions are defined; no machine data lives in this module."""
from __future__ import annotations

# factor to SI base unit, plus offset for temperatures
_LINEAR = {
    # length -> m
    "m": ("length", 1.0), "mm": ("length", 1e-3), "cm": ("length", 1e-2), "in": ("length", 0.0254),
    "ft": ("length", 0.3048),
    # mass flow -> kg/s
    "kg/s": ("mass_flow", 1.0), "lbm/s": ("mass_flow", 0.45359237), "kg/h": ("mass_flow", 1 / 3600.0),
    "lbm/min": ("mass_flow", 0.45359237 / 60.0),
    # pressure / stress -> Pa
    "Pa": ("pressure", 1.0), "kPa": ("pressure", 1e3), "MPa": ("pressure", 1e6), "bar": ("pressure", 1e5),
    "psi": ("pressure", 6894.757293168), "psia": ("pressure", 6894.757293168), "ksi": ("pressure", 6894757.293168),
    "atm": ("pressure", 101325.0),
    # speed -> rpm
    "rpm": ("speed", 1.0), "rad/s": ("speed", 60.0 / (2 * 3.141592653589793)),
    # power -> W
    "W": ("power", 1.0), "kW": ("power", 1e3), "MW": ("power", 1e6), "hp": ("power", 745.6998715822702),
    # density -> kg/m3
    "kg/m3": ("density", 1.0), "lbm/in3": ("density", 27679.904710191), "g/cm3": ("density", 1000.0),
    # frequency -> Hz
    "Hz": ("frequency", 1.0),
    # dimensionless
    "-": ("dimensionless", 1.0), "ratio": ("dimensionless", 1.0), "%": ("dimensionless", 0.01),
    # angle -> deg
    "deg": ("angle", 1.0),
}
_TEMP = {"K": (1.0, 0.0), "degC": (1.0, 273.15), "C": (1.0, 273.15), "R": (5.0 / 9.0, 0.0),
         "degF": (5.0 / 9.0, 255.3722222222222), "F": (5.0 / 9.0, 255.3722222222222)}


class UnitError(ValueError):
    pass


def kind(unit: str) -> str:
    if unit in _TEMP:
        return "temperature"
    if unit in _LINEAR:
        return _LINEAR[unit][0]
    raise UnitError(f"unknown unit '{unit}'. Known: {sorted(list(_LINEAR) + list(_TEMP))}")


def convert(value: float, src: str, dst: str) -> float:
    """Convert value from unit src to unit dst (same physical kind)."""
    if src == dst:
        return float(value)
    ks, kd = kind(src), kind(dst)
    if ks != kd:
        raise UnitError(f"cannot convert {src} ({ks}) to {dst} ({kd})")
    if ks == "temperature":
        a, b = _TEMP[src]
        kelvin = float(value) * a + b
        a2, b2 = _TEMP[dst]
        return (kelvin - b2) / a2
    return float(value) * _LINEAR[src][1] / _LINEAR[dst][1]
