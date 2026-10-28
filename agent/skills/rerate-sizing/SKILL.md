---
name: rerate-sizing
description: "Use when running the 1D Vista CCD sizing stage of a compressor re-rate. Turns the new duty into an exit-height change."
version: 1.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, vista, sizing]
    related_skills: [rerate-run]
---

# Sizing (Vista CCD, 1D)

Tools (`vista_v2`): `size_start {extra_inputs?}` (background job), `job_status {}`, `open_gui {}`, `status {}`.

What it does: two Vista designs at the case speed and blade counts: baseline duty (baseline mass flow and
pressure ratio) and target duty (mass flow scaled by target over baseline corrected flow, target pressure ratio).
The ratio of Vista's exit blade heights is applied to the case exit height.

Success: `job_status` is `finished` with an exit height scale and a `fits_casing` answer.

## Method
1. `size_start {}`. Wait a few minutes, then call `job_status`; repeat with a one-line status each time.
2. When finished, `open_gui {}` so the design is visible. A `warning` while the window starts is fine.

## Judge the result
- `fits_casing`: new exit height vs `limits.exit_blade_height_max`. If false, say the 1D estimate already exceeds
  the casing and ask the engineer whether to continue (a different design lever is needed).
- `inducer_tip_rel_mach` rising toward 0.9 or above: flag shock-loss and choke risk.
- Vista efficiency change is a 1D correlation trend, not a prediction of the real efficiency.
- `extra_inputs`: only pass Vista properties you can justify (e.g. backsweep from the datasheet). State them.

Print: `STAGE 2 | scale <x> | exit height <h> <unit> vs limit <l> | fits: yes/no | ok`.

## Pitfalls
- The batch run occasionally ends without a result; the tool retries once. If it fails twice, report the message
  in the reply and stop.
