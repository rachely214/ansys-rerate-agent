# Validation and limitations

What was actually run, on which setup, and what it showed. Numbers here are evidence from named runs, not
guarantees. Anything not listed as run is not validated.

## Known limits (read this first)
- **CFD is NOT CALIBRATED.** Against NASA's measured baseline the model over-predicts corrected flow by about 9 %
  and impeller efficiency by about 7.4 points. Likely causes: design-intent geometry instead of the
  as-manufactured impeller; the Student 1M-cell mesh cap (y+ 16 to 96, wall functions); different measurement
  stations. No correction factor is applied, so CFD rows cannot PASS.
- **Re-rated design point not demonstrated.** No converged CFD state was reached at the target flow.
- **Structural model:** a single blade on a hub slice, centrifugal load only.
- **Not simulated:** surge margin, shaft power, running tip clearance, Campbell diagram.
- **One design lever:** the impeller exit blade height, from the 1D sizing.
- **Windows and Ansys 2026 R1 only.**
- **The agent run from `examples/01_nasa_hecc/prompt.md` in a fresh profile has not yet been validated end to
  end** (in progress).

Details for each are in the history sections below.

## Packaging (current)
What has been checked for this packaged layout (`setup/`, `agent/`, `runtime/`, install home under
`%LOCALAPPDATA%\ansys-rerate-agent`) so far:
- `python -m unittest discover -s tests`: 71 tests pass (run on 2026-10-28).
- `python setup/verify_layout.py`: 41 of 41 required files present, 0 scan findings (run on 2026-10-28).
- `python setup/check.py` on a test install made during the build: ALL GREEN, 33 items, all six tool servers
  start and list their tools. (That test install has since been removed; on this machine without an install the
  check reports NOT READY, as expected.)
- Pending: a fresh install driven by the setup assistant (profile `ansys-rerate-setup`), and the demo agent run
  from `examples/01_nasa_hecc/prompt.md` in a freshly installed `ansys-rerate-agent` profile.

Everything below is the history of the live validation runs. They were made with the earlier development layout
(tools called through a developer harness, now `dev/mcp_call.py`); the engineering code is the same.

## Test setup
- One Windows 11 workstation, **Ansys 2026 R1 Student** (one app at a time, `license.mode: student`, CPU Fluent with
  4 processes, 128,000-node structural and 1M-cell CFD limits), Python 3.13, Hermes Agent desktop.
- Apps in GUI mode over Remote Desktop.
- Tools were exercised over real MCP stdio through `dev/mcp_call.py` (same transport Hermes uses), without an
  LLM in the loop, plus unit tests. The full agent-driven run from `examples/01_nasa_hecc/prompt.md` in a new chat is
  listed under "Not yet validated" until it is done.

## Not yet validated (commercial-license and deployment behaviour)
- **Concurrent apps** (`license.mode: commercial`): designed in (`free_seat_for` skips closing other apps) but never
  run; only Student was available.
- **Fluent GPU solver** (`fluent.gpu: true`): not licensed on Student; never run.
- **Headless modes** (`apps.<app>.mode: headless`) for Mechanical (batch) and Fluent (no-GUI): code paths exist,
  not run end to end yet. Discovery refuses headless by design.
- **HTTP transport** and an agent in a sandbox (NVIDIA OpenShell) with Ansys on Windows: not run.
- **Second machine / clean clone install**: see the clean-clone section below.

## Unit and static checks
- `python -m unittest discover -s tests`: 26 tests pass (units, case loader and approval hash, report scorecard and
  verdict labels, geometry adapters on a synthetic impeller, background job state machine including timeout,
  desktop-session parsing, config upgrade).
- `setup/verify_layout.py`: no example-machine values, user paths, temp paths, usernames or key-like strings
  outside `examples/`; no arbitrary-code tools in the MCP package.
- Health check, mcp group (then `doctor.py --mcp`, now `setup/check.py`): all six servers start over stdio and list their tools.
- Geometry adapter vs the earlier V1 converter on the same NASA tables: changed blade sections match to within
  0.03 mm (largest at the extrapolated end section), hub to 0.000003 mm.

