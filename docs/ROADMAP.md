# Roadmap (not built in V2)

V2 is an experimental concept demo. These items would turn it into a decision-grade tool. Ordered by value to the
re-rate deliverables of a typical request. Done in V2 and removed from this list: baseline-vs-measured CFD
calibration (result: NOT CALIBRATED), splitter and measured tip gap in the passage mesh, design evaluation at the
target flow.

1. **As-manufactured geometry and recalibration.** NASA states the tested example impeller differs from the published
   design-intent coordinates (blade thickness, splitter leading edge; NASA/TM-20240003692). Load the
   as-manufactured coordinates, rerun the calibration baseline, and only then judge aero results. Needs: adapter
   options for the archive format; no code change to the method.
2. **Resolved boundary layer on a commercial license.** y+ about 1 with a mesh study; expected (not yet shown) to
   reduce the efficiency over-prediction caused by wall functions under the Student 1M-cell cap.
3. **Diffuser or stage model.** Impeller + vaned diffuser with a mixing plane; reads pressure at the same stations
   as the rig (diffuser vane inlet, machine exit) and gives a matched operating point for re-rated designs.
4. **Speedline and surge margin.** Several back-pressure points per speed, surge margin by the customer's
   definition (the speedline fallback of DEC-19 is the starting point).
5. **Campbell diagram.** Prestressed modal analysis of the blade across the speed range against the excitation
   orders and margin in the case.
6. **Multiple candidate designs.** Conservative / balanced / aggressive variants on identical settings, compared
   with the calibrated baseline; pause for the customer's selection.
7. **GPU-accelerated Fluent on a commercial license.** Native GPU solver for the passage and stage models
   (config switch exists, not validated), and concurrent apps.
8. **Booth mode for trade shows.** Fast, clearly labelled lower-fidelity runs (coarse mesh, fewer iterations,
   banner "LOWER FIDELITY, NOT FOR DECISIONS") plus labelled replays of full recorded runs ("REPLAY of run
   <id>, recorded <date>"). Never mixes the two, never presents a replay as live.
9. **Shaft power** from CFD work input and the case's mechanical losses, against the driver limit.
10. **Running tip clearance** from centrifugal and thermal deformation at the shroud line.
11. **More design levers.** Blade angles and backsweep, diffuser vane count and stagger, with a Campbell re-check.
12. **STEP geometry adapter** (requirements in DECISIONS DEC-04).
13. **Sandboxed agent.** Agent in a sandbox, MCP servers over HTTP on the Windows host.
