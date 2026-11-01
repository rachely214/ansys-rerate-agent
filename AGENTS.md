# Agentic compressor re-rate workflow

Load `agents/rerate-engineer/SOUL.md`, then the `rerate-run` skill for re-rate work. If skill discovery is
unavailable, read the corresponding SKILL.md in `agents/rerate-engineer/skills/` directly. Machine data lives in
each case's `case.yaml`; method and order live in `rerate-run`. README and SETUP own installation. Validation
records and example outputs are evidence, not instructions.

One agent owns the dependent stages. Drive Ansys only through the six limited-action MCP servers in `plugins/ansys-mcp/`. Do not
substitute a script, a saved result or an earlier run's numbers for a live tool call.

## Invariants

- The Ansys apps run on this Windows desktop as the logged-in user. GUI mode needs a connected, unlocked desktop.
- Student license: one Ansys app at a time. Each stage closes its app.
- No simulation before the case is approved. Editing an approved case invalidates it.
- Long actions are start / status / fetch. Never block a call for minutes.
- Two failures on the same step: stop and report the exact error. Do not loop on variations.
- Never change targets, tolerances or measured values to make a check pass. No correction factors.
- NOT CHECKED is a valid result. A CFD-based check without a converged, calibrated result is never PASS.
- Approval denial or timeout is a stop condition.

## Files and scope

Run outputs go to `<install home>/runs/<case>_<timestamp>/` (install home: `%LOCALAPPDATA%/ansys-rerate-agent`).
Do not read earlier run folders during a run.

Before code changes, read the relevant files, add regression tests and run them. Do not commit or push unless
authorized.
