# How it works

This page explains how the parts fit together. It assumes no Ansys or programming background, but it names the
real files so an engineer can check them.

## Two phases

| Phase | Who does it | What happens | Done when |
|---|---|---|---|
| 1. Setup | The **setup assistant** (Hermes profile `ansys-rerate-setup`) plus the health check `setup/check.py` | Installs the tools on this computer and connects them to the demo agent | `python setup/check.py` prints **ALL GREEN** |
| 2. Demo | The **demo agent** (Hermes profile `ansys-rerate-agent`) | Runs the engineering study: documents, case, sizing, geometry, mesh, CFD, structural, report | `REPORT.md` is written |

The two agents are kept apart on purpose.

- The setup assistant knows about Python versions, packages, Hermes profiles and config files. It does no
  engineering.
- The demo agent knows only engineering. If a tool says the computer is not ready, it says so in plain words and
  stops. It never tries to repair the computer.
- Readiness is decided by `setup/check.py`, a fixed script with no AI in it. It never changes anything and never
  starts an Ansys app. Each item is PASS, WARN, FAIL or SKIP; the last line is ALL GREEN or `NOT READY: N problems`.
  Groups: system, ansys, python, config, hermes, mcp. Every item is explained in `docs/TROUBLESHOOTING.md`.

## The install home

Everything this computer needs, apart from Ansys and Hermes, lives in one folder outside the repository:
`%LOCALAPPDATA%\ansys-rerate-agent` (that is `AppData\Local\ansys-rerate-agent` in your Windows user folder).
Another folder can be chosen with the `ANSYS_RERATE_HOME` environment variable or `--home`. Keeping it here
avoids OneDrive syncing, long paths and a dependency on where the repository was unzipped.

