"""Health check for the Ansys re-rate agent on this computer. No AI involved; read-only (it never changes anything).

  python setup/check.py [--json] [--only GROUP] [--home DIR] [--profile NAME]

Groups: system, ansys, python, config, hermes, mcp. Prints one line per item:
  [PASS] / [FAIL] / [WARN] / [SKIP] item: detail      (FAIL lines add "  -> Fix: ...")
and ends with ALL GREEN or NOT READY: N problems. Exit code 0 only when nothing FAILed.
The system, ansys and python groups use the Python standard library only (any Python 3.8 or newer).
Later groups run small helpers with the install-home venv Python. It never launches Ansys applications.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GROUPS = ["system", "ansys", "python", "config", "hermes", "mcp"]
SERVERS = ["case_v2", "vista_v2", "geometry_v2", "turbogrid_v2", "fluent_v2", "mechanical_v2"]
MODULES = {s: "rerate_mcp_v2.servers.%s_server" % s[:-3] for s in SERVERS}
SKILLS = ["rerate-run", "rerate-intake", "rerate-sizing", "rerate-geometry", "rerate-meshing", "rerate-cfd",
          "rerate-structural", "rerate-report"]
BAD_TOOLS = {"run_code", "run_python", "run_script", "exec"}
PRODUCTS = {  # check id -> (plain name, path under the Ansys version root); same paths the runtime uses
    "vista_workbench": ("Workbench (runs Vista CCD)", "Framework/bin/Win64/RunWB2.exe"),
    "discovery": ("Discovery", "Discovery/Discovery.exe"),
    "turbogrid": ("TurboGrid", "TurboGrid/bin/cfxtg.exe"),
    "fluent": ("Fluent", "fluent/ntbin/win64/fluent.exe"),
    "mechanical": ("Mechanical", "aisol/bin/winx64/AnsysWBU.exe"),
}
TESTED_VERSION = "261"
NOWIN = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW: never flash console windows
# Same filter Hermes applies to stdio MCP servers: only these variables reach the server (plus its own env).
SAFE_ENV = {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM", "SHELL", "TMPDIR"}
SAFE_ENV_CI = {"ALLUSERSPROFILE", "APPDATA", "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)", "COMMONPROGRAMW6432",
               "COMPUTERNAME", "COMSPEC", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "NUMBER_OF_PROCESSORS", "OS",
               "PATHEXT", "PROCESSOR_ARCHITECTURE", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
               "PROGRAMW6432", "PUBLIC", "SYSTEMDRIVE", "SYSTEMROOT", "TEMP", "TMP", "USERDOMAIN", "USERNAME",
               "USERPROFILE", "WINDIR"}

RESULTS = []


def add(cid, group, status, detail, fix=None):
    RESULTS.append({"id": cid, "group": group, "status": status, "detail": detail,
                    "fix": fix if status == "FAIL" else None})


def run(cmd, timeout=60, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=NOWIN,
                          encoding="utf-8", errors="replace", **kw)


# ---------------------------------------------------------------- shared helpers (install_runtime.py imports these)
def install_home(arg=None):
    if arg:
        return Path(arg).expanduser()
    if os.environ.get("ANSYS_RERATE_HOME"):
        return Path(os.environ["ANSYS_RERATE_HOME"]).expanduser()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "ansys-rerate-agent"
    return Path.home() / ".ansys-rerate-agent"


def venv_python(home):
    return Path(home) / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def python_version(exe):
    """(major, minor) of an interpreter, or None if it does not run."""
    try:
        r = run([str(exe), "-c", "import sys; print('%d %d' % sys.version_info[:2])"], timeout=30)
        a, b = r.stdout.split()
        return int(a), int(b)
    except Exception:
        return None


def find_pythons():
    """All interpreters found: list of (path, (major, minor)), deduplicated, in a sensible preference order."""
    cands = []
    if shutil.which("py"):
        for v in ("3.13", "3.12"):
            try:
                r = run(["py", "-" + v, "-c", "import sys; print(sys.executable)"], timeout=30)
                if r.returncode == 0 and r.stdout.strip():
                    cands.append(r.stdout.strip().splitlines()[-1])
            except Exception:
                pass
    if os.name == "nt":
        roots = [os.environ.get("LOCALAPPDATA", "") + "/Programs/Python", os.environ.get("PROGRAMFILES", "")]
        for r in roots:
            for v in ("313", "312", "314", "315"):
                cands.append(str(Path(r) / ("Python" + v) / "python.exe"))
    else:
        for v in ("3.13", "3.12"):
            cands += ["/usr/bin/python" + v, "/usr/local/bin/python" + v, "/opt/homebrew/bin/python" + v]
    for n in ("python3.13", "python3.12", "python3", "python"):
        w = shutil.which(n)
        if w and "WindowsApps" not in w:  # the Microsoft Store stub opens the Store instead of running
            cands.append(w)
    seen, out = set(), []
    for c in cands:
        if not c or not Path(c).is_file():
            continue
        key = os.path.normcase(str(Path(c).resolve()))
        if key in seen:
            continue
        seen.add(key)
        v = python_version(c)
        if v:
            out.append((str(Path(c).resolve()), v))
    return out


def ansys_installs():
    """{version: root} from AWP_ROOT<ver> variables, plus standard install folders as a fallback."""
    found = {}
    for k, v in os.environ.items():
        m = re.fullmatch(r"AWP_ROOT(\d{3})", k.upper())
        if m and v:
            found[m.group(1)] = v
    if os.name == "nt":
        base = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "ANSYS Inc"
        for d in list(base.glob("v2[0-9][0-9]")) + list(base.glob("ANSYS Student/v2[0-9][0-9]")):
            found.setdefault(d.name[1:], str(d))
    return found


def pick_ansys():
    inst = ansys_installs()
    if TESTED_VERSION in inst:
        return TESTED_VERSION, inst[TESTED_VERSION]
    if inst:
        v = sorted(inst)[-1]
        return v, inst[v]
    return None, None


def run_json(py, code, timeout=120, env=None):
    """Run a small Python snippet with interpreter `py`; it must print one JSON value on its last line."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp = f.name
    try:
        r = run([str(py), tmp], timeout=timeout, env=env)
        lines = [x for x in r.stdout.splitlines() if x.strip()]
        if r.returncode != 0 or not lines:
            raise RuntimeError((r.stderr.strip().splitlines() or ["no output"])[-1][:300])
        return json.loads(lines[-1])
    finally:
        os.unlink(tmp)


