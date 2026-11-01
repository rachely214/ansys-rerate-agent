# One-command setup for the compressor re-rate agent (Windows PowerShell).
#
#   .\setup.ps1                     prepare everything and run the health check
#   .\setup.ps1 -License student    skip license auto-detection
#   .\setup.ps1 -SkipExampleData    do not download the NASA example data (about 4.9 GB)
#   .\setup.ps1 -SkipProfile        do not install or update the Hermes demo profile
#
# This is a thin wrapper around the existing installer steps (scripts\setup\install_runtime.py) and the health check
# (scripts\setup\check.py). It installs into %LOCALAPPDATA%\ansys-rerate-agent (or $env:ANSYS_RERATE_HOME). It does not
# install or license Ansys, does not install Python or Hermes, never reads or writes API keys, and never changes
# your default Hermes profile. Each step is safe to run again.
param([ValidateSet('', 'student', 'commercial')][string]$License = '',
      [switch]$SkipExampleData, [switch]$SkipProfile, [string]$Python = '', [string]$Proxy = '')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Find-Python {
    if ($Python) { return $Python }
    foreach ($v in '3.13', '3.12') {
        $p = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $p) { return $p.Trim() }
    }
    throw 'Python 3.13 (or 3.12) not found. Install it from https://www.python.org/downloads/ (the Ansys Python libraries do not support 3.14 yet), then run .\setup.ps1 again, or pass -Python <path to python.exe>.'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Install Git first: https://git-scm.com/download/win' }
if (-not (Get-Command hermes -ErrorAction SilentlyContinue) -and -not $SkipProfile) {
    throw 'Install Hermes Agent first: https://hermes-agent.nousresearch.com/docs/getting-started/installation (or run with -SkipProfile).'
}
$py = Find-Python
$common = @()
if ($Proxy) { $common += @('--proxy', $Proxy) }

& $py scripts\setup\install_runtime.py venv --python $py
if ($LASTEXITCODE -ne 0) { throw 'Creating the Python environment failed; see above.' }
$home_ = (& $py -c "import sys; sys.path.insert(0,'scripts/setup'); import check; print(check.install_home())").Trim()
$venvPy = Join-Path $home_ 'venv\Scripts\python.exe'

& $venvPy scripts\setup\install_runtime.py packages @common
if ($LASTEXITCODE -ne 0) { throw 'Installing packages failed; see above.' }
$cfgArgs = @('config')
if ($License) { $cfgArgs += @('--license', $License) }
& $venvPy scripts\setup\install_runtime.py @cfgArgs
if ($LASTEXITCODE -ne 0) { throw 'Writing the machine config failed; see above.' }
if (-not $SkipExampleData) {
    & $venvPy scripts\setup\install_runtime.py example-data
    if ($LASTEXITCODE -ne 0) { throw 'Example data download failed or is incomplete; run .\setup.ps1 again to resume.' }
}
if (-not $SkipProfile) {
    & $venvPy scripts\setup\install_runtime.py profile
    if ($LASTEXITCODE -ne 0) { throw 'Installing the Hermes demo profile failed; see above.' }
}
& $venvPy scripts\setup\check.py
if ($LASTEXITCODE -ne 0) { Write-Host 'Not ready yet: fix the items marked FAIL (each has a "-> Fix:" line), see SETUP.md.'; exit 1 }
Write-Host 'Setup complete. Follow SETUP.md for the one-time model key step, then start a new chat with profile ansys-rerate-agent.'