## Known limits (summary)
- **CFD is NOT CALIBRATED.** Against NASA's measured HECC baseline at the measured impeller-exit static pressure, the
  model over-predicts corrected flow by about **9 %** (11.82 vs 10.85 lbm/s, tolerance 5 %) and impeller
  efficiency by about **7.4 points** (0.949 vs 0.875, tolerance 2 points); impeller PR is not checkable (no
  measured value in the case). Run `HECC-baseline-calibration_20261027_154049`, PROGRESS C27.
- Likely causes, none corrected by a factor:
  1. **Geometry**: NASA design-intent hot coordinates; the tested impeller is as-manufactured (thicker blades,
     different splitter leading edge, NASA/TM-20240003692).
  2. **Mesh**: the Student license 1M-cell cap; near-wall y+ 16 to 96 means wall functions, not a resolved boundary
     layer, which tends to under-predict loss.
  3. **Measurement stations**: NASA impeller efficiency uses Station 2.4 total pressure (diffuser vane inlet,
     1.077 r_TE, area-averaged) and Station 3 total temperature (machine exit); the model reads both at 1.036 r_TE.
  A commercial license with a resolved boundary layer is **expected** to reduce the efficiency gap. This is an
  expectation, not a validated result.
- Single passage, no diffuser, steady, no seal leakage. Structural: one blade on a hub slice, centrifugal only.
- Surge margin, shaft power, running clearance, Campbell: not simulated.

## Live runs

> **Void notice (session 7):** every aero (CFD) number recorded before the rotation fix (commit b4fb790, PROGRESS
> C15/C17) is VOID: the impeller was simulated turning backwards. This covers Run 1, Run 2 and calibration
> experiments C1 to C14 in PROGRESS.md. Struck-through values below are kept only as a record.
See the run tables below (filled in as runs complete).

### Run 1: example 01 (HECC case), `runs/NASA-HECC-rerate_20261027_001027`
All stages through the V2 MCP tools over stdio, start/poll pattern, Student license, GUI mode.

| Stage | Result | Time |
|---|---|---|
| Approval gate | `start_run` refused before approval, accepted after | - |
| Sizing (Vista CCD batch) | exit height scale 1.0407, 0.6338 in vs 0.650 in limit, +5.99 % flow | 96 s |
| Geometry (Discovery) | impeller closed + manifold; single blade 9 faces (no root fillet, see below) | ~150 s |
| Mesh (TurboGrid, headless) | 235,050 cells, 0.029 % bad skew, 0 negative volume | 75 s |
| CFD (Fluent CPU 4 proc, GUI) | ~~PR 4.662, eta 0.613, 6.51 lbm/s~~ **VOID: impeller rotated backwards (rotation_sign -1, PROGRESS C15/C17)** | 32 min |
| Structural (Mechanical GUI) | 102,598 nodes; peak 355 MPa (51,517 psi) at the sharp blade root, SF 2.62 on yield (min 1.5) | 207 s |
| Report | ~~FAIL: 2 of 7 (corrected flow, efficiency)~~ aero rows **VOID** (reversed rotation); casing fit and speed rows unaffected | - |

Findings from this run:
- **Root fillet:** Mechanical 2026 R1 could not mesh the V2 blade with the case's 0.06 in root fillet ("surfaces
  cannot be meshed with acceptable quality"), at any element size tried. It meshes the same blade without the
  fillet, and a blade built today by the earlier V1 script (with fillet) from the same curves. Not yet resolved;
  the run used the documented fallback `root_fillet: false` and records "no root fillet" as a fidelity limit. The
  351 to 355 MPa peak sits at the sharp root edge (a stress singularity); the broad blade stress is about 160 to
  240 MPa. The SF 2.62 PASS is therefore conservative for the body, not a verified root stress.
- **VOID (reversed rotation, see Session 6):** this paragraph's aero reasoning no longer applies. Original text: **Aero FAILs are model-limited:** single passage without the vaned diffuser, no tip gap, main blade only,
  not converged. The pressure ratio is near target but flow and efficiency are far below the measured baseline,
  which the same model would also under-predict (roadmap item 1, baseline vs measured, is needed to judge this).
- Bugs found and fixed during this run: rim point added at the cut radius made the Discovery merge drop the blade
  faces; Mechanical script imported the material twice and kept old bodies; job errors hid the cause; the report
  marked an exactly-met +6.0 % sizing target as FAIL (rounding). Each has a commit and, where pure logic, a test.

