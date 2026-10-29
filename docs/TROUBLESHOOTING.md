# Troubleshooting

This page explains every item of the health check (`python setup/check.py`) in plain words, and what to do when
it is not green. The setup assistant reads this page; you can too.

How to read the check: `[PASS]` is fine, `[WARN]` works but deserves attention, `[FAIL]` must be fixed before a
run, `[SKIP]` means the item could not be checked yet because something before it is missing. Fix the first FAIL
first; later items often turn green by themselves.

The install home is the folder that holds this computer's setup: by default `%LOCALAPPDATA%\ansys-rerate-agent`
(the `AppData\Local` folder inside your Windows user folder). It holds `venv\`, `machine.config.yaml`,
`example-data\`, `runs\`, `work\` and `downloads\`. You can choose another folder with the `ANSYS_RERATE_HOME`
environment variable or `--home`.

---

## system group

### os_windows
**Means:** the Ansys applications this agent drives (Vista CCD in Workbench, Discovery, TurboGrid, Fluent,
Mechanical) need a 64-bit Windows 10 or 11 desktop. On macOS or Linux the check fails because the apps cannot run
there.
**Fix:** use a 64-bit Windows 10 or 11 computer with Ansys installed. (The AI model itself can run anywhere; the
Ansys side cannot.)

### cpu_cores
**Means:** number of logical processors. 4 or more is fine, 2 or 3 works but runs are slow.
**Fix:** use a computer with at least 4 cores, or accept long run times. Fluent uses `fluent.processors` from the
machine config; do not set it higher than the number of physical cores.

### memory_gb
**Means:** installed memory. 16 GB or more is fine, 8 to 15 GB may fail on the finer meshes, under 8 GB is too
little.
**Fix:** close other large programs during a run, or use a computer with 16 GB or more.

### disk_free_gb
**Means:** free space on the drive of the install home. The NASA example download alone is about 5 GB, and each
run writes meshes and results.
**Fix:** free up space (empty the Recycle Bin, delete old folders in `runs\`), or move the install home to a
bigger drive with `ANSYS_RERATE_HOME`.

### install_path_ok
**Means:** the install home must not be inside OneDrive and its path must be shorter than 100 characters.
OneDrive locks and uploads files while Ansys writes them, which breaks meshing and solving. Some Ansys tools fail
with long paths (the Windows 260-character limit is reached quickly inside run folders).
**Fix:** set a short local folder, for example `ANSYS_RERATE_HOME=C:\rerate`, then rerun the setup steps.

### desktop_session
**Means:** the Ansys windows need an active, unlocked Windows desktop. If you use Remote Desktop and close the
window, the session becomes "disconnected": Discovery hangs at launch ("Direct3DCreate9Ex failed"), Fluent cannot
import the TurboGrid mesh and has crashed mid-solve with "connection reset". A locked screen has the same effect.
This is a warning only, because it matters only while a run is going.
**Fix:** sign in at the computer itself, or keep the Remote Desktop window open (minimised is fine, closed is not)
for the whole run. Turn off the screen lock during runs. Where an app supports it, `apps.<app>.mode: headless` in
the machine config avoids windows (Discovery has no headless mode).

---

## ansys group

### ansys_found
**Means:** Ansys was found through the `AWP_ROOT<version>` environment variable (for example `AWP_ROOT261`) that
the Ansys installer sets, or in the standard install folder. This agent is tested with Ansys 2026 R1 (v261);
other versions fail the check because their scripting interfaces differ.
**Fix:** install Ansys 2026 R1 (Student or commercial). If it is installed but not found, sign out of Windows and
back in so the new environment variables are seen, or pass `--ansys-root` to the config step.

### vista_workbench, discovery, turbogrid, fluent, mechanical
**Means:** each product's program file exists under the Ansys folder:
`Framework\bin\Win64\RunWB2.exe` (Workbench, which runs Vista CCD), `Discovery\Discovery.exe`,
`TurboGrid\bin\cfxtg.exe`, `fluent\ntbin\win64\fluent.exe`, `aisol\bin\winx64\AnsysWBU.exe` (Mechanical).
**Fix:** run the Ansys installer again and tick the missing product.

### license_mode
**Means:** "student" when Ansys is installed under `ANSYS Student`, otherwise "commercial". Student limits that
shape the demo:
- only one Ansys application at a time (the agent closes one before opening the next; a second one is refused);
- CFD meshes up to 1 million cells, structural meshes up to 128,000 nodes (the case files stay inside these);
- no Fluent GPU solver (`fluent.gpu` must stay false).
**Fix:** none needed; it is information. The value is written to `license.mode` in the machine config.

### license_denials
**Means:** the Ansys license logs (`%TEMP%\.ansys\licdebug*.out`) show "DENIED" lines in the last 24 hours.
Usually another Ansys window is still open, or a leftover Fluent process holds the license after a crash.
**Fix:** close all Ansys windows. Then open Task Manager and end any leftover `fluent`, `cx2610`, `mpiexec`,
`AnsysFWW` or `cfxtg` processes (or sign out of Windows and back in). With a commercial license, ask your license
administrator whether the products are available.

---

## python group

### python_supported
**Means:** a Python 3.12 or 3.13 was found. The Ansys Python libraries (PyFluent, PyMechanical, PyTurboGrid,
PyAnsys Geometry) do not support Python 3.14 or newer yet. Hermes brings its own Python 3.14 for itself; that one
must not be used for the Ansys tools.
**Fix:** the setup assistant can install Python 3.13 (from python.org, "install for me only", no admin rights
needed). Do not uninstall other Pythons; this setup uses its own isolated copy.

### venv_present
**Means:** the private Python environment in `<install home>\venv` exists and uses Python 3.12 or 3.13.
**Fix:** `python setup/install_runtime.py venv --python <path to Python 3.13>`. If an old venv uses the wrong
version, delete the `venv` folder first.

### packages
**Means:** inside the venv these import: fastmcp, yaml, numpy, ansys.fluent.core, ansys.turbogrid.core,
ansys.mechanical.core, ansys.geometry.core and the agent runtime `rerate_mcp_v2`. A version different from
`setup/requirements.lock` is a warning; a missing package is a failure.
**Fix:** `python setup/install_runtime.py packages`. Behind a company proxy add `--proxy http://host:port` (ask IT
for the address). If antivirus software quarantines files during install (often the `.pyd` or `.exe` files of
grpcio, vtk or pywin32), allow the install home folder and run the step again.