def load_yaml(path, home):
    """Parse a YAML file with PyYAML from this Python, or else from the install-home venv."""
    try:
        import yaml  # noqa
        return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except ImportError:
        pass
    vp = venv_python(home)
    if not vp.exists():
        raise RuntimeError("cannot read YAML yet: the install-home Python environment (venv) does not exist")
    code = "import json,sys,yaml\nprint(json.dumps(yaml.safe_load(open(%r, encoding='utf-8')) or {}, default=str))" % str(path)
    return run_json(vp, code)


def hermes_exe():
    return shutil.which("hermes")


def profile_config_path(name):
    h = hermes_exe()
    if not h:
        return None
    r = run([h, "-p", name, "config", "path"], timeout=60)
    lines = [x.strip() for x in r.stdout.splitlines() if x.strip()]
    return Path(lines[-1]) if r.returncode == 0 and lines else None


def profile_exists(name):
    h = hermes_exe()
    return bool(h) and run([h, "profile", "show", name], timeout=60).returncode == 0


SECRET_WORDS = ("api_key", "apikey", "token", "secret", "password", "authorization")


def _set(v):
    return isinstance(v, str) and v.strip() != "" and not v.strip().startswith("<")


def _dotenv_has(path, name):
    try:
        for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == name and v.strip().strip("'\""):
                return True
    except OSError:
        pass
    return False


def _pool_has(auth_path, provider):
    try:
        pool = json.loads(Path(auth_path).read_text(encoding="utf-8")).get("credential_pool") or {}
        return bool(pool.get(provider)) or bool((json.loads(Path(auth_path).read_text(encoding="utf-8"))
                                                  .get("providers") or {}).get(provider))
    except Exception:
        return False


KNOWN_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "openrouter": "OPENROUTER_API_KEY",
             "gemini": "GEMINI_API_KEY", "google": "GOOGLE_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
             "xai": "XAI_API_KEY", "mistral": "MISTRAL_API_KEY", "groq": "GROQ_API_KEY"}


