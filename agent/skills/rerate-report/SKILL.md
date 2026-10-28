---
name: rerate-report-v2
description: "Use when writing the pass/fail report at the end of a compressor re-rate run (V2)."
version: 2.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, report, v2]
    related_skills: [rerate-run-v2]
---

# Report

Tool: `case_v2.build_report {}`. It reads only the active run's recorded stages and the approved case.

## Result labels (do not rename them)
- PASS / FAIL: measured value vs the case target.
- FAIL (model-limited): a FAIL from a stage that declared simplifications (single passage, no diffuser, not
  converged). It is still a FAIL. Tell the user the model may be the cause and what model would settle it.
- NOT CHECKED: no stage produced the value. Never present it as passing.
- NOT REQUESTED: the case has no target for it.
- Verdict "PASS ON CHECKED ITEMS ONLY" is not a release PASS.

## Final message
Follow the entry skill's final-answer format. In "Needs your review" list:
1. each FAIL (model-limited) with the fidelity reason,
2. each NOT CHECKED row and what would check it (roadmap),
3. every case value whose source starts with ENGINEERING CHOICE,
4. any stage with a warning you saw (failed fillet, stress peak on a cut face, non-converged solve).
Then `MEDIA:` the REPORT.md path and the images listed by `build_report`.
