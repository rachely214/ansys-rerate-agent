# Security

## What runs where
- The six limited-action MCP servers run on the Windows host as the logged-in user and start/stop Ansys applications, write files
  under the install home's `runs\` and `work\` folders (`%LOCALAPPDATA%\ansys-rerate-agent` by default), and read the case's geometry and material files.
- Limited-action means specific actions only: no server exposes a tool that executes agent-supplied code. In-app scripts are fixed files in the package;
  only a JSON block of case values is substituted.
- Stage tools close Ansys processes by name when `license.mode: student` (to free the single seat). Save open
  Ansys work before a run.
- With `transport: http` a server listens on the configured host/port without authentication. Bind it to
  `127.0.0.1` or a private network only, and firewall the port. Do not expose it to the internet.

## Credentials
The repository stores no credentials, license keys or model-provider keys. Hermes keeps model credentials in
its own profile; setup copies the model choice (never keys) into the `ansys-rerate-agent` profile and does not read or print
secrets. Never commit the install home, `.env` files or Hermes profile folders.

## Approvals
Keep Hermes approval prompts enabled. Approval denial or timeout is a stop condition for the agent.

## Reporting
Report vulnerabilities privately through GitHub's private vulnerability reporting on this repository (Security
tab, "Report a vulnerability"). Do not open public issues for security problems.
