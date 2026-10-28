---
name: rerate-meshing
description: "Use when meshing the compressor blade passage in TurboGrid during a re-rate. Accepts the mesh only on quality limits."
version: 1.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, turbogrid, mesh]
    related_skills: [rerate-run, rerate-cfd]
---

# Meshing (TurboGrid, single passage)

Tools (`turbogrid_v2`): `mesh_start {topology}`, `job_status {}`, `show_gui {}`, `close {}`.

Success: negative volume 0 %, bad skew well under 1 %, cell count under any license cell limit the tool reports.

## Method
1. `mesh_start {topology}`. Wait a minute or two, then call `job_status`; repeat until finished, one line each
   time. For a main blade with a blunt cut-off trailing edge, `Single Round Cutoff Symmetric` is a sound first
   choice; say why you chose it. The size factor comes from the case.
2. Accept the mesh only if: `negative_volume_percent` is 0, `skew_percent_bad` is small (well under 1%), and the
   element count is under the cell limit when the tool reports one.
   If it fails: try another topology once (e.g. `Single Round Round Refined`), then stop and report.
3. `show_gui {}` so the mesh is visible. A `warning` (window not detected yet) is fine.
4. If the tool says TurboGrid must be closed before the next app, call `close {}` before Fluent.

Print: `STAGE 4 | <cells> cells | bad skew <x>% | neg vol <y>% | ok`.

The fidelity of the passage model (single passage, what is and is not included) is recorded automatically by the
tool; read it from the reply and say it once to the user.
