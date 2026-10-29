---
name: rerate-structural
description: "Use when running the Mechanical spin-stress stage of a compressor re-rate. Checks blade and root fillet stress at overspeed."
version: 1.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, mechanical, stress]
    related_skills: [rerate-run, rerate-geometry]
---

# Structural (Mechanical, spin stress at overspeed)

Tools (`mechanical_v2`): `connect_start {}`, `geometry_diagnostics_start {step_path?}`,
`spin_stress_start {mesh_sizes, max_nodes?}`, `job_status {}`, `disconnect {}`.

Success: `solve_status` is `Done`, the mesh study converged, and the governing stress (the higher of blade body
and root fillet) gives a safety factor on yield that is compared with the case minimum.

## Method
1. `connect_start {}`. Wait a minute or two, then call `job_status` until finished.
2. `spin_stress_start {mesh_sizes}`, then wait a few minutes and call `job_status`; repeat with a one-line status.
   Give 3 to 5 element sizes in the case length unit, coarsest you trust first down to the finest that should
   fit the node limit in the case (`structural.max_mesh_nodes`). State the list.
   Speed = case speed x `limits.speed_max_fraction`; material and yield come from the case.
3. Check the answer before reporting it:
   - `solve_status` must be `Done` and a mesh size must have been used. If not, read `mechanical_errors` and
     `diagnostics.mesh_tries` in the result and report them; a meshing failure is a geometry issue, not something
     to retry blindly. `geometry_diagnostics_start` lists short edges and sliver faces if you need the cause.
   - Strength uses the higher of the bulk blade stress and the root fillet stress. Only the hub-slice cut planes
     and the fixed-support face are excluded (they are modelling cuts where the stress is singular). The root
     fillet is real geometry and is never excluded.
   - Look at the stress image and confirm the peak is on the blade or root fillet, not on a cut face or the
     fixed support. If it is on a cut or support face, say the number is a modelling artifact and do not use it
     for PASS.
4. If the tool says Mechanical must be closed before the next app, call `disconnect {}`.

Print: `STAGE 6 | governing <bulk or fillet> <s> <unit> | SF on yield <x> vs <min> | nodes <n> | mesh change <c>% | ok`.

Fidelity is recorded automatically: one blade on a hub slice (no disk), centrifugal load only (no aero pressure,
no thermal). Running clearance and Campbell checks are not simulated and stay NOT CHECKED.

## If the blade will not mesh
`job_status` returns `no mesh size gave a valid mesh` (or the mesher crashes) with the sizes tried. The usual
cause is a small sliver face next to the root fillet. In order:
1. Run `geometry_diagnostics_start {}` and read the flags (short edges, small or near-tangent faces).
2. Rebuild the geometry ONCE with the fillet kept and slightly larger margins: `geometry_v2.build_start {stride,
   theta_margin_deg: 4, le_pad: <about 0.15 in or 4 mm>, root_fillet: true}`, then rerun spin stress. These
   values meshed with the fillet on the NASA example.
3. Only if that also fails: rebuild with `root_fillet: false`, rerun, and report with the fidelity note
   "no root fillet". Do not quote the peak at the sharp root as a real stress; report the blade body stress away
   from the root and say the root needs a filleted model.
Mesh sizes (case length unit): the NASA example meshed and converged with 0.2 and 0.16 in (about 1/3 and 1/4 of
the exit blade height); 0.10 in and finer exceeded the Student node limit.
