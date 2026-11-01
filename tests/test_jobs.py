"""Unit tests: desktop-session parsing, background Job state machine, config upgrade merge (no Ansys needed)."""
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "ansys-mcp" / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "setup"))

from rerate_mcp_v2.servers.jobs import Job, parse_session_state  # noqa: E402
from upgrade_config import merge_missing  # noqa: E402

ACTIVE = (" SESSIONNAME   USERNAME   ID  STATE   TYPE  DEVICE\n services                 0  Disc\n"
          ">rdp-tcp#0     someone    1  Active\n console                  2  Conn\n")
DISC = (" SESSIONNAME   USERNAME   ID  STATE   TYPE  DEVICE\n services                 0  Disc\n"
        ">              someone    1  Disc\n console                  2  Conn\n")


class Session(unittest.TestCase):
    def test_active(self):
        self.assertEqual(parse_session_state(ACTIVE, 1), "Active")

    def test_disconnected_without_session_name(self):
        self.assertEqual(parse_session_state(DISC, 1), "Disc")

    def test_unknown(self):
        self.assertIsNone(parse_session_state(ACTIVE, 7))


class Jobs(unittest.TestCase):
    def wait(self, j, s=3):
        t = time.time()
        while j.status()["state"] == "running" and time.time() - t < s:
            time.sleep(0.05)
        return j.status()

    def test_finished(self):
        j = Job("t")
        self.assertEqual(j.start(lambda job: {"x": 1}, 5)["state"], "running")
        st = self.wait(j)
        self.assertEqual(st["state"], "finished")
        self.assertEqual(st["result"], {"x": 1})

    def test_error_reported(self):
        j = Job("t")

        def boom(job):
            raise RuntimeError("app said no")
        j.start(boom, 5)
        st = self.wait(j)
        self.assertEqual(st["state"], "error")
        self.assertIn("app said no", st["error"])

    def test_timeout_never_waits_silently(self):
        j = Job("t")
        j.start(lambda job: (time.sleep(2), {})[1], 0.2)
        time.sleep(0.4)
        st = j.status()
        self.assertEqual(st["state"], "timeout")
        self.assertIn("no result within", st["error"])

    def test_single_job_at_a_time(self):
        j = Job("t")
        j.start(lambda job: (time.sleep(0.5), {})[1], 5)
        self.assertEqual(j.start(lambda job: {}, 5)["status"], "error")


class ConfigUpgrade(unittest.TestCase):
    def test_adds_missing_keeps_values_skips_placeholders(self):
        dst = {"fluent": {"processors": 8}, "apps": {"fluent": {"mode": "headless"}}}
        src = {"fluent": {"processors": "<FLUENT_PROCESSORS>", "gpu": False},
               "apps": {"fluent": {"mode": "gui", "launch_timeout_s": 300}}, "ansys": {"root": "<ANSYS_ROOT>"}}
        added = merge_missing(dst, src)
        self.assertEqual(dst["fluent"]["processors"], 8)
        self.assertEqual(dst["apps"]["fluent"]["mode"], "headless")
        self.assertEqual(dst["apps"]["fluent"]["launch_timeout_s"], 300)
        self.assertIn("fluent.gpu", added)
        self.assertNotIn("root", dst.get("ansys", {}))


if __name__ == "__main__":
    unittest.main()
