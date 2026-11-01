"""Unit tests: CFD convergence rule (mass imbalance + stability window)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "ansys-mcp" / "src"))

from rerate_mcp_v2.servers.fluent_server import converged  # noqa: E402


def hist(points):
    return [{"iters": i, "mdot_in": m, "PR": p, "eta": e, "imbalance": b} for i, m, p, e, b in points]


class Convergence(unittest.TestCase):
    def test_converged_when_stable_and_balanced(self):
        h = hist([(100, 0.20, 4.0, 0.80, 0.01), (400, 0.2000, 4.000, 0.800, 0.004),
                  (700, 0.2005, 4.010, 0.801, 0.003)])
        ok, info = converged(h, 0.005, 0.005, 300)
        self.assertTrue(ok)
        self.assertEqual(info["window_from_iter"], 400)

    def test_not_converged_if_imbalance_high(self):
        h = hist([(400, 0.2, 4.0, 0.8, 0.004), (700, 0.2, 4.0, 0.8, 0.02)])
        self.assertFalse(converged(h, 0.005, 0.005, 300)[0])

    def test_not_converged_if_drifting(self):
        h = hist([(400, 0.2, 4.0, 0.8, 0.001), (700, 0.2, 4.1, 0.8, 0.001)])  # PR +2.5 %
        self.assertFalse(converged(h, 0.005, 0.005, 300)[0])

    def test_not_converged_before_window(self):
        h = hist([(100, 0.2, 4.0, 0.8, 0.001), (200, 0.2, 4.0, 0.8, 0.001)])
        ok, info = converged(h, 0.005, 0.005, 300)
        self.assertFalse(ok)
        self.assertIn("window", info["reason"])

    def test_not_converged_on_one_lucky_imbalance_sample(self):
        # C16: imbalance fell under the limit only at the last sample
        h = hist([(800, 0.142, 4.957, 0.627, 0.019), (900, 0.143, 4.960, 0.628, 0.016),
                  (1000, 0.144, 4.968, 0.627, 0.011), (1100, 0.142, 4.958, 0.628, 0.004)])
        self.assertFalse(converged(h, 0.005, 0.005, 300)[0])

    def test_not_converged_if_oscillating_back_to_start(self):
        # C16: PR oscillates 4.32 <-> 4.75; end points nearly equal
        h = hist([(1350, 0.156, 4.32, 0.565, 0.001), (1450, 0.156, 4.75, 0.603, 0.001),
                  (1550, 0.156, 4.32, 0.564, 0.001), (1650, 0.156, 4.33, 0.565, 0.001)])
        self.assertFalse(converged(h, 0.005, 0.005, 300)[0])

    def test_not_converged_with_nan(self):
        h = hist([(400, 0.0, 0.0, float("nan"), 0.001), (700, 0.0, 0.0, float("nan"), 0.001)])
        self.assertFalse(converged(h, 0.005, 0.005, 300)[0])


if __name__ == "__main__":
    unittest.main()
