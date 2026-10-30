---
name: setup-run
description: "Use when setting up this computer for the Ansys re-rate demo. Runs the install steps until the health check is ALL GREEN."
version: 1.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [setup, ansys, install, health-check]
    related_skills: [setup-diagnose]
---

# Setup: from a fresh computer to ALL GREEN

Work from the repository folder (the folder that has `START-HERE.md`). Every command below runs there.
`PY` means a Python 3.12 or 3.13 interpreter (found in step 2). The install home is
`%LOCALAPPDATA%\ansys-rerate-agent` unless the user chose another folder (`ANSYS_RERATE_HOME`).

Success: `PY setup/check.py` prints `ALL GREEN`, and the user knows the four handover steps (see SOUL).

## Steps
1. **First look.** Run the check with any Python you can find (`py setup/check.py`, or `python setup/check.py`).
   It needs only the standard library at this point. Show the user the summary: what is fine, what is missing.
   If there is no Python at all, go to step 2 first.
   - `os_windows` or `ansys_found` FAIL: stop and explain; this computer cannot run the demo as it is.
   - Any Ansys product FAIL: tell the user which product is missing; it must be added with the Ansys installer
     (you do not install Ansys).
   - `memory_gb` FAIL or `disk_free_gb` FAIL: explain and ask whether to continue anyway.
2. **Python 3.13.** Ansys's Python libraries need Python 3.12 or 3.13; newer versions (3.14+) do not work, and the
   Python that ships with Hermes must not be used. If `python_supported` FAILs, ask the user, then install it:
   `winget install --id Python.Python.3.13 -e --silent`. If winget is missing or blocked, give the user the
   python.org link for the Windows 64-bit 3.13 installer and ask them to run it with default options. Open a new
   terminal afterwards and confirm with `py -3.13 --version`. Use that interpreter as PY from now on.
3. **License mode.** Ask the user: "Is your Ansys a Student license or a full (commercial) license?" The check's
   `license_mode` item shows a guess (Student if the install path contains "ANSYS Student"); confirm it.
4. **Install the runtime** (one step at a time so the user sees progress; each is safe to repeat):
   - `PY setup/install_runtime.py venv --python <path of PY>`
   - `PY setup/install_runtime.py packages` (several minutes; downloads about 1 GB of Python packages).
     If it fails with a network or certificate error, ask whether the company uses a proxy and rerun with
     `--proxy http://host:port`.
   - `PY setup/install_runtime.py config --license student` (or `commercial`). Add `--processors N` only if the
     user wants fewer Fluent cores than the default.
5. **Example data.** Ask before downloading (about 5 GB from NASA, resumes if interrupted, can take a long time):
   `PY setup/install_runtime.py example-data`. If the user already has the NASA supplement zip:
   `--zip <path>`.
6. **Demo agent profile.** `PY setup/install_runtime.py profile`. It installs the `ansys-rerate-agent` profile,
   connects its six Ansys tool servers, and copies the model choice (not the key) from the user's default
   profile. A new profile does NOT inherit the key: show the user the exact command the step prints
   (`hermes -p ansys-rerate-agent auth add <provider> --type api-key`); they type the key themselves. The health
   check's `model_reachable` item then proves it works (HTTP 401 means the key is missing or wrong).
7. **Health check.** `PY setup/check.py`. Fix FAILs with `setup-diagnose` until `ALL GREEN`. WARN items: explain
   each in one line; they do not block.
8. **Handover** (see SOUL). Remind the user that the full demo takes 2 to 4.5 hours on a 4-core computer (about
   1.5 to 2 hours with demo mode, the default). To try a different AI model for the demo agent, the user runs
   `hermes -p ansys-rerate-agent model` and picks it; then `PY setup/check.py --only hermes` proves it answers.
   Nothing else changes: tools, skills and demo mode are model-independent.

## Rules
- Run the check before and after each change and show the summary line.
- Never paste or print secrets. Never edit the default Hermes profile or other profiles.
- If the same step fails twice with the same error, stop retrying and use `setup-diagnose`.
