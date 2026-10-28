"""Unit tests: centrifugal hand calculation and the public material XML writer."""
import math
import sys
import unittest
import xml.dom.minidom
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "src"))

from rerate_mcp_v2 import handcalc, materials, units  # noqa: E402


class HandCalc(unittest.TestCase):
    def test_blade_pull_formula(self):
        # rho*w^2*(rt^2-rr^2)/2 with simple numbers
        self.assertAlmostEqual(handcalc.blade_pull_stress(1000.0, 100.0, 0.0, 1.0), 1000 * 1e4 * 0.5)

    def test_zero_length_rejected(self):
        with self.assertRaises(ValueError):
            handcalc.blade_pull_stress(1000.0, 100.0, 1.0, 1.0)

    def test_check_dict_and_tip_speed(self):
        d = handcalc.centrifugal_check(4430.0, 60.0 / (2 * math.pi) * 100.0, 0.0, 0.5)
        self.assertAlmostEqual(d["omega_rad_s"], 100.0)
        self.assertAlmostEqual(d["tip_speed_m_s"], 50.0)
        self.assertAlmostEqual(d["ring_hoop_tip_Pa"], 4430.0 * 50.0 ** 2)

    def test_order_of_magnitude(self):
        self.assertTrue(handcalc.within_order_of_magnitude(3e8, 1e8))
        self.assertFalse(handcalc.within_order_of_magnitude(3e9, 1e8))


class MaterialXml(unittest.TestCase):
    def test_public_ti64_converts_and_matches_case_yield(self):
        src = ROOT / "examples" / "01_nasa_hecc" / "materials" / "ti6al4v_public.yaml"
        out = Path(ROOT / "work" / "test_materials")
        xml_path, props = materials.ensure_xml(src, out)
        xml.dom.minidom.parse(str(xml_path))
        self.assertIn("Ti-6Al-4V", xml_path.read_text())
        self.assertAlmostEqual(props["tensile_yield_pa"] / units.convert(120, "ksi", "Pa"), 1.0, places=5)

    def test_missing_property_rejected(self):
        p = Path(ROOT / "work" / "test_materials" / "bad.yaml")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("name: X\ndensity_kg_m3: 1\n")
        with self.assertRaises(ValueError):
            materials.load(p)


if __name__ == "__main__":
    unittest.main()
