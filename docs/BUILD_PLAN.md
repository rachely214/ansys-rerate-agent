# BUILD_PLAN.md: maintainer note on how this repository was built (not user documentation; start at README.md)

Repo: `ansys-rerate-agent`. Built from `compressor-rerate-agent-v2` (commit 68dbd2a), which stays as history.

## Two phases (the core design)

| Phase | Who | What | Done when |
|---|---|---|---|
| 1. Setup | **Setup agent** (Hermes profile `ansys-rerate-setup`) + **deterministic health check** (`scripts/setup/check.py`) | Installs and wires everything on this machine, iteratively, using setup skills | `check.py` reports ALL GREEN |
| 2. Demo | **Demo agent** (Hermes profile `ansys-rerate-agent`) | Engineering only: documents -> case -> sizing -> geometry -> mesh -> CFD -> structural -> report | Report written |

The demo agent is BLIND to setup: its skills and SOUL never mention Python versions, pip, Hermes restarts, MCP loading,
stale processes or config files. If a tool fails it reports the failure in plain words and stops; it does not repair
the environment. All environment knowledge lives in the setup agent's skills and in `check.py`.

## Layout

```
README.md, SETUP.md, setup.ps1    what this is, installation
agents/rerate-engineer/           DEMO agent: SOUL.md, skills/<8 rerate-* skills>
harnesses/hermes/                 Hermes profile distribution files: distribution.yaml, config.yaml,
                                  mcp_servers.json (template); the installer stages them with agents/rerate-engineer/
plugins/ansys-mcp/                Python package rerate_mcp_v2 (6 MCP servers + in-app Ansys scripts)
  pyproject.toml  src/rerate_mcp_v2/...  materials/
scripts/setup/
  setup-agent/                    Hermes profile distribution: SETUP agent (SOUL + setup skills)
  check.py                        deterministic health check (no LLM); PASS/FAIL per item + plain fix
  install_runtime.py              deterministic installer steps (venv, pip, config, example data, profile)
  requirements.lock               pinned packages
  machine.config.template.yaml    -> %LOCALAPPDATA%/ansys-rerate-agent/machine.config.yaml (per machine)
  fetch_example_data.py  verify_layout.py  upgrade_config.py  _run_module.py
scripts/dev/                      maintainer tools (mcp_call.py, clean_clone_test.py, stability_test.py); not used by either agent
examples/01_nasa_hecc/            prompts, inputs/, case.yaml, materials/, data_source.yaml, README.md
docs/                             HOW-IT-WORKS, VALIDATION, DECISIONS, ROADMAP, TROUBLESHOOTING, RELEASE_CHECKLIST;
                                  examples/01_nasa_hecc_expected.md
tests/                            unit tests (no Ansys)
```

## Machine state (never in git)

- Install home: `%LOCALAPPDATA%\ansys-rerate-agent\` -> `venv\`, `machine.config.yaml`, `example-data\`, `runs\`, `work\`, `downloads\`, `logs\`.
  Keeps OneDrive / long paths / repo location out of the picture.
- Hermes profiles under the Hermes home (installed with `hermes profile install`).
- MCP server entries: rendered at install time from `harnesses/hermes/mcp_servers.json` with the venv Python path and
  `RERATE_CONFIG` (the machine config path), written into the demo profile's `config.yaml`.

## Conventions
- Windows only for the Ansys side (Ansys GUIs need a Windows desktop); detected and stated plainly, not assumed.
- Python 3.13 in its own venv; never the Hermes-bundled Python.
- Model: Claude Opus via the user's provider for now; model choice lives only in each profile's config.
- Integrity rules from V2 unchanged: no tuning factors, honest NOT CHECKED, no machine values in code.