def key_status(cfg, profile_dir, global_dir):
    """('yes'|'none-needed'|'no'|'unknown', plain detail). Only checks presence; never reads values out."""
    model = cfg.get("model") or {}
    if not isinstance(model, dict):
        model = {"default": model}
    prov = str(model.get("provider") or "")
    base = str(model.get("base_url") or "")
    if prov.startswith("custom:"):
        for cp in cfg.get("custom_providers") or []:
            if isinstance(cp, dict) and str(cp.get("name", "")).lower() == prov[7:].lower():
                base = base or str(cp.get("base_url") or "")
                if _set(cp.get("api_key")):
                    return "yes", "a key for provider '%s' is stored in the profile config (not shown)" % prov
                if cp.get("key_env") and _dotenv_has(Path(profile_dir) / ".env", cp["key_env"]):
                    return "yes", "key variable %s is set in the profile .env (not shown)" % cp["key_env"]
    if re.search(r"//(localhost|127\.0\.0\.1|\[::1\])[:/]", base) or prov in ("ollama", "lmstudio", "local"):
        return "none-needed", "provider '%s' runs on this computer and needs no key" % prov
    if _set(model.get("api_key")):
        return "yes", "a key is stored in the profile config (not shown)"
    kenv = model.get("key_env") or model.get("api_key_env") or KNOWN_ENV.get(prov)
    if kenv and _dotenv_has(Path(profile_dir) / ".env", kenv):
        return "yes", "key variable %s is set in the profile .env (not shown)" % kenv
    if _pool_has(Path(profile_dir) / "auth.json", prov):
        return "yes", "the profile's credential store has an entry for '%s' (not shown)" % prov
    if global_dir and _pool_has(Path(global_dir) / "auth.json", prov):
        return "yes", ("no key in the profile itself; Hermes falls back to the main Hermes credential store, "
                       "which has an entry for '%s' (not shown)" % prov)
    if kenv and global_dir and _dotenv_has(Path(global_dir) / ".env", kenv):
        return "unknown", "%s is set only in the main Hermes .env, not in this profile" % kenv
    if prov:
        return "no", "no key found for provider '%s' in the profile .env, its config or a credential store" % prov
    return "unknown", "no provider is set, so the key cannot be checked"


# ---------------------------------------------------------------- system
def memory_gb():
    if os.name == "nt":
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + \
                       [(n, ctypes.c_ulonglong) for n in ("total", "avail", "tpf", "apf", "tv", "av", "ave")]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.total / 1024 ** 3
    if Path("/proc/meminfo").exists():
        kb = int(re.search(r"MemTotal:\s+(\d+)", Path("/proc/meminfo").read_text()).group(1))
        return kb / 1024 ** 2
    return int(run(["sysctl", "-n", "hw.memsize"]).stdout.strip()) / 1024 ** 3


def parse_session_state(query_output, session_id):
    """State column of `query session` output for one session id (same logic as the runtime's jobs.py)."""
    for line in query_output.splitlines():
        parts = line.replace(">", " ").split()
        if str(session_id) in parts:
            i = parts.index(str(session_id))
            if i + 1 < len(parts):
                return parts[i + 1]
    return None


def check_system(home):
    g = "system"
    sysname, machine = platform.system(), platform.machine().lower()
    if sysname == "Windows":
        rel = platform.release()
        is64 = machine in ("amd64", "x86_64", "arm64") or sys.maxsize > 2 ** 32
        if rel in ("10", "11") and is64:
            add("os_windows", g, "PASS", "Windows %s 64-bit (%s)" % (rel, platform.version()))
        else:
            add("os_windows", g, "FAIL", "Windows %s, %s" % (rel, machine),
                "Use a 64-bit Windows 10 or 11 computer; the Ansys applications need it.")
    else:
        add("os_windows", g, "FAIL", "this computer runs %s; the Ansys applications used here (Fluent, TurboGrid, "
            "Mechanical, Discovery, Vista CCD) need a Windows desktop" % (sysname or "an unknown system"),
            "Run the setup and the demo on a 64-bit Windows 10 or 11 computer with Ansys installed.")
    n = os.cpu_count() or 0
    if n >= 4:
        add("cpu_cores", g, "PASS", "%d logical processors" % n)
    elif n >= 2:
        add("cpu_cores", g, "WARN", "%d logical processors; runs will be slow (4 or more recommended)" % n)
    else:
        add("cpu_cores", g, "FAIL", "%d logical processor(s)" % n, "Use a computer with at least 4 processor cores.")
    mem = memory_gb()
    if mem >= 15.5:
        add("memory_gb", g, "PASS", "%.0f GB memory" % mem)
    elif mem >= 7.5:
        add("memory_gb", g, "WARN", "%.0f GB memory; 16 GB or more recommended, large meshes may fail" % mem)
    else:
        add("memory_gb", g, "FAIL", "%.1f GB memory" % mem, "Use a computer with at least 8 GB (better 16 GB) memory.")
    p = Path(home).resolve()
    while not p.exists() and p != p.parent:
        p = p.parent
    free = shutil.disk_usage(str(p)).free / 1024 ** 3
    drive = Path(home).resolve().anchor or str(p)
    if free >= 20:
        add("disk_free_gb", g, "PASS", "%.0f GB free on %s" % (free, drive))
    elif free >= 5:
        add("disk_free_gb", g, "WARN", "%.1f GB free on %s; 20 GB recommended (the NASA download alone is about "
            "5 GB)" % (free, drive))
    else:
        add("disk_free_gb", g, "FAIL", "%.1f GB free on %s" % (free, drive),
            "Free up at least 20 GB on drive %s (empty the Recycle Bin, remove old files)." % drive)
    hs = str(Path(home).resolve())
    probs = []
    if "onedrive" in hs.lower():
        probs.append("it is inside OneDrive (sync locks files while Ansys writes them)")
    if len(hs) >= 100:
        probs.append("the path is %d characters long (Ansys tools break on long paths)" % len(hs))
    if probs:
        add("install_path_ok", g, "FAIL", "install folder %s: %s" % (hs, "; ".join(probs)),
            "Use a short local folder outside OneDrive, for example set ANSYS_RERATE_HOME=C:\\rerate and rerun setup.")
    else:
        add("install_path_ok", g, "PASS", "%s (%d characters, not in OneDrive)" % (hs, len(hs)))
    if os.name != "nt":
        add("desktop_session", g, "SKIP", "not Windows")
        return
    import ctypes
    sid = ctypes.c_ulong()
    ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sid))
    fix = "Sign in at the screen (or reconnect Remote Desktop) and keep the session open and unlocked during a run."
    if sid.value == 0:
        add("desktop_session", g, "WARN", "running in the background service session; Ansys windows cannot show here")
        return
    state = None
    try:
        state = parse_session_state(run(["query", "session"], timeout=20).stdout, sid.value)
    except Exception:
        pass
    if state and state.lower().startswith("disc"):
        add("desktop_session", g, "WARN", "Windows session %d is disconnected (Remote Desktop closed). " % sid.value
            + fix)
        return
    h = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0100)
    if not h:
        add("desktop_session", g, "WARN", "the Windows desktop is locked. " + fix)
        return
    ctypes.windll.user32.CloseDesktop(h)
    add("desktop_session", g, "PASS", "desktop session %d is active and unlocked (state %s)" % (sid.value, state or "?"))


