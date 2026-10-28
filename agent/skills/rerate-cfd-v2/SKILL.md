---
name: rerate-cfd-v2
description: "Use when running the Fluent passage CFD stage of a compressor re-rate (V2)."
version: 2.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, fluent, cfd, v2]
    related_skills: [rerate-run-v2]
---

# CFD (Fluent, rotating single passage), non-blocking

Tools (`fluent_v2`): `connect_start`, `setup_start`, `prep_status`, `solve_start`, `solve_status`, `solve_stop`,
`solve_fetch`, `images`, `disconnect`. No call blocks for long; the solve runs in the background.

## Method
1. `connect_start {}`, poll `prep_status` until finished: it says CPU or GPU, core count and GUI or no-GUI
   (from the config). Tell the user which.
2. `setup_start {}`, poll `prep_status`: imports this run's passage mesh, applies the case operating point,
   hybrid-initialises.
   If this run already has a recorded `cfd` stage (`case_v2.run_status`), reuse it; do not solve again.
3. `solve_start {chunk, time_limit_s}`: chunk about 50; time limit from your time budget (say it).
   Iteration cap is `cfd.max_iterations` from the case.
4. Poll: run `sleep 240` (shell, under 5 minutes), then `solve_status`. Repeat. Report progress in one line each
   time: iterations, PR, efficiency, mass imbalance. Do not call `setup` or `solve_start` while running.
5. When `state` is `finished`: `solve_fetch {}` (the result is also recorded automatically). If `state` is
   `error`, report it; retry once via `disconnect`, `connect_start`, `setup_start`, `solve_start`.
6. `images {}` for the contour pictures, then (Student) `disconnect {}`.

## Judge the result
- `converged: false` means the numbers are not final. Report them as partial; the report labels them.
  Converged = mass imbalance under the case limit on every sample of the window AND flow/PR/eta max-min spread
  under the stability tolerance (DEC-14).
- Choked points (flow constant while back pressure changes) are valid, converged speedline points: they give the
  maximum flow of the passage.
- Calibration (DEC-16): the design result only counts if a BASELINE run (unmodified geometry, same mesh
  topology/splitter/size factor/turbulence/rotation/outlet radius) was compared with measured data by
  `case_v2.calibrate_cfd {baseline_run_dir}` and came out CALIBRATED. Otherwise the report says "model not
  calibrated" and aero rows cannot PASS. Never change tolerances or measured values, never scale a result.
- Rotation sign is a geometry property (DEC/C15): the outlet RELATIVE swirl must oppose the rotation for a
  backswept impeller. Same-sign relative swirl means the impeller turns backwards.
- Corrected flow uses the case reference pressure/temperature and the main blade count.

## Re-rated designs: evaluate at the target flow (DEC-19)
The measured exit pressure belongs to the baseline. For a design run:
1. Start field: `set_back_pressure {low value (e.g. 1.6 x inlet total), reinitialize: true}`, solve ~300 it.
   If its (choke) flow is BELOW the target, that is a real FAIL: report the choke flow as the maximum flow.
2. Otherwise `set_design_flow_target {reason}` and `solve_start`. Recorded as stage `cfd` (design flow target).
   A run that ends `choked below target flow` is a real FAIL with the maximum flow.
3. If it is unstable (outlet pressure runs away, flow collapses, solver error), relaunch, and run a speedline:
   3 to 5 back pressures from config `fluent.design_point.speedline_static_to_inlet_total`, ascending, each to
   convergence; then `speedline_result {reason}` interpolates PR/eta at the target flow (no extrapolation).

## Start path at a high back pressure
A cold hybrid start at the case outlet pressure can stall (PROGRESS C25). Use back-pressure continuation:
`set_back_pressure {lower value, reinitialize: true}`, solve until the flow is flat (about 300 it), `solve_stop`,
then `restore_case_back_pressure {reason}` and `solve_start`. The result is recorded as stage `cfd` with its
start path. If the case-value solve still collapses (inlet reversal rising, flow falling), stop and report "did
not converge (stall at the case back pressure)"; never lower the case value to get a number.

Print: `STAGE 5 | PR <x> | eta <y> | corrected flow <q> <unit> | converged yes/no (<n> it) | ok/partial`.