---

## config group

### machine_config
**Means:** `<install home>\machine.config.yaml` exists and parses, `ansys.root` points at a real folder,
`license.mode` is student or commercial, and the runs and work folders are writable.
**Fix:** `python setup/install_runtime.py config --license student` (or `commercial`). To start over add
`--force` (the old file is kept as `.bak`). After updating the repository, `python setup/upgrade_config.py` adds new
keys without touching your values.

### example_data
**Means:** the NASA compressor geometry tables for example 01 are in
`<install home>\example-data\01_nasa_hecc\geometry_data`. They come from a public NASA archive and are not shipped
with the repository.
**Fix:** `python setup/install_runtime.py example-data`. It downloads about 5 GB from ntrs.nasa.gov into
`<install home>\downloads`; if it stops, run it again and it continues. If you already have the zip file, add
`--zip <path>`.

---

## hermes group

### hermes_cli
**Means:** the `hermes` command works and is version 0.21 or newer.
**Fix:** install Hermes Agent, or run `hermes update`. Open a new terminal afterwards so the command is found.

### profile_installed
**Means:** the demo agent's Hermes profile (default name `ansys-rerate-agent`) exists.
**Fix:** `python setup/install_runtime.py profile`. Your default Hermes profile is never changed.

### profile_mcp_wired
**Means:** the profile's `config.yaml` lists the 6 tool servers (case_v2, vista_v2, geometry_v2, turbogrid_v2,
fluent_v2, mechanical_v2), each started with the install-home venv Python, and each gets `RERATE_CONFIG` pointing
at the machine config. Hermes passes only a short list of safe environment variables to tool servers (PATH,
TEMP, USERPROFILE and similar); anything else, such as your own variables, does not reach them. That is why the
config path is written into the profile and why the runtime sets `AWP_ROOT261` itself from the machine config.
**Fix:** `python setup/install_runtime.py profile`, then close Hermes completely and reopen it.

