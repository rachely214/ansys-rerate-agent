---
name: rerate-report
description: "Use when writing the pass/fail report at the end of a compressor re-rate run. Builds the scorecard from this run only."
version: 1.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, report]
    related_skills: [rerate-run, rerate-cfd]
---

# Report

Tool: `case_v2.build_report {}`. It reads only the active run's recorded stages and the approved case.

Success: REPORT.md written in the run folder, with a verdict line and one scorecard row per check.

## Result labels (do not rename them)
- PASS / FAIL: measured value vs the case target.
- FAIL (model-limited): a FAIL from a stage that declared simplifications (single passage, no diffuser). It is
  still a FAIL. Tell the user the model may be the cause and what model would settle it.
- NOT CHECKED: no stage produced a usable value (not run, not converged, or model not calibrated). Never present
  it as passing.
- NOT REQUESTED: the case has no target for it.
- Verdict "PASS ON CHECKED ITEMS ONLY" is not a release PASS. Say so.

## Final message
Follow the final-answer format in `rerate-run`. In "Needs your review" list:
1. each FAIL (model-limited) with the fidelity reason,
2. each NOT CHECKED row and what would check it,
3. every case value whose source starts with ENGINEERING CHOICE,
4. any stage warning you saw (failed fillet, stress peak on a cut face, non-converged solve, model not
   calibrated).
Then `MEDIA:` the REPORT.md path and the images listed by `build_report`.
