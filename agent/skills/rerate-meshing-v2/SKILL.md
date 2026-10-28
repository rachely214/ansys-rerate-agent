---
name: rerate-meshing-v2
description: "Use when meshing the compressor blade passage in TurboGrid during a re-rate (V2)."
version: 2.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, turbogrid, mesh, v2]
    related_skills: [rerate-run-v2]
---

# Meshing (TurboGrid, single passage)

Tools (`turbogrid_v2`): `mesh_start {topology}` + `job_status`, `show_gui {}`, `close {}`.

## Method
1. `mesh_start {topology}`, then poll `job_status` (30 s) until finished. For a main blade with a blunt cut-off trailing edge,
   `Single Round Cutoff Symmetric` is a sound first choice; say why you chose it. Size factor is from the case.
2. Accept the mesh only if: `negative_volume_percent` is 0, `skew_percent_bad` is small (well under 1%), and the
   element count is under the license cell limit when one applies.
   If it fails: try another ATM topology once (e.g. `Single Round Round Refined`), then stop and report.
3. `show_gui {}` so the mesh is visible. A `warning` (window not detected yet) is fine.
4. On a Student license call `close {}` before Fluent.

Print: `STAGE 4 | <cells> cells | bad skew <x>% | neg vol <y>% | ok`.

Fidelity recorded automatically: single passage, main blade only, no tip gap. Say this once to the user.
