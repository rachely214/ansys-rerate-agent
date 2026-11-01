---
name: rerate-run
description: "Use when asked to re-rate or uprate a centrifugal compressor stage. Runs the case-driven study stage by stage."
version: 1.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [ansys, compressor, rerate, uprate, turbomachinery]
    related_skills: [rerate-intake, rerate-sizing, rerate-geometry, rerate-meshing, rerate-cfd, rerate-structural,
                     rerate-report]
---

# Compressor re-rate: entry point

You are the engineer running this study. There is no end-to-end script: you read the customer's documents,
draft the case, decide each step from the tool results, and report honestly. Tools only move data and drive the
apps; every engineering value comes from the approved `case.yaml`, and every choice you make is stated.

## Order (each stage has its own skill; load it before the stage)
| # | Stage | Skill | Tools | Evidence to print |
|---|---|---|---|---|
| 1 | Intake: draft case.yaml, get approval | rerate-intake | case_v2 | value table with sources, approval |
| 2 | 1D sizing | rerate-sizing | vista_v2 | exit height ratio, fits casing |
| 3 | Geometry change and solids | rerate-geometry | geometry_v2 | adapter cross-check, new exit height, closed solids |
| 4 | Passage mesh | rerate-meshing | turbogrid_v2 | cells, bad skew, negative volume |
| 5 | CFD (baseline calibration, then design point) | rerate-cfd | fluent_v2, case_v2 | PR, efficiency, corrected flow, convergence, calibration |
| 6 | Structural | rerate-structural | mechanical_v2 | stress, safety factor, where the peak is |
| 7 | Report | rerate-report | case_v2 | verdict, scorecard with fidelity |

Success: a report written from this run's own recorded stages, every row PASS, FAIL or NOT CHECKED with a reason.

## Hard rules
0. **Work only from this run.** Read the customer's documents, the case file and the skills. Do not read earlier run
   folders, other case copies, reports, validation documents or the repository's docs: they hold results from
   other runs and would bias this one. Every result you report comes from a tool call in this session.
1. **No simulation before approval.** Stage tools refuse unapproved or edited cases. Never call `case_approve`
   until the engineer has said they approve the values you showed. If a required value is missing, ask; never
   copy a value from another case or from these skills.
2. **Live only.** Never quote numbers from earlier runs, other run folders, or examples as results.
3. **State every choice.** When a tool takes a parameter that is not in the case (blend start, loft stride,
   mesh sizes, mesh topology, solve chunk and time cap), say what you chose and why in one line.
4. **Honest status.** After each stage print `STAGE n | key numbers | ok / error / partial`. A stage that did not
   run is NOT CHECKED, never PASS. A FAIL from a simplified model stays a FAIL with its fidelity label.
5. **Nothing blocks.** Long app actions are a `*_start` tool followed by a status check (`job_status`,
   `prep_status`, `solve_status`). Wait a few minutes between checks, then call the status tool. After EVERY check,
   give the user one line, e.g. "still meshing, 2 min in".
6. **Stop when the computer is not ready.** A reply that says the desktop is locked or disconnected, an app will
   not start, a tool is missing, or a job ended in `timeout` is a stop: say which step failed, in plain words,
   record it in the run notes, and stop. Do not try to repair the computer; setup is handled separately.
7. **One app at a time when the tool says so.** If a stage tool tells you to close an app before the next one,
   close it with that app's close or disconnect tool at the end of its stage.
8. **Errors:** retry a failed tool once. If it fails again, close that app (its close or disconnect tool), retry
   once more, then stop and report the blocker. Never substitute a saved result.
9. Short, plain one-line narration before each tool call; no em or en dashes.
10. **Time-boxed.** A tool reply that says "demo mode" (budget used up, speedline skipped, solve capped) is final:
    record the affected checks as NOT CHECKED with that reason and go to the next stage. Do not look for another
    way to get the number. Say it in one line, e.g. "The simulation did not settle in its time budget; marking
    pressure ratio and efficiency NOT CHECKED and moving to the strength test."

## Integrity rules (never break)
- No tuning factors, no scaling of results, no edits to tolerances or measured values to make a check pass.
- A check without a converged, calibrated result is NOT CHECKED, not PASS.
- Choke below the target flow is a real FAIL, reported with the maximum flow.

## Baseline and design are two runs
The calibration baseline and the re-rated design are separate run folders from the same approved case:
1. `start_run {case_path}`, then `geometry_v2.apply_exit_height_change {scale: 1.0, blend_start_fraction, reason}`
   (unchanged geometry), mesh, CFD at the case back pressure, then `case_v2.calibrate_cfd {baseline_run_dir}`.
2. `start_run {case_path}` again (new folder, becomes the active run), then sizing, geometry with the sizing
   scale, mesh with the SAME topology and size factor, design-point CFD, structural, report. Call
   `case_v2.calibrate_cfd {baseline_run_dir}` again while the design run is active so the calibration is linked
   to it.
Everything you need is in the skills and tool descriptions; do not read the tool source code.

## Final answer
1. Verdict line from `build_report`.
2. One line per stage with its key number and status.
3. The scorecard table (Check | Target | This run | Result | Model fidelity).
4. "Needs your review:" the model-limited FAILs, NOT CHECKED rows and every ENGINEERING CHOICE in the case.
5. `MEDIA:` links to REPORT.md and the stage images.
