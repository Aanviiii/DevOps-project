# Shelfwise on AWS: VPC + EKS with Terraform

Plain AWS provider resources, no community modules, so every piece of the infrastructure is visible in these files.

| File | What it creates |
|---|---|
| `network.tf` | VPC `10.42.0.0/16`, two public `/20` subnets in separate AZs, internet gateway, route table |
| `iam.tf` | Roles for the control plane, the worker nodes, and the EBS CSI driver (via Pod Identity) |
| `cluster.tf` | EKS 1.35 control plane (access entries, pinned to standard support), `vpc-cni` and `kube-proxy` add-ons |
| `nodes.tf` | Managed node group (2 × t3.medium **Spot**), plus `coredns`, Pod Identity agent, EBS CSI driver and `metrics-server` add-ons |
| `budget.tf` | Monthly AWS Budget with email alerts (optional) |

## Cost

Rough `ap-south-1` prices; check the AWS pricing pages for current figures.

| Item | Per hour |
|---|---|
| EKS control plane (standard support) | $0.10 |
| 2 × t3.medium Spot nodes | ≈ $0.03 |
| 2 × 20 GiB gp3 node disks + 1 GiB Postgres volume | < $0.01 |
| Load balancer for the ingress controller | ≈ $0.02 |
| **Total** | **≈ $0.16/hour**, about $0.40 for a 2½-hour demo session |

Design choices that keep it cheap:
- **No NAT gateway** (≈ $1.10/day): nodes live in public subnets, and only the cluster can reach them through the EKS-managed security group.
- **Spot** nodes.
- **No control-plane logging** to CloudWatch.
- **`upgrade_policy = STANDARD`**, so the cluster never slips into extended support at 6× the price.

## Accounts that cannot call EC2 yet

A brand-new AWS account (including Free plan accounts still being set up) can have EC2 and EKS denied by an AWS service control policy. In that state `terraform plan` fails on the availability-zone lookup. Set `availability_zones = ["ap-south-1a", "ap-south-1b"]` in `terraform.tfvars` to pin the zones; `plan` then works, and the zone lookup is skipped entirely. Remove the line (or leave it) once the account is active: `apply` works either way. `apply` itself still needs EC2/EKS access.

## Usage

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # then edit: your IP, your email
terraform init
terraform plan -out tfplan
terraform apply tfplan                          # ~12–15 minutes
aws eks update-kubeconfig --region ap-south-1 --name shelfwise
kubectl get nodes
```

Deploy the app with `scripts/eks-up.ps1`, which installs the ingress controller and the Helm chart.

## Tear down (do this the same day)

```bash
# Delete Kubernetes-created load balancers first, or the VPC cannot be deleted
pwsh ../scripts/eks-down.ps1          # uninstalls the Helm releases, waits for the LB to go
terraform destroy
```

Afterwards, check the AWS console (EC2 → Load Balancers, EC2 → Volumes, VPC) in `ap-south-1` and confirm that nothing tagged `Project = shelfwise` remains.

## Credentials

Terraform uses the standard AWS credential chain (`aws configure`). Never commit keys, `terraform.tfvars` or state files; `.gitignore` excludes them, and gitleaks in CI scans the whole history.
