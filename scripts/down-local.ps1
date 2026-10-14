<#
.SYNOPSIS
  Stop (or delete) the local Shelfwise cluster so it stops using CPU and memory.

.EXAMPLE
  ./scripts/down-local.ps1           # stop minikube; everything comes back on the next start
  ./scripts/down-local.ps1 -Delete   # delete the cluster and all its data
#>
[CmdletBinding()]
param([switch]$Delete)

# Native tools report failure through exit codes, which are checked explicitly. "Stop"
# would also abort on harmless stderr output in Windows PowerShell 5.1.
$ErrorActionPreference = "Continue"

if ($Delete) {
    Write-Host "Deleting the minikube cluster and all of its data..." -ForegroundColor Yellow
    minikube delete
} else {
    Write-Host "Stopping minikube (run ./scripts/up-local.ps1 to start it again)..." -ForegroundColor Cyan
    minikube stop
}

# The docker compose stack, if it was started, is not needed alongside the cluster.
$root = Split-Path -Parent $PSScriptRoot
docker compose -f "$root/docker-compose.yml" down 2>$null | Out-Null
Write-Host "Done." -ForegroundColor Green
