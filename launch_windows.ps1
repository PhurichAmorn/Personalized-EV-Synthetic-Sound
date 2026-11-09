# One-command setup + launch for EV Sound Lab on Windows. No admin rights needed.
#   launch_windows.cmd           install whatever changed, start the app
#   launch_windows.cmd -Clean    also delete node_modules, the native build and caches first
#   launch_windows.cmd -Pull     run "git pull" first
param([switch]$Clean, [switch]$Pull)

# Native tools write to stderr normally; check $LASTEXITCODE ourselves instead of stopping on stderr text.
$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo

function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Warn($text) { Write-Host $text -ForegroundColor Yellow }
function Fail($text) { Write-Host ""; Write-Host "ERROR: $text" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- tools
Step 'Checking tools'
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    # Portable Node (no installer): any folder under %USERPROFILE%\tools that holds node.exe.
    $portable = Get-ChildItem "$env:USERPROFILE\tools" -Directory -Filter 'node*' -ErrorAction SilentlyContinue |
        Where-Object { Test-Path "$($_.FullName)\node.exe" } | Sort-Object Name -Descending | Select-Object -First 1
    if ($portable) { $env:Path = "$($portable.FullName);$env:Path" }
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Fail 'Node.js not found. Install Node LTS, or extract the Node zip into %USERPROFILE%\tools\ (node.exe inside the folder).'
}
$env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    Fail 'Rust not found. Install it from https://rustup.rs (per-user install, no admin needed).'
}
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Fail 'Python launcher "py" not found. Install Python 3.12 from python.org.'
}
py -3.12 --version | Out-Null
if ($LASTEXITCODE -ne 0) { Fail 'Python 3.12 not found. Install it from python.org (it can sit next to other versions).' }
Write-Host ("node " + (node -v) + "  |  " + (cargo --version) + "  |  " + (py -3.12 --version))

# ---------------------------------------------------------------- leftovers (the usual cause of EBUSY)
Step 'Stopping leftover EV Sound Lab processes'
$stopped = 0
Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and (
        ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($repo, [System.StringComparison]::OrdinalIgnoreCase)) -or
        ($_.CommandLine -and $_.CommandLine.IndexOf('backend.sidecar', [System.StringComparison]::OrdinalIgnoreCase) -ge 0) -or
        (($_.Name -eq 'node.exe') -and $_.CommandLine -and $_.CommandLine.IndexOf($repo, [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
    )
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    $stopped++
}
Write-Host "stopped $stopped process(es)"
Start-Sleep -Milliseconds 800

# ---------------------------------------------------------------- update
if ($Pull) {
    Step 'Updating code (git pull)'
    git pull --ff-only
    if ($LASTEXITCODE -ne 0) { Warn 'git pull did not finish (local changes or no network). Continuing with the code you have.' }
}

# ---------------------------------------------------------------- clean
function Remove-Folder($path) {
    for ($try = 1; $try -le 4; $try++) {
        if (-not (Test-Path $path)) { return }
        Remove-Item -Recurse -Force $path -ErrorAction SilentlyContinue
        if (-not (Test-Path $path)) { return }
        Start-Sleep -Seconds 1
    }
    Fail "Could not delete $path. A program still has files open there: close File Explorer windows, VS Code and extra PowerShell windows on this repo, then run again."
}
if ($Clean) {
    Step 'Cleaning (node_modules, caches, native build)'
    Remove-Folder "$repo\desktop\node_modules"
    Remove-Folder "$repo\desktop\dist"
    Remove-Folder "$repo\build"
    Get-ChildItem "$repo\audio" -Filter '_native_dsp*.pyd' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Remove-Item "$repo\.venv\.installed-requirements.txt" -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------- python
Step 'Python environment'
$venvPy = "$repo\.venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    & $venvPy -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)"
    if ($LASTEXITCODE -ne 0) { Warn 'Existing .venv is not Python 3.12; recreating it.'; Remove-Folder "$repo\.venv" }
}
if (-not (Test-Path $venvPy)) {
    py -3.12 -m venv "$repo\.venv"
    if ($LASTEXITCODE -ne 0) { Fail 'Could not create the Python virtual environment.' }
}
$reqStamp = "$repo\.venv\.installed-requirements.txt"
$reqHash = (Get-FileHash "$repo\requirements.txt").Hash
$reqSaved = ''
if (Test-Path $reqStamp) { $reqSaved = (Get-Content $reqStamp -Raw).Trim() }
if ($reqHash -ne $reqSaved) {
    & $venvPy -m pip install -r "$repo\requirements.txt"
    if ($LASTEXITCODE -ne 0) { Fail 'pip install failed (see the lines above).' }
    Set-Content -Path $reqStamp -Value $reqHash
} else {
    Write-Host 'Python packages up to date'
}

# ---------------------------------------------------------------- native module (rebuild only when sources are newer)
Step 'Native audio module'
$pyd = Get-ChildItem "$repo\audio" -Filter '_native_dsp*.pyd' -ErrorAction SilentlyContinue | Select-Object -First 1
$newest = Get-ChildItem -Path "$repo\audio\*" -Include '*.cpp', '*.h' -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
$setupPy = Get-Item "$repo\setup.py"
if ($setupPy.LastWriteTime -gt $newest.LastWriteTime) { $newest = $setupPy }
if ((-not $pyd) -or ($newest.LastWriteTime -gt $pyd.LastWriteTime)) {
    Write-Host 'Building (needs Visual Studio Build Tools with the C++ workload)...'
    & $venvPy "$repo\setup.py" build_ext --inplace
    if ($LASTEXITCODE -ne 0) { Fail 'Native build failed. Send the first line containing "error" above.' }
} else {
    Write-Host 'Native module up to date'
}
& $venvPy -c "import audio"
if ($LASTEXITCODE -ne 0) { Fail 'The native audio module does not load (see the message above).' }

# ---------------------------------------------------------------- frontend packages
Step 'Frontend packages'
Set-Location "$repo\desktop"
$lockHash = (Get-FileHash "$repo\desktop\package-lock.json").Hash
$lockStamp = "$repo\desktop\node_modules\.lock-hash"
$lockSaved = ''
if (Test-Path $lockStamp) { $lockSaved = (Get-Content $lockStamp -Raw).Trim() }
$viteOk = Test-Path "$repo\desktop\node_modules\.bin\vite.cmd"
if ((-not $viteOk) -or ($lockHash -ne $lockSaved)) {
    # A half-finished install is what produces "vite not found": start from a clean folder.
    if (-not $viteOk) { Remove-Folder "$repo\desktop\node_modules" }
    npm.cmd install
    if ($LASTEXITCODE -ne 0) { Fail 'npm install failed. Look for the "npm error" lines above (a "path:" line names a locked file).' }
    Set-Content -Path $lockStamp -Value $lockHash
} else {
    Write-Host 'Frontend packages up to date'
}

# ---------------------------------------------------------------- run
Step 'Starting EV Sound Lab (the first Rust build takes several minutes; later starts are fast)'
npm.cmd run tauri -- dev
