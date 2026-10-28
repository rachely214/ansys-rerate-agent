"""Unit tests: units, case loader/approval, report logic, adapters (synthetic geometry, no Ansys needed)."""
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "ansys-mcp" / "src"))

from rerate_mcp_v2 import case as casemod  # noqa: E402
from rerate_mcp_v2 import report, units  # noqa: E402
from rerate_mcp_v2.adapters import NeutralImpeller, bladegen_inf, check, read_geometry  # noqa: E402
from rerate_mcp_v2.adapters.modify import scale_exit_height  # noqa: E402

EXAMPLE = ROOT / "examples" / "01_nasa_hecc" / "case.yaml"


def tmp_case(mutate=None) -> Path:
    d = Path(tempfile.mkdtemp())
    data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    data.pop("approval", None)
    data["material"]["library_file"] = str((EXAMPLE.parent / data["material"]["library_file"]).resolve())
    if mutate:
        mutate(data)
    p = d / "case.yaml"
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return p


class Units(unittest.TestCase):
    def test_roundtrip(self):
        self.assertAlmostEqual(units.convert(1, "in", "mm"), 25.4)
        self.assertAlmostEqual(units.convert(1, "psi", "Pa"), 6894.757, places=2)
        self.assertAlmostEqual(units.convert(1, "lbm/s", "kg/s"), 0.45359237)
        self.assertAlmostEqual(units.convert(15, "degC", "K"), 288.15)
        self.assertAlmostEqual(units.convert(5, "%", "-"), 0.05)

    def test_kind_mismatch(self):
        with self.assertRaises(units.UnitError):
            units.convert(1, "in", "Pa")


class CaseLoader(unittest.TestCase):
    def test_example_is_clean(self):
        c = casemod.load(tmp_case())
        self.assertEqual(c.issues, [])
        raw = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))["operating_point"]["speed"]["value"]
        self.assertAlmostEqual(c.q("operating_point.speed", "rpm"), raw)

    def test_missing_required_is_blocking_no_default(self):
        p = tmp_case(lambda d: d["geometry"].pop("tip_clearance"))
        self.assertTrue(any("tip_clearance" in str(i) for i in casemod.load(p).issues))

    def test_missing_required_is_blocking_no_default_original(self):
        c = casemod.load(tmp_case(lambda d: d["targets"].pop("corrected_flow_min")))
        self.assertTrue(any(i["field"] == "targets.corrected_flow_min" for i in c.issues))
        with self.assertRaises(casemod.CaseError):
            c.q("targets.corrected_flow_min", "kg/s")
        with self.assertRaises(casemod.CaseError):
            c.require_stage("sizing")

    def test_wrong_unit_kind(self):
        c = casemod.load(tmp_case(lambda d: d["operating_point"]["speed"].update(unit="in")))
        self.assertTrue(any(i["field"] == "operating_point.speed" for i in c.issues))

    def test_unknown_field_warns(self):
        c = casemod.load(tmp_case(lambda d: d["targets"].update(flow_typo={"value": 1, "unit": "-"})))
        self.assertTrue(any(i["field"] == "targets.flow_typo" for i in c.warnings))

    def test_approval_and_edit_invalidates(self):
        p = tmp_case()
        self.assertFalse(casemod.load(p).approved)
        with self.assertRaises(casemod.CaseError):
            casemod.approve(p, "")
        casemod.approve(p, "Test Engineer")
        self.assertTrue(casemod.load(p).approved)
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        d["operating_point"]["speed"]["value"] += 100
        p.write_text(yaml.safe_dump(d, sort_keys=False), encoding="utf-8")
        self.assertFalse(casemod.load(p).approved)
        with self.assertRaises(casemod.CaseError):
            casemod.load(p).require_approved()

    def test_cannot_approve_with_blocking_issues(self):
        p = tmp_case(lambda d: d["material"].pop("yield_strength"))
        with self.assertRaises(casemod.CaseError):
            casemod.approve(p, "X")


