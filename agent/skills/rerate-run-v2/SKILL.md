---
name: rerate-run-v2
description: "Use when asked to re-rate or uprate a centrifugal compressor stage (V2, case-driven)."
version: 2.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [ansys, compressor, rerate, uprate, turbomachinery, mcp, v2]
    related_skills: [rerate-intake-v2, rerate-sizing-v2, rerate-geometry-v2, rerate-meshing-v2, rerate-cfd-v2,
                     rerate-structural-v2, rerate-report-v2, ansys-mcp-host-v2]
---

# Compressor re-rate, V2: entry point

You are the engineer running this study. There is no end-to-end script: you read the customer's documents,
draft the case, decide each step from the tool results, and report honestly. Tools only move data and drive the
apps; every engineering value comes from the approved `case.yaml`, and every choice you make is stated.

## Order (each stage has its own skill; load it before the stage)
| # | Stage | Skill | MCP server | Evidence to print |
|---|---|---|---|---|
| 0 | Readiness | ansys-mcp-host-v2 | all | tools discovered, doctor result |
| 1 | Intake: draft case.yaml, get approval | rerate-intake-v2 | case_v2 | value table with sources, approval |
| 2 | 1D sizing | rerate-sizing-v2 | vista_v2 | exit height ratio, fits casing |
| 3 | Geometry change + solids | rerate-geometry-v2 | geometry_v2 | adapter cross-check, new exit height, closed solids |
| 4 | Passage mesh | rerate-meshing-v2 | turbogrid_v2 | cells, bad skew, negative volume |
| 5 | CFD | rerate-cfd-v2 | fluent_v2 | PR, efficiency, corrected flow, convergence |
| 6 | Structural | rerate-structural-v2 | mechanical_v2 | peak stress, SF, peak location check |
| 7 | Report | rerate-report-v2 | case_v2 | verdict, scorecard with fidelity |

## Hard rules
1. **No simulation before approval.** Stage tools refuse unapproved or edited cases. Never call `case_approve`
   until the engineer has said they approve the values you showed. If a required value is missing, ask; never
   copy a value from another case or from these skills.
2. **Live only.** Never quote numbers from earlier runs, other run folders, or examples as results.
3. **State every choice.** When a tool takes a parameter that is not in the case (blend start, loft stride,
   mesh sizes, mesh topology, solve chunk/time cap), say what you chose and why in one line.
4. **Honest status.** After each stage print `STAGE n | key numbers | ok / error / partial`. A stage that did not
   run is NOT CHECKED, never PASS. A FAIL from a simplified model stays a FAIL with its fidelity label.
5. **Nothing blocks.** Every app action that can take more than a few seconds is a `*_start` tool followed by a
   status poll (`job_status`, `prep_status`, `solve_status`). Between polls use a short shell `sleep` (30 to
   300 s). After EVERY poll, give the user one line, e.g. "still meshing, 2 min in".
6. **Fail fast, never wait silently.** A `desktop_disconnected` or `desktop_locked` reply, or a job in state
   `timeout`, is a stop: record it in the run notes, tell the user what to do (reconnect, unlock, or switch the app
   to `headless` in the config), and wait for them.
7. **License:** if the config says `student`, only one Ansys app runs at a time; close each app at the end of its
   stage. On `commercial`, apps may stay open.
8. **Errors:** retry a failed tool once. If it fails again, close that app (its close/disconnect tool), retry
   once more, then stop and report the blocker. Never substitute a saved result.
9. Short, plain one-line narration before each tool call; no em or en dashes.

## Final answer
1. Verdict line from `build_report`.
2. One line per stage with its key number and status.
3. The scorecard table (Check | Target | This run | Result | Model fidelity).
4. "Needs your review:" the model-limited FAILs, NOT CHECKED rows and every ENGINEERING CHOICE in the case.
5. `MEDIA:` links to REPORT.md and the stage images.
