# Release checklist

Do not publish until every box is checked or the item is listed as an open limitation in docs/VALIDATION.md.

## Content whose redistribution rights are unclear (not committed)

| Item | Where | Status | Decision needed |
|---|---|---|---|
| NASA HECC impeller coordinates (NASA/CR-2014-218114/REV1 supplement, App. E.4, tables C_1 to C_24) | install home `example-data/` (downloaded by setup) | Download only. The supplement's `README_ExportControlClassification.txt` states the documents contain no technical data subject to the EAR or ITAR. | Confirm NASA release terms before any redistribution; keep download-only. |
| Ti-6Al-4V material properties | `examples/01_nasa_hecc/materials/ti6al4v_public.yaml` (committed) | Written from public data with citations (MMPDS / MIL-HDBK-5J). No Ansys library file. | Confirm citation wording. |
| Re-rate request and casing limits documents | `examples/01_nasa_hecc/inputs/` (committed) | Synthetic, written for this project; datasheet values cite the public NASA AIAA paper. | Confirm OK to publish. |
| In-app Ansys scripts (Discovery, Mechanical APIs) | `plugins/ansys-mcp/src/rerate_mcp_v2/app_scripts/` (committed) | Original code calling documented Ansys APIs; no Ansys code copied. | Check Ansys API terms for public scripts. |
| Run outputs (REPORT.md, Discovery/Fluent/Mechanical screenshots) | install home `runs/` (not in repo) | Screenshots of Ansys GUIs. | Keep out until cleared; then add as historical example outputs only. |

## Repository release

- [ ] README and SETUP links resolve and match the installer's actual behavior.
- [ ] `python -m unittest discover -s tests` passes.
- [ ] `python scripts/setup/verify_layout.py` passes (required files; no example machine numbers, user paths, keys; no
      arbitrary-code tools).
- [ ] `.\setup.ps1` run twice on the same machine; second run changes nothing; health check ALL GREEN.
- [ ] No install home, `runs/`, `work/`, `.venv/`, `*.trn`, `*.log`, credentials or NASA data in `git ls-files`.
- [ ] Skills describe method and judgement, not a hidden end-to-end script.
- [ ] Every known gap is in docs/VALIDATION.md and in the README "does not demonstrate" line.
- [ ] Owner decisions: maintainers list, NASA data terms, NVIDIA open-source review.

## Demo readiness (separate from source publication)

- [ ] Fresh clone on a second machine with only Ansys, Git, Python and Hermes; README and SETUP only; ALL GREEN.
- [ ] Hermes restarted after setup; `stale_servers` and `runtime_current` PASS.
- [ ] Desktop session stays connected (or console handover) for the whole run.
- [ ] Full run from `prompt_demo.md` with demo-mode caps active; record model, provider, time and any human input.
- [ ] Session audited: no earlier runs, reports or validation docs read; every number from this run.
- [ ] Test a named model before making a compatibility claim for it.

## Before calling it production-ready (not this release)

- [ ] Commercial-license validation (concurrent apps, GPU Fluent, headless modes).
- [ ] Calibrated CFD (as-manufactured geometry, resolved boundary layer) before any aero result is trusted.
- [ ] A converged solution at the target flow for a re-rated design.
- [ ] Repeatability across a second machine and a second Ansys release.

Publish experimental source with unresolved validation items clearly labeled. Never convert an unchecked item
into a success statement.
