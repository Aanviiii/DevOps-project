<#
.SYNOPSIS
  Build the whole Shelfwise platform on a local minikube cluster with one command.

.DESCRIPTION
  1. Starts minikube with the ingress and metrics-server add-ons.
  2. Installs kube-prometheus-stack (Prometheus + Grafana) into "monitoring".
  3. Installs Argo CD and Argo CD Image Updater into "argocd".
  4. Applies the shelfwise namespace, the Argo CD Application and the ImageUpdater.
  5. Waits until Argo CD reports the app Synced and Healthy.

  From then on, every push to main that passes CI is deployed automatically.
  Re-running the script is safe: every step is an upgrade or an apply.

.EXAMPLE
  ./scripts/up-local.ps1
  ./scripts/up-local.ps1 -Cpus 6 -MemoryMb 8192
#>
[CmdletBinding()]
param(
    [int]$Cpus = 4,
    [int]$MemoryMb = 7168,
    [string]$KubernetesVersion = "v1.35.0"
)

# Native tools report failure through exit codes, which are checked explicitly. "Stop"
# would also abort on harmless stderr output in Windows PowerShell 5.1.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot

# Chart versions are pinned so the platform builds the same way every time.
$ArgoCdChart = "10.10.3"
$ImageUpdaterChart = "1.3.2"
$PrometheusStackChart = "92.7.0"

function Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }
function Invoke-Checked {
    param([string]$What, [scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)" }
}

Step "Checking tools"
foreach ($tool in "docker", "minikube", "kubectl", "helm") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool is not installed or not on PATH."
    }
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker is not running. Start Docker Desktop and try again." }

Step "Starting minikube ($Cpus CPUs, $MemoryMb MB, Kubernetes $KubernetesVersion)"
$status = minikube status --format "{{.APIServer}}" 2>$null
if ($status -ne "Running") {
    Invoke-Checked "minikube start" {
        minikube start --driver=docker --cpus=$Cpus --memory=$MemoryMb `
            --kubernetes-version=$KubernetesVersion --addons=ingress,metrics-server
    }
} else {
    Write-Host "minikube is already running."
    Invoke-Checked "enable add-ons" { minikube addons enable ingress; minikube addons enable metrics-server }
}
Invoke-Checked "select context" { kubectl config use-context minikube }

Step "Adding Helm repositories"
helm repo add argo https://argoproj.github.io/argo-helm --force-update | Out-Null
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update | Out-Null
Invoke-Checked "helm repo update" { helm repo update | Out-Null }

Step "Installing Prometheus and Grafana (kube-prometheus-stack $PrometheusStackChart)"
Invoke-Checked "monitoring install" {
    helm upgrade --install monitoring prometheus-community/kube-prometheus-stack `
        --version $PrometheusStackChart -n monitoring --create-namespace `
        -f "$root/monitoring/kube-prometheus-stack.values.yaml" --wait --timeout 15m
}

Step "Installing Argo CD $ArgoCdChart and Image Updater $ImageUpdaterChart"
Invoke-Checked "argo cd install" {
    helm upgrade --install argocd argo/argo-cd --version $ArgoCdChart -n argocd --create-namespace `
        -f "$root/k8s/argocd/argocd-values.yaml" --wait --timeout 10m
}
Invoke-Checked "image updater install" {
    helm upgrade --install argocd-image-updater argo/argocd-image-updater --version $ImageUpdaterChart `
        -n argocd -f "$root/k8s/argocd/image-updater-values.yaml" --wait --timeout 5m
}

Step "Handing Shelfwise to Argo CD"
Invoke-Checked "apply manifests" {
    kubectl apply -f "$root/k8s/namespace.yaml"
    kubectl apply -f "$root/k8s/argocd/application.yaml"
    kubectl apply -f "$root/k8s/argocd/image-updater.yaml"
}

Step "Waiting for Argo CD to sync the app (up to 10 minutes)"
$deadline = (Get-Date).AddMinutes(10)
do {
    Start-Sleep -Seconds 10
    $state = kubectl get application shelfwise -n argocd `
        -o jsonpath="{.status.sync.status}/{.status.health.status}" 2>$null
    Write-Host "  $state"
} until ($state -eq "Synced/Healthy" -or (Get-Date) -gt $deadline)
if ($state -ne "Synced/Healthy") { throw "Argo CD did not report Synced/Healthy in time; check the Argo CD UI." }

kubectl get pods -n shelfwise

$argoPassword = kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" 2>$null
if ($argoPassword) { $argoPassword = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($argoPassword)) }
$grafanaPassword = kubectl -n monitoring get secret monitoring-grafana -o jsonpath="{.data.admin-password}"
$grafanaPassword = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($grafanaPassword))

Write-Host @"

Shelfwise is running.

One-time setup (Administrator):
  Add this line to C:\Windows\System32\drivers\etc\hosts
    127.0.0.1 shelfwise.local argocd.shelfwise.local grafana.shelfwise.local prometheus.shelfwise.local

Keep this running in an Administrator terminal while you use the URLs:
    minikube tunnel

  App         http://shelfwise.local
  Argo CD     http://argocd.shelfwise.local     admin / $argoPassword
  Grafana     http://grafana.shelfwise.local    admin / $grafanaPassword
  Prometheus  http://prometheus.shelfwise.local

Stop everything with ./scripts/down-local.ps1 (or -Delete to remove the cluster).
"@ -ForegroundColor Green
