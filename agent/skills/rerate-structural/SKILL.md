---
name: rerate-structural-v2
description: "Use when running the Mechanical spin-stress stage of a compressor re-rate (V2)."
version: 2.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [compressor, rerate, mechanical, stress, v2]
    related_skills: [rerate-run-v2]
---

# Structural (Mechanical, spin stress at overspeed)

Tools (`mechanical_v2`): `connect_start {}`, `spin_stress_start {mesh_sizes, max_nodes?}`, `job_status {}`,
`disconnect {}`. Nothing blocks; poll `job_status` every 30 to 60 s with a one-line status.

## Method
1. `connect_start {}` (GUI or batch per config), poll `job_status` until finished (1 to 3 minutes).
2. `spin_stress_start {mesh_sizes}`, poll `job_status`: give 3 to 5 element sizes in the case length unit, finest first that you expect to
   fit the node limit (Student: 128,000 nodes, set in the case). State the list.
   Speed = case speed x `limits.speed_max_fraction`; material and yield from the case.
3. Check the answer before reporting it:
   - `solve_status` must be `Done` and a mesh size must have been used. If not, read `mechanical_errors` and
     `diagnostics.mesh_tries` in the result and report them; a meshing failure is a geometry issue (see
     `geometry_tolerances` in the config), not something to retry blindly.
   - Look at the stress image (vision) and confirm the peak is on the blade or root fillet, not a single node on
     the cut faces of the hub slice or the fixed support edge. If it is on a cut/support face, say the number is
     a modelling artifact and do not use it for PASS.
4. `disconnect {}` (Student).

Print: `STAGE 6 | peak <s> <unit> | SF on yield <x> vs <min> | nodes <n> | ok`.

Fidelity recorded automatically: one blade on a hub slice (no disk), centrifugal load only (no aero pressure,
no thermal). Tip clearance and Campbell checks are roadmap items and stay NOT CHECKED.

## If the blade will not mesh
`job_status` returns `no mesh size gave a valid mesh` with the tried sizes. The usual cause is the root fillet
(Mechanical reports "surfaces cannot be meshed with acceptable quality"). Then: tell the user, rebuild the geometry
with `geometry_v2.build_start {..., root_fillet: false}`, rerun spin stress, and report the result with the fidelity
note "no root fillet". Do not quote the peak at the sharp root as a real stress; report the blade body stress away
from the root and say the root needs a filleted model.
