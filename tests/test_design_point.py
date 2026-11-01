"""Unit tests: design operating point (target flow conversion, choke verdict, speedline interpolation)."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "ansys-mcp" / "src"))

from rerate_mcp_v2 import design_point as dp  # noqa: E402


class DesignPoint(unittest.TestCase):
    def test_target_flow_inverts_corrected_flow(self):
        m = dp.target_passage_mass_flow(5.0, 10, 80000.0, 300.0, 101325.0, 288.15)
        corrected = m * 10 * math.sqrt(300.0 / 288.15) / (80000.0 / 101325.0)
        self.assertAlmostEqual(corrected, 5.0, places=9)

    def test_reached(self):
        h = [{"iters": 50 * i, "mdot_in": 0.2601, "p_out_pa": 2.3e5} for i in range(1, 8)]
        self.assertEqual(dp.choke_verdict(h, 0.26, 0.005, 300)["state"], "reached")

    def test_choked_at_lower_bound(self):
        h = [{"iters": 50 * i, "mdot_in": 0.250, "p_out_pa": 4e4, "at_lower_bound": True} for i in range(1, 8)]
        v = dp.choke_verdict(h, 0.26, 0.005, 300)
        self.assertEqual(v["state"], "choked")
        self.assertAlmostEqual(v["max_flow_kg_s"], 0.25)

    def test_still_moving_is_not_choke(self):
        h = [{"iters": 50 * i, "mdot_in": 0.24 + 0.002 * i, "p_out_pa": 2.3e5 - 1e3 * i} for i in range(1, 8)]
        self.assertEqual(dp.choke_verdict(h, 0.26, 0.005, 300)["state"], "not_settled")

    def test_interpolation_and_no_extrapolation(self):
        pts = [{"mdot": 0.24, "PR": 5.4, "eta": 0.94, "p_out_pa": 2.4e5},
               {"mdot": 0.28, "PR": 4.6, "eta": 0.90, "p_out_pa": 1.8e5}]
        r = dp.interpolate_at_flow(pts, 0.26)
        self.assertEqual(r["status"], "ok")
        self.assertAlmostEqual(r["PR"], 5.0)
        self.assertEqual(dp.interpolate_at_flow(pts, 0.30)["status"], "out_of_range")


if __name__ == "__main__":
    unittest.main()
