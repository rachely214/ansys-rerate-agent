# Example 01: what a successful run produces

"Successful" means every stage ran and the report was written from this run's own results. It does not mean every
check passes. Based on the validation runs in `docs/VALIDATION.md`, the honest expected verdict is below.

## Run folder

One new folder under the machine's runs folder, named `NASA-HECC-rerate_<date>_<time>/`, containing at least:

| File | From stage |
|---|---|
| `run.json` | every stage records its numbers, status and model fidelity here |
| `case.snapshot.yaml` | copy of the approved case at run start |
| `sizing/` | Vista CCD baseline and target designs |
| `geometry/` | changed blade curves for this run |
| `geometry_impeller.png` | picture of the changed impeller |
| `single_blade.stp` | one blade on a hub slice, for the structural stage |
| `materials/` | material data converted for Mechanical |
| `passage.gtm` | TurboGrid passage mesh |
| `cfd_result.cas.h5`, `cfd_result.dat.h5` | Fluent case and data (plus `cfd_diag_*` files for start-field and speedline points) |
| `cfd_pressure_*.png` | CFD contour pictures (if the CFD stage got that far) |
| `structural_stress_iso.png` | stress picture |
| `REPORT.md` | the pass/fail report |

A calibration baseline run (unchanged geometry) may also be in its own run folder; the design run links to it.

## Scorecard rows

| Check | Expected result | Why |
|---|---|---|
| Fits casing (impeller exit blade height) | PASS | the 1D sizing gives an exit height just under the casing limit |
| Speed unchanged | PASS | the re-rate keeps the speed |
| Inlet corrected flow | likely NOT CHECKED | see "Aero rows" below |
| Total pressure ratio | likely NOT CHECKED | see "Aero rows" below |
| Adiabatic efficiency (t-t) | likely NOT CHECKED | see "Aero rows" below |
| Strength at overspeed | PASS, or PASS (indicative, fillet not modeled) | safety factor well above the minimum. Plain PASS when the root fillet is modelled. If Mechanical cannot mesh the filleted root, the run falls back to a sharp root and the label is "PASS (indicative, fillet not modeled)" (validation run 4: SF 4.77 vs 1.5) |
| Flow increase at sizing (1D estimate) | PASS | a 1D estimate only, labelled as such |
| Surge margin | NOT CHECKED | needs a full speedline; not simulated |
| Shaft power increase | NOT CHECKED | not computed |
| Running tip clearance | NOT CHECKED | needs a thermal and deformation run; not simulated |
| Campbell diagram | NOT CHECKED | needs a modal run; not simulated |

The report also has a calibration table (measured baseline vs the baseline model).

## Expected verdict

**PASS ON CHECKED ITEMS ONLY**, which is not a release PASS.

- **Model NOT CALIBRATED.** Against NASA's measured baseline the CFD model over-predicts corrected flow (about
  9 %) and impeller efficiency (about 7 points). Likely causes: design-intent geometry instead of the
  as-manufactured impeller, wall-function mesh resolution within the Student cell limit, and different measuring
  stations. Nothing is corrected with a factor, so aero rows cannot PASS.
- **Aero rows likely NOT CHECKED.** In validation the re-rated design reached more than the target flow at choke,
  but no converged solution was found AT the target flow (the targeted-flow run was unstable and the speedline
  points between choke and the target oscillated). The report then says so instead of estimating.
- **Strength PASS**: blade body and root stress are mesh-converged. The filleted root is tried first; if the
  Mechanical mesher fails on it (seen in validation run 4), the run uses a sharp root and the row reads
  **PASS (indicative, fillet not modeled)**, never plain PASS.
- **Validation run 4** (2026-10-28, 4 h 50 min, no human input): 4 PASS (strength indicative, fillet not
  modeled), 7 NOT CHECKED, 0 FAIL. See `docs/VALIDATION.md`.
- **Casing fit PASS** from the 1D sizing.

If your run gives a different verdict, the report and `run.json` say why. A different result is not wrong by
itself; an unexplained one is worth a look.