### profile_model_set
**Means:** the profile has a model and a provider chosen. The profile step copies these settings (never keys)
from your default profile when the new profile has none.
**Fix:** `hermes -p ansys-rerate-agent model` and pick the provider and model.

### profile_key_present
**Means:** best-effort check that the profile can authenticate to its model provider: a key in the profile's
`.env`, its config, or the Hermes credential store, or a provider that needs no key (a local model). The key
itself is never shown. A warning means the check cannot tell; send one test message to the agent to be sure.
**Fix:** `hermes -p ansys-rerate-agent auth add <provider> --type api-key` and paste the key when asked. Keys are
never written by the setup scripts. A key that is present can still be wrong or expired: `model_reachable` is the
real test.

### model_reachable
**Means:** the check sent one short test message through the profile ("Reply with the single word READY") and
the model answered. This is the only reliable proof that the model, provider and key work. It costs one tiny
request; skip it with `--no-model-call` when offline.
**Fix:** HTTP 401 means the provider rejected the key: add a valid one with
`hermes -p ansys-rerate-agent auth add <provider> --type api-key`. Real case seen: the main Hermes profile kept
its key inside its own config.yaml; new profiles get the model choice but, correctly, not the key, so they answer
401 until a key is added to them. Any other error: check the model choice with `hermes -p ansys-rerate-agent model`.

### skills_present
**Means:** the 8 demo skills are installed in the profile: rerate-run, rerate-intake, rerate-sizing,
rerate-geometry, rerate-meshing, rerate-cfd, rerate-structural, rerate-report.
**Fix:** `python setup/install_runtime.py profile` (reinstalls the skills; your own skills stay).

### stale_servers
**Means:** a tool server process is still running code from before the last runtime install. Tool servers are
started once by Hermes and do not reload when the runtime changes, so a run would use the old code.
**Fix:** close Hermes completely (all windows and the tray icon), then open it again. After any change to the tool
servers or the profile, also start a NEW chat: an existing chat keeps the tool list it started with.

---

## mcp group

### mcp_case_v2, mcp_vista_v2, mcp_geometry_v2, mcp_turbogrid_v2, mcp_fluent_v2, mcp_mechanical_v2
**Means:** each tool server was started exactly as Hermes will start it (same command, same filtered
environment), answered within 60 seconds and listed its tools. None may offer a "run any code" tool (run_code,
run_python, run_script, exec). This does not open any Ansys application.
**Fix:** if one does not start, the message shows the last error line. Usual causes: packages missing
(`install_runtime.py packages`), wrong Python in the profile (`install_runtime.py profile`), antivirus blocking
the venv Python (allow the install home folder), or a machine config error (see machine_config). If it times
out, close Hermes and any leftover Python windows and run the check again.

---

## Things that happen during a run (not checked up front)

- **Long steps run as background jobs.** Building geometry, meshing and solving take minutes to hours. The agent
  starts them as jobs and polls their status; a quiet chat for a few minutes is normal. Each job has a time limit
  (`apps.<app>.job_timeout_s`) after which it is reported as timed out, never left hanging.
- **Student: one app at a time.** If an Ansys window from an earlier attempt is still open, the next stage is
  refused or gets a license denial. Close it and retry the stage.
- **Leftover Fluent processes.** After a crash, `fluent`, `cx2610` and `mpiexec` processes can stay alive and hold
  the license and files. End them in Task Manager or sign out and back in.
- **Remote Desktop closed mid-run.** See desktop_session. Reconnect and rerun the stage that failed.
- **Mesh too big for Student.** The cases are sized to stay under 1 million CFD cells and 128,000 structural nodes;
  a modified case that exceeds them is stopped with a clear message. Use a coarser size factor or a commercial
  license.
- **Antivirus.** Real-time scanning can slow Fluent and Mechanical file writes a lot and sometimes blocks the venv
  Python. Adding the install home folder as an exclusion helps (ask IT on a managed computer).
- **Company proxy.** pip and the NASA download need internet. Use `--proxy` for packages; for the example data,
  download the zip in a browser and pass `--zip`.
