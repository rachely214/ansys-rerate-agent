# Third-party notices

This repository's own code and documents are licensed under Apache-2.0 (see LICENSE).

## Software used (installed by setup, not vendored)
Pinned versions are in `scripts/setup/requirements.lock`. Main components and their licenses (check each package's metadata
for the authoritative text):

| Package | Purpose | License |
|---|---|---|
| ansys-fluent-core, ansys-turbogrid-core, ansys-mechanical-core, ansys-geometry-core (PyAnsys) | Ansys app control | MIT |
| fastmcp, mcp | MCP servers | Apache-2.0 / MIT |
| numpy | geometry math | BSD-3-Clause |
| PyYAML | case/config files | MIT |

Ansys products (Vista CCD, Discovery, TurboGrid, Fluent, Mechanical, Workbench) are commercial software licensed
separately by Ansys, Inc. This repository contains no Ansys software or Ansys data files. In-app scripts in
`plugins/ansys-mcp/src/rerate_mcp_v2/app_scripts/` are original code that calls documented Ansys scripting APIs.

## Data referenced but not included
- Ti-6Al-4V properties in `examples/01_nasa_hecc/materials/ti6al4v_public.yaml` (committed; factual property
  values with citation): density, Young's modulus, Poisson's ratio and ultimate strength are typical values from
  ASM Aerospace Specification Metals, "Titanium Ti-6Al-4V (Grade 5), Annealed" material data sheet
  (asm.matweb.com, bassnum MTP641). Tensile yield is the design minimum (S-basis) Fty = 120 ksi for annealed
  Ti-6Al-4V from MIL-HDBK-5J / MMPDS (U.S. DoD / FAA). The Engineering Data XML Mechanical reads is generated from
  this file at run time by `rerate_mcp_v2.materials`; no Ansys library content is used.
- NASA High Efficiency Centrifugal Compressor (HECC) geometry: NASA/CR-2014-218114/REV1 supplemental files,
  NASA Glenn Research Center. Downloaded by the user from NTRS; see `examples/01_nasa_hecc/geometry_data.README.md`.
- Measured HECC performance values quoted in `examples/01_nasa_hecc/inputs/02_baseline_datasheet.md`:
  Braunscheidel et al., AIAA 2014-3632 (NASA Glenn). Quoted as published values with citation.
- Optional material XML files: a case may point at an Engineering Data XML exported by the user from their own
  Ansys installation; none ships here.

## Design reference
Repository structure modelled on `nvsdef/fusion-agentic-workflow` (structure and principles only; no code copied).

Trademarks belong to their owners. Not affiliated with or endorsed by Ansys, NASA, NVIDIA or Nous Research.