# ---------------------------------------------------------------- ansys
def check_ansys(home):
    g = "ansys"
    inst = ansys_installs()
    ver, root = pick_ansys()
    if not root:
        add("ansys_found", g, "FAIL", "no Ansys installation found (no AWP_ROOT variable, no standard folder)",
            "Install Ansys 2026 R1 (Student or commercial) with Workbench, Fluent, TurboGrid, Mechanical, Discovery.")
    elif ver == TESTED_VERSION:
        extra = " (also found: %s)" % ", ".join("v" + v for v in sorted(inst) if v != ver) if len(inst) > 1 else ""
        add("ansys_found", g, "PASS", "Ansys 2026 R1 (v261) at %s%s" % (root, extra))
    else:
        add("ansys_found", g, "FAIL", "found Ansys v%s at %s; this agent is tested with Ansys 2026 R1 (v261)"
            % (ver, root), "Install Ansys 2026 R1 (v261); other versions are not tested.")
    for cid, (name, rel) in PRODUCTS.items():
        if not root:
            add(cid, g, "SKIP", "%s: no Ansys installation" % name)
            continue
        p = Path(root) / rel
        if p.exists():
            add(cid, g, "PASS", "%s found (%s)" % (name, rel))
        else:
            add(cid, g, "FAIL", "%s not found at %s" % (name, p),
                "Rerun the Ansys installer and select %s, then run this check again." % name)
    if root:
        mode = "student" if "ansys student" in str(root).lower() else "commercial"
        add("license_mode", g, "PASS", "%s (%s)" % (mode, "one Ansys app at a time; 1 million CFD cells and 128,000 "
            "structural nodes at most" if mode == "student" else "license server; apps may run at the same time"))
    else:
        add("license_mode", g, "SKIP", "no Ansys installation")
    d = Path(os.environ.get("TEMP", tempfile.gettempdir())) / ".ansys"
    cutoff = time.time() - 24 * 3600
    hits = []
    files = sorted(d.glob("licdebug*.out"), key=lambda p: p.stat().st_mtime, reverse=True)[:6] if d.exists() else []
    for f in files:
        if f.stat().st_mtime < cutoff:
            continue
        for line in f.read_text(errors="ignore").splitlines():
            if "DENIED" in line:
                try:  # lines start with a timestamp; old lines stay in recently touched files
                    if time.mktime(time.strptime(" ".join(line.split()[:2]), "%Y/%m/%d %H:%M:%S")) < cutoff:
                        continue
                except ValueError:
                    pass
                hits.append("%s: %s" % (f.name, " ".join(line.split()[:5])))
    if hits:
        add("license_denials", g, "WARN", "%d license denial(s) in the last 24 h, latest: %s. Usually another Ansys "
            "app or a leftover Fluent process holds the license" % (len(hits), hits[-1][:160]))
    else:
        add("license_denials", g, "PASS", "no license denials in the last 24 h (%d log file(s) read)" % len(files))


