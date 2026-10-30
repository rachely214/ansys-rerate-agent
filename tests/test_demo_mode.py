"""Demo mode limits (pure helpers, no Ansys)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime" / "src"))
from rerate_mcp_v2 import demo_mode  # noqa: E402

ON = {"enabled": True, "solve_cap_s": 2700.0, "total_budget_s": 5400.0, "allow_speedline": False}
OFF = {"enabled": False, "solve_cap_s": 2700.0, "total_budget_s": 5400.0, "allow_speedline": True}


def pt(t_s):
    return {"history_last": [{"t_s": t_s}]}


class DemoMode(unittest.TestCase):
    def test_off_keeps_request(self):
        self.assertEqual(demo_mode.plan_solve(7200, {}, OFF), (7200.0, None))

    def test_cap_per_solve(self):
        self.assertEqual(demo_mode.plan_solve(7200, {}, ON), (2700.0, None))

    def test_budget_left_limits(self):
        st = {"cfd_diagnostic": {"points": [pt(2000), pt(2400)]}}
        lim, why = demo_mode.plan_solve(7200, st, ON)
        self.assertIsNone(why)
        self.assertEqual(lim, 1000.0)

    def test_budget_used_refuses(self):
        st = {"cfd_diagnostic": {"points": [pt(2700)]}, "cfd": pt(2700)}
        lim, why = demo_mode.plan_solve(600, st, ON)
        self.assertIsNone(lim)
        self.assertIn("NOT CHECKED", why)

    def test_settings_from_config(self):
        cfg = {"demo_mode": {"enabled": True, "cfd_solve_cap_s": 100, "cfd_total_budget_s": 200,
                             "allow_speedline": False}}
        d = demo_mode.settings(cfg)
        self.assertTrue(d["enabled"])
        self.assertEqual(d["solve_cap_s"], 100.0)
        self.assertFalse(d["allow_speedline"])

    def test_settings_missing_section_is_off(self):
        self.assertFalse(demo_mode.settings({})["enabled"])


if __name__ == "__main__":
    unittest.main()
