---
name: rerate-geometry
description: "Use when changing and building compressor impeller geometry in a re-rate. Applies the sized exit-height change and builds solids."
version: 1.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, geometry, discovery, adapter]
    related_skills: [rerate-run, rerate-structural]
---

# Geometry: read, change, build

Tools (`geometry_v2`): `inspect_geometry {}`, `apply_exit_height_change {blend_start_fraction, scale?, reason}`,
`build_start {stride, theta_margin_deg, le_pad, root_fillet?}`, `job_status {}`, `screenshot {}`,
`close_discovery {}`.

Success: new exit height equals the sizing target, the impeller solid is closed, and the single-blade STEP for
the structural stage exists.

## Method
1. `inspect_geometry {}` and cross-check against the case before changing anything:
   - `exit_blade_height_from_geometry` vs the case value: within a few percent is normal (the datasheet may quote
     a nominal or a different station). Over about 5%: stop and ask; the adapter options may be wrong.
   - `blade_count_matches_case` must be true.
2. `apply_exit_height_change {blend_start_fraction, reason}`. Scale defaults to the sizing ratio.
   - `blend_start_fraction` = where (as a fraction of the trailing-edge radius) the shroud starts to move. The
     inducer and inlet radii must stay fixed (they are casing walls), so start the blend well outside the inducer
     tip radius. Choose it from the meridional shape and say why. A start at about 1.4 times the inducer tip
     radius (as a fraction of the trailing-edge radius) usually keeps the whole inlet unchanged; compute it for
     this impeller, do not reuse a number from another case.
   - Check the returned exit height equals the sizing target.
3. `build_start {stride, theta_margin_deg, le_pad}` (visible Discovery, background job). Wait a few minutes,
   then call `job_status`; repeat with a one-line status each time. State the values you chose:
   - `stride`: use every Nth resampled section point for the loft (lower = finer, slower). Example: stride 4
     worked for the NASA example, because it gives a smooth closed loft in a few minutes.
   - a few degrees of theta margin, and a small leading-edge pad in the case length unit. Example: theta margin
     4 deg and LE pad 0.15 in gave a single blade with a root fillet that Mechanical meshes on the NASA example;
     3 deg and 0.05 in left a sliver face next to the fillet that crashed the structural mesher.
   - Pass only if the impeller solid is closed and the single-blade STEP exists. Read the logs for `FAIL` lines
     (merge or fillet); a failed fillet is acceptable only if you say so in the report.
4. If the tool says Discovery must be closed before the next app, call `close_discovery {}` before meshing.

Print: `STAGE 3 | exit height <h> | impeller closed, volume <v> | single blade STEP ok | ok`.

## Pitfalls
- A reply saying the desktop is locked or disconnected, or a job in `timeout`, is a stop: report the step and
  stop. Do not retry blindly.
- `status: error` twice on launch means stop and report.
- The change is applied to the neutral geometry, so it works for any adapter; never edit curve files by hand.
