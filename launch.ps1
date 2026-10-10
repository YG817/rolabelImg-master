param(
    [switch]$CheckOnly,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ImageArguments
)
$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
Set-Location -LiteralPath $projectDirectory
$candidates = [System.Collections.Generic.List[string]]::new()
function Add-PythonCandidate([string]$candidate) {
    if ($candidate -and -not $candidates.Contains($candidate)) {
        $candidates.Add($candidate)
    }
}
Add-PythonCandidate $env:ROLABELIMG_PYTHON
Add-PythonCandidate (Join-Path $projectDirectory '.venv\Scripts\python.exe')
if ($env:CONDA_PREFIX) { Add-PythonCandidate (Join-Path $env:CONDA_PREFIX 'python.exe') }
$pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if ($pythonCommand -and $pythonCommand.Source -notlike '*\WindowsApps\*') {
    Add-PythonCandidate $pythonCommand.Source
}
$pyCommand = Get-Command py.exe -ErrorAction SilentlyContinue
if ($pyCommand) {
    $detectedPython = & $pyCommand.Source -3 -c 'import sys; print(sys.executable)' 2>$null
    if ($LASTEXITCODE -eq 0) { Add-PythonCandidate ([string]$detectedPython) }
}
$condaEnvironments = Join-Path $env:USERPROFILE '.conda\environments.txt'
if (Test-Path -LiteralPath $condaEnvironments) {
    foreach ($environmentPath in Get-Content -LiteralPath $condaEnvironments) {
        if ($environmentPath.Trim()) { Add-PythonCandidate (Join-Path $environmentPath.Trim() 'python.exe') }
    }
}
$pythonInstallDirectory = Join-Path $env:LOCALAPPDATA 'Programs\Python'
if (Test-Path -LiteralPath $pythonInstallDirectory) {
    foreach ($installation in Get-ChildItem -LiteralPath $pythonInstallDirectory -Directory) {
        Add-PythonCandidate (Join-Path $installation.FullName 'python.exe')
    }
}
$selectedPython = $null
$failures = [System.Collections.Generic.List[string]]::new()
foreach ($candidate in $candidates) {
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    try {
        # lxml is optional: Pascal VOC also supports the standard XML library.
        $check = & $candidate -c 'import PyQt5.QtWidgets, rasterio, numpy; import roLabelImg' 2>&1
        if ($LASTEXITCODE -eq 0) {
            $selectedPython = $candidate
            break
        }
        $failures.Add($candidate + ': ' + (($check | Select-Object -Last 1) -join ' '))
    } catch {
        $failures.Add($candidate + ': ' + $_.Exception.Message)
    }
}
if (-not $selectedPython) {
    Write-Host 'No Python environment with PyQt5, rasterio and numpy was found.'
    Write-Host 'Install requirements.txt in your Python environment, then retry.'
    Write-Host 'You can set ROLABELIMG_PYTHON to the full path of python.exe.'
    foreach ($failure in $failures) { Write-Host $failure }
    exit 1
}
Write-Host ('Python: ' + $selectedPython)
if ($CheckOnly) { exit 0 }
function Quote-ProcessArgument([string]$argument) {
    # Match the Windows command-line quoting rules, including trailing slashes.
    $quoted = [regex]::Replace($argument, '(\\*)"', '$1$1\"')
    $quoted = [regex]::Replace($quoted, '(\\+)$', '$1$1')
    return '"' + $quoted + '"'
}
$arguments = @((Join-Path $projectDirectory 'roLabelImg.py')) + $ImageArguments
$argumentLine = ($arguments | ForEach-Object { Quote-ProcessArgument $_ }) -join ' '
$windowPython = Join-Path (Split-Path -Parent $selectedPython) 'pythonw.exe'
if (Test-Path -LiteralPath $windowPython) { $selectedPython = $windowPython }
Start-Process -FilePath $selectedPython -ArgumentList $argumentLine -WorkingDirectory $projectDirectory -WindowStyle Normal | Out-Null
