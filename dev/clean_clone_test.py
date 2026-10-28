"""Clean-clone install test: clone this repository into a NEW folder and install it into a NEW install home using
only the documented installer steps (venv, packages, config; no Hermes profile is touched), then run the unit
tests, the layout scan and the health check groups that do not need a Hermes profile, from the clone.

  python dev/clean_clone_test.py --dest <new empty folder> [--license student] [--python <py3.13 exe>]

The install home is <dest>_home next to the clone (passed with --home), so the user's real install home is not changed.
Prints a JSON summary. Not used by either agent.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd, timeout=1800):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return {"cmd": " ".join(map(str, cmd)), "rc": r.returncode, "tail": (r.stdout + r.stderr)[-1500:]}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dest", required=True)
    p.add_argument("--license", default="commercial", choices=["commercial", "student"])
    p.add_argument("--python", default="")
    a = p.parse_args()
    dest = Path(a.dest)
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"{dest} is not empty")
    steps = [run(["git", "clone", "--quiet", str(ROOT), str(dest)], cwd=ROOT.parent)]
    home = dest.parent / (dest.name + "_home")  # outside the clone, so the layout scan does not see the venv
    inst = [a.python or sys.executable, "setup/install_runtime.py"]
    venv = inst + ["venv", "--home", str(home)] + (["--python", a.python] if a.python else [])
    steps.append(run(venv, cwd=dest, timeout=900))
    py = str(home / "venv" / "Scripts" / "python.exe")
    steps.append(run([py, "setup/install_runtime.py", "packages", "--home", str(home)], cwd=dest, timeout=3600))
    steps.append(run([py, "setup/install_runtime.py", "config", "--home", str(home), "--license", a.license],
                     cwd=dest))
    steps.append(run([py, "-m", "unittest", "discover", "-s", "tests"], cwd=dest))
    steps.append(run([py, "setup/verify_layout.py"], cwd=dest))
    for grp in ("system", "ansys", "python"):
        steps.append(run([py, "setup/check.py", "--home", str(home), "--only", grp], cwd=dest, timeout=600))
    tracked = subprocess.run(["git", "ls-files"], cwd=dest, capture_output=True, text=True).stdout.split()
    leaked = [f for f in tracked if f.startswith(("runs/", "work/", ".venv")) or f.endswith((".trn", ".xml"))]
    print(json.dumps({"dest": str(dest), "ok": all(s["rc"] == 0 for s in steps) and not leaked,
                      "leaked_files": leaked, "steps": steps}, indent=1))


if __name__ == "__main__":
    main()