# ---------------------------------------------------------------- python
PKG_DIST = {"fastmcp": "fastmcp", "yaml": "PyYAML", "numpy": "numpy", "ansys.fluent.core": "ansys-fluent-core",
            "ansys.turbogrid.core": "ansys-turbogrid-core", "ansys.mechanical.core": "ansys-mechanical-core",
            "ansys.geometry.core": "ansys-geometry-core", "rerate_mcp_v2": "rerate-mcp-v2"}


def runtime_dist():
    """(distribution name, version) of the runtime, read from runtime/pyproject.toml."""
    pp = REPO / "runtime" / "pyproject.toml"
    txt = pp.read_text(encoding="utf-8") if pp.exists() else ""
    n = re.search(r'^name\s*=\s*"([^"]+)"', txt, re.M)
    v = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)
    return (n.group(1) if n else "rerate-mcp-v2"), (v.group(1) if v else None)


PKG_DIST["rerate_mcp_v2"] = runtime_dist()[0]


def lock_versions():
    out = {}
    lock = REPO / "setup" / "requirements.lock"
    if lock.exists():
        for line in lock.read_text(encoding="utf-8").splitlines():
            if "==" in line and not line.startswith("#"):
                k, v = line.split("==", 1)
                out[k.strip().lower().replace("_", "-")] = v.strip()
    name, ver = runtime_dist()
    if ver:
        out[name.lower().replace("_", "-")] = ver
    return out


def check_python(home):
    g = "python"
    found = find_pythons()
    good = sorted([x for x in found if x[1] in ((3, 13), (3, 12))], key=lambda x: x[1], reverse=True)
    if good:
        add("python_supported", g, "PASS", "Python %d.%d at %s" % (good[0][1] + (good[0][0],)))
    else:
        seen = ", ".join("%d.%d" % v for _, v in found) or "none"
        add("python_supported", g, "FAIL", "no Python 3.12 or 3.13 found (found: %s). The Ansys Python libraries do "
            "not support 3.14 or newer yet" % seen, "The setup assistant can install Python 3.13.")
    vp = venv_python(home)
    v = python_version(vp) if vp.exists() else None
    if not vp.exists():
        add("venv_present", g, "FAIL", "no Python environment at %s" % vp.parent.parent,
            "Run: python setup/install_runtime.py venv --python <path of Python 3.13>.")
    elif v not in ((3, 13), (3, 12)):
        add("venv_present", g, "FAIL", "the environment at %s uses Python %s" % (vp.parent.parent, v),
            "Delete that venv folder and recreate it with Python 3.13 (install_runtime.py venv).")
    else:
        add("venv_present", g, "PASS", "Python %d.%d environment at %s" % (v + (vp.parent.parent,)))
    if not v:
        add("packages", g, "SKIP", "no usable Python environment yet")
        return
    code = ("import json, importlib, importlib.metadata as md\nout = {}\n"
            "for mod, dist in %r.items():\n"
            "    try:\n        importlib.import_module(mod)\n        ok = True\n"
            "    except Exception as e:\n        ok = '%%s: %%s' %% (type(e).__name__, str(e)[:120])\n"
            "    try:\n        ver = md.version(dist)\n    except Exception:\n        ver = None\n"
            "    out[mod] = [ok, ver]\nprint(json.dumps(out))\n") % PKG_DIST
    res = run_json(vp, code, timeout=300)
    lock = lock_versions()
    missing = ["%s (%s)" % (m, r[0] if r[0] is not True else "?") for m, r in res.items() if r[0] is not True]
    mism = ["%s %s (lock file: %s)" % (PKG_DIST[m], r[1], lock[PKG_DIST[m].lower()]) for m, r in res.items()
            if r[0] is True and PKG_DIST[m].lower() in lock and r[1] != lock[PKG_DIST[m].lower()]]
    if missing:
        add("packages", g, "FAIL", "missing or broken: " + "; ".join(missing),
            "Run: python setup/install_runtime.py packages.")
    elif mism:
        add("packages", g, "WARN", "all %d packages import; versions differ from the lock file: %s"
            % (len(res), ", ".join(mism)))
    else:
        add("packages", g, "PASS", "all %d packages import at the locked versions" % len(res))


# ---------------------------------------------------------------- config
def config_file(home):
    return Path(home) / "machine.config.yaml"


def _cfg_path(cfgfile, value):
    q = Path(os.path.expandvars(os.path.expanduser(str(value))))
    return q if q.is_absolute() else Path(cfgfile).parent / q


