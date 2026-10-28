# Contributing

## Principles (keep these)
1. **No machine data in code.** Numbers for a specific compressor belong in its `case.yaml`, with a source.
   `scripts/setup/verify_layout.py` scans for known example values, user paths and key-like strings.
2. **No end-to-end scripts.** Skills describe method and judgement; MCP tools perform one specific action each.
3. **No arbitrary-code tools.** A new capability is a new named action with typed parameters. In-app scripts are
   fixed files; pass values as a JSON block.
4. **Honest results.** A stage records `status` (ok / partial / error) and its model fidelity. Never turn a
   missing result into a PASS.
5. **Nothing blocks long.** Any action that can take minutes uses start / status / fetch.

## Adding things
- **Geometry adapter:** add `adapters/<name>.py` with `read(source, options) -> NeutralImpeller`, register it in
  `adapters/__init__.py`, add `allowed` to the schema, add tests with a synthetic geometry.
- **Case field:** add it to `schema/case_schema.yaml` with `kind`/`type`, `required` and the `stages` that use it;
  no default.
- **Design lever:** add a function in `adapters/modify.py` acting on the neutral form, a tool action that
  records its parameters, a stage-skill section explaining when to use it, and tests.
- **Report row:** extend `report.scorecard`; include its fidelity and a NOT CHECKED path; add a test.

## Before a pull request
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\setup\verify_layout.py
.\.venv\Scripts\python.exe scripts\setup\doctor.py --mcp
```
Describe what was run live (which Ansys version and license) in the PR and update `docs/VALIDATION.md`.
Do not commit run outputs, `.local/`, credentials, Ansys data files or third-party data with unclear rights.