### Run 2: test case B (changed duty), `runs/TEST-B-changed-duty_20261027_023028`
Same impeller, deliberately changed inputs in SI units: speed 20,500 rpm (was 21,789), flow target 5.40 kg/s (+9.8 %),
exit-height limit 16.0 mm, exit height 15.47 mm, material Structural Steel (yield 250 MPa, file extracted from the
Ansys sample library), hub-slice depth 9 mm, fillet 1.5 mm. Purpose: prove every stage and the report use the case.

| Stage | Result | Case value used? |
|---|---|---|
| Sizing | 20,500 rpm, flow ratio +9.76 %, exit height 16.35 mm, **does not fit** 16.0 mm limit | speed, flows, mm limit: yes |
| Geometry | inspect: 15.53 mm from geometry vs 15.47 mm in case (0.4 %); closed solids; 9 mm slice depth | units mm, depth: yes |
| Mesh | 236,010 cells, 0.03 % bad skew | size factor from case: yes |
| CFD | ~~PR 4.162, eta 0.623, 2.879 kg/s~~ **VOID: reversed rotation (-20,500 rpm)**; still shows the case speed and unit were used | speed, unit: yes |
| Structural | **error**: Mechanical could not mesh the single blade at 2.0 to 3.0 mm even without the fillet | not solved |
| Report | casing fit FAIL stands (1D sizing); flow/PR/efficiency rows **VOID** (reversed rotation); strength NOT CHECKED; targets shown in case units (kg/s, mm, MPa) | yes |

Note: the casing-fit FAIL is labelled "model-limited" only because the sizing stage carries a 1D-model fidelity
note; the estimate itself exceeds the limit. Review item: label casing-fit by its own meaning.

### Session 6 corrections (supersede the aero results of Runs 1 and 2)
- **Rotation was reversed in every earlier CFD run** (PROGRESS C15, C17). After `mirror_theta` the blades wrap
  toward -theta, so a backswept impeller must rotate toward +theta; the case had -1. Same mesh at 120 kPa:
  +1 gives 12.54 lbm/s (choke, matches the 1-D throat estimate within 1 %), exit relative swirl -237 m/s
  (opposes rotation, as backsweep requires); -1 gave 6.41 lbm/s and +13.5 m/s. All aero numbers in Runs 1 and 2
  (6.51 lbm/s, PR 4.66, eta 0.61; case B 2.88 kg/s) are void.
- **Measured back pressure now works** (C18): main blade only, 228.3 kPa at 1.036 r_TE (App. E.2), converged:
  11.30 lbm/s (+4.1 % vs measured 10.85, tolerance 5 %), PR_tt 5.09, eta_tt 0.955 vs impeller-alone 0.875
  (+8.0 points, tolerance 2: OUTSIDE). The impeller-alone PR is not in the case, so PR is NOT CHECKABLE. This was
  a diagnostic point on the main-blade-only mesh; it is not the calibration baseline.
- **Convergence rule tightened** (C16, DEC-14): imbalance under 0.5 % on every sample of the 300-iteration window,
  and max-min spread of flow, PR and eta under 0.5 %. The old end-point rule had passed a point whose imbalance
  was 1.1 to 1.9 % until the last sample.
- **Calibration gate** (DEC-16): `case_v2.calibrate_cfd` and the report: without a matching CALIBRATED baseline,
  CFD rows can never PASS ("model not calibrated").
- **Strength check** (DEC-15): only the hub-slice cut planes and fixed-support face are excluded; the root fillet
  zone (3 x fillet radius from the root line) is evaluated and reported separately, and the check uses the higher
  of fillet and bulk stress. Code and unit tests done; NOT yet run in Mechanical (see below).
- **Case B** regenerated with rotation +1 and the measured back pressure (C20).

Not completed in session 6 (blocked):
- Splitter-passage calibration baseline (C19): the mesh is fine (898,546 cells, 0.019 % bad skew), but the Remote
  Desktop session disconnected at about 13:13. Fluent GUI launch is refused in that state and the no-GUI import
  of TurboGrid meshes fails ("TWF_*/0.def not found") even for the main-only mesh that imported normally while
  connected. Therefore not run: calibration baseline, HECC design rerun, case B rerun, Mechanical fillet check.
