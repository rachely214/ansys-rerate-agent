"""Unit tests: machine config lookup, config-relative paths, AWP_ROOT startup hook, case path fallback."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "ansys-mcp" / "src"))

import rerate_mcp_v2  # noqa: E402
from rerate_mcp_v2 import case as casemod  # noqa: E402
from rerate_mcp_v2 import config  # noqa: E402

CFG = """ansys: {version: 261, root: ansys_here}
license: {mode: student}
paths: {runs_dir: runs, work_dir: work, example_data: example-data}
"""


class ConfigLookup(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.cfg = self.d / "machine.config.yaml"
        self.cfg.write_text(CFG, encoding="utf-8")

    def test_runtime_is_the_imported_package(self):
        self.assertTrue(Path(rerate_mcp_v2.__file__).resolve().is_relative_to((ROOT / "plugins" / "ansys-mcp" / "src").resolve()))

    def test_env_order(self):
        with mock.patch.dict(os.environ, {"RERATE_CONFIG": str(self.cfg), "RERATE_V2_CONFIG": "elsewhere.yaml"}):
            self.assertEqual(config.config_path(), self.cfg)
        with mock.patch.dict(os.environ, {"RERATE_CONFIG": "", "RERATE_V2_CONFIG": str(self.cfg)}):
            self.assertEqual(config.config_path(), self.cfg)

    def test_default_location(self):
        env = {"RERATE_CONFIG": "", "RERATE_V2_CONFIG": "", "LOCALAPPDATA": str(self.d)}
        with mock.patch.dict(os.environ, env):
            p = config.config_path()
        self.assertEqual(p.name, "machine.config.yaml")
        self.assertIn("ansys-rerate-agent", p.parent.name)
        if os.name == "nt":
            self.assertEqual(p, self.d / "ansys-rerate-agent" / "machine.config.yaml")

    def test_relative_paths_resolve_against_config_dir(self):
        with mock.patch.dict(os.environ, {"RERATE_CONFIG": str(self.cfg)}):
            self.assertEqual(config.runs_root().resolve(), (self.d / "runs").resolve())
            self.assertEqual(config.work_root().resolve(), (self.d / "work").resolve())
            self.assertEqual(config.example_data_root().resolve(), (self.d / "example-data").resolve())
            self.assertEqual(config.ansys_root().resolve(), (self.d / "ansys_here").resolve())

    def test_awp_root_set_only_if_missing(self):
        with mock.patch.dict(os.environ, {"RERATE_CONFIG": str(self.cfg), "AWP_ROOT261": ""}):
            self.assertEqual(config.ensure_awp_root(), "AWP_ROOT261")
            self.assertEqual(Path(os.environ["AWP_ROOT261"]).resolve(), (self.d / "ansys_here").resolve())
        with mock.patch.dict(os.environ, {"RERATE_CONFIG": str(self.cfg), "AWP_ROOT261": "keep"}):
            config.ensure_awp_root()
            self.assertEqual(os.environ["AWP_ROOT261"], "keep")

    def test_missing_config_is_reported(self):
        with mock.patch.dict(os.environ, {"RERATE_CONFIG": str(self.d / "nope.yaml")}):
            with self.assertRaises(config.ConfigError):
                config.load_config()
            self.assertIsNone(config.ensure_awp_root())


class CasePathFallback(unittest.TestCase):
    def test_case_folder_then_example_data(self):
        d = Path(tempfile.mkdtemp())
        case_dir = d / "repo" / "01_demo"
        case_dir.mkdir(parents=True)
        case_file = case_dir / "case.yaml"
        case_file.write_text("case: {name: x}\n", encoding="utf-8")
        data = d / "example-data"
        (data / "01_demo" / "geometry_data").mkdir(parents=True)
        got = casemod.resolve_relative("geometry_data", case_file, example_data=data)
        self.assertEqual(got, (data / "01_demo" / "geometry_data").resolve())
        (case_dir / "geometry_data").mkdir()
        got = casemod.resolve_relative("geometry_data", case_file, example_data=data)
        self.assertEqual(got, (case_dir / "geometry_data").resolve())

    def test_missing_everywhere_points_at_case_folder(self):
        d = Path(tempfile.mkdtemp())
        case_file = d / "case.yaml"
        got = casemod.resolve_relative("nothing_here", case_file, example_data=d / "none")
        self.assertEqual(got, (d / "nothing_here").resolve())

    def test_example_case_material_resolves_next_to_case(self):
        ex = ROOT / "examples" / "01_nasa_hecc" / "case.yaml"
        c = casemod.load(ex)
        self.assertTrue(c.resolve_path("material.library_file").exists())


if __name__ == "__main__":
    unittest.main()
