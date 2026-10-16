<#
.SYNOPSIS
  Tear down everything eks-up.ps1 created, in an order that leaves nothing billing.

.DESCRIPTION
  Kubernetes creates two AWS resources that Terraform does not know about: the
  ingress load balancer and the EBS volume behind the Postgres claim. If they still
  exist, terraform destroy cannot delete the VPC, and an orphaned volume or load
  balancer keeps costing money. So this script:

    1. uninstalls Shelfwise and deletes its PersistentVolumeClaims (EBS volume),
    2. uninstalls ingress-nginx and waits until AWS has removed the load balancer,
    3. runs terraform destroy,
    4. lists anything still tagged Project=shelfwise, which should be nothing.

.EXAMPLE
  ./scripts/eks-down.ps1
  ./scripts/eks-down.ps1 -AutoApprove
#>
[CmdletBinding()]
param(
    [string]$Region = "ap-southeast-2",
    [string]$ClusterName = "shelfwise",
    [switch]$AutoApprove
)

# Native tools report failure through exit codes, which are checked explicitly. "Stop"
# would also abort on harmless stderr output in Windows PowerShell 5.1.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot

function Step($message) { Write-Host "`n==> $message" -ForegroundColor Cyan }

$clusterExists = $false
aws eks describe-cluster --region $Region --name $ClusterName *> $null
if ($LASTEXITCODE -eq 0) { $clusterExists = $true }

if ($clusterExists) {
    aws eks update-kubeconfig --region $Region --name $ClusterName | Out-Null

    Step "Removing Shelfwise and its database volume"
    helm uninstall shelfwise -n shelfwise --wait 2>$null
    kubectl delete pvc --all -n shelfwise --wait=true 2>$null

    Step "Removing the ingress controller and its AWS load balancer"
    # Kubernetes names the load balancer randomly, so remember its DNS name first and
    # wait for exactly that one to disappear.
    $lbHost = kubectl get svc ingress-nginx-controller -n ingress-nginx `
        -o jsonpath="{.status.loadBalancer.ingress[0].hostname}" 2>$null
    helm uninstall ingress-nginx -n ingress-nginx --wait 2>$null
    if ($lbHost) {
        $deadline = (Get-Date).AddMinutes(10)
        do {
            Start-Sleep -Seconds 15
            $remaining = aws elbv2 describe-load-balancers --region $Region `
                --query "LoadBalancers[?DNSName=='$lbHost'].LoadBalancerName" --output text
            Write-Host "  load balancer $(if ($remaining) { "$remaining still deleting" } else { 'gone' })"
        } until (-not $remaining -or (Get-Date) -gt $deadline)
    }
} else {
    Write-Host "No EKS cluster named $ClusterName in $Region; going straight to terraform destroy."
}

Step "terraform destroy"
Push-Location "$root/terraform"
try {
    $destroyArgs = @("destroy", "-input=false", "-var", "region=$Region", "-var", "cluster_name=$ClusterName")
    if ($AutoApprove) { $destroyArgs += "-auto-approve" }
    terraform @destroyArgs
    if ($LASTEXITCODE -ne 0) { throw "terraform destroy failed; re-run this script." }
} finally {
    Pop-Location
}

Step "Checking for anything left behind (should print nothing)"
aws resourcegroupstaggingapi get-resources --region $Region `
    --tag-filters "Key=Project,Values=shelfwise" --query "ResourceTagMappingList[].ResourceARN" --output text
aws ec2 describe-volumes --region $Region --filters "Name=status,Values=available" `
    --query "Volumes[].{id:VolumeId,size:Size}" --output table

kubectl config delete-context "arn:aws:eks:${Region}:$(aws sts get-caller-identity --query Account --output text):cluster/$ClusterName" 2>$null | Out-Null
Write-Host "`nEKS is gone. Double-check the AWS console (EC2, VPC, EKS) in $Region if you like." -ForegroundColor Green