def stages_pass(c):
    """Stage results just better than the case targets (values derived from the case, not typed in)."""
    rpm = c.q("operating_point.speed", "rpm")
    lu = c.raw("limits.exit_blade_height_max")["unit"]
    fu = c.raw("targets.corrected_flow_min")["unit"]
    gain = (c.q("targets.corrected_flow_min", fu) / c.q("baseline.corrected_flow", fu) - 1) * 100
    return {
        "sizing": {"status": "ok", "speed_rpm": rpm, "flow_gain_pct": gain + 0.1,
                   "exit_blade_height": {lu: 0.98 * c.q("limits.exit_blade_height_max", lu)}, "fidelity": ["1D"]},
        "cfd": {"status": "ok", "converged": True, "speed_rpm": rpm, "PR_tt": c.q("targets.pressure_ratio_min", "-") + 0.1,
                "eta_isen_tt": c.q("targets.efficiency_tt_min", "-") + 0.01,
                "corrected_flow": {fu: 1.01 * c.q("targets.corrected_flow_min", fu)}, "fidelity": []},
        "structural": {"status": "ok", "peak_stress_Pa": 4.0e8, "body_stress_Pa": 3.0e8, "body_converged": True,
                       "fillet_stress_Pa": 3.2e8, "fillet_converged": True, "governing_stress_Pa": 3.2e8,
                       "governing_location": "root/fillet", "governing_converged": True,
                       "peak_converged": False, "hand_check_ok": True, "fidelity": []},
    }


def with_calibration(c, st, status="CALIBRATED"):
    from rerate_mcp_v2 import calibration
    st["meshing"] = {"status": "ok", "topology": "T", "with_splitter": True, "size_factor": 1.5}
    st["cfd_calibration"] = {"status": status, "reasons": [] if status == "CALIBRATED" else ["x"], "items": [],
                             "pr_reference": "impeller", "baseline_run": "b",
                             "signature": calibration.model_signature(st, c)}
    return st


