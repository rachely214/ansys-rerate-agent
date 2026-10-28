"""Fluent setup for a single TurboGrid passage (.gtm) and performance reports, via the PyFluent settings API.

Zone conventions from a TurboGrid one-domain .gtm export:
  inflow-inblock = inlet; outflow-passage = outlet; inflow-passage + outflow-inblock = internal seam (fused)
  per1-*/per2-* rotational periodic pair; hub-*/shroud-* walls; blade zones bld-* or exportpoints*
All operating values are arguments (from the case); the turbulence model is an argument too.
"""
from __future__ import annotations

import math


def setup_passage(s, gtm: str, rpm: float, pt_in_pa: float, tt_in_k: float, p_out_pa: float, turbulence: str,
                  axis=(0, 0, 1), air: dict | None = None) -> list[str]:
    log = []
    s.settings.file.import_.read(file_type="gtm-files", file_name=gtm)
    mz = s.settings.mesh.modify_zones
    bc = s.settings.setup.boundary_conditions
    walls = list(bc.wall.keys())
    vi = list(bc.velocity_inlet.keys())
    of = list(bc.outflow.keys())
    seam = [z for z in ("inflow-passage", "outflow-inblock") if z in vi + of]
    if len(seam) == 2:
        mz.fuse_face_zones(face_zones=seam, fused_zone_name="seam")
        log.append("fused internal seam")
    for new, parts in {"per1": ["per1-inblock", "per1-passage"], "per2": ["per2-inblock", "per2-passage"],
                       "hub": ["hub-inblock", "hub-passage"], "shroud": ["shroud-inblock", "shroud-passage"]}.items():
        have = [p for p in parts if p in walls]
        if len(have) == 2:
            mz.merge_zones(zone_names=have)
        if have:
            mz.zone_name(zone_name=have[0], new_name=new)
    inlet = "inflow-inblock" if "inflow-inblock" in vi else vi[0]
    outlet = "outflow-passage" if "outflow-passage" in of else of[-1]
    mz.zone_name(zone_name=inlet, new_name="inlet")
    mz.zone_name(zone_name=outlet, new_name="outlet")
    mz.make_periodic(zone_name="per1", shadow_zone_name="per2", rotate_periodic=True, create=True,
                     auto_translation=True)
    st = s.settings.setup
    st.general.operating_conditions.operating_pressure = 0
    st.models.energy.enabled = True
    if turbulence == "sst":
        st.models.viscous.model = "k-omega"
        st.models.viscous.k_omega_model = "sst"
    elif turbulence == "k-epsilon":
        st.models.viscous.model = "k-epsilon"
    else:
        raise ValueError(f"unsupported turbulence model {turbulence}")
    mat = st.materials.fluid["air"]
    mat.density.option = "ideal-gas"
    if air:  # temperature-dependent properties (config fluent.air), see PROGRESS C22/C23, DEC-17
        mat.specific_heat.option = "polynomial"
        mat.specific_heat.polynomial = {"function_of": "temperature",
                                        "coefficients": [float(x) for x in air["cp_polynomial"]]}
        su = air["sutherland"]
        mat.viscosity.option = "sutherland"
        mat.viscosity.sutherland = {"option": "three-coefficient-method",
                                    "reference_viscosity": float(su["reference_viscosity"]),
                                    "reference_temperature": float(su["reference_temperature"]),
                                    "effective_temperature": float(su["effective_temperature"])}
        log.append("air: cp(T) polynomial, Sutherland viscosity")
    cz = list(st.cell_zone_conditions.fluid.keys())[0]
    rf = st.cell_zone_conditions.fluid[cz].reference_frame
    rf.frame_motion = True
    rf.reference_frame_axis_origin = [0, 0, 0]
    rf.reference_frame_axis_direction = list(axis)
    rf.mrf_omega.value = rpm * 2 * math.pi / 60
    bc.set_zone_type(zone_list=["inlet"], new_type="pressure-inlet")
    bc.set_zone_type(zone_list=["outlet"], new_type="pressure-outlet")
    pi = bc.pressure_inlet["inlet"]
    pi.momentum.gauge_total_pressure.value = pt_in_pa
    pi.momentum.supersonic_or_initial_gauge_pressure.value = 0.95 * pt_in_pa
    pi.thermal.total_temperature.value = tt_in_k
    po = bc.pressure_outlet["outlet"]
    po.momentum.gauge_pressure.value = p_out_pa
    po.thermal.backflow_total_temperature.value = 1.2 * tt_in_k
    try:  # damps outlet backflow cycling on a short vaneless exit
        po.momentum.avg_pressure_spec = True
        po.momentum.prevent_reverse_flow = True
    except Exception:
        log.append("average-pressure outlet options not available")
    w = bc.wall["shroud"].momentum  # stationary casing in the rotating frame
    w.wall_motion = "Moving Wall"
    w.relative = False
    w.rotating = True
    w.rotation_speed = 0
    w.rotation_axis_direction = list(axis)
    so = s.settings.solution
    so.methods.p_v_coupling.flow_scheme = "Coupled"
    rd = so.report_definitions
    for n, z in (("mdot_in", "inlet"), ("mdot_out", "outlet")):
        if n not in rd.flux.keys():
            rd.flux[n] = {}
        rd.flux[n].boundaries = [z]
    # Mass-weighted (energy/momentum-consistent) and area-weighted (how rig rakes are averaged) totals.
    for kind, sfx in (("surface-massavg", ""), ("surface-areaavg", "_area")):
        for n, f, z in (("pt_in", "total-pressure", "inlet"), ("pt_out", "total-pressure", "outlet"),
                        ("tt_in", "total-temperature", "inlet"), ("tt_out", "total-temperature", "outlet")):
            n = n + sfx
            if n not in rd.surface.keys():
                rd.surface[n] = {}
            r = rd.surface[n]
            r.report_type = kind
            r.field = f
            r.surface_names = [z]
    log.append(f"setup done: zone {cz}, {rpm} rpm, outlet {p_out_pa} Pa, {turbulence}")
    return log


