---
name: rerate-sizing-v2
description: "Use when running the 1D Vista CCD sizing stage of a compressor re-rate (V2)."
version: 2.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, vista, sizing, v2]
    related_skills: [rerate-run-v2]
---

# Sizing (Vista CCD, 1D)

Tools: `vista_v2.size_start {extra_inputs?}` (background, Workbench batch), poll `vista_v2.job_status` every
30 to 60 s with a one-line status each time, then `vista_v2.open_gui {}` so the design is visible (skipped in
headless mode).

What it does: two Vista designs at the case speed and blade counts: baseline duty (baseline mass flow and
pressure ratio) and target duty (mass flow scaled by target/baseline corrected flow, target pressure ratio).
The ratio of Vista's exit blade heights (B5) is applied to the case exit height.

## Judge the result
- `fits_casing`: new exit height vs `limits.exit_blade_height_max`. If false, say the 1D estimate already exceeds
  the casing and ask the engineer whether to continue (a different design lever is needed).
- `inducer_tip_rel_mach` rising toward 0.9 or above: flag shock-loss and choke risk.
- Vista efficiency change is a 1D correlation trend, not a prediction of the real efficiency.
- `extra_inputs`: only pass Vista properties you can justify (e.g. backsweep from the datasheet). State them.

Print: `STAGE 2 | scale <x> | exit height <h> <unit> vs limit <l> | fits: yes/no | ok`.

## Pitfalls
- Workbench batch occasionally exits without a result; the tool retries once. Two failures: check
  `license_denials` in the reply and stop.
- `open_gui` may return `warning` while Workbench starts; that is fine, continue.
