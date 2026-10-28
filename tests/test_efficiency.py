"""Unit tests: efficiency definitions (constant gamma vs gas-table cp(T))."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "ansys-mcp" / "src"))

from rerate_mcp_v2 import fluent_setup as fs  # noqa: E402


class Efficiency(unittest.TestCase):
    def test_constant_cp_gas_table_equals_perfect_gas(self):
        cp, r = 1004.5, 287.0
        g = cp / (cp - r)
        pr, tr = 4.0, 1.6
        self.assertAlmostEqual(fs.eta_tt_gas_table(pr, 300.0, 300.0 * tr, [cp], r), fs.eta_tt(pr, tr, g), places=6)

    def test_isentropic_is_one(self):
        cp, r = 1004.5, 287.0
        g = cp / (cp - r)
        t2 = 300.0 * 3.0 ** ((g - 1) / g)
        self.assertAlmostEqual(fs.eta_tt_gas_table(3.0, 300.0, t2, [cp], r), 1.0, places=6)

    def test_rising_cp_lowers_eta_vs_gamma_14(self):
        poly = [1030.42, -0.232525, 0.000530303, -1.41414e-07]
        self.assertLess(fs.eta_tt_gas_table(5.0, 288.15, 470.0, poly, 287.05), fs.eta_tt(5.0, 470.0 / 288.15))

    def test_nan_on_no_work(self):
        self.assertTrue(math.isnan(fs.eta_tt_gas_table(1.0, 300.0, 300.0, [1004.5], 287.0)))


if __name__ == "__main__":
    unittest.main()