def check_config(home):
    g = "config"
    cf = config_file(home)
    fix_new = "Run: python setup/install_runtime.py config --license student (or commercial)."
    if not cf.exists():
        add("machine_config", g, "FAIL", "no machine config at %s" % cf, fix_new)
    else:
        cfg = load_yaml(cf, home)
        probs = []
        root = (cfg.get("ansys") or {}).get("root")
        if not root or not _cfg_path(cf, root).exists():
            probs.append("ansys.root %r does not exist" % root)
        if (cfg.get("license") or {}).get("mode") not in ("student", "commercial"):
            probs.append("license.mode must be student or commercial")
        paths = cfg.get("paths") or {}
        for k in ("runs_dir", "work_dir"):
            if not paths.get(k):
                probs.append("paths.%s is not set" % k)
                continue
            d = _cfg_path(cf, paths[k])
            try:
                d.mkdir(parents=True, exist_ok=True)
                t = d / ".write_test"
                t.write_text("ok")
                t.unlink()
            except OSError as e:
                probs.append("cannot write to %s (%s)" % (d, e.strerror or e))
        if probs:
            add("machine_config", g, "FAIL", "%s: %s" % (cf, "; ".join(probs)),
                "Fix those keys in the file, or recreate it with install_runtime.py config --force.")
        else:
            add("machine_config", g, "PASS", "%s (license %s, Ansys v%s)" % (cf, cfg["license"]["mode"],
                                                                         (cfg.get("ansys") or {}).get("version")))
    ds = REPO / "examples" / "01_nasa_hecc" / "data_source.yaml"
    txt = ds.read_text(encoding="utf-8")
    expected = re.findall(r"^\s+-\s+(\S+)\s*$", txt.split("expected_files:", 1)[1], re.M)
    out = Path(home) / "example-data" / "01_nasa_hecc" / "geometry_data"
    missing = [f for f in expected if not (out / f).exists()]
    if missing:
        add("example_data", g, "FAIL", "%d of %d example geometry files missing in %s (first: %s)"
            % (len(missing), len(expected), out, missing[0]),
            "Run: python setup/install_runtime.py example-data (downloads about 5 GB from NASA, resumable).")
    else:
        add("example_data", g, "PASS", "all %d example geometry files present in %s" % (len(expected), out))


# ---------------------------------------------------------------- hermes
def _profile_cfg(profile, home):
    p = profile_config_path(profile)
    if not p or not p.exists():
        raise RuntimeError("profile config not found")
    return p, load_yaml(p, home)


def stale_server_processes(home):
    """[(pid, started_epoch)] of running rerate_mcp_v2 server processes, plus the newest runtime file time."""
    site = Path(home) / "venv" / "Lib" / "site-packages" / "rerate_mcp_v2"
    if not site.exists():
        site = next((Path(home) / "venv").glob("lib/python3*/site-packages/rerate_mcp_v2"), None)
    if not site or not site.exists():
        return None, []
    newest = max(f.stat().st_mtime for f in site.rglob("*.py"))
    venv_key = os.path.normcase(str((Path(home) / "venv").resolve()))
    procs = []  # (pid, parent pid, start epoch) of servers launched from THIS install home's venv
    if os.name == "nt":
        ps = ("Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | Where-Object { $_.CommandLine -like "
              "'*rerate_mcp_v2.servers*' } | ForEach-Object { '{0} {1} {2} {3}' -f $_.ProcessId, $_.ParentProcessId, "
              "([DateTimeOffset]$_.CreationDate).ToUnixTimeSeconds(), $_.CommandLine }")
        r = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=60)
        for line in r.stdout.splitlines():
            parts = line.split(None, 3)
            if len(parts) == 4 and parts[0].isdigit() and venv_key in os.path.normcase(parts[3]):
                procs.append((int(parts[0]), int(parts[1]), int(parts[2])))
    else:
        r = run(["ps", "-eo", "pid=,ppid=,lstart=,args="], timeout=30)
        for line in r.stdout.splitlines():
            if "rerate_mcp_v2.servers" in line and venv_key in os.path.normcase(line):
                bits = line.split()
                t = time.mktime(time.strptime(" ".join(bits[2:7]), "%a %b %d %H:%M:%S %Y"))
                procs.append((int(bits[0]), int(bits[1]), int(t)))
    pids = {p[0] for p in procs}
    # on Windows a venv python.exe is a launcher that starts the real interpreter as its child: count it once
    servers = [p for p in procs if p[1] not in pids]
    return newest, [(p[0], p[2]) for p in servers if p[2] < newest - 1]


