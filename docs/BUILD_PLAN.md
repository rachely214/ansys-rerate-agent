# BUILD_PLAN.md: maintainer note on how this repository was built (not user documentation; start at START-HERE.md)

Repo: `ansys-rerate-agent`. Built from `compressor-rerate-agent-v2` (commit 68dbd2a), which stays as history.

## Two phases (the core design)

| Phase | Who | What | Done when |
|---|---|---|---|
| 1. Setup | **Setup agent** (Hermes profile `ansys-rerate-setup`) + **deterministic health check** (`setup/check.py`) | Installs and wires everything on this machine, iteratively, using setup skills | `check.py` reports ALL GREEN |
| 2. Demo | **Demo agent** (Hermes profile `ansys-rerate-agent`) | Engineering only: documents -> case -> sizing -> geometry -> mesh -> CFD -> structural -> report | Report written |

The demo agent is BLIND to setup: its skills and SOUL never mention Python versions, pip, Hermes restarts, MCP loading,
stale processes or config files. If a tool fails it reports the failure in plain words and stops; it does not repair
the environment. All environment knowledge lives in the setup agent's skills and in `check.py`.

## Layout

```
START-HERE.md                     plain-language entry for a non-technical user
README.md                         what this is, honest status and limits, architecture
agent/                            Hermes profile distribution: DEMO agent
  distribution.yaml  SOUL.md  config.yaml  mcp_servers.json (template)  skills/<8 rerate-* skills>
runtime/                          Python package rerate_mcp_v2 (6 MCP servers + in-app Ansys scripts)
  pyproject.toml  src/rerate_mcp_v2/...  materials/
setup/
  setup-agent/                    Hermes profile distribution: SETUP agent (SOUL + setup skills)
  check.py                        deterministic health check (no LLM); PASS/FAIL per item + plain fix
  install_runtime.py              deterministic installer steps the setup agent calls (venv, pip, config, profile)
  requirements.lock               pinned packages
  machine.config.template.yaml    -> %LOCALAPPDATA%/ansys-rerate-agent/machine.config.yaml (per machine)
  fetch_example_data.py  verify_layout.py  upgrade_config.py  _run_module.py
examples/01_nasa_hecc/            prompt.md, inputs/, case.yaml, materials/, data_source.yaml, README.md (expected outcome: docs/examples/01_nasa_hecc_expected.md)
docs/                             HOW-IT-WORKS.md, VALIDATION.md, DECISIONS.md, ROADMAP.md, TROUBLESHOOTING.md
tests/                            unit tests (no Ansys)
dev/                              maintainer tools (mcp_call.py, clean_clone_test.py); not used by either agent
```

## Machine state (never in git)

- Install home: `%LOCALAPPDATA%\ansys-rerate-agent\` -> `venv\`, `machine.config.yaml`, `example-data\`, `runs\`, `work\`, `downloads\`, `logs\`.
  Keeps OneDrive / long paths / repo location out of the picture.
- Hermes profiles under the Hermes home (installed with `hermes profile install`).
- MCP server entries: rendered at install time from `agent/mcp_servers.json` with the venv Python path and
  `RERATE_CONFIG` (the machine config path), written into the demo profile's `config.yaml`.

## Conventions
- Windows only for the Ansys side (Ansys GUIs need a Windows desktop); detected and stated plainly, not assumed.
- Python 3.13 in its own venv; never the Hermes-bundled Python.
- Model: Claude Opus via the user's provider for now; model choice lives only in each profile's config.
- Integrity rules from V2 unchanged: no tuning factors, honest NOT CHECKED, no machine values in code.
