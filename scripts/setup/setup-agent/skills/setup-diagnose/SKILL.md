---
name: setup-diagnose
description: "Use when a setup step or health-check item fails for the Ansys re-rate demo. Finds the cause and fixes it."
version: 1.0.0
license: Apache-2.0
metadata:
  hermes:
    tags: [setup, ansys, troubleshooting]
    related_skills: [setup-run, ansys-host-diagnostics]
---

# Setup: diagnose and fix

Start from the failing item's id in `PY scripts/setup/check.py` (or `--json` for details). Read its entry in
`docs/TROUBLESHOOTING.md`, apply the fix, then rerun the check. One item at a time, first FAIL first.

Success: the item turns PASS (or WARN with a reason the user accepts) on the next check.

## Known causes (learned on real machines)
| Symptom | Cause | Fix |
|---|---|---|
| `python_supported` FAIL although Python is installed | only Python 3.14 or newer, or only the Microsoft Store stub | install 3.13 (setup-run step 2); never use the Hermes-bundled Python |
| `packages` FAIL, pip errors about SSL or connection | company proxy or firewall | ask for the proxy, rerun `packages --proxy ...`; or ask IT |
| `packages` FAIL, "Microsoft Visual C++ ... required" | a package needed a compiler | rerun `packages` (the lock uses prebuilt wheels); if it repeats, report the package name |
| `install_path_ok` FAIL | install home in OneDrive or path too long | set `ANSYS_RERATE_HOME` to a short local folder (for example `C:\rerate`) and rerun install steps |
| `profile_mcp_wired` FAIL | profile installed before the venv or config existed, or paths changed | rerun `install_runtime.py profile` |
| `mcp_*` FAIL "did not start" | runtime package missing or broken in the venv | rerun `packages`; then `profile`; then the check |
| `mcp_*` FAIL, works in the check but not in Hermes | Hermes still runs old server processes | user closes Hermes completely (tray icon too) and reopens it |
| `stale_servers` WARN | servers started before the last install | same: close Hermes completely and reopen it |
| `profile_model_set` FAIL | default profile had no model to copy | `hermes -p ansys-rerate-agent model` and let the user pick |
| `profile_key_present` WARN or FAIL | no key for the chosen provider | show the user `hermes -p ansys-rerate-agent auth add <provider>`; they type the key |
| `license_denials` WARN | recent Ansys license denials in the license log | quote the line to the user; for Student check that no other Ansys app is open; otherwise their license administrator must help |
| `ansys_found` FAIL with another version | this demo is tested with Ansys 2026 R1 (v261) only | tell the user; other versions are not supported yet |
| `desktop_session` WARN | screen locked or Remote Desktop disconnected | fine during setup; for the run, keep the session open and unlocked |
| `example_data` FAIL after a download | download interrupted | rerun `example-data`; it resumes |

## Ansys-specific problems
Load `ansys-host-diagnostics` for app launch problems, licensing and the desktop session.

## Rules
- Change one thing, then rerun the check.
- Never delete the user's files outside the install home. Inside the install home, ask before deleting `runs\`.
- If two different fixes failed for the same item, stop and tell the user plainly what is wrong and what you
  tried. Suggest they share `PY scripts/setup/check.py --json` output with whoever supports them.