class Report(unittest.TestCase):
    def setUp(self):
        self.c = casemod.load(tmp_case())

    def test_all_pass_is_not_release_pass_when_items_open(self):
        rows = report.scorecard(self.c, with_calibration(self.c, stages_pass(self.c)))
        res = {r["check"]: r["result"] for r in rows}
        self.assertEqual(res["Inlet corrected flow"], "PASS")
        self.assertEqual(res["Surge margin"], "NOT CHECKED")
        self.assertTrue(report.verdict(rows).startswith("PASS ON CHECKED ITEMS ONLY"))

    def test_uncalibrated_model_never_passes_aero(self):
        for st in (stages_pass(self.c), with_calibration(self.c, stages_pass(self.c), "NOT CALIBRATED")):
            rows = report.scorecard(self.c, st)
            r = [x for x in rows if x["check"] == "Inlet corrected flow"][0]
            self.assertEqual(r["result"], "NOT CHECKED")
            self.assertIn("model not calibrated", r["note"])

    def test_calibration_from_other_model_does_not_apply(self):
        st = with_calibration(self.c, stages_pass(self.c))
        st["meshing"]["with_splitter"] = False  # design run meshed differently from the calibrated baseline
        r = [x for x in report.scorecard(self.c, st) if x["check"] == "Inlet corrected flow"][0]
        self.assertEqual(r["result"], "NOT CHECKED")
        self.assertIn("with_splitter", r["note"])

    def test_uncalibrated_fail_is_model_limited(self):
        st = stages_pass(self.c)
        st["cfd"]["PR_tt"] = 0.5 * st["cfd"]["PR_tt"]
        r = [x for x in report.scorecard(self.c, st) if x["check"] == "Total pressure ratio"][0]
        self.assertEqual(r["result"], "FAIL (model-limited)")

    def test_calibration_evaluate(self):
        from rerate_mcp_v2 import calibration
        fu = self.c.raw("baseline.corrected_flow")["unit"]
        m = self.c.q("baseline.corrected_flow", fu)
        eta_m = self.c.opt("baseline.impeller_efficiency_tt", "-")
        cfd = {"status": "ok", "converged": True, "corrected_flow": {fu: m * 1.01}, "PR_tt": 4.0,
               "eta_isen_tt": eta_m - 0.005}
        cal = calibration.evaluate(self.c, cfd, "b")
        q = {i["quantity"].split(" (")[0]: i["result"] for i in cal["items"]}
        self.assertEqual(q["corrected flow"], "WITHIN")
        self.assertEqual(q["t-t efficiency"], "WITHIN")
        if self.c.opt("baseline.impeller_pressure_ratio", "-") is None:
            self.assertEqual(q["total pressure ratio"], "NOT CHECKABLE")
            self.assertEqual(cal["status"], "NOT CALIBRATED")
        cfd["converged"] = False
        self.assertEqual(calibration.evaluate(self.c, cfd, "b")["status"], "NOT CALIBRATED")

    def test_fail_labelled_model_limited(self):
        st = stages_pass(self.c)
        st["cfd"].update(eta_isen_tt=0.5 * st["cfd"]["eta_isen_tt"], fidelity=["single passage"])
        rows = report.scorecard(self.c, st)
        r = [x for x in rows if x["check"].startswith("Adiabatic")][0]
        self.assertEqual(r["result"], "FAIL (model-limited)")
        self.assertIn("simplified model", report.verdict(rows))

    def test_choked_design_is_real_flow_fail(self):
        st = with_calibration(self.c, stages_pass(self.c), "NOT CALIBRATED")
        st["cfd"].update(choked=True, converged=False, outlet_condition="design flow target (targeted mass flow, DEC-19)")
        rows = report.scorecard(self.c, st)
        r = {x["check"]: x for x in rows}
        self.assertEqual(r["Inlet corrected flow"]["result"], "FAIL")
        self.assertIn("choked", r["Inlet corrected flow"]["this_run"])
        self.assertEqual(r["Total pressure ratio"]["result"], "NOT CHECKED")
        self.assertTrue(any(x["check"].startswith("Strength") for x in rows))

    def test_unconverged_cfd_never_scored(self):
        for eta_scale in (0.5, 1.5):
            st = with_calibration(self.c, stages_pass(self.c))
            st["cfd"].update(status="partial", converged=False, eta_isen_tt=eta_scale * st["cfd"]["eta_isen_tt"])
            r = [x for x in report.scorecard(self.c, st) if x["check"].startswith("Adiabatic")][0]
            self.assertEqual(r["result"], "NOT CHECKED")
            self.assertIn("not converged", r["note"])

    def test_missing_stage_never_passes(self):
        rows = report.scorecard(self.c, {})
        self.assertFalse(any(r["result"] == "PASS" for r in rows))
        self.assertTrue(report.verdict(rows).startswith("INCOMPLETE"))

    def test_targets_follow_case(self):
        p = tmp_case(lambda d: d["targets"]["corrected_flow_min"].update(value=d["targets"]["corrected_flow_min"]["value"] * 1.2))
        c2 = casemod.load(p)
        rows = report.scorecard(c2, stages_pass(c2))
        r = [x for x in rows if x["check"] == "Inlet corrected flow"][0]
        fu = c2.raw("targets.corrected_flow_min")["unit"]
        self.assertIn(f"{c2.q('targets.corrected_flow_min', fu):.4g}", r["target"])
        st = with_calibration(self.c, stages_pass(self.c))  # passes the ORIGINAL target, must fail the raised one
        r2 = [x for x in report.scorecard(c2, st) if x["check"] == "Inlet corrected flow"][0]
        self.assertEqual(r2["result"], "FAIL")

    def test_casing_fit_fail_is_real_not_model_limited(self):
        st = stages_pass(self.c)
        lu = self.c.raw("limits.exit_blade_height_max")["unit"]
        st["sizing"]["exit_blade_height"] = {lu: 1.05 * self.c.q("limits.exit_blade_height_max", lu)}
        r = [x for x in report.scorecard(self.c, st) if x["check"].startswith("Fits casing")][0]
        self.assertEqual(r["result"], "FAIL")

    def test_sizing_gain_rounded_like_stage_passes(self):
        st = stages_pass(self.c)
        fu = self.c.raw("targets.corrected_flow_min")["unit"]
        exact = (self.c.q("targets.corrected_flow_min", fu) / self.c.q("baseline.corrected_flow", fu) - 1) * 100
        st["sizing"]["flow_gain_pct"] = round(exact, 2)  # exactly what the sizing stage records
        r = [x for x in report.scorecard(self.c, st) if x["check"].startswith("Flow increase")][0]
        self.assertEqual(r["result"], "PASS")

    def test_strength_not_checked_when_body_unconverged(self):
        st = stages_pass(self.c)
        st["structural"]["body_converged"] = False
        st["structural"]["governing_converged"] = False
        r = [x for x in report.scorecard(self.c, st) if x["check"].startswith("Strength")][0]
        self.assertEqual(r["result"], "NOT CHECKED")

    def test_strength_fails_on_fillet_above_bulk(self):
        # DEC-15: bulk passes, the root fillet does not -> the check must FAIL
        st = stages_pass(self.c)
        ys = self.c.q("material.yield_strength", "Pa")
        sf = self.c.q("structural.safety_factor_min", "-")
        st["structural"].update(body_stress_Pa=0.5 * ys / sf, fillet_stress_Pa=1.2 * ys / sf,
                                governing_stress_Pa=1.2 * ys / sf)
        r = [x for x in report.scorecard(self.c, st) if x["check"].startswith("Strength")][0]
        self.assertEqual(r["result"], "FAIL")
        self.assertIn("root/fillet", r["this_run"])

    def test_strength_not_checked_without_fillet_value(self):
        st = stages_pass(self.c)
        for k in ("fillet_stress_Pa", "governing_stress_Pa"):
            st["structural"].pop(k)
        st["structural"]["governing_converged"] = False
        r = [x for x in report.scorecard(self.c, st) if x["check"].startswith("Strength")][0]
        self.assertEqual(r["result"], "NOT CHECKED")

    def test_strength_uses_body_not_peak(self):
        st = stages_pass(self.c)
        ys = self.c.q("material.yield_strength", "Pa")
        st["structural"]["peak_stress_Pa"] = ys * 2  # singular peak above yield must not decide
        r = [x for x in report.scorecard(self.c, st) if x["check"].startswith("Strength")][0]
        self.assertEqual(r["result"], "PASS")

    def test_strength_uses_case_material_and_sf(self):
        p = tmp_case(lambda d: d["structural"]["safety_factor_min"].update(value=4.0))
        c2 = casemod.load(p)
        rows = report.scorecard(c2, stages_pass(c2))
        r = [x for x in rows if x["check"].startswith("Strength")][0]
        self.assertEqual(r["result"], "FAIL")


