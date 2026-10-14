<#
.SYNOPSIS
  Create the AWS VPC + EKS cluster with Terraform and deploy Shelfwise to it.

.DESCRIPTION
  1. terraform init / plan / apply in ./terraform (asks before applying unless -AutoApprove).
  2. Points kubectl at the new cluster.
  3. Installs the ingress-nginx controller (creates one AWS load balancer).
  4. Creates the namespace and a database Secret with a random password.
  5. helm upgrade --install with values-eks.yaml and the image built for -ImageTag.
  6. Prints the public URL.

  EKS costs about $0.16 an hour in total. Run ./scripts/eks-down.ps1 as soon as
  you have finished.

.EXAMPLE
  ./scripts/eks-up.ps1                       # deploys the image for the current commit
  ./scripts/eks-up.ps1 -ImageTag sha-1a2b3c4
#>
[CmdletBinding()]
param(
    [string]$Region = "ap-south-1",
    [string]$ClusterName = "shelfwise",
    [string]$ImageTag = "",
    [switch]$AutoApprove
)

# Native tools report failure through exit codes, which are checked explicitly. "Stop"
# would also abort on harmless stderr output in Windows PowerShell 5.1.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$IngressNginxChart = "4.15.1"

function Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }
function Invoke-Checked {
    param([string]$What, [scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)" }
}

Step "Checking tools and AWS credentials"
foreach ($tool in "aws", "terraform", "kubectl", "helm", "git") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool is not installed or not on PATH." }
}
$identity = aws sts get-caller-identity --query Arn --output text
if ($LASTEXITCODE -ne 0) { throw "AWS credentials are not configured. Run 'aws configure' first." }
Write-Host "Using AWS identity $identity in $Region"

if (-not $ImageTag) { $ImageTag = "sha-" + (git -C $root rev-parse --short=7 HEAD) }
Write-Host "Deploying images tagged $ImageTag"

Step "Provisioning VPC + EKS with Terraform (about 15 minutes)"
Push-Location "$root/terraform"
try {
    Invoke-Checked "terraform init" { terraform init -input=false }
    Invoke-Checked "terraform plan" {
        terraform plan -input=false -out tfplan -var "region=$Region" -var "cluster_name=$ClusterName"
    }
    if (-not $AutoApprove) {
        $answer = Read-Host "Apply this plan and start paying for EKS (~`$0.16/hour)? Type yes"
        if ($answer -ne "yes") { throw "Cancelled before apply. Nothing was created." }
    }
    Invoke-Checked "terraform apply" { terraform apply -input=false tfplan }
} finally {
    Pop-Location
}

Step "Configuring kubectl"
Invoke-Checked "update-kubeconfig" { aws eks update-kubeconfig --region $Region --name $ClusterName }
kubectl get nodes -o wide

Step "Installing the ingress-nginx controller (creates an AWS load balancer)"
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx --force-update | Out-Null
helm repo update | Out-Null
Invoke-Checked "ingress-nginx" {
    helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx --version $IngressNginxChart `
        -n ingress-nginx --create-namespace `
        --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"=nlb `
        --set controller.resources.requests.cpu=50m --set controller.resources.requests.memory=96Mi `
        --wait --timeout 10m
}

Step "Creating the namespace and database credentials"
Invoke-Checked "namespace" { kubectl apply -f "$root/k8s/namespace.yaml" }
kubectl get secret shelfwise-db -n shelfwise *> $null
if ($LASTEXITCODE -ne 0) {
    # A fresh random password, never written to disk or to Git.
    $bytes = New-Object byte[] 24
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $password = ([Convert]::ToBase64String($bytes) -replace "[^A-Za-z0-9]", "").Substring(0, 24)
    $url = "postgresql+psycopg://shelfwise:$password@shelfwise-postgres:5432/shelfwise"
    Invoke-Checked "db secret" {
        kubectl create secret generic shelfwise-db -n shelfwise `
            --from-literal=postgres-password=$password --from-literal=database-url=$url
    }
}

Step "Deploying Shelfwise $ImageTag with Helm"
Invoke-Checked "helm install" {
    helm upgrade --install shelfwise "$root/helm/shelfwise" -n shelfwise `
        -f "$root/helm/shelfwise/values-eks.yaml" --set image.tag=$ImageTag --wait --timeout 10m
}
Invoke-Checked "helm test" { helm test shelfwise -n shelfwise --logs }

kubectl get pods,svc,hpa,ingress -n shelfwise
helm list -n shelfwise

$lb = kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath="{.status.loadBalancer.ingress[0].hostname}"
Write-Host @"

Shelfwise is live on EKS:  http://$lb
(the load balancer's DNS name can take a couple of minutes to resolve)

When you are done:  ./scripts/eks-down.ps1
"@ -ForegroundColor Green
