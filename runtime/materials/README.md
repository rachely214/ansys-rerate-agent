# Material library files (user-supplied, never in the repository)

`case.yaml` points `material.library_file` at an Ansys Engineering Data XML that contains `material.name`.
No material files ship with this repository: Ansys library data is Ansys-derived content (see
docs/RELEASE_CHECKLIST.md). Keep your files outside git, for example in the git-ignored `work/materials/` folder.

To create one from your own Ansys installation:
1. Open Ansys Workbench > Engineering Data (or Granta materials data if licensed).
2. Find or add the material (e.g. Ti-6Al-4V). Check density, Young's modulus, Poisson's ratio and the tensile
   yield strength against the customer's material specification.
3. Export it: Engineering Data > right-click the material > Export Engineering Data, save as XML, e.g.
   `work/materials/<material>.xml` (example 01 expects `work/materials/ti64.xml`).
4. Point `material.library_file` in `case.yaml` at that file and put the same yield strength into
   `material.yield_strength` with its source. Example 01 uses 134,885 psi, the value in the file used during
   validation; if your file differs, update the case and re-approve it.

One material can also be extracted from a larger Engineering Data XML in your own installation with
`python scripts/dev/extract_material.py <library.xml> "<name>" <out.xml>`.

`doctor.py --case <case.yaml>` reports a missing material file.
