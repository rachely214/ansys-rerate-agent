## Changes and rationale

## Verification
- [ ] `python -m unittest discover -s tests` passes
- [ ] `python scripts/setup/verify_layout.py` reports 0 scan findings
- [ ] `python scripts/setup/check.py` ALL GREEN on a real install (if setup or runtime changed)
- [ ] Skills edited in `agents/rerate-engineer/skills/` or `scripts/setup/setup-agent/skills/`
- [ ] No credentials, personal paths, run folders or NASA data staged
- [ ] Live Ansys evidence vs unit tests explicitly distinguished; docs/VALIDATION.md updated
- [ ] Open validation gaps documented

## Tool, gate or report changes
Include Ansys version, the exact tool call, the measured result and the expected result. Do not infer success
from a tool return alone or relax a check without a rationale in docs/DECISIONS.md.
