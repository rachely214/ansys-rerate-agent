# Decisions

## DEC-01 Case file is the single source of machine data
All machine-specific values (operating point, targets, geometry limits, material, boundary conditions,
mechanical criteria) live in one `case.yaml` per compressor, each with unit and source. Code holds conversions
and methods only. Reason: V1 hard-coded one machine's numbers in six places and could not run another machine.

## DEC-02 Approval by content hash
`case_approve` stores a SHA-256 of the case content. Stage tools refuse an unapproved or edited case, and a run
is bound to the hash at start. Reason: guarantees that every simulated number traces to values a person approved.

## DEC-03 No defaults in the schema
The schema has no default values. Missing required fields block the stages that need them. Engineering choices
the documents do not cover (outlet back pressure, hub-slice depth) must be written into the case with an
`ENGINEERING CHOICE:` source and approved.

## DEC-04 Geometry adapters and a neutral impeller form
Adapters convert sources into a neutral impeller (meridional hub/shroud + spanwise blade sections, metres,
axis +z, exit plane z = 0). Design changes act on the neutral form; writers emit BladeGen curve sets.
Implemented: `nasa_tables`, `bladegen_inf` (read and write).
Not implemented: `step`. A STEP solid has no explicit hub/shroud curves, spanwise sections or blade count.
A STEP adapter needs: (1) identify the blade surfaces of one main blade and one splitter; (2) cut them with
surfaces of revolution at chosen span fractions to get closed sections; (3) trace hub and shroud meridional
curves from the hub surface and a supplied shroud contour (the shroud is a casing part, not in the impeller
STEP); (4) count blades from rotational symmetry. Step 2 and 3 can be done in Discovery scripting, but would
need a new specific MCP action and validation against a known geometry. Until then ask for a BladeGen/curve
export (BladeGen, BladeEditor, CFturbo and most design tools can write one).

## DEC-05 One design lever in V2: exit blade height
V2 implements one design change (exit height scaled from the 1D sizing ratio, inlet fixed). Other levers in the
casing sheet (blade angles, backsweep, diffuser re-match) are roadmap items. The report shows this limitation.

## DEC-06 Non-blocking Fluent solve
Hermes and other MCP hosts cap a tool call (V1 hit a 420 s limit mid-solve). Fluent now iterates in a
background thread; tools return immediately; the agent polls.

## DEC-07 No arbitrary-code tools
V1 had `run_code` / `run_mechanical_script` / `run_design_script`. V2 exposes specific actions only. In-app
scripts are fixed files shipped with the package; servers substitute a JSON argument block, never code.

## DEC-08 Fidelity travels with results
Each stage records the simplifications of its model. The report shows them next to each result and marks
FAILs from simplified models as `FAIL (model-limited)`; the verdict counts them as FAIL.

## DEC-09 License mode in config
`license.mode: commercial` (standard) lets apps run concurrently; `student` closes other apps before each
launch. Fluent GPU is a config switch. Development and testing used Student (see VALIDATION.md).

## DEC-10 Separate Hermes profile
Setup installs the demo agent as its own Hermes profile (`ansys-rerate-agent`; the earlier development layout
used `rerate-v2`) and writes the tool servers into that profile only. It never edits the
default profile, so an existing setup (including V1) stays unchanged.

## DEC-11 Transport from config
Each server runs over stdio (default) or HTTP with host and port from the config, so the agent can run in a
sandbox while Ansys stays on Windows.

## DEC-12 Structural mesh method: patch-independent tetrahedra
The default (patch-conforming) mesher could not mesh the single-blade body (with or without the root fillet in
case B; with the fillet in example 01): "surfaces cannot be meshed with acceptable quality". Diagnostics found no
edge below 0.002 x r_te and no near-tangent faces; the trouble spots are a 2.8 mm^2 face at the trailing-edge
corner and 0.5 mm edges where the blade meets the slice rim. Virtual topology created no cells. Patch-independent
tetrahedra (mesh-based defeaturing 0.0023 x r_te, minimum size 0.5 x element size, no proximity refinement,
growth 1.5) mesh both bodies. Physical justification: the defeatured features (sub-mm) are far smaller than the
blade thickness and the element size, so ignoring them does not change the load path; refinement is controlled
by the explicit mesh study instead. All values live in config `structural_meshing`.

## DEC-13 Strength is judged on converged body stress, not the singular peak
Sharp re-entrant edges (blade-to-hub junction, the planar cuts of the hub slice and the fixed support face) carry an
elastic stress singularity: the peak keeps rising with refinement (+22 % and +56 % between the two meshes in the
two cases). The strength check therefore uses the 99th-percentile stress on blade nodes farther than 0.02 x r_te
from those edges, and requires it to change by less than `mesh_convergence_tol` (5 %) between the two finest
meshes. The peak is reported next to it. A centrifugal hand calculation must agree within an order of magnitude;
otherwise, or if the body stress is not converged, the strength check is NOT CHECKED. The real root stress needs a
model with the actual disk and fillet geometry, which the case does not provide.

## DEC-14 CFD convergence is judged over the whole window
A steady RANS passage solution is accepted as converged only if, over the last `window_iterations`, (a) the
inlet-outlet mass imbalance stays under `mass_imbalance_max` on every sampled point and (b) the max-min spread of
corrected flow, PR and efficiency is under `stability_tol` relative to the window start. Reason (PROGRESS C16):
the earlier end-point rule passed a solution whose imbalance was 1.1 to 1.9 % until the last sample, and would
pass a limit-cycle oscillation that happens to return to its start value. Conservation must hold persistently
and an oscillating solution has no single operating point to compare with test data. Tolerances are unchanged.