def synthetic_impeller(n_sets=7) -> NeutralImpeller:
    """Simple radial-exit wheel in metres; exit plane z=0, r_te=0.2, exit height 0.015."""
    t = np.linspace(0, 1, 40)
    hub = np.column_stack([-0.12 + 0.12 * np.sin(t * math.pi / 2), 0.04 + 0.16 * (1 - np.cos(t * math.pi / 2))])
    shr = np.column_stack([-0.12 + 0.105 * np.sin(t * math.pi / 2), 0.09 + 0.11 * (1 - np.cos(t * math.pi / 2))])
    rows = []
    for _row in range(2):
        secs = []
        for k in range(5):
            f = k / 4
            m = hub * (1 - f) + shr * f
            th = np.linspace(0, -0.6, len(m))
            loop = np.vstack([np.column_stack([m[:, 1] * np.cos(th + 0.01), m[:, 1] * np.sin(th + 0.01), m[:, 0]]),
                              np.column_stack([m[::-1, 1] * np.cos(th[::-1] - 0.01),
                                               m[::-1, 1] * np.sin(th[::-1] - 0.01), m[::-1, 0]])])
            secs.append(loop)
        rows.append(secs)
    return NeutralImpeller(hub=hub, shroud=shr, blades=rows, n_sets=n_sets, meta={"r_te_m": 0.2})


class Adapters(unittest.TestCase):
    def test_check_and_height(self):
        imp = synthetic_impeller()
        check(imp)
        self.assertAlmostEqual(imp.exit_blade_height(0.2), 0.015, places=6)

    def test_scale_exit_height_keeps_inlet(self):
        imp = synthetic_impeller()
        up = scale_exit_height(imp, 1.10, 0.5)
        self.assertAlmostEqual(up.exit_blade_height(0.2), 0.0165, places=6)
        self.assertTrue(np.allclose(up.shroud[0], imp.shroud[0]))  # inlet point unchanged
        self.assertTrue(np.allclose(up.blades[0][0], imp.blades[0][0], atol=1e-12))  # hub section unchanged

    def test_outlet_radius_cut_and_extend(self):
        from rerate_mcp_v2.adapters.outlet import set_outlet_radius
        imp = synthetic_impeller()
        cut = set_outlet_radius(imp, 0.21)        # beyond the curve end (0.20): extended radially
        self.assertAlmostEqual(cut.hub[-1, 1], 0.21)
        self.assertAlmostEqual(cut.shroud[-1, 1], 0.21)
        with self.assertRaises(ValueError):
            set_outlet_radius(imp, 0.19)           # inside the trailing edge: refused

    def test_bladegen_roundtrip(self):
        imp = synthetic_impeller(n_sets=9)
        d = Path(tempfile.mkdtemp())
        inf = bladegen_inf.write(imp, d, unit="mm", section_extension=0.0)
        back = read_geometry("bladegen_inf", inf, {})
        self.assertEqual(back.n_sets, 9)
        self.assertEqual(len(back.blades), 2)
        self.assertAlmostEqual(back.exit_blade_height(0.2), 0.015, places=5)
        shutil.rmtree(d)

    def test_step_adapter_explains(self):
        with self.assertRaises(Exception) as cm:
            read_geometry("step", Path("x.stp"), {})
        self.assertIn("not implemented", str(cm.exception))

    def test_nasa_adapter_requires_options(self):
        with self.assertRaises(Exception) as cm:
            read_geometry("nasa_tables", Path("."), {"units": "in"})
        self.assertIn("adapter_options", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
