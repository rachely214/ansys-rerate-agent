---
name: Bug report
about: Something behaves differently from what the skills or docs say
labels: bug
---

## What happened

## What the skill or doc says should happen

Quote the relevant line.

## Evidence

A tool returning `status: ok` is not evidence on its own. Include the measured values from `run.json` for the
stage.

## Environment

- Ansys version and license (Student / commercial):
- Hermes version and model:
- Health check summary line:
- OS:

## Checked first

- [ ] `scripts/setup/check.py` is ALL GREEN
- [ ] Desktop session was connected and unlocked during the run
- [ ] Not a retry of a step that had already succeeded