| Item | What it holds | Made by |
|---|---|---|
| `venv\` | A private Python 3.12 or 3.13 with the pinned packages and the tool package `rerate_mcp_v2` | `install_runtime.py venv`, `packages` |
| `machine.config.yaml` | This computer's settings: Ansys folder and version, license mode, Fluent cores, app modes, folders | `install_runtime.py config` (from `setup/machine.config.template.yaml`) |
| `example-data\` | Downloaded example data, one subfolder per example (`01_nasa_hecc\`) | `install_runtime.py example-data` |
| `downloads\` | The NASA archive while downloading (resumable) | `setup/fetch_example_data.py` |
| `runs\` | One folder per run, plus `active_run.txt` (the run the tools are working on) | the demo agent's `start_run` |
| `work\` | Scratch space for app logs and debug output | the tools |
| `logs\` | Log files | the tools |

The installer steps are `venv`, `packages`, `config`, `example-data`, `profile` (or `all`). Each is safe to run
again.

## How the demo agent finds its tools

The demo agent uses six tool servers. They speak MCP (Model Context Protocol), the standard way Hermes connects
to outside tools, over stdio (Hermes starts each server as a child process).

1. `agent/mcp_servers.json` is a template. It lists the six servers with two placeholders: the Python to run
   (`@@RERATE_PYTHON@@`) and the machine config (`@@RERATE_CONFIG@@`).
2. `python setup/install_runtime.py profile` installs `agent/` as the Hermes profile `ansys-rerate-agent`, fills
   in the placeholders with the install home's venv Python and `machine.config.yaml`, and writes the result into
   the profile's `config.yaml` under `mcp_servers`. Each server gets the environment variable `RERATE_CONFIG`
   pointing at the machine config. It also copies the model choice (never a key) from the default profile.
3. Hermes loads MCP servers when it starts. That is why Hermes must be closed completely and reopened after setup.
4. The health check's mcp group starts each server from the profile config and lists its tools, the same way
   Hermes does.

## The six tool servers

Every long Ansys action is a `*_start` tool that returns at once, followed by a status tool. No tool runs
arbitrary code; in-app scripts are fixed files in the package.

**case_v2** (case file, runs, report)
- `case_validate`: check a case file against the schema; list blocking issues and the fields each stage needs.
- `case_approve`: record the engineer's approval (stores a content hash). Only after the engineer approves.
- `start_run`: create a new run folder for an approved case.
- `run_status`: the active run, its case, and each stage's status.
- `calibrate_cfd`: compare a finished baseline run with the measured baseline; CALIBRATED or NOT CALIBRATED.
- `build_report`: build the scorecard and `REPORT.md` from the active run only.

**vista_v2** (1D sizing, Vista CCD in Workbench)
- `size_start`: size the baseline and target duty in the background (Workbench batch).
- `job_status`: progress and result.
- `open_gui`: show the target design in a Vista CCD window for the audience.
- `status`: install check and this run's sizing record.

**geometry_v2** (geometry change and solids, Discovery)
- `inspect_geometry`: read the case geometry and report what was found, without changes.
- `apply_exit_height_change`: scale the impeller exit blade height and write the changed blade curves.
- `build_start`: build the solids in Discovery in the background.
- `job_status`: progress and result.
- `screenshot`: picture of Discovery, saved in the run folder.
- `close_discovery`: close Discovery and free its license.

**turbogrid_v2** (passage mesh, TurboGrid)
- `mesh_start`: mesh one blade passage in the background.
- `job_status`: progress and result (cells, quality).
- `show_gui`: open the saved mesh in a visible TurboGrid window.
- `close`: quit TurboGrid.

**fluent_v2** (CFD, Fluent)
- `connect_start`, `setup_start`, `prep_status`: start Fluent, set up the rotating passage from the approved case,
  and check progress.
- `solve_start`, `solve_status`, `solve_stop`, `solve_fetch`: iterate in the background, watch progress, stop,
  and fetch the final performance with a convergence verdict.
- `set_back_pressure`, `restore_case_back_pressure`: diagnostic outlet pressure changes, then back to the case value.
- `set_design_flow_target`: evaluate the design at its target flow.
- `speedline_result`: fallback that interpolates converged points at the target flow (never extrapolates).
- `model_check`: read-only checks of the set-up model (extents, rotation, flows).
- `images`: pressure pictures into the run folder.
- `disconnect`: stop the solve and close Fluent.

**mechanical_v2** (spin stress, Mechanical)
- `connect_start`: start Mechanical in the background.
- `geometry_diagnostics_start`: check the single-blade solid for edges and faces that are hard to mesh.
- `spin_stress_start`: overspeed spin-stress study with a mesh study.
- `job_status`: progress and result.
- `disconnect`: close Mechanical.

## Skills

Skills are short instruction files the agent loads when it needs them.

Demo agent (`agent/skills/`):

| Skill | What it does |
|---|---|
| `rerate-run` | Entry point: stage order, hard rules (approval first, live results only, honest status), final answer |
| `rerate-intake` | Read the customer documents, draft `case.yaml` with a source for every value, get approval, start the run |
| `rerate-sizing` | 1D sizing in Vista CCD: turn the new duty into an exit-height change and check it fits the casing |
| `rerate-geometry` | Apply the exit-height change to the blade curves and build solids in Discovery |
| `rerate-meshing` | Mesh the blade passage in TurboGrid; accept it only on quality limits |
| `rerate-cfd` | Calibrate the CFD on the baseline, then evaluate the design at its target flow; judge convergence |
| `rerate-structural` | Spin stress at overspeed in Mechanical: blade body and root fillet, mesh study, safety factor |
| `rerate-report` | Build the scorecard from this run only and summarise it |

Setup assistant (`setup/setup-agent/skills/`):

| Skill | What it does |
|---|---|
| `setup-run` | The setup steps in order, from the first health check to ALL GREEN and the handover |
| `setup-diagnose` | Find and fix the cause of a failed step or check item, one item at a time |
| `ansys-host-diagnostics` | Ansys-specific problems: desktop session, licensing, apps left running, tool servers |

## The case file and the approval lock

The case file (`case.yaml`) holds every engineering value of the study: duty, targets, limits, geometry source,
material, mesh and solver choices. Each value has a unit and a source (a document section, or
`ENGINEERING CHOICE:` with a reason). Nothing has a default; a missing value is a question for the engineer. The
schema is `runtime/src/rerate_mcp_v2/schema/case_schema.yaml`. The example's draft is
`examples/01_nasa_hecc/case.yaml`.

Approval works like a lock. `case_approve` stores the engineer's name and a SHA-256 hash of the case content.
`start_run` and every stage tool check that the file still matches that hash. If anyone edits the case after
approval, the tools refuse to run until it is approved again.

## A run folder

`start_run` creates `runs\<case name>_<date>_<time>\` in the install home. Typical contents:

| File or folder | Written by |
|---|---|
| `run.json` | Every stage: its numbers, status (ok, partial, error) and model fidelity |
| `case.snapshot.yaml` | `start_run`: copy of the approved case |
| `sizing\` | Vista CCD baseline and target designs |
| `geometry\`, `geometry_impeller.png`, `single_blade.*` | Changed blade curves, a picture, one blade on a hub slice |
| `passage.gtm` | TurboGrid mesh |
| `cfd_result.*`, `cfd_pressure_*.png` | Fluent case and data, pictures |
| `materials\`, `structural_stress_iso.png` | Material data for Mechanical, stress picture |
| `REPORT.md` | `build_report`: the pass/fail report |

The report reads only this run's `run.json` and approved case, never older runs.
`examples/01_nasa_hecc/expected.md` lists what a finished example run contains.