def check_hermes(home, profile):
    g = "hermes"
    h = hermes_exe()
    if not h:
        add("hermes_cli", g, "FAIL", "the hermes command is not on PATH",
            "Install Hermes Agent (hermes-agent.nousresearch.com), then open a new terminal.")
        for cid in ("profile_installed", "profile_mcp_wired", "profile_model_set", "profile_key_present",
                    "skills_present", "stale_servers"):
            add(cid, g, "SKIP", "Hermes not installed")
        return
    out = run([h, "--version"], timeout=60).stdout
    m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", out)
    ver = tuple(int(x) for x in m.groups()) if m else None
    if ver and ver >= (0, 21, 0):
        add("hermes_cli", g, "PASS", "Hermes %d.%d.%d at %s" % (ver + (h,)))
    else:
        add("hermes_cli", g, "FAIL", "Hermes version %s is too old or unknown (0.21 or newer needed)"
            % (".".join(map(str, ver)) if ver else "?"), "Run: hermes update")
    if not profile_exists(profile):
        add("profile_installed", g, "FAIL", "Hermes profile '%s' does not exist" % profile,
            "Run: python setup/install_runtime.py profile --name %s." % profile)
        for cid in ("profile_mcp_wired", "profile_model_set", "profile_key_present", "skills_present"):
            add(cid, g, "SKIP", "profile not installed")
    else:
        cfgp, cfg = _profile_cfg(profile, home)
        pdir = cfgp.parent
        add("profile_installed", g, "PASS", "profile '%s' at %s" % (profile, pdir))
        _wired(g, cfg, home, profile)
        model = cfg.get("model") or {}
        model = model if isinstance(model, dict) else {"default": model}
        if model.get("default") and model.get("provider"):
            add("profile_model_set", g, "PASS", "model %s via provider %s" % (model["default"], model["provider"]))
        else:
            add("profile_model_set", g, "FAIL", "the profile has no model and provider chosen",
                "Run: hermes -p %s model (pick the provider and model)." % profile)
        gp = profile_config_path("default")
        st, detail = key_status(cfg, pdir, gp.parent if gp else None)
        if st in ("yes", "none-needed"):
            add("profile_key_present", g, "PASS", detail)
        elif st == "no":
            add("profile_key_present", g, "FAIL", detail,
                "Add your model key: hermes -p %s auth add %s (it asks for the key privately)."
                % (profile, model.get("provider") or "<provider>"))
        else:
            add("profile_key_present", g, "WARN", detail + "; send one test message to the agent to confirm")
        names = set()
        for f in (pdir / "skills").rglob("SKILL.md"):
            names.add(f.parent.name)
            mm = re.search(r"^name:\s*['\"]?([\w.-]+)", f.read_text(encoding="utf-8", errors="ignore"), re.M)
            if mm:
                names.add(mm.group(1))
        miss = [s for s in SKILLS if s not in names]
        old = [s for s in miss if s + "-v2" in names]
        if not miss:
            add("skills_present", g, "PASS", "all %d demo skills installed" % len(SKILLS))
        elif len(old) == len(miss):
            add("skills_present", g, "WARN", "skills installed under older -v2 names: %s" % ", ".join(old))
        else:
            add("skills_present", g, "FAIL", "missing skills: %s" % ", ".join(miss),
                "Run: python setup/install_runtime.py profile --name %s (reinstalls the skills)." % profile)
    newest, stale = stale_server_processes(home)
    if newest is None:
        add("stale_servers", g, "SKIP", "runtime not installed yet")
    elif stale:
        add("stale_servers", g, "WARN", "%d tool server process(es) (pid %s) started before the last runtime update, "
            "so they run old code. Fix: close Hermes completely (also the tray icon) and reopen it"
            % (len(stale), ", ".join(str(p) for p, _ in stale)))
    else:
        add("stale_servers", g, "PASS", "no tool server is running old code")


def _wired(g, cfg, home, profile):
    servers = cfg.get("mcp_servers") or {}
    vp = os.path.normcase(str(venv_python(home).resolve()))
    probs = []
    for s in SERVERS:
        e = servers.get(s)
        if not isinstance(e, dict):
            probs.append("%s missing" % s)
            continue
        if os.path.normcase(str(Path(str(e.get("command", ""))).resolve())) != vp:
            probs.append("%s runs %s, not the install-home venv" % (s, e.get("command")))
        if MODULES[s] not in " ".join(map(str, e.get("args") or [])):
            probs.append("%s args do not start %s" % (s, MODULES[s]))
        rc = (e.get("env") or {}).get("RERATE_CONFIG")
        if not rc or not Path(rc).is_file():
            probs.append("%s RERATE_CONFIG %s is not an existing file" % (s, rc))
        if e.get("enabled") is False:
            probs.append("%s is disabled" % s)
    if probs:
        add("profile_mcp_wired", g, "FAIL", "; ".join(probs[:4]) + (" (+%d more)" % (len(probs) - 4)
                                                                    if len(probs) > 4 else ""),
            "Run: python setup/install_runtime.py profile --name %s, then close Hermes fully and reopen it." % profile)
    else:
        add("profile_mcp_wired", g, "PASS", "all 6 tool servers point at %s" % venv_python(home))