- Unit tests: 50 pass; layout scan: 0 findings. (All of these were completed in session 7, below.)

### Session 7: calibration baseline, HECC rerun, case B (Ansys 2026 R1 Student, GUI, desktop connected)
Model changes before these runs (each with a DECISIONS entry): measured tip gap 0.012 in in the CFD mesh
(case `geometry.tip_clearance`, datasheet value) and splitter in the passage; mesh size factor 1.2 to stay under
1M cells (C21); air cp(T) and Sutherland viscosity, efficiency by the gas-table method like the rig data
(DEC-17, C22); convergence over the whole window (DEC-14); unconverged CFD never scored (DEC-18); strength on
max(bulk, root fillet) (DEC-15) with a node-unit bug fixed (S10).

Pre-run checks (PROGRESS C22, C23):
- Efficiency definition: NOT identical to NASA's. NASA impeller eta = Station 2.4 Pt (diffuser vane LE, 1.077 r_TE,
  area-averaged Kiel heads) with Station 3 Tt (machine exit, adiabatic diffuser assumed), gas tables. The model:
  outlet at 1.036 r_TE, mass-averaged (area-averaged also reported), now gas-table. Constant gamma had added
  ~0.9 points; fixed. The station differences remain and are stated, not corrected.
- Walls: all no-slip, rotating-frame blade/hub, stationary shroud; SST with Fluent's all-y+ wall treatment.
  y+ 16 to 96 on blade/hub/shroud: wall-function regime, not a resolved boundary layer (fidelity limit; y+ ~1
  does not fit the Student cell limit with splitter and gap).

| Run | Stage | Result |
|---|---|---|
| Calibration baseline `HECC-baseline-calibration_20261027_154049` | Mesh | Single Splitter + 0.305 mm gap, 780,920 cells, 0.092 % bad skew |
| | CFD at 228.3 kPa (case) | cold start stalls (C25); from a 120 kPa start field converged at 950 it: 11.82 lbm/s, PR 5.26, eta 0.949 (area-avg 0.933) |
| | Calibration | **NOT CALIBRATED**: flow +9.0 % (tol 5 %), eta +7.4 points vs impeller-alone 0.875 (tol 2), impeller PR not in the case (not checkable) |
| HECC design `NASA-HECC-rerate_20261027_173730` | Sizing / geometry / mesh | +5.99 %, exit 0.6338 in (limit 0.650); 283.9 in3, single blade with 0.06 in fillet; 780,920 cells |
| | CFD at 228.3 kPa | does NOT converge: from the same start the flow collapses to stall (inlet reversal 26 %, C29). The baseline exit static is not a valid exit condition for the uprate; no design exit pressure is available |
| | Strength (105 % speed, Ti-6Al-4V) | bulk p99 151 MPa, root fillet p99 169 MPa (governs), both mesh-converged (2.1 %, 2.8 %); SF 4.89 vs 1.5: **PASS** |
| | Report | PASS ON CHECKED ITEMS ONLY: 4 pass, 7 not checked. Aero targets NOT demonstrated |
| Case B `TEST-B-changed-duty_20261027_185250` | Sizing | 20,500 rpm, +9.76 %, exit 16.35 mm > 16.0 mm: casing **FAIL** (real) |
| | Geometry / mesh | 1.5 mm fillet on 4 edges; 780,920 cells |
| | Strength (steel 250 MPa, 21,525 rpm) | bulk p99 246 MPa, fillet p99 266 MPa (governs), converged (1.9 %, 4.0 %); SF 0.94: **FAIL** |
| | CFD | 120 kPa start field converged to choke (0.2793 kg/s/passage); stepped to 228.3 kPa it stalls within 200 it (flow 0.28 -> 0.008, inlet reversal 30 %): not converged, not scored. Same cause as the HECC design: the case reuses the 21,789 rpm baseline exit static at 20,500 rpm and a larger exit (C20, C29) |
| | Report | FAIL: 2 of 4 checked (casing fit, real; strength, model-limited, SF 0.94 on the fillet); aero NOT CHECKED (not converged, model not calibrated) |