def eta_tt(pr: float, tr: float, gamma: float = 1.4) -> float:
    """Total-to-total adiabatic (isentropic) efficiency of a compressor, perfect gas (constant gamma)."""
    return (pr ** ((gamma - 1) / gamma) - 1) / (tr - 1) if tr > 1 else float("nan")


def eta_tt_gas_table(pr: float, t1: float, t2: float, cp_poly: list[float], r_gas: float) -> float:
    """Total-to-total adiabatic efficiency with temperature-dependent cp (gas-table method): ideal enthalpy rise to
    the isentropic exit temperature T2s at the measured PR, over the actual enthalpy rise T1 -> T2."""
    a = [float(x) for x in cp_poly]
    h = lambda T: sum(a[i] * T ** (i + 1) / (i + 1) for i in range(len(a)))
    phi = lambda T: a[0] * math.log(T) + sum(a[i] * T ** i / i for i in range(1, len(a)))  # integral cp/T dT
    if not (t2 > t1 > 0 and pr > 0):
        return float("nan")
    target = phi(t1) + r_gas * math.log(pr)
    lo, hi = t1 * 0.5, t2 * 2.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if phi(mid) < target else (lo, mid)
    return (h(0.5 * (lo + hi)) - h(t1)) / (h(t2) - h(t1))


def performance(s, gamma: float = 1.4, air: dict | None = None) -> dict:
    """PR/TR/eta from mass-weighted totals (primary) and, if defined, from area-weighted totals (`*_area`, the
    averaging used for rig rake data). Inlet values are at the model inlet; outlet at the model outlet."""
    rd = s.settings.solution.report_definitions
    names = ["mdot_in", "mdot_out", "pt_in", "pt_out", "tt_in", "tt_out"]
    area = [n + "_area" for n in ("pt_in", "pt_out", "tt_in", "tt_out")]
    have_area = all(n in rd.surface.keys() for n in area)
    v = rd.compute(report_defs=names + (area if have_area else []))
    d = {list(x)[0]: list(x.values())[0][0] for x in v}
    pr, tr = d["pt_out"] / d["pt_in"], d["tt_out"] / d["tt_in"]
    # eta_isen_tt is the reported value: gas-table (cp(T)) when air properties are configured, the same
    # reduction method as the rig data; the constant-gamma value is kept for reference.
    eta_g = eta_tt(pr, tr, gamma)
    eta = eta_tt_gas_table(pr, d["tt_in"], d["tt_out"], air["cp_polynomial"], air["gas_constant"]) if air else eta_g
    out = {"PR_tt": round(pr, 4), "TR_tt": round(tr, 4), "eta_isen_tt": round(eta, 4),
           "eta_isen_tt_const_gamma": round(eta_g, 4),
           "eta_method": "gas-table cp(T)" if air else f"constant gamma {gamma}"}
    if have_area:
        pra, tra = d["pt_out_area"] / d["pt_in_area"], d["tt_out_area"] / d["tt_in_area"]
        eta_a = (eta_tt_gas_table(pra, d["tt_in_area"], d["tt_out_area"], air["cp_polynomial"], air["gas_constant"])
                 if air else eta_tt(pra, tra, gamma))
        out.update(PR_tt_area=round(pra, 4), TR_tt_area=round(tra, 4), eta_isen_tt_area=round(eta_a, 4))
    return {**out, **{k: round(v, 5) for k, v in d.items()}}


def corrected_flow_kg_s(mdot_passage: float, n_passages: int, pt_in: float, tt_in: float, p_ref: float,
                        t_ref: float) -> float:
    """Standard corrected flow: m * sqrt(Tt/Tref) / (Pt/Pref), whole wheel."""
    return abs(mdot_passage) * n_passages * math.sqrt(tt_in / t_ref) / (pt_in / p_ref)


def outlet_static(s) -> float | None:
    """Area-averaged static pressure at the outlet (Pa); defines the report on first use."""
    rd = s.settings.solution.report_definitions
    try:
        if "p_out_static" not in rd.surface.keys():
            rd.surface["p_out_static"] = {}
            r = rd.surface["p_out_static"]
            r.report_type = "surface-areaavg"
            r.field = "pressure"
            r.surface_names = ["outlet"]
        v = rd.compute(report_defs=["p_out_static"])
        return float(list(v[0].values())[0][0])
    except Exception:
        return None