## DEC-15 Strength uses the higher of bulk and root/fillet stress (supersedes the exclusion part of DEC-13)
The single-blade model ends in artificial planar cuts (the hub slice) and a fixed support face. The real disk
continues past them, so the singular stress at those edges is a modelling artefact and is excluded (nodes within
`body_stress_exclusion_fraction` x r_te). The blade root and its fillet are REAL geometry: the root fillet is the
classic life-limiting location of a centrifugal impeller blade under centrifugal load, so excluding it (as the
DEC-13 implementation did, by listing the blade-to-hub edges as sharp) could hide the governing stress. Now:
- root/fillet zone = blade nodes within `root_zone_fillet_multiple` (3) x fillet radius of the hub-side root
  line (covers the fillet arc and where its concentration decays); bulk = all other evaluated blade nodes;
- both are mesh-studied (99th percentile, `mesh_convergence_tol`); the check uses max(bulk, root/fillet) and
  is NOT CHECKED unless both are converged. Peak at the cut/support edges is reported, not used.
- Without a fillet (radius 0) the root is a sharp re-entrant corner, singular by elasticity theory; the root zone
  then does not converge and the check honestly ends NOT CHECKED rather than PASS.

## DEC-16 CFD results are gated by a baseline calibration
A CFD model is only trusted for design decisions after it reproduces measured data on the unmodified machine.
`case_v2.calibrate_cfd {baseline_run_dir}` compares a baseline run (geometry scale 1, stage `cfd`) with the
case's measured values: corrected flow (relative, `flow_tol`), PR and efficiency (`pr_tol` relative, `eta_tol`
absolute points) against impeller-alone or stage data per `pr_reference`. CALIBRATED requires a converged
baseline (DEC-14) and every quantity within tolerance; a measured value missing from the case makes that
quantity NOT CHECKABLE and the model NOT CALIBRATED (nothing is estimated in its place). The result is linked
into the design run. The report applies it only if the CFD model signature (mesh topology, splitter, size
factor, turbulence model, rotation sign, outlet radius ratio) matches. Without a valid calibration, aero rows
can never PASS: a pass becomes NOT CHECKED, a fail is FAIL (model-limited), both noted "model not calibrated".
No correction or scaling factor is ever derived from the comparison.

## DEC-17 Temperature-dependent air and gas-table efficiency
The rig efficiencies are reduced with gas tables (temperature-dependent properties, AIAA 2014-3632 Sec. V.A). The
model used Fluent's default air (constant cp 1006.43, constant viscosity) and a constant-gamma 1.4 efficiency. Over
the ~180 K impeller temperature rise this alone shifts eta by about 0.7 to 0.9 points (PROGRESS C22), larger than
half the calibration tolerance. Physical correction, no tuning: the solver uses cp(T) (polynomial fit to ideal-gas
air tables, 250-600 K) and Sutherland viscosity; eta is evaluated with the same cp(T); the constant-gamma value is
kept alongside for reference. Coefficients are physical constants of air, in config `fluent.air` (not machine
data). Remaining definition differences that are NOT corrected because they cannot be from published data: NASA's
impeller Tt is taken at the machine exit (Station 3, adiabatic diffuser assumed), its Pt at the diffuser vane LE
(1.077 r_TE, area-averaged Kiel heads), the model's at 1.036 r_TE (mass-averaged; area-averaged also reported).
These are stated next to the calibration result.

## DEC-18 Unconverged CFD is never scored
A CFD state that does not meet the DEC-14 rule is not a solution of the model, so neither PASS nor FAIL can be
derived from it: the aero rows are NOT CHECKED with the note "CFD not converged" and the values are shown for the
record. Earlier, an unconverged FAIL was scored "FAIL (model-limited)", which presented an arbitrary iterate as a
model result (C29: a stalling design run reads eta > 1). Converged-but-uncalibrated results keep DEC-16 handling.

## DEC-19 Re-rated designs are evaluated at their target flow
The measured exit static pressure belongs to the baseline at its measured flow. A re-rated design runs at a
different flow with a different exit geometry; its exit pressure is a RESULT, not an input. Imposing the baseline
value stalled both designs (C29, B8). Method:
1. Primary: Fluent pressure outlet with targeted mass flow = the case corrected-flow target converted to physical
   flow per passage at the case inlet (`design_point.target_passage_mass_flow`). The outlet static floats;
   PR and efficiency are read at the target flow, scored against the targets (and gated by calibration, DEC-16).
   Pressure bounds (config `fluent.design_point`) are numerical guard rails only.
2. Choke: if the flow stays short of the target while the outlet pressure has stopped falling (at its lower bound
   or flat) and the flow is flat over the convergence window, the passage cannot pass the target flow: a real
   FAIL on flow, reported with the maximum flow achieved. The calibration shows the model over-predicts flow, so a
   model choke below the target is not an optimistic artefact.
3. Fallback if the targeted-mass-flow run does not settle: a short speedline (3 to 5 converged back pressures,
   config `speedline_static_to_inlet_total` x inlet total), and PR/eta linearly interpolated at the target flow
   between the two bracketing points. No extrapolation: a target outside the converged range is NOT CHECKED.
Physical justification: this is the standard way to rate a compressor component at a specified duty; it needs no
exit pressure that the documents do not provide. Generic: all inputs from the case and config.
