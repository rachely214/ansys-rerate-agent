# Compressor Re-rate Agent

**An agentic workflow for Ansys turbomachinery:** give the agent a customer's re-rate request, baseline
datasheet and casing limits; it drafts a sourced case file, then sizes, changes the geometry, meshes, runs CFD and
a spin-stress check, and writes a pass/fail report, driving five Ansys apps live through MCP.

There is **no prewritten end-to-end script**. Skills teach the method; the agent reads the documents, chooses
the run parameters, judges convergence and failures, and decides each next step. Six MCP servers expose
specific actions only (launch, mesh, solve, measure). Machine data lives in one case file per compressor, not in
code.

## Status

Windows/local-desktop **experimental**, Ansys 2026 R1 Student. Two complete agent runs from the prompt, with no
human input, ended "PASS ON CHECKED ITEMS ONLY": Claude Opus in 4 h 50 min and DeepSeek V4 Flash in 2 h 43 min.
**The CFD model is not calibrated** against NASA's measured baseline, so the airflow targets are NOT CHECKED. See
[validation and limitations](docs/VALIDATION.md). A fresh install on a second machine remains required before
calling this reproducible.

## Quick start (Windows PowerShell)

Install **Ansys 2026 R1** with Vista CCD, Discovery, TurboGrid, Fluent and Mechanical, install
[Hermes Agent](https://hermes-agent.nousresearch.com/docs/getting-started/installation) with a working model, and
have Git plus [Python 3.13](https://www.python.org/downloads/) available. Then:

```powershell
git clone https://github.com/rachely214/ansys-rerate-agent.git
cd ansys-rerate-agent
.\setup.ps1
```

The installer creates a **private Python environment** in `%LOCALAPPDATA%\ansys-rerate-agent`, installs locked
packages and the agent tools, writes a machine config, downloads the NASA example geometry (about 4.9 GB), and
installs a separate Hermes profile, `ansys-rerate-agent`, with its six MCP servers. It ends with a health check
that must say ALL GREEN. It does not install or license Ansys, read or write API keys, or change your default
Hermes profile.

Follow [SETUP.md](SETUP.md) for the one-time model key and the desktop-session rules. Then restart Hermes, choose
the profile **ansys-rerate-agent**, start a new chat, attach the three files from
`examples/01_nasa_hecc/inputs/`, and ask the agent:

> Our customer sent a re-rate request for their compressor: they need about 6% more flow without changing the
> casing. Their request, the baseline datasheet and the casing limits are attached. The impeller geometry and a
> draft case file are in the example folder `examples/01_nasa_hecc/`. Can we do it? Check the case against their
> documents and show me the key values with their sources. For this session I approve the case on the engineer's
> behalf once every value has a source, so carry on without waiting. Then size it, change the geometry, mesh it,
> simulate it and check its strength, live in Ansys, and give me a pass/fail report. This is a time-boxed
> feasibility check: if a simulation does not settle within its budget, mark it NOT CHECKED and keep going.

Full prompt: [examples/01_nasa_hecc/prompt_demo.md](examples/01_nasa_hecc/prompt_demo.md). A version that waits
for the engineer's approval: [examples/01_nasa_hecc/prompt.md](examples/01_nasa_hecc/prompt.md).

## Architecture

```text
Agent on this desktop (Hermes profile ansys-rerate-agent)
  ├─ skills: intake / sizing / geometry / meshing / cfd / structural / report
  └─ MCP stdio servers (private Python environment)
       ├─ case_v2        case file, approval, runs, calibration, report
       ├─ vista_v2       → Vista CCD (Workbench)   1D sizing
       ├─ geometry_v2    → Discovery               blade change, solids
       ├─ turbogrid_v2   → TurboGrid               passage mesh
       ├─ fluent_v2      → Fluent                  passage CFD
       └─ mechanical_v2  → Mechanical              spin stress
  run folder: %LOCALAPPDATA%\ansys-rerate-agent\runs\<case>_<time>\ → REPORT.md
```

One agent owns all dependent stages. No hidden subagents and no sandbox. The servers contain app control,
geometry conversion and checks, not machine data or engineering choices. More:
[docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

## Repository map

| Path | Purpose |
|---|---|
| `agents/rerate-engineer/SOUL.md` | Agent behavior |
| `agents/rerate-engineer/skills/` | Eight stage skills; `rerate-run` is the entry point |
| `harnesses/hermes/` | Hermes profile manifest, behavior config, MCP server template (`mcp_servers.json`) |
| `plugins/ansys-mcp/` | Python package of the six MCP servers, geometry adapters, in-app Ansys scripts, case schema, report |
| `setup.ps1`, `scripts/setup/` | Host-local installer, health check (`check.py`), layout scan, pinned packages |
| `scripts/setup/setup-agent/` | Optional setup assistant (Hermes profile `ansys-rerate-setup`) |
| `scripts/dev/` | Maintainer test tools; never used by the agent |
| `examples/01_nasa_hecc/` | Customer documents, draft case, material file, prompts |
| `docs/` | How it works, validation, decisions, troubleshooting, roadmap, release checklist; `docs/examples/` expected outcome |
| `tests/` | Unit tests, no Ansys needed |
| `.github/` | Issue and pull request templates, CI (unit tests and layout scan) |
| install home (`%LOCALAPPDATA%\ansys-rerate-agent`) | Machine config, environment, example data, runs; never commit |

## What the HECC example demonstrates

- NASA High Efficiency Centrifugal Compressor (public data): 15 main blades and 15 splitters, 21,789 rpm,
  baseline 10.85 lbm/s; customer target 11.5 lbm/s (+6 %) with the exit blade height limited to 0.650 in.
- Case intake: every value with a document source or a labelled engineering choice.
- 1D sizing in Vista CCD: exit blade height 0.609 to 0.634 in, inside the casing limit.
- Geometry changed from NASA's blade tables and built as solids in Discovery; TurboGrid passage mesh with the
  splitter and tip gap, 780,920 cells.
- Fluent passage CFD: the re-rated design reaches 12.59 lbm/s at choke, above the target.
- Mechanical spin stress at 105 % speed: safety factor 4.86 against a minimum of 1.5 with the root fillet
  modelled, mesh-converged (4.77, labelled indicative, in a run that fell back to a sharp root).
- A report where every check is PASS, FAIL or NOT CHECKED with a reason.

**It does not demonstrate a calibrated or validated design.** The CFD model over-predicts NASA's measured
baseline flow and efficiency, and no converged solution was found at the target flow, so pressure ratio and
efficiency at the target are NOT CHECKED. Surge margin, shaft power, running clearance and the Campbell diagram
are not simulated. The design change is one lever, the impeller exit blade height. See
[decisions](docs/DECISIONS.md).

## Development and sharing

```powershell
$py = "$env:LOCALAPPDATA\ansys-rerate-agent\venv\Scripts\python.exe"
& $py -m unittest discover -s tests -v
& $py scripts\setup\verify_layout.py
& $py scripts\setup\check.py
```

`check.py` checks this computer and sends one short test message to the model; it does not run a study.
Follow [CONTRIBUTING.md](CONTRIBUTING.md). Do not commit credentials, machine paths, run folders, Ansys files or
NASA data.

License: Apache-2.0 for this repository. Ansys is a trademark of ANSYS, Inc. Not affiliated with or endorsed by
Ansys, NASA, NVIDIA, or Nous Research. Read [SECURITY.md](SECURITY.md).
