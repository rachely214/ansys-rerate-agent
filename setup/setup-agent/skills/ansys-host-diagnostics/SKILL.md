---
name: ansys-mcp-host-v2
description: "Use when setting up or troubleshooting the V2 Ansys MCP servers for the re-rate workflow."
version: 2.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [ansys, mcp, setup, troubleshooting, v2]
    related_skills: [rerate-run-v2]
---

# Ansys MCP servers (V2): setup and troubleshooting

Servers (stdio by default, or HTTP from the config): `case_v2`, `vista_v2`, `geometry_v2`, `turbogrid_v2`,
`fluent_v2`, `mechanical_v2`. Package: `plugins/ansys-mcp` (`rerate_mcp_v2`). One config file:
`.local/rerate.config.yaml` (or env `RERATE_V2_CONFIG`). Install and registration: root `SETUP.md`.

## Readiness (stage 0)
1. Confirm the tools are listed (six servers, about 26 tools). If none show, the Hermes profile is wrong or the
   servers failed to start: run `python scripts/setup/doctor.py --mcp` from the repo `.venv`.
2. `doctor.py --case <case.yaml>` also checks the case and that its geometry and material files exist.

## Run modes, timeouts and the desktop session
- `apps.<app>.mode` in the config: `gui` (visible windows, demos) or `headless`. Mechanical runs batch, Fluent
  no-GUI, TurboGrid meshing is always headless (its window is only a demo view), Vista sizing is always batch.
  Discovery has no supported headless mode for scripted geometry and refuses with a clear message.
- GUI apps need a connected, unlocked Windows session. A closed Remote Desktop window disconnects the session:
  Discovery then hangs at launch ("Direct3DCreate9Ex failed" in its log). Every GUI start tool checks the
  session first and returns `desktop_disconnected` / `desktop_locked` instead of hanging.
- `apps.<app>.launch_timeout_s` and `job_timeout_s` bound every launch and background job; a job past its limit
  shows state `timeout` and the agent must stop and report.
- After pulling a newer version run `python scripts/setup/upgrade_config.py` to add new config keys.

## Known behaviours
- Student license: one solver seat. With `license.mode: student` every stage closes the other Ansys apps first.
- Discovery 2026 R1 with ansys-geometry-core 0.18: the V1 gRPC protocol breaks `run_script_file` ("File X.py does
  not exist"); geometry_v2 forces `proto_version="v0"`.
- MCP hosts may start servers with cwd = System32, where TurboGrid/Fluent cannot write logs. Servers chdir to
  `paths.work_dir` at start.
- Fluent GPU: set `fluent.gpu: true` only with a license that includes it; on Student the GPU solver is denied.
- `license_denials` in a tool error comes from `%TEMP%/.ansys/licdebug.*.out`; quote it to the user.
- Stale Fluent `mpiexec`/`hydra_pmi_proxy` processes block relaunch: `fluent_v2.disconnect` kills them.
- No tool runs arbitrary code inside an app. If you need something the tools cannot do, say so; do not work
  around it with shell scripts that drive the apps.

## Running in a sandbox (e.g. NVIDIA OpenShell) with Ansys on Windows
Set `mcp.servers.<name>: {transport: http, host: 0.0.0.0, port: <p>}` in the config, start each server on the
Windows host (`python -m rerate_mcp_v2.servers.<x>_server`), and register them in the sandboxed agent by URL.
Not yet validated (see docs/VALIDATION.md).
