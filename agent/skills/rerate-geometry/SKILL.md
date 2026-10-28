---
name: rerate-geometry-v2
description: "Use when changing and building compressor impeller geometry in a re-rate (V2)."
version: 2.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, geometry, discovery, adapter, v2]
    related_skills: [rerate-run-v2]
---

# Geometry: read, change, build

Tools (`geometry_v2`): `inspect_geometry`, `apply_exit_height_change`, `build_start` + `job_status`,
`screenshot`, `close_discovery`.

## Method
1. `inspect_geometry {}` and cross-check against the case before changing anything:
   - `exit_blade_height_from_geometry` vs the case value: within a few percent is normal (the datasheet may quote
     a nominal or a different station). Over about 5%: stop and ask; the adapter options may be wrong.
   - `blade_count_matches_case` must be true.
2. `apply_exit_height_change {blend_start_fraction, reason}`. Scale defaults to the sizing ratio.
   - `blend_start_fraction` = where (as a fraction of the trailing-edge radius) the shroud starts to move. The
     inducer and inlet radii must stay fixed (they are casing walls), so start the blend well outside the inducer
     tip radius. Choose it from the meridional shape and say why.
   - Check the returned exit height equals the sizing target.
3. `build_start {stride, theta_margin_deg, le_pad}` (visible Discovery, background job), then poll
   `job_status` every 30 to 60 s with a one-line status. A `desktop_disconnected`/`desktop_locked` reply or a
   `timeout` state is a stop: tell the user, do not retry blindly. Start with stride 4 (lower =
   finer loft), a few degrees of theta margin, and a small LE pad in the case length unit. State the values.
   - Pass only if the impeller solid is closed and the single-blade STEP exists. Read the logs for `FAIL` lines
     (merge/fillet); a failed fillet is acceptable only if you say so in the report.
4. On a Student license call `close_discovery` before meshing.

Print: `STAGE 3 | exit height <h> | impeller closed, volume <v> | single blade STEP ok | ok`.

## Pitfalls
- Discovery launch can take a minute and retries itself; `status: error` twice means stop and report.
- The change is applied to the neutral geometry, so it works for any adapter; never edit curve files by hand.