# ---------------------------------------------------------------- mcp
MCP_PROBE = r'''
import asyncio, json, sys
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
spec = json.loads(sys.argv[1])
async def main():
    t = StdioTransport(command=spec["command"], args=spec["args"], env=spec["env"])
    async with Client(t, timeout=60, init_timeout=60) as c:
        return sorted(x.name for x in await c.list_tools())
print(json.dumps(asyncio.run(asyncio.wait_for(main(), 90))))
'''


def safe_env(extra):
    env = {k: v for k, v in os.environ.items()
           if k in SAFE_ENV or k.upper() in SAFE_ENV_CI or k.startswith("XDG_")}
    env.update({str(k): str(v) for k, v in (extra or {}).items()})
    return env


def check_mcp(home, profile):
    g = "mcp"
    vp = venv_python(home)
    servers = None
    try:
        if profile_exists(profile):
            servers = _profile_cfg(profile, home)[1].get("mcp_servers") or {}
    except Exception:
        servers = None
    for s in SERVERS:
        cid = "mcp_" + s
        if not vp.exists():
            add(cid, g, "SKIP", "no Python environment yet")
            continue
        if servers is None or not isinstance(servers.get(s), dict):
            add(cid, g, "FAIL", "%s is not in profile '%s'" % (s, profile),
                "Run: python setup/install_runtime.py profile --name %s." % profile)
            continue
        e = servers[s]
        spec = {"command": str(e.get("command")), "args": [str(a) for a in e.get("args") or []],
                "env": safe_env(e.get("env"))}
        try:
            r = run([str(vp), "-c", MCP_PROBE, json.dumps(spec)], timeout=150)
            lines = [x for x in r.stdout.splitlines() if x.strip()]
            if r.returncode != 0 or not lines:
                err = [x for x in r.stderr.splitlines() if x.strip()]
                raise RuntimeError(err[-1][:250] if err else "no output")
            tools = json.loads(lines[-1])
        except subprocess.TimeoutExpired:
            add(cid, g, "FAIL", "%s did not answer within 150 s" % s,
                "Close Hermes and any leftover Python windows, then run the check again.")
            continue
        except Exception as ex:
            add(cid, g, "FAIL", "%s did not start: %s" % (s, ex),
                "Run install_runtime.py packages again; if it persists see docs/TROUBLESHOOTING.md (%s)." % cid)
            continue
        bad = sorted(BAD_TOOLS & set(tools))
        if bad:
            add(cid, g, "FAIL", "%s exposes arbitrary-code tools %s" % (s, bad),
                "Reinstall the runtime from this repository; these tools must not exist.")
        elif not tools:
            add(cid, g, "FAIL", "%s started but lists no tools" % s, "Run install_runtime.py packages again.")
        else:
            add(cid, g, "PASS", "%s started, %d tools" % (s, len(tools)))


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print a JSON list instead of text")
    ap.add_argument("--only", choices=GROUPS, help="run one group only")
    ap.add_argument("--home", help="install folder (default: LOCALAPPDATA/ansys-rerate-agent or ANSYS_RERATE_HOME)")
    ap.add_argument("--profile", default="ansys-rerate-agent", help="Hermes profile of the demo agent")
    a = ap.parse_args()
    home = install_home(a.home)
    funcs = {"system": lambda: check_system(home), "ansys": lambda: check_ansys(home),
             "python": lambda: check_python(home), "config": lambda: check_config(home),
             "hermes": lambda: check_hermes(home, a.profile), "mcp": lambda: check_mcp(home, a.profile)}
    for gname in ([a.only] if a.only else GROUPS):
        before = len(RESULTS)
        try:
            funcs[gname]()
        except Exception as ex:  # one broken check never stops the others
            add(gname + "_error", gname, "FAIL", "the %s checks crashed after %d item(s): %s: %s"
                % (gname, len(RESULTS) - before, type(ex).__name__, str(ex)[:200]),
                "Report this message; it is a bug in the check or an unusual setup.")
    bad = sum(r["status"] == "FAIL" for r in RESULTS)
    if a.json:
        print(json.dumps(RESULTS, indent=2))
    else:
        for r in RESULTS:
            print("[%s] %s: %s" % (r["status"], r["id"], r["detail"]))
            if r["status"] == "FAIL":
                print("  -> Fix: %s" % r["fix"])
        print("ALL GREEN" if not bad else "NOT READY: %d problem%s" % (bad, "" if bad == 1 else "s"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
