# Example 01: compressor re-rate, the prompt

Before this: the setup assistant has finished and the health check said **ALL GREEN**.

Open Hermes, choose the profile **ansys-rerate-agent**, start a **new chat**, and paste everything between the
two lines below. Keep this computer unlocked and, if you use Remote Desktop, keep that window open until the
report is done (the Ansys apps draw on this desktop).

---

Our customer sent a re-rate request for their compressor. The documents are in the ansys-rerate-agent example
folder `examples/01_nasa_hecc/inputs/` (re-rate request, baseline datasheet, casing limits). The impeller
geometry is NASA's published coordinate tables, already referenced by the draft case file
`examples/01_nasa_hecc/case.yaml`.

1. Check the draft case file against the three documents: fix anything wrong and keep a source for every value.
   Show me every value with its source and every engineering choice, then wait for my approval.
2. After I approve, run every stage live: sizing, geometry change and solids, passage mesh, CFD (calibration
   against the measured baseline, then the new design at its target flow), and structural.
   Tell me in one line what each step is doing and print each stage's numbers as you go.
3. Give me the pass/fail report. Record failures instead of declaring unverified checks passed, and label results
   that come from simplified models.

---

What to expect: about 2 to 4.5 hours on a 4-core computer with the Student license, most of it CFD.
`expected.md` describes what a finished run looks like.
