# Example 01: NASA HECC re-rate

## What this is

A worked example of a compressor re-rate. The machine is NASA's High Efficiency Centrifugal Compressor (HECC),
a single-stage centrifugal compressor whose impeller shape NASA published as coordinate tables. The re-rate
request is made up for this example: the "customer" wants about 6 % more corrected flow at the same speed,
inside the existing casing, without losing pressure ratio or efficiency.

The agent reads three short documents in `inputs/`, drafts a case file, asks you to approve it, and then runs
every stage live in Ansys: 1D sizing (Vista CCD), geometry change (Discovery), passage mesh (TurboGrid), CFD
(Fluent) and spin stress (Mechanical). It ends with a pass/fail report.

## Files

| File | What it is |
|---|---|
| `prompt.md` | The message to paste into a new chat with the demo agent |
| `inputs/01_rerate_request.md` | The customer's request: new duty and acceptance criteria |
| `inputs/02_baseline_datasheet.md` | Measured baseline performance and key dimensions |
| `inputs/03_casing_limits.md` | What the existing casing allows |
| `case.yaml` | A reviewed draft of the case, every value with its source |
| `materials/ti6al4v_public.yaml` | Public material data for the impeller (cited in the file) |
| `data_source.yaml` | Where the NASA geometry tables come from |
| `geometry_data.README.md` | How the geometry tables are downloaded |
| `expected.md` | What a successful run produces, and the honest expected verdict |

## Geometry data

The NASA tables are not stored in this repository; they are downloaded once during setup. The case says
`geometry.source: geometry_data/AppendixE.4_HotCoordinates`. That relative path is looked up first next to
`case.yaml`, then under the machine's example-data folder (`<example data folder>/01_nasa_hecc/`). So the
download can live outside the repository.

## Honest limits

The CFD model has not been calibrated against NASA's measured baseline (it over-predicts flow and efficiency),
so the aero targets are not expected to be demonstrated. See `expected.md` and `docs/VALIDATION.md`.
