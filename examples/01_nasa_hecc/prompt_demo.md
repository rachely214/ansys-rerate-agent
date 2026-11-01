# Example 01: compressor re-rate, the DEMO prompt (recording or live audience)

Use this one for a demo. `prompt.md` is the full engineering version (the agent waits for your approval).

Before this:
- the setup assistant has finished and the health check said **ALL GREEN**;
- `demo_mode.enabled: true` in the machine config (the default), so CFD is time-boxed and the run takes
  about 1.5 to 2 hours on a 4-core Student computer;
- this computer stays unlocked, and any Remote Desktop window stays open (or use the console handover in
  START-HERE.md).

Open Hermes, choose the profile **ansys-rerate-agent**, start a **new chat**, attach the three files from
`examples/01_nasa_hecc/inputs/` (re-rate request, baseline datasheet, casing limits), and paste the text between
the two lines.

---

Our customer sent a re-rate request for their compressor: they need about 6% more flow without changing the
casing. Their request, the baseline datasheet and the casing limits are attached. The impeller geometry and a
draft case file are in the example folder `examples/01_nasa_hecc/`.

Can we do it? Check the case against their documents and show me the key values with their sources. For this
session I approve the case on the engineer's behalf once every value has a source, so carry on without waiting.
Then size it, change the geometry, mesh it, simulate it and check its strength, live in Ansys, and give me a
pass/fail report.

This is a time-boxed feasibility check: if a simulation does not settle within its budget, mark it NOT CHECKED
and keep going.

---

What to expect: one plain line per step while each Ansys app opens on screen, then a report. Results that the
simplified model could not settle are NOT CHECKED with a reason; that is the expected, honest outcome
(`docs/examples/01_nasa_hecc_expected.md`).
