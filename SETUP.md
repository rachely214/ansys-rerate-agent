# Installation (Windows, host-local)

## Prerequisites

- 64-bit Windows 10 or 11, about 30 GB free disk, a desktop session you can leave unlocked for a few hours.
- **Ansys 2026 R1** (Student or commercial) with Vista CCD (in Workbench), Discovery, TurboGrid, Fluent and
  Mechanical. Setup does not install or license Ansys.
- **Git**, **Python 3.13** (or 3.12; the Ansys Python libraries do not support 3.14 yet) and
  **Hermes Agent** with a model that already answers in your normal profile.

Sources: [Git](https://git-scm.com/download/win), [Python](https://www.python.org/downloads/),
[Hermes](https://hermes-agent.nousresearch.com/docs/getting-started/installation).

Use a model capable of sustained tool use over several hours. Validated: Claude Opus and DeepSeek V4 Flash
(docs/VALIDATION.md).

## Prepare automatically

Open PowerShell in the clone and run `.\setup.ps1`. If PowerShell blocks scripts, inspect the file and follow your
organization's policy; do not disable machine-wide policy.

It runs the installer steps in `scripts/setup/install_runtime.py`, then the health check:
1. a Python environment in the install home (`%LOCALAPPDATA%\ansys-rerate-agent\venv`, or `$env:ANSYS_RERATE_HOME`);
2. the locked packages (`scripts/setup/requirements.lock`) and the agent tools from `plugins/ansys-mcp/` (a copy, not editable);
3. `machine.config.yaml` in the install home (Ansys path and version, license mode, Fluent cores, demo mode);
4. the NASA example geometry, about 4.9 GB, resumable;
5. the Hermes profile `ansys-rerate-agent` with its six MCP servers. Your default Hermes profile is not changed.

Options: `-License student|commercial`, `-SkipExampleData`, `-SkipProfile`, `-Python <path>`, `-Proxy <url>`.
Each step is safe to run again. Run outputs and machine state stay in the install home, never in the clone.

**ALL GREEN** on the last line means ready. Otherwise the check ends with `NOT READY: N problems`; each failed
item prints a `-> Fix:` line, explained in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Or: let the setup assistant do it

A second Hermes profile walks a first-time user through the same steps in plain language and fixes failed
checks. It never asks for or sees keys.

```powershell
hermes profile install ./scripts/setup/setup-agent --name ansys-rerate-setup -y
hermes -p ansys-rerate-setup model
```

Then start a chat with that profile and say: `Please set up this computer for the Ansys re-rate demo. The
repository folder is <path to this clone>.` It finishes when the health check says ALL GREEN.

## One-time model key

A new Hermes profile copies the model choice from your default profile but not the key. Add it yourself:

```powershell
hermes -p ansys-rerate-agent auth add <provider> --type api-key
```

The health check item `model_reachable` sends one short test message and proves the key works (HTTP 401 means the
key is missing or wrong). To try another model: `hermes -p ansys-rerate-agent model`.

## Before the first run

1. Close Hermes completely, including the tray icon, and reopen it, so the profile loads its tools.
2. Choose the profile **ansys-rerate-agent** and start a new chat.
3. Keep the desktop unlocked until the report is written. The Ansys apps draw on this desktop; a locked screen or
   a closed Remote Desktop window stops the run, and the agent then stops on purpose and says so. Before walking
   away, or on a weak connection, run `tscon %sessionname% /dest:console` in an administrator Command Prompt.

## Demo mode

On by default (`demo_mode` in `machine.config.yaml`): at most 45 minutes per Fluent solve, 90 minutes of solving
per run, and no fallback speedline. A capped result is NOT CHECKED, never PASS. Set `enabled: false` for a full
study (2 to 5 hours on a 4-core Student computer).

## Watching an unattended run

The desktop app is the easiest way to watch. For a run that survives a Hermes restart, start it from a terminal:

```powershell
hermes -p ansys-rerate-agent chat -q "<prompt text>" > "$env:LOCALAPPDATA\ansys-rerate-agent\run.log" 2>&1
Get-Content "$env:LOCALAPPDATA\ansys-rerate-agent\run.log" -Wait -Tail 40 -Encoding UTF8
```

Runs started this way are one-shot sessions and do not appear in the desktop app's list;
`hermes -p ansys-rerate-agent sessions list` shows them.

## Updating

After `git pull`, run `.\setup.ps1 -SkipExampleData` and restart Hermes completely. The health check item
`runtime_current` fails until the installed tools match the repository.

## Validation boundary

Setup and tests do not remove Ansys version, license or desktop-session differences. A fresh install on a second
machine driven only by these instructions has not been done yet. See [docs/VALIDATION.md](docs/VALIDATION.md) and
[SECURITY.md](SECURITY.md).
