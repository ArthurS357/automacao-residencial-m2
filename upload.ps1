# ASCII-only PowerShell wrapper.
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\upload.ps1
# Optional slow fallback:
#   powershell -ExecutionPolicy Bypass -File .\upload.ps1 --method exec --chunk-size 192

param(
    [string]$TargetHost = "localhost",
    [int]$Port = 4000,
    [int]$MaxRetries = 20,
    [int]$RetryDelay = 2,
    [switch]$NoReset,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$UploaderArgs = @(
    ".\tools\upload_wokwi_micropython.py",
    "--host", $TargetHost,
    "--port", $Port,
    "--retries", $MaxRetries,
    "--delay", $RetryDelay
)

if ($NoReset) {
    $UploaderArgs += "--no-reset"
}

if ($ExtraArgs) {
    $UploaderArgs += $ExtraArgs
}

& python @UploaderArgs
exit $LASTEXITCODE
