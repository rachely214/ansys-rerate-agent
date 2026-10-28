# Material files

`case.yaml` points `material.library_file` at a material file. Two kinds work:

1. **A small YAML file with cited public data** (recommended). Example 01 uses
   `examples/01_nasa_hecc/materials/ti6al4v_public.yaml`. The structural stage converts it to the Engineering Data
   XML that Mechanical reads, at run time, into the run folder (`rerate_mcp_v2.materials`). Required keys: `name`,
   `density_kg_m3`, `youngs_modulus_pa`, `poisson_ratio`, `tensile_yield_pa`; give a source for each value.
2. **An Engineering Data XML** exported from your own Ansys installation (Workbench > Engineering Data >
   right-click the material > Export Engineering Data). It is used as is. Ansys library data is Ansys content:
   keep such files outside git (for example in the install home's `work\` folder). XML files in this folder are
   git-ignored.

Whichever you use, put the same yield strength into `material.yield_strength` in the case, with its source, and
re-approve the case if you change it.
