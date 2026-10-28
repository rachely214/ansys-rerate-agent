# Example 01: NASA HECC re-rate, the prompt

Prerequisites: setup done (SETUP.md), NASA tables downloaded (`geometry_data.README.md`), material file exported
(`plugins/ansys-mcp/materials/README.md`), `doctor.py --mcp --case examples/01_nasa_hecc/case.yaml` ready.

Start the agent in the V2 profile from the repository folder (`hermes -p rerate-v2`, or pick the profile in the
desktop app), open a NEW chat, and paste:

---

Read `agents/rerate-engineer/skills/rerate-run-v2/SKILL.md` and follow it.

Our customer sent a re-rate request for their compressor. The documents are in
`examples/01_nasa_hecc/inputs/` (re-rate request, baseline datasheet, casing limits). The geometry source is
NASA's coordinate tables in `examples/01_nasa_hecc/geometry_data/AppendixE.4_HotCoordinates`.

1. Draft the case file at `examples/01_nasa_hecc/case.yaml` from those documents (a draft already exists: check
   every value against the documents, fix anything wrong, and keep the sources). Show me every value with its
   source and every engineering choice, then wait for my approval.
2. After I approve, run every stage live: sizing, geometry change and solids, passage mesh, CFD, structural.
   Narrate each step in one line and print each stage's measured numbers as you go.
3. Give me the pass/fail report. Record failures instead of declaring unverified stages passed, and label
   results that come from simplified models.

---

The draft case in this folder is the one used for validation. A full run takes about 35 to 45 minutes on a
4-core CPU Fluent (Student license); most of it is the CFD solve.
