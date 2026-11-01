---
name: rerate-intake
description: "Use when drafting a compressor re-rate case.yaml from customer documents. Gets explicit approval before any simulation."
version: 1.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, intake, case]
    related_skills: [rerate-run]
---

# Intake: from documents to an approved case.yaml

Input: the customer's re-rate request, baseline datasheet, casing and limit sheet, and a geometry source.
Output: an approved `case.yaml` beside the inputs, and a started run.

Tools (`case_v2`): `case_validate {case_path}`, `case_approve {case_path, approved_by}`, `start_run {case_path}`,
`run_status {}`. `case_validate` also returns the field list (fields, units, which stage needs what).

Success: `case_validate` shows no blocking issues, the engineer approved the shown table, `start_run` returned a
run folder.

## Method
0. **Work on a copy.** If the case file the user points to is part of an example or a shared folder, first copy
   that folder's `case.yaml` (and its `materials/` folder if present) into a new folder under the runs area
   (`<install home>\runs\cases\<case name>_<date>\`) and edit only the copy. In the copy, change
   `geometry.source` and `material.library_file` to ABSOLUTE paths of the original files right away (a relative
   path stops resolving once the file moves): the geometry data is under `<install home>\example-data\<example>\`,
   the material file is next to the original case. Then validate. Never edit the original example.
1. Read every document fully. List each number you can use, with document and section.
2. Write `case.yaml` next to the documents. Every quantity is `{value, unit, source}`.
   - `source` names the document and the table or section, e.g. `"02 datasheet, Operating point"`.
   - Use the document's own units; the tools convert.
   - When a value is your choice (not in the documents), start its source with `ENGINEERING CHOICE:` and say why.
     Typical ones: outlet static pressure for the passage CFD, hub-slice depth, fillet radius, inlet temperature
     if only "standard day" is implied. Never invent targets or limits.
   - File paths (`geometry.source`, `material.library_file`) may be relative to the case file.
3. `baseline.mass_flow` is the physical flow the 1D tool uses for the baseline duty. If the datasheet gives only
   corrected flow, convert at the 1D tool's inlet condition and say so in the source.
4. Geometry: pick the adapter that matches the source (`nasa_tables` or `bladegen_inf`). A STEP solid alone is not
   enough, because the change is made on blade curves, not on a solid; ask for a BladeGen or curve export. Adapter
   options describe the files (units, axis conventions); read them from the data's own documentation.
5. Call `case_validate`. Fix blocking issues you can fix from the documents. For anything still missing,
   STOP and ask the engineer one consolidated question listing each missing field and why it is needed.
6. Show the engineer the full value table from `case_validate.values`: Field | Value | Unit | Source, with the
   ENGINEERING CHOICE rows called out. Ask for approval in one clear question.
7. Only after an explicit "approve" (or corrections, then re-validate and re-show), call
   `case_approve {case_path, approved_by}` with the name they give, then `start_run {case_path}`.
   If the user's first message already approves on the engineer's behalf (a demo or unattended run), show the
   table anyway, then approve with `approved_by` naming that (e.g. "demo run, approved in the prompt") and go on.
   Pre-approval never covers a blocking issue from `case_validate`: those still stop the run.

## Pitfalls
- Do not reuse numbers from an example case for a different machine. Each case stands alone.
- Corrected flow needs a reference pressure and temperature: put them in the case explicitly.
- Rotation sign depends on the geometry's wrap direction; if unsure, say so and ask, or check with the
  geometry stage's `inspect_geometry` before approval. A wrong sign runs the impeller backwards.
- Editing case.yaml after approval invalidates it; the tools will refuse until it is re-approved.
- If a stage tool says the geometry or material file is not found, tell the user which file is missing and stop;
  do not search the computer for it.
