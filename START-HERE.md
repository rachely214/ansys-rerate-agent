# Start here

## What this is

This folder holds an AI assistant that runs a compressor re-rate study in Ansys, step by step, while you watch.
It reads a customer's request, asks you to approve the plan, then drives the Ansys apps and writes a pass/fail report.
It is a concept demo of an AI agent using engineering tools, not a validated design tool.

## What you need before you start

- [ ] A 64-bit Windows 10 or 11 computer.
- [ ] Ansys 2026 R1 (Student or commercial license) with these five apps: Vista CCD (in Workbench), Discovery,
      TurboGrid, Fluent and Mechanical.
- [ ] Hermes Agent installed, with an AI model that already works (tested with Claude Opus through the user's own
      provider). If you do not have Hermes yet, follow
      https://hermes-agent.nousresearch.com/docs/getting-started/installation first.
- [ ] This folder on your computer (downloaded with git or unzipped). Note where it is, for example
      `C:\Work\ansys-rerate-agent`.
- [ ] About 30 GB of free disk space (the NASA example data alone is about 5 GB).
- [ ] A computer you can leave unlocked for a few hours. The Ansys apps draw on the screen; a locked screen or a
      closed Remote Desktop window stops the run.

## Step 1: install the setup assistant

1. Open a terminal in this folder. (In File Explorer, open the folder, click the address bar, type `cmd` and
   press Enter.)
2. Run this one command:

   ```
   hermes profile install ./setup/setup-agent --name ansys-rerate-setup -y
   ```

3. Give the setup assistant an AI model. Run the command below and pick the same provider and model you use in
   your normal Hermes profile:

   ```
   hermes -p ansys-rerate-setup model
   ```

4. If it asks for an API key, paste it there. If it does not ask, add the key yourself (a new profile does not
   inherit keys from your normal profile). Replace `<provider>` with the provider name you picked:

   ```
   hermes -p ansys-rerate-setup auth add <provider> --type api-key
   ```

5. Check it works: `hermes -p ansys-rerate-setup chat -q "Reply with OK"` should print OK. If it says "401" or
   "credential is invalid", the key is missing or wrong: repeat step 4. The demo agent profile created later needs
   the same key; the setup assistant will tell you the command.

## Step 2: talk to the setup assistant

The setup assistant runs commands relative to this folder, so it must know where the folder is.

- **Hermes in a terminal:** open a terminal in this folder (as in Step 1) and run `hermes -p ansys-rerate-setup`.
- **Hermes desktop app:** choose the profile **ansys-rerate-setup**, start a new chat, and include the folder
  path in your first message.

First message to paste (replace the path with yours):

```
Please set up this computer for the Ansys re-rate demo. The repository folder is C:\Work\ansys-rerate-agent.
```

What it will do:

- Run a health check and tell you, in plain words, what is fine and what is missing.
- Install Python 3.13 if needed, a private Python environment for the Ansys tools, and the machine settings.
- Download the NASA example data (about 5 GB).
- Install the demo agent (Hermes profile **ansys-rerate-agent**) and connect its six Ansys tools.

What it will ask you:

- Permission before it installs software or starts the large download.
- Whether your Ansys license is Student or commercial.
- If the demo agent still needs a model key, it shows you the exact command. You type the key yourself; the
  assistant never asks for or sees passwords or keys.

It cannot install Ansys or fix a license. If something like that is missing, it says so and stops.

Setup takes about 20 to 60 minutes, plus the time for the 5 GB download.

**ALL GREEN** is the finish line. It is the last line of the health check (`python setup/check.py`), a fixed
script with no AI in it. ALL GREEN means every item passed and the computer is ready. Anything else ends with
`NOT READY: N problems`, and the assistant keeps fixing until it is green.

## Step 3: run the demo

1. Close Hermes completely, including the tray icon, and open it again. This loads the demo agent's tools.
2. Choose the profile **ansys-rerate-agent**.
3. Start a **new chat**.
4. Open `examples/01_nasa_hecc/prompt.md` and paste the text between the two lines into the chat.
5. The agent shows you every value of the study with its source and waits. Read it and reply that you approve
   (or say what to change).
6. Keep the computer unlocked, and keep any Remote Desktop window open, until the report is done.
   - On a weak connection, or before you walk away: in a Command Prompt run as administrator on the Ansys
     computer, type `tscon %sessionname% /dest:console`. Your Remote Desktop window closes but the desktop
     stays active, so the Ansys apps keep running. Reconnect later as usual. (A closed or dropped Remote Desktop
     window otherwise stops the run: the agent then stops on purpose and says so.)

How long it takes: about 2 to 5 hours on a 4-core computer with the Student license. Most of that is CFD.

What you get: a run folder under `%LOCALAPPDATA%\ansys-rerate-agent\runs\` with pictures, the Ansys files,
`REPORT.md` (a pass/fail report) and `RUN_NOTES.md` (the agent's notes and choices). Each check is PASS, FAIL or
NOT CHECKED, with a reason. `examples/01_nasa_hecc/expected.md` shows what a finished run looks like. Expect
"PASS ON CHECKED ITEMS ONLY": the CFD model is not calibrated, so the airflow results cannot pass. README.md
explains why.

## Optional: run it from a terminal and watch the log
The desktop app is the easiest way to watch. For an unattended run that survives a Hermes restart, start it from
a Command Prompt in this folder and write a log:

```
hermes -p ansys-rerate-agent chat -q "<the prompt text>" > "%LOCALAPPDATA%\ansys-rerate-agent\run.log" 2>&1
```

Watch it from PowerShell (the `-Encoding UTF8` keeps the symbols readable):

```powershell
Get-Content "$env:LOCALAPPDATA\ansys-rerate-agent\run.log" -Wait -Tail 40 -Encoding UTF8
```

Runs started this way do not appear in the desktop app's session list (they are saved as one-shot sessions);
`hermes -p ansys-rerate-agent sessions list` shows them.

## If something goes wrong

- Run the health check from this folder: `python setup/check.py`. Each failed item has a line starting with
  `-> Fix:`.
- Look up the item name in `docs/TROUBLESHOOTING.md`.
- Or open the setup assistant again (Step 2) and tell it what happened. It reads the check and the
  troubleshooting page for you.
- If the demo agent stops and says the computer is not ready, that is on purpose. Fix it with the setup
  assistant, then start a new chat with the demo agent.

More detail: `README.md` (status and limits) and `docs/HOW-IT-WORKS.md` (how the parts fit together).
