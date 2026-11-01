# Support

Run the health check from the repository folder with the install-home Python:

```powershell
& "$env:LOCALAPPDATA\ansys-rerate-agent\venv\Scripts\python.exe" scripts\setup\check.py
```

Each failed item prints a `-> Fix:` line. Look up the item name in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

- Agent stops with "computer not ready": the desktop is locked or disconnected, or an app did not start.
  Reconnect, rerun the check, start a new chat.
- `runtime_current` FAIL: the repository changed but the tools were not reinstalled. Run
  `.\setup.ps1 -SkipExampleData`, then restart Hermes completely.
- `stale_servers` WARN: close Hermes completely, including the tray icon, and reopen it.
- `model_reachable` FAIL with 401: add the model key to the profile (SETUP.md).
- Remote Desktop dropped mid-run: before walking away, run `tscon %sessionname% /dest:console` in an
  administrator Command Prompt.

In a GitHub issue include: Ansys version and license type, Hermes version, model, the health check output, the
stage and tool call that failed, and the run folder's `run.json` stage entry (remove paths and keys).
