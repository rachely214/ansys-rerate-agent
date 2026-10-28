"""Installer steps for the Ansys re-rate agent. No AI involved. Each step is safe to run again.

  python setup/install_runtime.py STEP [options]

Steps (run in this order; `all` runs venv, packages, config, profile):
  venv          --python PATH            create <home>/venv with Python 3.12 or 3.13 (refuses 3.14 and newer)
  packages      [--proxy URL]            install the locked packages, then the runtime (a normal, non-editable copy)
  config        [--license student|commercial] [--processors N] [--ansys-root PATH] [--force]
                                          write <home>/machine.config.yaml (kept if present; new keys are added)
  example-data  [--zip PATH] [--from-dir DIR]
                                          NASA example geometry into <home>/example-data (about 5 GB download, resumable)
  profile       [--name ansys-rerate-agent] [--model-from-profile default]
                                          install the demo agent as a Hermes profile and connect its 6 tool servers
  all           [--with-example-data] plus any option above

<home> is --home, else the ANSYS_RERATE_HOME variable, else %LOCALAPPDATA%/ansys-rerate-agent.
This script never writes passwords or API keys and never changes the default Hermes profile.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "setup"))
import check  # noqa: E402  (stdlib-only helpers shared with the health check)

SECRET_WORDS = ("api_key", "apikey", "token", "secret", "password", "authorization")
MODEL_KEYS = ("model", "providers", "custom_providers")
GOOD = ((3, 13), (3, 12))


class StepError(Exception):
    pass


def say(msg):
    print(msg, flush=True)


def sh(cmd, **kw):
    say("  running: " + " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], creationflags=check.NOWIN, **kw)


def need_yaml(home):
    """PyYAML is needed for config/profile steps. If this Python lacks it, rerun this step with the venv Python."""
    try:
        import yaml  # noqa
        return yaml
    except ImportError:
        vp = check.venv_python(home)
        if not vp.exists() or os.path.samefile(vp, sys.executable):
            raise StepError("PyYAML is missing. Run the 'venv' and 'packages' steps first.")
        say("(continuing with the install-home Python, which has PyYAML)")
        sys.exit(subprocess.call([str(vp), str(Path(__file__).resolve())] + sys.argv[1:]))


# ---------------------------------------------------------------- steps
def step_venv(a, home):
    vp = check.venv_python(home)
    if vp.exists():
        v = check.python_version(vp)
        if v in GOOD:
            say("venv: already present at %s (Python %d.%d); nothing to do" % ((vp.parent.parent,) + v))
            return
        raise StepError("A Python environment already exists at %s but uses Python %s, which the Ansys libraries "
                        "do not support. Delete that folder and run this step again." % (vp.parent.parent, v))
    py = a.python
    if not py:
        good = sorted([x for x in check.find_pythons() if x[1] in GOOD], key=lambda x: x[1], reverse=True)
        if not good:
            raise StepError("No Python 3.12 or 3.13 found on this computer. Install Python 3.13, then run: "
                            "python setup/install_runtime.py venv --python <path to python.exe>")
        py = good[0][0]
    v = check.python_version(py)
    if v is None:
        raise StepError("Could not run Python at %s." % py)
    if v >= (3, 14):
        raise StepError("Python %d.%d at %s is too new: the Ansys Python libraries support 3.12 and 3.13 only. "
                        "Install Python 3.13 and pass its path." % (v + (py,)))
    if v not in GOOD:
        raise StepError("Python %d.%d at %s is too old; Python 3.12 or 3.13 is needed." % (v + (py,)))
    home.mkdir(parents=True, exist_ok=True)
    r = sh([py, "-m", "venv", home / "venv"])
    if r.returncode != 0 or not vp.exists():
        raise StepError("Creating the Python environment failed (see the message above). If antivirus software "
                        "blocked it, allow the folder %s and try again." % home)
    say("venv: created %s with Python %d.%d" % ((home / "venv",) + v))


def step_packages(a, home):
    vp = check.venv_python(home)
    if not vp.exists():
        raise StepError("No Python environment yet. Run the 'venv' step first.")
    proxy = ["--proxy", a.proxy] if a.proxy else []
    pip = [vp, "-m", "pip", "--disable-pip-version-check"]
    sh(pip + ["install", "--upgrade", "pip"] + proxy)
    runtime = REPO / "runtime"
    jobs = [("locked packages", pip + ["install", "-r", REPO / "setup" / "requirements.lock"] + proxy),
            # non-editable copy: later edits in the repository do not change a running install by accident
            ("runtime", pip + ["install", "--no-deps", "--force-reinstall", runtime] + proxy)]
    for name, cmd in jobs:
        for attempt in (1, 2):
            if sh(cmd).returncode == 0:
                break
            if attempt == 2:
                raise StepError("Installing the %s failed twice (see the pip messages above). Common causes: no "
                                "internet, a company proxy (rerun with --proxy http://host:port), or antivirus "
                                "blocking files in %s." % (name, home))
            say("  %s install failed; trying once more" % name)
    r = subprocess.run([str(vp), "-c", "import rerate_mcp_v2, fastmcp, ansys.fluent.core; print('ok')"],
                       capture_output=True, text=True, creationflags=check.NOWIN)
    if "ok" not in r.stdout:
        raise StepError("Packages installed but do not import: %s" % (r.stderr.strip().splitlines() or ["?"])[-1])
    say("packages: locked packages and the runtime are installed in %s" % vp.parent.parent)


def render_config(home, mode, processors, ver, root):
    txt = (REPO / "setup" / "machine.config.template.yaml").read_text(encoding="utf-8")
    vals = {"<ANSYS_VERSION>": str(ver), "<ANSYS_ROOT>": json.dumps(Path(root).as_posix()),
            "<LICENSE_MODE>": mode, "<FLUENT_PROCESSORS>": str(processors)}
    for k, v in vals.items():
        txt = txt.replace(k, v)
    return txt


def step_config(a, home):
    cf = home / "machine.config.yaml"
    if cf.exists() and not a.force:
        say("config: keeping existing %s; adding any new keys from the template" % cf)
        vp = check.venv_python(home)
        py = str(vp) if vp.exists() else sys.executable
        r = subprocess.call([py, str(REPO / "setup" / "upgrade_config.py"), "--config", str(cf)])
        if r != 0:
            raise StepError("Could not update %s (see above)." % cf)
        return
    ver, root = check.pick_ansys()
    if a.ansys_root:
        root = a.ansys_root
        ver = next((p.name[1:] for p in [Path(root)] if p.name[:1].lower() == "v" and p.name[1:].isdigit()), ver)
    if not root or not ver:
        raise StepError("Ansys was not found (no AWP_ROOT variable). Pass --ansys-root with the folder that "
                        "contains Framework, fluent and TurboGrid, for example ...\\ANSYS Inc\\v261.")
    if not Path(root).exists():
        raise StepError("The Ansys folder %s does not exist." % root)
    mode = a.license or ("student" if "ansys student" in str(root).lower() else "commercial")
    procs = a.processors or max(1, min(4, os.cpu_count() or 1))
    home.mkdir(parents=True, exist_ok=True)
    if cf.exists():
        shutil.copy2(cf, cf.with_suffix(".yaml.bak"))
        say("  old config saved as %s" % cf.with_suffix(".yaml.bak"))
    cf.write_text(render_config(home, mode, procs, ver, root), encoding="utf-8")
    for d in ("runs", "work", "example-data", "logs"):
        (home / d).mkdir(exist_ok=True)
    say("config: wrote %s (Ansys v%s at %s, license %s, Fluent processors %d)" % (cf, ver, root, mode, procs))


def step_example_data(a, home):
    need_yaml(home)
    import fetch_example_data
    if fetch_example_data.fetch("01_nasa_hecc", home, a.zip, a.from_dir) != 0:
        raise StepError("Example data is still incomplete. Run this step again to resume.")
    say("example-data: ready in %s" % (home / "example-data" / "01_nasa_hecc"))


def strip_secrets(obj, path, stripped):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if any(w in str(k).lower() for w in SECRET_WORDS):
                stripped.append("%s.%s" % (path, k))
                continue
            out[k] = strip_secrets(v, "%s.%s" % (path, k), stripped)
        return out
    if isinstance(obj, list):
        return [strip_secrets(v, "%s[%d]" % (path, i), stripped) for i, v in enumerate(obj)]
    return obj


def render_servers(home):
    tmpl = (REPO / "agent" / "mcp_servers.json").read_text(encoding="utf-8")
    vp, cf = check.venv_python(home).resolve(), (home / "machine.config.yaml").resolve()
    tmpl = tmpl.replace("@@RERATE_PYTHON@@", json.dumps(str(vp))[1:-1]).replace(
        "@@RERATE_CONFIG@@", json.dumps(str(cf))[1:-1])
    if "@@" in tmpl:
        raise StepError("agent/mcp_servers.json has an unknown @@TOKEN@@; the repository copy looks broken.")
    servers = json.loads(tmpl)
    for e in servers.values():
        e.setdefault("enabled", True)
    return servers


def step_profile(a, home):
    yaml = need_yaml(home)
    h = check.hermes_exe()
    if not h:
        raise StepError("The hermes command was not found. Install Hermes Agent first, then open a new terminal.")
    if a.name == "default":
        raise StepError("Refusing to install over the default Hermes profile. Use another --name.")
    for need in (check.venv_python(home), home / "machine.config.yaml"):
        if not need.exists():
            raise StepError("%s is missing. Run the 'venv', 'packages' and 'config' steps first." % need)
    servers = render_servers(home)
    exists = check.profile_exists(a.name)
    old = {}
    if exists:
        p = check.profile_config_path(a.name)
        if p and p.exists():
            old = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            shutil.copy2(p, p.with_suffix(".yaml.bak"))
            say("  existing profile config saved as %s" % p.with_suffix(".yaml.bak"))
    cmd = [h, "profile", "install", REPO / "agent", "-y", "--name", a.name] + (["--force"] if exists else [])
    r = sh(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise StepError("hermes profile install failed: %s" % ((r.stderr or r.stdout).strip()[-400:]))
    say("  profile '%s' %s from %s" % (a.name, "reinstalled" if exists else "installed", REPO / "agent"))
    p = check.profile_config_path(a.name)
    if not p:
        raise StepError("Could not find the config file of profile '%s'." % a.name)
    data = (yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}) or {}
    for k, v in old.items():  # a reinstall resets config.yaml; keep the user's own settings
        if k not in data or k in MODEL_KEYS:
            data[k] = v
    model = data.get("model") or {}
    model_set = bool(model.get("default") and model.get("provider")) if isinstance(model, dict) else bool(model)
    stripped, copied = [], []
    if not model_set and a.model_from_profile:
        sp = check.profile_config_path(a.model_from_profile)
        src = (yaml.safe_load(sp.read_text(encoding="utf-8")) or {}) if sp and sp.exists() else {}
        for k in MODEL_KEYS:
            if k in src:
                data[k] = strip_secrets(src[k], k, stripped)
                copied.append(k)
        say("  copied model settings (%s) from profile '%s', without keys or passwords"
            % (", ".join(copied) or "none found", a.model_from_profile))
    mcp = data.get("mcp_servers") or {}
    mcp.update(servers)
    data["mcp_servers"] = mcp
    if p.exists():
        shutil.copy2(p, p.with_suffix(".yaml.bak"))
    p.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    say("  connected %d tool servers in %s" % (len(servers), p))
    gp = check.profile_config_path("default")
    st, detail = check.key_status(data, p.parent, gp.parent if gp else None)
    prov = (data.get("model") or {}).get("provider") if isinstance(data.get("model"), dict) else None
    say("profile: done. Model key: " + detail + ".")
    if st == "no" or (st == "unknown" and prov):
        say("WHAT YOU STILL NEED TO DO: give profile '%s' its model key. In a terminal run:\n"
            "    hermes -p %s auth add %s\n"
            "and paste the key when it asks (it is stored privately by Hermes, never in this repository)."
            % (a.name, a.name, prov or "<provider>"))
    elif not prov:
        say("WHAT YOU STILL NEED TO DO: choose a model: hermes -p %s model" % a.name)
    say("Then close Hermes completely and open it again, and start a NEW chat with profile '%s'." % a.name)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["venv", "packages", "config", "example-data", "profile", "all"])
    ap.add_argument("--home")
    ap.add_argument("--python")
    ap.add_argument("--proxy")
    ap.add_argument("--license", choices=["student", "commercial"])
    ap.add_argument("--processors", type=int)
    ap.add_argument("--ansys-root")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--zip")
    ap.add_argument("--from-dir")
    ap.add_argument("--name", default="ansys-rerate-agent")
    ap.add_argument("--model-from-profile", default="default")
    ap.add_argument("--with-example-data", action="store_true")
    a = ap.parse_args()
    home = check.install_home(a.home).resolve()
    say("install home: %s" % home)
    steps = {"venv": step_venv, "packages": step_packages, "config": step_config,
             "example-data": step_example_data, "profile": step_profile}
    order = (["venv", "packages", "config"] + (["example-data"] if a.with_example_data else []) + ["profile"]
             if a.step == "all" else [a.step])
    for s in order:
        say("== %s" % s)
        try:
            if s in ("example-data", "profile") and a.step == "all":
                # these need PyYAML: run them with the venv Python that the earlier steps just set up
                r = subprocess.call([str(check.venv_python(home)), str(Path(__file__).resolve()), s]
                                    + [x for x in sys.argv[2:] if x != "--with-example-data"])
                if r != 0:
                    return r
                continue
            steps[s](a, home)
        except StepError as e:
            say("FAILED (%s): %s" % (s, e))
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
