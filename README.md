# ansys-rerate-agent

**New here? Read [START-HERE.md](START-HERE.md) first.** This page is for engineers and reviewers.

An AI agent (Hermes Agent) runs a centrifugal compressor re-rate study in Ansys 2026 R1 on a Windows desktop. It
reads the customer's documents, drafts a case file, gets the engineer's approval, then sizes, changes the
geometry, meshes, runs CFD and a spin-stress check, and writes a pass/fail report from that run's own results.

**This is a concept demo of an agent operating existing engineering tools. It is not a validated design tool.**
Status: experimental.

## What is validated and what is not

Details and evidence: [docs/VALIDATION.md](docs/VALIDATION.md).

Validated (Windows 11, Ansys 2026 R1 Student, GUI mode, tools called over real MCP stdio without an LLM):
- Every stage runs live on the NASA compressor example (examples/01_nasa_hecc): 1D sizing, geometry change and solids, passage mesh, CFD,
  structural, report.
- CFD calibration against NASA's measured baseline was run. Result: NOT CALIBRATED (see limits).
- Strength check at overspeed with the root fillet, mesh-converged.
- A second, deliberately changed case (other speed, units, material) is carried through every stage and the report.
- Unit tests and the layout scan pass. The health check is ALL GREEN on a test install of this packaged layout.

Not validated yet:
- The agent run from `examples/01_nasa_hecc/prompt.md` in a freshly installed profile, end to end (in progress).
- A fresh install driven by the setup assistant.
- Commercial license behaviour (concurrent apps, GPU Fluent, headless modes), a second machine, other Ansys versions.

## Known limits

- **CFD is not calibrated.** Against NASA's measured baseline the model over-predicts corrected flow by about 9 %
  and impeller efficiency by about 7.4 points. Likely causes: design-intent geometry instead of the
  as-manufactured impeller; the Student 1M-cell mesh cap (near-wall y+ 16 to 96, wall functions); different
  measurement stations. Nothing is corrected with a factor, so aero rows cannot PASS.
- **Re-rated design point not demonstrated.** Neither design reached a converged state at its target flow.
- **Structural model** is a single blade on a hub slice, centrifugal load only.
- **Not simulated:** surge margin, shaft power, running tip clearance, Campbell diagram.
- **One design lever:** the impeller exit blade height, from the 1D sizing.
- **Windows and Ansys 2026 R1 only.**
- **The agent run from the prompt in a fresh profile has not yet been validated end to end** (in progress).

## Agent vs scripted

The agent does:
- read the customer documents, draft and validate the case, and ask the engineer about missing values;
- choose run parameters (mesh sizes, solve chunks, time caps) and state each choice;
- judge convergence and failures, retry or recover, and stop when the computer is not ready;
- write the summary.

Fixed, tested tools do the Ansys work: the geometry recipe, meshing, solver setup, stress study and scorecard.
The design change is one lever (exit blade height from the 1D sizing).

## Architecture

```
 Phase 1: setup                                   Phase 2: demo
 --------------                                   -------------
 setup assistant (Hermes profile                  demo agent (Hermes profile ansys-rerate-agent)
   ansys-rerate-setup, setup skills)                 SOUL + 8 rerate-* skills
        |                                                  |
        | runs                                             | MCP over stdio (6 servers)
        v                                                  v
 setup/install_runtime.py ---> install home        case_v2  vista_v2  geometry_v2  turbogrid_v2  fluent_v2  mechanical_v2
 setup/check.py (no AI)        %LOCALAPPDATA%\        |        |          |            |             |           |
   decides: ALL GREEN          ansys-rerate-agent\    |        v          v            v             v           v
        |                        venv\  (runtime)     |   Vista CCD   Discovery    TurboGrid       Fluent    Mechanical
        |                        machine.config.yaml  |   (Workbench)
        |                        example-data\        |        |          |            |             |           |
        +---> demo profile       runs\  work\         +--------+----------+------------+-------------+-----------+
              (mcp_servers                                                   |
               rendered with                                                 v
               RERATE_CONFIG)                               run folder: runs\<case>_<timestamp>\
                                                              run.json, case.snapshot.yaml, stage files
                                                              -> REPORT.md
```

