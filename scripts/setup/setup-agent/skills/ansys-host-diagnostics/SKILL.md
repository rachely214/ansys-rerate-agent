---
name: ansys-host-diagnostics
description: "Use when an Ansys app will not start or a license or desktop problem blocks the re-rate demo. Plain checks and fixes."
version: 1.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [ansys, license, desktop, troubleshooting]
    related_skills: [setup-run, setup-diagnose]
---

# Ansys host diagnostics

For the computer the demo runs on. The demo agent's six tool servers are `case_v2`, `vista_v2`, `geometry_v2`,
`turbogrid_v2`, `fluent_v2`, `mechanical_v2` (package `rerate_mcp_v2`, installed in the install home's `venv`).
Their settings are in `machine.config.yaml` in the install home (`%LOCALAPPDATA%\ansys-rerate-agent`).

Success: the health check's ansys, config and mcp groups are PASS.

## Desktop session
- Every Ansys window needs an active, unlocked Windows desktop. A closed Remote Desktop window disconnects the
  session: Discovery then hangs at launch ("Direct3DCreate9Ex failed"), Fluent cannot import the mesh, and Fluent
  has crashed mid-solve with "connection reset". The tools check the session and refuse with
  `desktop_disconnected` or `desktop_locked`.
- Fix: sign in at the computer, or keep the Remote Desktop window open (minimised is fine). Turn off the screen
  lock for the length of a run.
- Optional: `apps.<app>.mode: headless` in machine.config.yaml runs Fluent without a window and Mechanical in
  batch. TurboGrid meshing and Vista sizing always run in the background. Discovery has no headless mode.
- `apps.<app>.launch_timeout_s` and `job_timeout_s` bound every launch and background job; a job past its limit
  shows `timeout`.

## Licensing
- Student license: one Ansys app at a time (`license.mode: student` makes every stage close other apps first),
  1M CFD cells, 128k structural nodes, no Fluent GPU solver. Set `fluent.gpu: true` only with a license that
  includes it.
- License denials are logged in `%TEMP%\.ansys\licdebug.*.out`; the health check reports recent ones. Quote the
  line to the user. Common causes: another Ansys app still open (Student), license server unreachable (commercial).
- Never change license settings or files; a license administrator must fix commercial license problems.

## Apps left running
- Crashed Fluent sessions leave `fluent`, `cx2610`, `fl2610`, `mpiexec` or `hydra_pmi_proxy` processes that hold
  the license. Ask the user before closing them (Task Manager, or `taskkill /F /IM <name>.exe` in a Windows
  command prompt).

## Tool servers
- After `install_runtime.py packages` or `profile`, Hermes may still run old server processes. The user must close
  Hermes completely (tray icon too) and reopen it; the check's `stale_servers` item shows this.
- Hermes gives tool servers a reduced environment. The servers get everything from `RERATE_CONFIG` (set by the
  installer); do not add other variables by hand.
- New or changed tools appear only in a NEW chat after Hermes restarts.
- After updating the repository, run `PY scripts/setup/upgrade_config.py` to add new settings to machine.config.yaml.

## Known app behaviours (handled in the tools; listed so you recognise them)
- Discovery 2026 R1 needs the older gRPC protocol ("File X.py does not exist" otherwise); the geometry tool forces it.
- Servers started from `C:\Windows\System32` cannot write logs there; they switch to the install home's `work`.
- No tool runs arbitrary code inside an app. Do not work around a missing capability with scripts that drive the
  apps.

## Agent elsewhere, Ansys here (not validated)
Set `mcp.servers.<name>: {transport: http, host: 127.0.0.1, port: <p>}` in machine.config.yaml, start each
server on this computer, and register them by URL in the remote agent. The servers have no authentication: keep
them on a private address.