Root causes for NOT CALIBRATED (documented, none corrected by a factor):
1. Geometry is NASA's Design-Intent hot shape; the tested impeller (As-Manufactured) differs in blade thickness and
   splitter LE angle (NASA/TM-20240003692). Thicker real blades reduce flow and add loss: the right direction for
   both errors. Needs the As-Manufactured coordinates.
2. Wall-function resolution (y+ 16-96) under-predicts profile and separation loss.
3. Station/definition differences in the efficiency (above): area averaging alone moves 1.6 points.
4. Steady single passage, no diffuser potential field, no seal or back-face leakage.

### Session 8: design exit condition (DEC-19), final runs
Method: re-rated designs are evaluated at their target flow (targeted mass flow at the outlet), with a speedline
fallback (fixed back pressures, interpolation at the target flow, no extrapolation). Logic unit-tested; live:

| Run | Step | Result |
|---|---|---|
| Calibration case (converged C27 solution) | Targeted mass flow, live probe (D1) | works: outlet static rises as the flow is driven toward the target |
| HECC design `NASA-HECC-rerate_20261027_173730` | Start field 1.6 x inlet total | converged: choke flow 12.59 lbm/s (>= 11.5 target) |
| | Targeted mass flow (D2) | **unstable**: flow stays at choke while the outlet static is raised 126 -> 434 kPa, then collapses to stall; Fluent ended abnormally |
| | Speedline fallback (D3) | 121 kPa converged; 182 and 212 kPa in a limit cycle (flow swings up to 15 %, across the target) for 800 it; no converged bracket |
| | Report | **PASS ON CHECKED ITEMS ONLY** (4 pass, 7 not checked). Flow/PR/eta NOT CHECKED: "max converged flow 12.59 lbm/s (>= target); no converged point AT the target". Strength PASS (root fillet governs, SF 4.89) |
| Case B `TEST-B-changed-duty_20261027_185250` | Start field | converged at 121 kPa: choke 5.60 kg/s (>= 5.40 target), PR 2.81, eta 0.776 (read live, not recorded: Fluent died as the point finished) |
| | Targeted mass flow (D5b) | creeps on the choke branch (outlet static +19 kPa in 600 it, no flow response); stopped |
| | Speedline (D6) | **blocked**: Remote Desktop disconnected; Fluent died twice with 'connection reset' |
| | Report | **FAIL** 2 of 4 checked: casing fit (16.35 > 16.0 mm, real) and strength (fillet SF 0.94, model-limited). Aero NOT CHECKED |

Finding: with this model (impeller-only passage, steady RANS, Student mesh) the re-rated designs have no steady
solution between choke and the higher back pressures needed to reach the target flow, so PR and efficiency at the
target are not demonstrated. Reported as NOT CHECKED, never estimated. A stage model with the diffuser (roadmap 3)
is the likely remedy.

### Clean-clone install test
Earlier development layout (history): a clone test (git clone into a new folder, the old PowerShell setup with
Hermes skipped, new venv from requirements.lock, local config generated), unit tests, `verify_layout.py`, and the
old server start check. The current maintainer script is `dev/clean_clone_test.py`.
Result: all steps exit 0, all six servers start from the clone, no machine or run files tracked by git.
Same machine (Ansys and Python already installed); a second machine is still not validated.

## Open issues found by validation
1. **CFD model NOT CALIBRATED** (session 7): over-predicts flow (+9 %) and impeller efficiency (+7 points) at the
   measured exit static. Next step: As-Manufactured geometry (NASA archive), then a near-wall mesh study if a
   larger cell budget is available.
2. **Re-rated design point not demonstrated**: the design-flow method (DEC-19) is implemented and tested, but
   neither design reached a converged state at its target flow (targeted mass flow unstable from the choked side;
   speedline points between choke and the target oscillate). Needs a stage model with the diffuser.
3. **Remote Desktop disconnects stop GUI runs** (Fluent crashes / mesh import fails). Keep the session open, or
   use headless mode where supported.
4. Single-blade structural meshing now works with the fillet for both cases (patch-independent tets, DEC-12).
   (The session-4 issue is resolved.)
5. Agent-driven run in a new Hermes chat (prompt.md) not yet done; pending a fresh install of the `ansys-rerate-agent` profile.