More: [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

## Repository map

| Path | What it is |
|---|---|
| `START-HERE.md` | Plain-language guide for a first-time user |
| `agent/` | Hermes profile distribution of the demo agent: `SOUL.md`, `config.yaml`, `distribution.yaml`, `mcp_servers.json` (template), `skills/rerate-*` (8 skills) |
| `setup/setup-agent/` | Hermes profile distribution of the setup assistant: `SOUL.md`, `config.yaml`, `distribution.yaml`, `skills/setup-run`, `setup-diagnose`, `ansys-host-diagnostics` |
| `setup/check.py` | Deterministic health check (no AI); prints ALL GREEN or NOT READY |
| `setup/install_runtime.py` | Installer steps: venv, packages, config, example-data, profile, all |
| `setup/fetch_example_data.py` | Resumable NASA example data download into the install home |
| `setup/machine.config.template.yaml` | Template for the per-machine `machine.config.yaml` |
| `setup/requirements.lock` | Pinned Python packages |
| `setup/upgrade_config.py`, `setup/_run_module.py` | Config upgrade helper; module runner used to start servers |
| `setup/verify_layout.py` | Static scan: required files, no machine values, no arbitrary-code tools |
| `runtime/` | Python package `rerate_mcp_v2`: 6 MCP servers (`servers/`), geometry adapters, in-app Ansys scripts (`app_scripts/`), case schema, report |
| `runtime/materials/` | Notes on material files (no Ansys material data ships here) |
| `examples/01_nasa_hecc/` | Worked example: `prompt.md`, `inputs/` (3 customer documents), `case.yaml`, `materials/`, `data_source.yaml`, `expected.md` |
| `docs/` | `HOW-IT-WORKS.md`, `TROUBLESHOOTING.md`, `VALIDATION.md`, `DECISIONS.md`, `ROADMAP.md`, `BUILD_PLAN.md` (maintainer note) |
| `tests/` | Unit tests (no Ansys needed) |
| `dev/` | Maintainer tools (`mcp_call.py`, `clean_clone_test.py`); not used by either agent |
| `LICENSE`, `THIRD_PARTY_NOTICES.md`, `SECURITY.md`, `CONTRIBUTING.md` | Legal, security and contribution notes |

## How a report scores results

`REPORT.md` is built by `case_v2.build_report` from the active run's `run.json` only, never from older runs.

- **PASS / FAIL:** a measured value from this run against the case target.
- **FAIL (model-limited):** a FAIL where the stage declared fidelity limits (for example single passage, no
  diffuser). The FAIL stands; the label says why it may not reflect the real machine.
- **NOT CHECKED:** no stage produced the value. Never counted as a PASS.
- **Calibration gate:** unless a matching baseline run says CALIBRATED, CFD rows cannot PASS. A would-be PASS
  becomes NOT CHECKED with "model not calibrated"; unconverged CFD is never scored.
- **Design point at target flow:** a re-rated design is evaluated at its target flow (targeted mass flow, with a
  speedline fallback). Choke below the target is a real FAIL with the maximum flow. No converged point at the
  target means NOT CHECKED.

Verdict lines: `PASS`, `FAIL: n of m checks fail`, or `PASS ON CHECKED ITEMS ONLY` (not a release PASS).

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md). Design decisions and their reasons: [docs/DECISIONS.md](docs/DECISIONS.md).

## Development

Use the install-home venv Python (or any Python 3.12/3.13 with `setup/requirements.lock` installed):

```
python -m unittest discover -s tests
python setup/verify_layout.py
python setup/check.py
```

Maintainer tools in `dev/` are not used by either agent. Rules for changes: [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache License 2.0, see [LICENSE](LICENSE). Third-party notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Ansys is a trademark of ANSYS, Inc.; this project is not affiliated with or endorsed by Ansys.
