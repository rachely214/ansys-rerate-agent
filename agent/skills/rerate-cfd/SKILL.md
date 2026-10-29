---
name: rerate-cfd
description: "Use when running the Fluent passage CFD stage of a compressor re-rate. Calibrates on the baseline, then evaluates the design at its target flow."
version: 1.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, fluent, cfd]
    related_skills: [rerate-run, rerate-meshing, rerate-report]
---

# CFD (Fluent, rotating single passage), non-blocking

Tools (`fluent_v2`): `connect_start`, `setup_start`, `prep_status`, `solve_start {chunk, time_limit_s}`,
`solve_status`, `solve_stop`, `solve_fetch`, `set_back_pressure`, `restore_case_back_pressure`,
`set_design_flow_target`, `speedline_result`, `model_check`, `images`, `disconnect`.
Also `case_v2.calibrate_cfd {baseline_run_dir}` and `case_v2.run_status {}`.

Success: a converged result recorded as stage `cfd`, judged against a calibration baseline, with the outlet
condition (case back pressure, design flow target, or speedline) stated.

## Method
1. `connect_start {}`, then wait a minute and call `prep_status` until finished. It says CPU or GPU, core count
   and GUI or no-GUI. Tell the user which.
2. `setup_start {}`, then `prep_status` until finished: imports this run's passage mesh, applies the case
   operating point, initialises. If this run already has a recorded `cfd` stage (`case_v2.run_status`), reuse
   it; do not solve again.
3. `solve_start {chunk, time_limit_s}`: chunk about 50; time limit from your time budget (say it). The iteration
   cap is `cfd.max_iterations` from the case.
4. Wait a few minutes, then call `solve_status`. Repeat. One line each time: iterations, PR, efficiency, mass
   imbalance. Do not call `setup_start` or `solve_start` while a solve is running.
5. When `state` is `finished`: `solve_fetch {}` (the result is also recorded automatically). If `state` is
   `error`, report it; retry once via `disconnect`, `connect_start`, `setup_start`, `solve_start`.
6. `images {}` for the contour pictures. If the tool says Fluent must be closed before the next app, call
   `disconnect {}`.

## Convergence rule
`converged: false` means the numbers are not final; they are never scored. Converged = mass imbalance under the
case limit on every sample of the stability window AND the max-min spread of flow, PR and efficiency over that
window under the case stability tolerance. An end-point check alone is not enough, because a solve can look
settled on its last sample while still drifting.

## Calibration gate
The design result only counts if a BASELINE run (unmodified geometry; same mesh topology, splitter, size factor,
turbulence model, rotation and outlet radius) was compared with measured data by
`case_v2.calibrate_cfd {baseline_run_dir}` and came out CALIBRATED. Otherwise the report says "model not
calibrated" and aero rows cannot PASS. Never change tolerances or measured values, never scale a result.

## Physics checks
- Rotation sign is a geometry property: for a backswept impeller the outlet RELATIVE swirl must oppose the
  rotation. Same-sign relative swirl means the impeller turns backwards. Use `model_check` if in doubt.
- Choked points (flow constant while back pressure changes) are valid, converged points: they give the maximum
  flow of the passage.
- Corrected flow uses the case reference pressure and temperature and the main blade count.

## Re-rated designs: evaluate at the target flow
The measured exit pressure belongs to the baseline machine, so a design run is evaluated at its target flow:
1. Start field: `set_back_pressure {low value, e.g. 1.6 x inlet total, reinitialize: true}` and solve until
   `solve_status` reports `converged`. If this choke flow is BELOW the target, that is a real FAIL: report the
   choke flow as the maximum flow.
2. Otherwise `set_design_flow_target {reason}` and `solve_start` (targeted mass flow; outlet pressure floats).
   A run that ends `choked below target flow` is a real FAIL with the maximum flow.
3. If it is unstable (outlet pressure runs away, flow collapses, solver error), relaunch and run a speedline:
   3 to 5 back pressures from the tool's configured list, ascending, each to convergence; then
   `speedline_result {reason}` interpolates PR and efficiency at the target flow (no extrapolation).
4. If no converged point brackets the target, the aero rows are NOT CHECKED. Say so; never estimate.

## Start path at a high back pressure
A cold start directly at a high outlet pressure can stall the passage. Use back-pressure continuation:
`set_back_pressure {lower value, reinitialize: true}`, then `solve_start` and let it run until `solve_status`
reports `converged` (stop reason `converged`; typically 500 to 800 iterations). Do NOT stop it early because the
flow looks flat: a start field that is still moving can tip the step-up onto the stall side.
`restore_case_back_pressure` refuses until the start field is converged. Then call it and `solve_start`. The
result is recorded as stage `cfd` with its start path. If the solve at the case value still collapses (inlet
reversal rising, flow falling), stop and report "did not converge (stall at the case back pressure)"; never
lower the case value to get a number.

Print: `STAGE 5 | PR <x> | eta <y> | corrected flow <q> <unit> | converged yes/no (<n> it) | calibrated yes/no | ok/partial`.
